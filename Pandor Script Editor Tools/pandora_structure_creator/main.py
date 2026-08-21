#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
====================================================================
 Pandora® Structure Creator
====================================================================
 Ein PyQt6-Tool, mit dem beliebige Ordner-/Dateistrukturen aus einer
 textuellen Baum-Darstellung (z.B. wie sie oft in READMEs oder
 Doku-Beispielen zu finden ist) automatisch am gewünschten Zielort
 erzeugt werden können.

 Unterstützte Eingabeformate:
   1) Baum-Zeichen-Format:
        Pandora/
        ├── main.py
        ├── core/
        │   ├── __init__.py
        │   └── config.py
        └── gui/
            ├── __init__.py
            └── main_window.py

   2) Einfaches Einrückungs-Format (Leerzeichen/Tabs), z.B.:
        Pandora/
            main.py
            core/
                __init__.py
                config.py

 Funktionen:
   - Zielverzeichnis frei wählbar (QFileDialog)
   - Live-Vorschau der geparsten Struktur
   - Optionale Kommentar-Header in neu erstellten .py-Dateien
   - Vorlagen (Templates) als .txt speichern/laden
   - Kollisions-Check: bereits vorhandene Dateien werden nicht
     überschrieben (nur angelegt, falls nicht vorhanden)
====================================================================
"""

import os
import sys
import re

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QPlainTextEdit, QFileDialog, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QCheckBox, QSplitter,
    QGroupBox, QStatusBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QColor, QPalette


# --------------------------------------------------------------
# Pandora® Farbschema (Dark-Red Cyberpunk Look)
# --------------------------------------------------------------
COLOR_BG = "#141014"
COLOR_BG_LIGHT = "#1e181e"
COLOR_ACCENT = "#c8102e"
COLOR_ACCENT_HOVER = "#e8203e"
COLOR_TEXT = "#f0e8ea"
COLOR_TEXT_DIM = "#a89aa0"
COLOR_BORDER = "#3a2a30"

STYLE_SHEET = f"""
QMainWindow, QWidget {{
    background-color: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
}}
QGroupBox {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: bold;
    color: {COLOR_ACCENT};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}}
