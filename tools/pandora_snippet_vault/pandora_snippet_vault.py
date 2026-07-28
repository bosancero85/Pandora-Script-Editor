#!/usr/bin/env python3
"""
================================================================================
 PANDORA CODE SNIPPET VAULT
 Intelligente, sprachübergreifende Code-Bibliothek für den Pandora Script
 Editor
================================================================================

Features:
  - Multi-Language Support: freie Kategorisierung nach Sprache (Python, Lua,
    JavaScript, ...) und Kategorie/Framework, zusätzlich Tags pro Snippet
  - Vault-Browser: Suche/Filter nach Sprache, Kategorie und Freitext,
    Live-Vorschau, Anlegen/Bearbeiten/Duplizieren/Löschen
  - Quick-Insert-Popup: schmales Suchfenster (per Tastenkombination im
    Haupteditor geöffnet), Enter fügt das oberste/gewählte Snippet direkt an
    der aktuellen Cursor-Position ein
  - Variable Placeholders: Platzhalter der Form ${name} bzw. ${name:default}
    im Snippet-Code werden beim Einfügen automatisch erkannt und in einem
    kleinen Formular abgefragt
  - Persistente Bibliothek als JSON-Datei (~/.pandora_snippet_vault.json),
    unabhängig vom Speicherort dieses Skripts

Integration in den Pandora Script Editor:
  Dieses Modul ist so gebaut, dass es sowohl EIGENSTÄNDIG gestartet werden
  kann (Bibliothek verwalten/durchsuchen, Einfügen kopiert dann in die
  Zwischenablage) ALS AUCH direkt vom Pandora Script Editor per
  `importlib` in dessen laufenden Prozess geladen wird - nur so kann das
  "Quick-Insert" Snippets direkt an der Cursor-Position im aktiven Editor
  einfügen (ein per subprocess gestartetes, separates Fenster hätte keinen
  Zugriff auf den Text-Cursor des Haupteditors).

Abhängigkeiten:
  pip install PyQt6 --break-system-packages

Start (eigenständig):
  python3 pandora_snippet_vault.py
================================================================================
"""

import sys
import os
import re
import json
import uuid
import argparse
import datetime

from PyQt6.QtWidgets import (
    QApplication, QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QLabel, QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QPlainTextEdit, QSplitter, QMessageBox, QFrame, QSizePolicy
)
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtCore import Qt, QEvent


# ------------------------------------------------------------------------
# THEME - orientiert an der Farbpalette des Pandora Script Editors, damit
# sich der Vault-Dialog nahtlos einfügt (auch im eigenständigen Betrieb).
# ------------------------------------------------------------------------
VAULT_QSS = """
QDialog, QWidget {
    background-color: #1b1c22;
    color: #d4d4d4;
    font-family: 'Fira Code', 'DejaVu Sans Mono', monospace;
    font-size: 10.5pt;
}
QLineEdit {
    background-color: #1e1f26;
    border: 1px solid #33354a;
    border-radius: 4px;
    padding: 6px;
    color: #d4d4d4;
    selection-background-color: #3b5070;
}
QLineEdit:focus {
    border: 1px solid #4ec9b0;
}
QComboBox {
    background-color: #1e1f26;
    border: 1px solid #33354a;
    border-radius: 4px;
    padding: 4px 6px;
    color: #d4d4d4;
}
QComboBox QAbstractItemView {
    background-color: #23242c;
    color: #d4d4d4;
    selection-background-color: #3b5070;
}
QPlainTextEdit {
    background-color: #1e1f26;
    color: #d4d4d4;
    border: 1px solid #33354a;
    border-radius: 4px;
    selection-background-color: #3b5070;
}
QListWidget {
    background-color: #1e1f26;
    color: #d4d4d4;
    border: 1px solid #33354a;
    border-radius: 4px;
    outline: none;
}
QListWidget::item {
    padding: 6px 4px;
    border-bottom: 1px solid #23242c;
}
QListWidget::item:selected {
    background-color: #3b5070;
    color: #ffffff;
}
QPushButton {
    background-color: #33354a;
    color: #ffffff;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #40425c;
}
QPushButton:default {
    background-color: #4ec9b0;
    color: #04121a;
    font-weight: bold;
}
QPushButton:default:hover {
    background-color: #6fe0c8;
}
QLabel#Badge {
    color: #4ec9b0;
    font-weight: bold;
}
QLabel#Hint {
    color: #9aa0ab;
    font-style: italic;
    font-size: 9.5pt;
}
QFrame#Divider {
    background-color: #33354a;
    max-height: 1px;
    min-height: 1px;
}
"""