QPlainTextEdit, QListWidget, QLineEdit {{
    background-color: {COLOR_BG_LIGHT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 4px;
    padding: 6px;
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_ACCENT};
}}
QPushButton {{
    background-color: {COLOR_ACCENT};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {COLOR_ACCENT_HOVER};
}}
QPushButton:disabled {{
    background-color: #4a3a3e;
    color: #8a7a7e;
}}
QPushButton#secondary {{
    background-color: {COLOR_BG_LIGHT};
    border: 1px solid {COLOR_ACCENT};
    color: {COLOR_TEXT};
}}
QPushButton#secondary:hover {{
    background-color: {COLOR_BORDER};
}}
QLabel#header {{
    font-size: 20px;
    font-weight: bold;
    color: {COLOR_ACCENT};
}}
QLabel#subheader {{
    color: {COLOR_TEXT_DIM};
}}
QCheckBox {{
    color: {COLOR_TEXT};
}}
QStatusBar {{
    background-color: {COLOR_BG_LIGHT};
    color: {COLOR_TEXT_DIM};
}}
"""


# --------------------------------------------------------------
# Parser: Baum-Text -> Liste von (relativer_pfad, ist_ordner)
# --------------------------------------------------------------
class StructureParseError(Exception):
    """Wird ausgelöst, wenn die eingegebene Struktur nicht interpretiert werden kann."""
    pass


def parse_tree_structure(text: str):
    """
    Wandelt eine textuelle Baum-Darstellung in eine geordnete Liste von
    (relativer_pfad, ist_ordner) Tupeln um.

    Unterstützt sowohl Baum-Zeichen (├── └── │   ) als auch reine
    Einrückung mit Leerzeichen/Tabs.
    """
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        raise StructureParseError("Die Struktur ist leer.")

    entries = []          # (depth, name, is_folder)
    tree_chars = re.compile(r"[│├└─]")

    for raw_line in lines:
        # Kommentarzeilen (mit # beginnend, z.B. Erklärungen) ignorieren
        stripped_for_comment = raw_line.strip()
        if stripped_for_comment.startswith("#"):
            continue

        # Baum-Zeichen entfernen, dabei Tiefe anhand deren Position bestimmen
        if tree_chars.search(raw_line):
            # Tiefe = Anzahl der 4er-Blöcke vor dem eigentlichen Namen
            match = re.match(r"^([│\s]*)(├──|└──)?\s*(.*)$", raw_line)
            prefix = match.group(1) if match else ""
            name = match.group(3).strip() if match else raw_line.strip()
            depth = len(prefix) // 4
            if match and match.group(2):
                depth = len(prefix) // 4
        else:
            # Einrückungs-basiert (Leerzeichen oder Tabs)
            stripped = raw_line.lstrip(" \t")
            indent = raw_line[: len(raw_line) - len(stripped)]
            indent = indent.replace("\t", "    ")
            depth = len(indent) // 4
            name = stripped.strip()

        # Kommentare hinter dem Namen abschneiden (z.B. "main.py  ← Einstiegspunkt")
        name = re.split(r"\s{2,}(?:#|←|<-|--)", name)[0].strip()
        name = name.strip()

        if not name:
            continue

        is_folder = name.endswith("/") or name.endswith("\\")
        name = name.rstrip("/\\")

        if not name:
            continue

        entries.append((depth, name, is_folder))

    if not entries:
        raise StructureParseError("Es konnten keine gültigen Einträge erkannt werden.")

    # Baum in vollständige relative Pfade auflösen, anhand der Tiefe
    stack = []  # Liste aktueller Ordnernamen je Tiefe
    result = []  # (relativer_pfad, ist_ordner)

    for depth, name, is_folder in entries:
        stack = stack[:depth]
        full_parts = stack + [name]
        rel_path = os.path.join(*full_parts)
        result.append((rel_path, is_folder))
        if is_folder:
            stack.append(name)

    return result


# --------------------------------------------------------------
# Hauptfenster
# --------------------------------------------------------------
class StructureCreatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pandora® Structure Creator")
        self.resize(1000, 680)
        self.target_directory = ""

        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(12)

        # Header
        header = QLabel("Pandora® Structure Creator")
        header.setObjectName("header")
        subheader = QLabel("Ordner- und Dateistrukturen aus einer Textvorlage erzeugen")
        subheader.setObjectName("subheader")
        outer_layout.addWidget(header)
        outer_layout.addWidget(subheader)

        # Zielverzeichnis-Auswahl
        target_group = QGroupBox("Zielort")
        target_layout = QHBoxLayout()
        self.target_line_edit = QLineEdit()
        self.target_line_edit.setPlaceholderText("Noch kein Zielverzeichnis gewählt …")
        self.target_line_edit.setReadOnly(True)
        browse_btn = QPushButton("Verzeichnis wählen …")
        browse_btn.clicked.connect(self.choose_target_directory)
        target_layout.addWidget(self.target_line_edit)
        target_layout.addWidget(browse_btn)
        target_group.setLayout(target_layout)
        outer_layout.addWidget(target_group)

        # Splitter: links Texteingabe, rechts Vorschau
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Linke Seite: Struktur-Eingabe
        input_group = QGroupBox("Struktur (Baum- oder Einrückungsformat)")
        input_layout = QVBoxLayout()
        self.structure_edit = QPlainTextEdit()
        self.structure_edit.setPlaceholderText(
            "Beispiel:\n\n"
            "MeinProjekt/\n"
            "├── main.py\n"
            "├── core/\n"
            "│   ├── __init__.py\n"
            "│   └── config.py\n"
            "└── gui/\n"
            "    ├── __init__.py\n"
            "    └── main_window.py\n"
        )
        self.structure_edit.setFont(QFont("Consolas", 11))
        input_layout.addWidget(self.structure_edit)

        template_btns = QHBoxLayout()
        load_template_btn = QPushButton("Vorlage laden …")
        load_template_btn.setObjectName("secondary")
        load_template_btn.clicked.connect(self.load_template)
        save_template_btn = QPushButton("Vorlage speichern …")
        save_template_btn.setObjectName("secondary")
        save_template_btn.clicked.connect(self.save_template)
        template_btns.addWidget(load_template_btn)
        template_btns.addWidget(save_template_btn)
        input_layout.addLayout(template_btns)

        self.py_header_checkbox = QCheckBox("Kommentar-Header in neue .py-Dateien einfügen")
        self.py_header_checkbox.setChecked(True)
        input_layout.addWidget(self.py_header_checkbox)

        input_group.setLayout(input_layout)

        # Rechte Seite: Vorschau
        preview_group = QGroupBox("Vorschau")
        preview_layout = QVBoxLayout()
        self.preview_list = QListWidget()
        preview_layout.addWidget(self.preview_list)
        preview_refresh_btn = QPushButton("Vorschau aktualisieren")
        preview_refresh_btn.setObjectName("secondary")
        preview_refresh_btn.clicked.connect(self.update_preview)
        preview_layout.addWidget(preview_refresh_btn)
        preview_group.setLayout(preview_layout)

        splitter.addWidget(input_group)
        splitter.addWidget(preview_group)
        splitter.setSizes([500, 500])
        outer_layout.addWidget(splitter, stretch=1)

        # Aktion-Button
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.create_btn = QPushButton("Struktur erstellen")
        self.create_btn.clicked.connect(self.create_structure)
        action_layout.addWidget(self.create_btn)
        outer_layout.addLayout(action_layout)

        # Statusleiste
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit.")

        # Live-Vorschau bei Texteingabe
        self.structure_edit.textChanged.connect(self.update_preview)

        self.setStyleSheet(STYLE_SHEET)

    # ------------------------------------------------------------------
    def choose_target_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Zielverzeichnis wählen", os.path.expanduser("~")
        )
        if directory:
            self.target_directory = directory
            self.target_line_edit.setText(directory)
            self.status_bar.showMessage(f"Zielverzeichnis gesetzt: {directory}")

    # ------------------------------------------------------------------
    def update_preview(self):
        self.preview_list.clear()
        text = self.structure_edit.toPlainText()
        if not text.strip():
            return
        try:
            entries = parse_tree_structure(text)
        except StructureParseError as exc:
            item = QListWidgetItem(f"⚠ {exc}")
            self.preview_list.addItem(item)
            return

        for rel_path, is_folder in entries:
            depth = rel_path.count(os.sep)
            indent = "    " * depth
            icon = "📁" if is_folder else "📄"
            item = QListWidgetItem(f"{indent}{icon} {rel_path}")
            self.preview_list.addItem(item)

    # ------------------------------------------------------------------
    def load_template(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Vorlage laden", os.path.expanduser("~"), "Textdateien (*.txt);;Alle Dateien (*)"
        )
        if path:
            with open(path, "r", encoding="utf-8") as f:
                self.structure_edit.setPlainText(f.read())
            self.status_bar.showMessage(f"Vorlage geladen: {path}")

    # ------------------------------------------------------------------
    def save_template(self):
        text = self.structure_edit.toPlainText()
        if not text.strip():
            QMessageBox.warning(self, "Leere Struktur", "Es gibt nichts zu speichern.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Vorlage speichern", os.path.expanduser("~/struktur.txt"),
            "Textdateien (*.txt);;Alle Dateien (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.status_bar.showMessage(f"Vorlage gespeichert: {path}")

    # ------------------------------------------------------------------
    def create_structure(self):
        if not self.target_directory:
            QMessageBox.warning(
                self, "Kein Zielverzeichnis",
                "Bitte zuerst ein Zielverzeichnis auswählen."
            )
            return

        text = self.structure_edit.toPlainText()
        try:
            entries = parse_tree_structure(text)
        except StructureParseError as exc:
            QMessageBox.critical(self, "Fehler beim Parsen", str(exc))
            return

        created_dirs = 0
        created_files = 0
        skipped_files = 0
        errors = []

        for rel_path, is_folder in entries:
            full_path = os.path.join(self.target_directory, rel_path)
            try:
                if is_folder:
                    os.makedirs(full_path, exist_ok=True)
                    created_dirs += 1
                else:
                    parent_dir = os.path.dirname(full_path)
                    if parent_dir:
                        os.makedirs(parent_dir, exist_ok=True)
                    if os.path.exists(full_path):
                        skipped_files += 1
                        continue
                    with open(full_path, "w", encoding="utf-8") as f:
                        if full_path.endswith(".py") and self.py_header_checkbox.isChecked():
                            f.write(self._python_header(rel_path))
                    created_files += 1
            except OSError as exc:
                errors.append(f"{rel_path}: {exc}")

        summary = (
            f"Fertig!\n\n"
            f"Ordner erstellt: {created_dirs}\n"
            f"Dateien erstellt: {created_files}\n"
            f"Übersprungen (bereits vorhanden): {skipped_files}\n"
        )
        if errors:
            summary += "\nFehler:\n" + "\n".join(errors)
            QMessageBox.warning(self, "Struktur erstellt (mit Fehlern)", summary)
        else:
            QMessageBox.information(self, "Struktur erstellt", summary)

        self.status_bar.showMessage(
            f"Erstellt in {self.target_directory} — "
            f"{created_dirs} Ordner, {created_files} Dateien"
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _python_header(rel_path: str) -> str:
        """Erzeugt einen einfachen Kommentar-Header für neu angelegte .py-Dateien."""
        filename = os.path.basename(rel_path)
        return (
            f"# -*- coding: utf-8 -*-\n"
            f'"""\n'
            f"{filename}\n"
            f"Automatisch erstellt mit Pandora® Structure Creator.\n"
            f'"""\n\n'
        )


# --------------------------------------------------------------
# Einstiegspunkt
# --------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = StructureCreatorWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