DEFAULT_STORE_PATH = os.path.join(os.path.expanduser("~"), ".pandora_snippet_vault.json")

LANGUAGES = ["Python", "Lua", "JavaScript", "HTML", "CSS", "Bash", "SQL", "Andere"]

PLACEHOLDER_RE = re.compile(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^}]*))?\}")


# ------------------------------------------------------------------------
# PLATZHALTER-LOGIK
# ------------------------------------------------------------------------
def extract_placeholders(code):
    """Findet alle ${name} / ${name:default}-Platzhalter im Code, in
    Auftrittsreihenfolge, ohne Duplikate. Gibt eine Liste von
    {"name": ..., "default": ...} zurück."""
    seen = {}
    order = []
    for m in PLACEHOLDER_RE.finditer(code or ""):
        name = m.group(1)
        default = m.group(2) if m.group(2) is not None else ""
        if name not in seen:
            seen[name] = default
            order.append(name)
    return [{"name": n, "default": seen[n]} for n in order]


def render_snippet(code, values):
    """Ersetzt alle ${name}/${name:default}-Platzhalter im Code durch die
    übergebenen Werte (values: dict name -> value). Fehlt ein Wert, wird
    der Default (bzw. leerer String) verwendet."""
    def _replace(m):
        name = m.group(1)
        default = m.group(2) if m.group(2) is not None else ""
        return values.get(name, default)

    return PLACEHOLDER_RE.sub(_replace, code or "")


# ------------------------------------------------------------------------
# PERSISTENTER SNIPPET-SPEICHER
# ------------------------------------------------------------------------
class SnippetStore:
    def __init__(self, path=None):
        self.path = path or DEFAULT_STORE_PATH
        self.snippets = []
        self.load()

    def load(self):
        if os.path.isfile(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.snippets = data.get("snippets", [])
                return
            except Exception:
                self.snippets = []
        # Keine (lesbare) Datei vorhanden -> mit Beispiel-Snippets starten
        self.snippets = self._default_snippets()
        self.save()

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"snippets": self.snippets}, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def all(self):
        return sorted(self.snippets, key=lambda s: (s.get("language", ""), s.get("title", "")))

    def get(self, snippet_id):
        for s in self.snippets:
            if s.get("id") == snippet_id:
                return s
        return None

    def add(self, snippet):
        snippet = dict(snippet)
        snippet["id"] = uuid.uuid4().hex
        snippet["created"] = datetime.datetime.now().isoformat(timespec="seconds")
        self.snippets.append(snippet)
        self.save()
        return snippet

    def update(self, snippet_id, new_data):
        s = self.get(snippet_id)
        if s is None:
            return None
        s.update(new_data)
        s["modified"] = datetime.datetime.now().isoformat(timespec="seconds")
        self.save()
        return s

    def delete(self, snippet_id):
        self.snippets = [s for s in self.snippets if s.get("id") != snippet_id]
        self.save()

    def languages(self):
        return sorted({s.get("language", "").strip() for s in self.snippets if s.get("language", "").strip()})

    def categories(self):
        return sorted({s.get("category", "").strip() for s in self.snippets if s.get("category", "").strip()})

    def search(self, query="", language=None, category=None):
        query = (query or "").strip().lower()
        results = []
        for s in self.all():
            if language and language != "Alle Sprachen" and s.get("language", "") != language:
                continue
            if category and category != "Alle Kategorien" and s.get("category", "") != category:
                continue
            if query:
                haystack = " ".join([
                    s.get("title", ""),
                    s.get("description", ""),
                    s.get("language", ""),
                    s.get("category", ""),
                    " ".join(s.get("tags", [])),
                    s.get("code", ""),
                ]).lower()
                if query not in haystack:
                    continue
            results.append(s)
        return results

    def _default_snippets(self):
        return [
            {
                "id": uuid.uuid4().hex,
                "title": "Python: Funktion mit Docstring",
                "language": "Python",
                "category": "Boilerplate",
                "tags": ["funktion", "docstring"],
                "description": "Standard-Funktionsgerüst mit Typannotation und Docstring.",
                "code": (
                    "def ${funktionsname:mach_etwas}(${parameter:x}):\n"
                    "    \"\"\"${beschreibung:Kurze Beschreibung der Funktion.}\"\"\"\n"
                    "    pass\n"
                ),
            },
            {
                "id": uuid.uuid4().hex,
                "title": "Python: try/except mit Logging",
                "language": "Python",
                "category": "Fehlerbehandlung",
                "tags": ["exception", "logging"],
                "description": "Try/Except-Block mit Platzhalter für die Exception-Klasse.",
                "code": (
                    "try:\n"
                    "    ${code:pass}\n"
                    "except ${exception:Exception} as e:\n"
                    "    print(f\"Fehler: {e}\")\n"
                ),
            },
            {
                "id": uuid.uuid4().hex,
                "title": "Lua: Funktion",
                "language": "Lua",
                "category": "Boilerplate",
                "tags": ["funktion"],
                "description": "Einfaches Lua-Funktionsgerüst.",
                "code": (
                    "function ${funktionsname:machEtwas}(${parameter:arg})\n"
                    "    -- ${beschreibung:TODO}\n"
                    "end\n"
                ),
            },
            {
                "id": uuid.uuid4().hex,
                "title": "Lua: for-Schleife (numerisch)",
                "language": "Lua",
                "category": "Kontrollfluss",
                "tags": ["schleife", "for"],
                "description": "Numerische for-Schleife mit Start/Ende/Schritt.",
                "code": (
                    "for i = ${start:1}, ${ende:10}, ${schritt:1} do\n"
                    "    ${code:print(i)}\n"
                    "end\n"
                ),
            },
            {
                "id": uuid.uuid4().hex,
                "title": "JavaScript: Fetch mit async/await",
                "language": "JavaScript",
                "category": "Netzwerk",
                "tags": ["fetch", "async", "api"],
                "description": "Asynchroner Fetch-Aufruf inkl. Fehlerbehandlung.",
                "code": (
                    "async function ${funktionsname:ladeDaten}() {\n"
                    "    try {\n"
                    "        const response = await fetch(\"${url:https://api.example.com}\");\n"
                    "        const data = await response.json();\n"
                    "        return data;\n"
                    "    } catch (error) {\n"
                    "        console.error(\"Fehler beim Laden:\", error);\n"
                    "    }\n"
                    "}\n"
                ),
            },
            {
                "id": uuid.uuid4().hex,
                "title": "JavaScript: Event-Listener",
                "language": "JavaScript",
                "category": "DOM",
                "tags": ["event", "dom"],
                "description": "addEventListener-Boilerplate für ein Element per ID.",
                "code": (
                    "document.getElementById(\"${elementId:meinButton}\")"
                    ".addEventListener(\"${event:click}\", () => {\n"
                    "    ${code:// TODO}\n"
                    "});\n"
                ),
            },
        ]


# ------------------------------------------------------------------------
# PLATZHALTER-ABFRAGE-DIALOG
# ------------------------------------------------------------------------
class PlaceholderDialog(QDialog):
    def __init__(self, placeholders, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Platzhalter ausfüllen")
        self.setStyleSheet(VAULT_QSS)
        self.setMinimumWidth(420)
        self._fields = {}

        layout = QVBoxLayout(self)
        hint = QLabel("Dieses Snippet enthält Platzhalter - bitte Werte eingeben:")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        form = QFormLayout()
        for ph in placeholders:
            edit = QLineEdit(ph.get("default", ""))
            edit.selectAll()
            form.addRow(f"{ph['name']}:", edit)
            self._fields[ph["name"]] = edit
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_ok = QPushButton("Einfügen")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        if self._fields:
            first = next(iter(self._fields.values()))
            first.setFocus()

    def get_values(self):
        return {name: edit.text() for name, edit in self._fields.items()}


# ------------------------------------------------------------------------
# SNIPPET ANLEGEN / BEARBEITEN
# ------------------------------------------------------------------------
class SnippetEditDialog(QDialog):
    def __init__(self, snippet=None, languages=None, categories=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Snippet bearbeiten" if snippet else "Neues Snippet")
        self.setStyleSheet(VAULT_QSS)
        self.resize(680, 560)
        snippet = snippet or {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(snippet.get("title", ""))
        form.addRow("Titel:", self.title_edit)

        self.language_combo = QComboBox()
        self.language_combo.setEditable(True)
        all_langs = sorted(set(LANGUAGES) | set(languages or []))
        self.language_combo.addItems(all_langs)
        self.language_combo.setCurrentText(snippet.get("language", all_langs[0] if all_langs else ""))
        form.addRow("Sprache:", self.language_combo)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(sorted(categories or []))
        self.category_combo.setCurrentText(snippet.get("category", ""))
        form.addRow("Kategorie/Framework:", self.category_combo)

        self.tags_edit = QLineEdit(", ".join(snippet.get("tags", [])))
        self.tags_edit.setPlaceholderText("z. B. schleife, api, boilerplate")
        form.addRow("Tags (Komma-getrennt):", self.tags_edit)

        self.description_edit = QLineEdit(snippet.get("description", ""))
        form.addRow("Beschreibung:", self.description_edit)

        layout.addLayout(form)

        code_hint = QLabel(
            "Code - Platzhalter mit ${name} bzw. ${name:Standardwert} markieren "
            "(werden beim Einfügen automatisch abgefragt):"
        )
        code_hint.setObjectName("Hint")
        layout.addWidget(code_hint)

        self.code_edit = QPlainTextEdit(snippet.get("code", ""))
        font = QFont("Fira Code", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.code_edit.setFont(font)
        layout.addWidget(self.code_edit, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Speichern")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        self.title_edit.setFocus()

    def _on_save(self):
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Titel fehlt", "Bitte einen Titel für das Snippet vergeben.")
            return
        if not self.code_edit.toPlainText().strip():
            QMessageBox.warning(self, "Code fehlt", "Der Snippet-Code darf nicht leer sein.")
            return
        self.accept()

    def get_snippet(self):
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        return {
            "title": self.title_edit.text().strip(),
            "language": self.language_combo.currentText().strip(),
            "category": self.category_combo.currentText().strip(),
            "tags": tags,
            "description": self.description_edit.text().strip(),
            "code": self.code_edit.toPlainText(),
        }


# ------------------------------------------------------------------------
# VAULT-BROWSER (Verwalten, Durchsuchen, Einfügen)
# ------------------------------------------------------------------------
class SnippetVaultDialog(QDialog):
    """insert_callback: optionale Funktion(text: str) -> None. Ist sie
    gesetzt, erscheint ein 'Einfügen'-Button, der den (ggf. mit Platzhaltern
    gefüllten) Snippet-Text an sie übergibt und den Dialog schließt. Ohne
    Callback (eigenständiger Betrieb) landet der Text stattdessen in der
    Zwischenablage."""

    def __init__(self, store, insert_callback=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.insert_callback = insert_callback
        self.setWindowTitle("⧉ Pandora Code Snippet Vault")
        self.setStyleSheet(VAULT_QSS)
        self.resize(980, 600)

        self._build_ui()
        self.refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Suche nach Titel, Tag, Kategorie oder Code…")
        self.search_edit.textChanged.connect(self.refresh_list)
        filter_row.addWidget(self.search_edit, 2)

        self.language_filter = QComboBox()
        self.language_filter.addItem("Alle Sprachen")
        self.language_filter.addItems(self.store.languages())
        self.language_filter.currentTextChanged.connect(self.refresh_list)
        filter_row.addWidget(self.language_filter, 1)

        self.category_filter = QComboBox()
        self.category_filter.addItem("Alle Kategorien")
        self.category_filter.addItems(self.store.categories())
        self.category_filter.currentTextChanged.connect(self.refresh_list)
        filter_row.addWidget(self.category_filter, 1)

        layout.addLayout(filter_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._update_preview)
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        splitter.addWidget(self.list_widget)

        preview_panel = QWidget()
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        self.badge_label = QLabel("")
        self.badge_label.setObjectName("Badge")
        preview_layout.addWidget(self.badge_label)

        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        preview_layout.addWidget(self.desc_label)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        preview_layout.addWidget(divider)

        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        font = QFont("Fira Code", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.preview_edit.setFont(font)
        preview_layout.addWidget(self.preview_edit, 1)

        self.tags_label = QLabel("")
        self.tags_label.setObjectName("Hint")
        preview_layout.addWidget(self.tags_label)

        splitter.addWidget(preview_panel)
        splitter.setSizes([340, 640])
        layout.addWidget(splitter, 1)

        btn_row = QHBoxLayout()
        if self.insert_callback is not None:
            self.btn_insert = QPushButton("⏎ Einfügen")
            self.btn_insert.setDefault(True)
            self.btn_insert.clicked.connect(self.do_insert)
            btn_row.addWidget(self.btn_insert)
        else:
            self.btn_insert = QPushButton("📋 In Zwischenablage kopieren")
            self.btn_insert.clicked.connect(self.do_insert)
            btn_row.addWidget(self.btn_insert)

        btn_new = QPushButton("🆕 Neu")
        btn_new.clicked.connect(self.new_snippet)
        btn_row.addWidget(btn_new)

        btn_edit = QPushButton("✏️ Bearbeiten")
        btn_edit.clicked.connect(self.edit_snippet)
        btn_row.addWidget(btn_edit)

        btn_dup = QPushButton("📄 Duplizieren")
        btn_dup.clicked.connect(self.duplicate_snippet)
        btn_row.addWidget(btn_dup)

        btn_del = QPushButton("🗑️ Löschen")
        btn_del.clicked.connect(self.delete_snippet)
        btn_row.addWidget(btn_del)

        btn_row.addStretch(1)
        btn_close = QPushButton("Schließen")
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)
        self.search_edit.setFocus()

    # -------------------- Filter/Liste --------------------
    def refresh_list(self, *_):
        selected_id = self._current_snippet_id()
        self.list_widget.clear()
        results = self.store.search(
            self.search_edit.text(),
            self.language_filter.currentText(),
            self.category_filter.currentText(),
        )
        restore_row = 0
        for i, s in enumerate(results):
            label = f"{s.get('title', '(ohne Titel)')}   [{s.get('language', '?')}]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, s.get("id"))
            self.list_widget.addItem(item)
            if s.get("id") == selected_id:
                restore_row = i
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(restore_row)
        else:
            self._update_preview(None, None)

    def _current_snippet_id(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _current_snippet(self):
        sid = self._current_snippet_id()
        return self.store.get(sid) if sid else None

    def _update_preview(self, _current=None, _previous=None):
        s = self._current_snippet()
        if s is None:
            self.badge_label.setText("")
            self.desc_label.setText("")
            self.preview_edit.setPlainText("")
            self.tags_label.setText("")
            return
        cat = f" · {s['category']}" if s.get("category") else ""
        self.badge_label.setText(f"{s.get('title', '')}  —  {s.get('language', '')}{cat}")
        self.desc_label.setText(s.get("description", ""))
        self.preview_edit.setPlainText(s.get("code", ""))
        tags = s.get("tags", [])
        self.tags_label.setText(("Tags: " + ", ".join(tags)) if tags else "Keine Tags")

    # -------------------- Aktionen --------------------
    def _on_double_click(self, _item):
        if self.insert_callback is not None:
            self.do_insert()
        else:
            self.edit_snippet()

    def new_snippet(self):
        dlg = SnippetEditDialog(languages=self.store.languages(), categories=self.store.categories(), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_snippet = self.store.add(dlg.get_snippet())
            self._refresh_filters()
            self.refresh_list()
            self._select_snippet(new_snippet["id"])

    def edit_snippet(self):
        s = self._current_snippet()
        if s is None:
            return
        dlg = SnippetEditDialog(s, languages=self.store.languages(), categories=self.store.categories(), parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.store.update(s["id"], dlg.get_snippet())
            self._refresh_filters()
            self.refresh_list()
            self._select_snippet(s["id"])

    def duplicate_snippet(self):
        s = self._current_snippet()
        if s is None:
            return
        copy_data = {
            "title": s.get("title", "") + " (Kopie)",
            "language": s.get("language", ""),
            "category": s.get("category", ""),
            "tags": list(s.get("tags", [])),
            "description": s.get("description", ""),
            "code": s.get("code", ""),
        }
        new_snippet = self.store.add(copy_data)
        self.refresh_list()
        self._select_snippet(new_snippet["id"])

    def delete_snippet(self):
        s = self._current_snippet()
        if s is None:
            return
        reply = QMessageBox.question(
            self, "Snippet löschen",
            f"„{s.get('title', '')}“ wirklich löschen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.store.delete(s["id"])
            self._refresh_filters()
            self.refresh_list()

    def _refresh_filters(self):
        current_lang = self.language_filter.currentText()
        current_cat = self.category_filter.currentText()
        self.language_filter.blockSignals(True)
        self.category_filter.blockSignals(True)
        self.language_filter.clear()
        self.language_filter.addItem("Alle Sprachen")
        self.language_filter.addItems(self.store.languages())
        self.category_filter.clear()
        self.category_filter.addItem("Alle Kategorien")
        self.category_filter.addItems(self.store.categories())
        idx = self.language_filter.findText(current_lang)
        self.language_filter.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.category_filter.findText(current_cat)
        self.category_filter.setCurrentIndex(idx if idx >= 0 else 0)
        self.language_filter.blockSignals(False)
        self.category_filter.blockSignals(False)

    def _select_snippet(self, snippet_id):
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == snippet_id:
                self.list_widget.setCurrentRow(i)
                return

    def do_insert(self):
        s = self._current_snippet()
        if s is None:
            return
        code = s.get("code", "")
        placeholders = extract_placeholders(code)
        if placeholders:
            ph_dlg = PlaceholderDialog(placeholders, parent=self)
            if ph_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            values = ph_dlg.get_values()
        else:
            values = {}
        rendered = render_snippet(code, values)

        if self.insert_callback is not None:
            self.insert_callback(rendered)
            self.accept()
        else:
            QApplication.clipboard().setText(rendered)
            QMessageBox.information(self, "Kopiert", "Snippet wurde in die Zwischenablage kopiert.")


# ------------------------------------------------------------------------
# QUICK-INSERT-POPUP (Schnellsuche per Tastenkombination)
# ------------------------------------------------------------------------
class QuickInsertPopup(QDialog):
    """Schlankes Suchfenster: tippen filtert live, Pfeiltasten navigieren,
    Enter fügt das gewählte Snippet sofort ein (inkl. Platzhalter-Abfrage),
    Escape bricht ab."""

    def __init__(self, store, insert_callback, parent=None):
        super().__init__(parent)
        self.store = store
        self.insert_callback = insert_callback
        self.setWindowTitle("Pandora Snippet - Schnell-Einfügen")
        self.setStyleSheet(VAULT_QSS)
        self.setFixedWidth(520)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Snippet suchen und mit Enter einfügen…")
        self.search_edit.installEventFilter(self)
        self.search_edit.textChanged.connect(self._refresh_results)
        layout.addWidget(self.search_edit)

        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(220)
        self.list_widget.itemDoubleClicked.connect(lambda _i: self._insert_current())
        layout.addWidget(self.list_widget)

        hint = QLabel("↑↓ navigieren · Enter einfügen · Esc abbrechen")
        hint.setObjectName("Hint")
        layout.addWidget(hint)

        self._refresh_results()
        self.search_edit.setFocus()

    def _refresh_results(self, *_):
        query = self.search_edit.text()
        self.list_widget.clear()
        for s in self.store.search(query)[:30]:
            cat = f" · {s['category']}" if s.get("category") else ""
            label = f"{s.get('title', '(ohne Titel)')}   [{s.get('language', '?')}{cat}]"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, s.get("id"))
            self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def eventFilter(self, obj, event):
        if obj is self.search_edit and event.type() == QEvent.Type.KeyPress:
            key_event: QKeyEvent = event
            key = key_event.key()
            if key == Qt.Key.Key_Down:
                row = min(self.list_widget.currentRow() + 1, self.list_widget.count() - 1)
                self.list_widget.setCurrentRow(row)
                return True
            if key == Qt.Key.Key_Up:
                row = max(self.list_widget.currentRow() - 1, 0)
                self.list_widget.setCurrentRow(row)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._insert_current()
                return True
            if key == Qt.Key.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)

    def _insert_current(self):
        item = self.list_widget.currentItem()
        if item is None:
            return
        snippet_id = item.data(Qt.ItemDataRole.UserRole)
        s = self.store.get(snippet_id)
        if s is None:
            return
        code = s.get("code", "")
        placeholders = extract_placeholders(code)
        if placeholders:
            ph_dlg = PlaceholderDialog(placeholders, parent=self)
            if ph_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            values = ph_dlg.get_values()
        else:
            values = {}
        rendered = render_snippet(code, values)
        self.insert_callback(rendered)
        self.accept()


# ------------------------------------------------------------------------
# ENTRY POINT (eigenständiger Betrieb: Bibliothek verwalten/durchsuchen)
# ------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Pandora Code Snippet Vault")
    parser.add_argument("--store", help="Alternativer Pfad zur Snippet-Bibliothek (JSON)")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyleSheet(VAULT_QSS)

    store = SnippetStore(path=args.store)
    dlg = SnippetVaultDialog(store, insert_callback=None)
    dlg.setWindowFlag(Qt.WindowType.Window, True)
    dlg.finished.connect(lambda _r: app.quit())
    dlg.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
