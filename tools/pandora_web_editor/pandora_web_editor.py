#!/usr/bin/env python3
"""
================================================================================
 PANDORA WEB EDITOR
 Eigenständiger HTML/CSS/JavaScript-Editor mit Echtzeit-Live-Vorschau
 Optimiert für Raspberry Pi 4B (8GB) / Kali Linux
================================================================================

Features:
  - Drei separate Code-Editoren (HTML / CSS / JavaScript) mit einfachem
    Syntax-Highlighting, nebeneinander in eigenen Spalten
  - Live-Vorschau via QWebEngineView (vollwertige Chromium-Engine) in der
    unteren Hälfte des Fensters
  - Echtzeit-Logik: Textänderungs-Signale aller drei Editoren werden mit
    einer Update-Funktion verbunden (leicht entprellt via QTimer), die alle
    drei Inhalte zu einem HTML-Dokument kombiniert und die Vorschau
    aktualisiert
  - Speichern/Öffnen als eigenständiger Projektordner mit getrennten
    Dateien:
        <projekt>/index.html
        <projekt>/assets/style/style.css
        <projekt>/assets/script/script.js
    index.html verlinkt CSS/JS dabei ganz normal per <link>/<script src>
  - Öffnen bestehender einzelner .html-Dateien (Inline <style>/<script>
    werden automatisch in die CSS-/JS-Spalte extrahiert)
  - Zusätzlich: Export als eine einzelne, portable .html-Datei (alles
    inline, z.B. zum schnellen Teilen)
  - Dunkles "Pandora"-Neon-Theme (Cyan/Magenta auf Tiefschwarz) - identisch
    zum restlichen Pandora-Werkzeugkasten

Abhängigkeiten:
  pip install PyQt6 PyQt6-WebEngine --break-system-packages

Start:
  python3 pandora_web_editor.py [projektordner|datei.html]
================================================================================
"""

import sys
import os
import re
import argparse

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QSplitter, QPlainTextEdit, QFileDialog, QMessageBox,
    QToolBar, QStatusBar, QLabel, QCheckBox
)
from PyQt6.QtGui import (
    QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QAction, QTextOption
)
from PyQt6.QtCore import Qt, QRegularExpression, QTimer, QSize, QUrl

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAVE_WEBENGINE = True
except ImportError:
    QWebEngineView = None
    HAVE_WEBENGINE = False


# ------------------------------------------------------------------------
# PANDORA THEME (Neon-Dark) - identisch zum restlichen Werkzeugkasten
# ------------------------------------------------------------------------
PANDORA_QSS = """
QMainWindow, QWidget {
    background-color: #0a0e14;
    color: #c9f2ef;
    font-family: 'Fira Code', 'DejaVu Sans Mono', monospace;
    font-size: 11pt;
}
QToolBar {
    background-color: #0f1420;
    border-bottom: 2px solid #00e5ff;
    spacing: 6px;
    padding: 4px;
}
QStatusBar {
    background-color: #0f1420;
    border-top: 1px solid #00e5ff;
    color: #7de8ff;
}
QGroupBox {
    border: 1px solid #1f3a4a;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: bold;
    color: #00e5ff;
    background-color: #0d1320;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #ff2fd0;
}
QCheckBox {
    color: #c9f2ef;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #00e5ff;
    border-radius: 3px;
    background-color: #0d1520;
}
QCheckBox::indicator:checked {
    background-color: #00e5ff;
}
QPushButton {
    background-color: #131a2b;
    border: 1px solid #00e5ff;
    border-radius: 5px;
    padding: 6px 14px;
    color: #00e5ff;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #00e5ff;
    color: #04121a;
}
QPushButton:pressed {
    background-color: #ff2fd0;
    border-color: #ff2fd0;
    color: #04121a;
}
QPlainTextEdit {
    background-color: #05080d;
    color: #7de8ff;
    border: 1px solid #1f3a4a;
    border-radius: 4px;
    selection-background-color: #00e5ff;
    selection-color: #001014;
}
QPlainTextEdit:focus {
    border: 1px solid #00e5ff;
}
QSplitter::handle {
    background-color: #00e5ff;
}
QSplitter::handle:horizontal {
    width: 3px;
}
QSplitter::handle:vertical {
    height: 3px;
}
"""


# ------------------------------------------------------------------------
# EINFACHE SYNTAX-HIGHLIGHTER
# ------------------------------------------------------------------------
class HtmlHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        tag_fmt = QTextCharFormat()
        tag_fmt.setForeground(QColor("#ff2fd0"))
        tag_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((QRegularExpression(r"</?[a-zA-Z0-9\-]+"), tag_fmt))

        attr_fmt = QTextCharFormat()
        attr_fmt.setForeground(QColor("#00e5ff"))
        self.rules.append((QRegularExpression(r'\b[a-zA-Z\-]+(?=\s*=)'), attr_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#39ff88"))
        self.rules.append((QRegularExpression(r'"[^"]*"'), string_fmt))
        self.rules.append((QRegularExpression(r"'[^']*'"), string_fmt))

        bracket_fmt = QTextCharFormat()
        bracket_fmt.setForeground(QColor("#ffd500"))
        self.rules.append((QRegularExpression(r"[<>/]"), bracket_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6c7d8c"))
        comment_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"<!--[^>]*-->"), comment_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class CssHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        selector_fmt = QTextCharFormat()
        selector_fmt.setForeground(QColor("#ff2fd0"))
        selector_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((QRegularExpression(r"[.#]?[a-zA-Z0-9_\-]+(?=\s*\{)"), selector_fmt))

        prop_fmt = QTextCharFormat()
        prop_fmt.setForeground(QColor("#00e5ff"))
        self.rules.append((QRegularExpression(r"[a-zA-Z\-]+(?=\s*:)"), prop_fmt))

        value_fmt = QTextCharFormat()
        value_fmt.setForeground(QColor("#39ff88"))
        self.rules.append((QRegularExpression(r":[^;{}]+;"), value_fmt))

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#ffd500"))
        self.rules.append((QRegularExpression(r"\b-?\d+\.?\d*(px|em|rem|%|vh|vw|s|ms)?\b"), number_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6c7d8c"))
        comment_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"/\*.*\*/"), comment_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class JsHighlighter(QSyntaxHighlighter):
    KEYWORDS = [
        "var", "let", "const", "function", "return", "if", "else", "for",
        "while", "do", "break", "continue", "switch", "case", "default",
        "try", "catch", "finally", "throw", "new", "delete", "typeof",
        "instanceof", "in", "of", "class", "extends", "super", "this",
        "import", "export", "from", "async", "await", "yield", "null",
        "undefined", "true", "false", "void", "static", "get", "set",
    ]

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#ff2fd0"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        for kw in self.KEYWORDS:
            self.rules.append((QRegularExpression(rf"\b{kw}\b"), kw_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#39ff88"))
        self.rules.append((QRegularExpression(r'"[^"]*"'), string_fmt))
        self.rules.append((QRegularExpression(r"'[^']*'"), string_fmt))
        self.rules.append((QRegularExpression(r"`[^`]*`"), string_fmt))

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#ffd500"))
        self.rules.append((QRegularExpression(r"\b-?\d+\.?\d*\b"), number_fmt))

        func_fmt = QTextCharFormat()
        func_fmt.setForeground(QColor("#00e5ff"))
        self.rules.append((QRegularExpression(r"\b[a-zA-Z_$][\w$]*(?=\s*\()"), func_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6c7d8c"))
        comment_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r"//[^\n]*"), comment_fmt))
        self.rules.append((QRegularExpression(r"/\*.*\*/"), comment_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# ------------------------------------------------------------------------
# CODE-EDITOR (QPlainTextEdit mit 4-Spaces-Tab)
# ------------------------------------------------------------------------
class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        font = QFont("Fira Code", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setWordWrapMode(QTextOption.WrapMode.NoWrap)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)


DEFAULT_HTML = """<h1>Willkommen im Pandora Web Editor</h1>
<p>Schreib links dein HTML, CSS und JavaScript - die Vorschau unten
aktualisiert sich in Echtzeit.</p>
<button id="demoBtn">Klick mich</button>
"""

DEFAULT_CSS = """body {
    background: #0a0e14;
    color: #c9f2ef;
    font-family: sans-serif;
    padding: 24px;
}
h1 {
    color: #ff2fd0;
}
button {
    background: #00e5ff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-weight: bold;
    cursor: pointer;
}
"""

DEFAULT_JS = """document.getElementById('demoBtn').addEventListener('click', () => {
    alert('Live-Vorschau funktioniert!');
});
"""

# Feste Projektstruktur beim Speichern/Öffnen als Ordner:
#   <projektordner>/index.html
#   <projektordner>/assets/style/style.css
#   <projektordner>/assets/script/script.js
CSS_REL_PATH = os.path.join("assets", "style", "style.css")
JS_REL_PATH = os.path.join("assets", "script", "script.js")
CSS_HREF = "assets/style/style.css"
JS_SRC = "assets/script/script.js"


# ------------------------------------------------------------------------
# HAUPTFENSTER
# ------------------------------------------------------------------------
class PandoraWebEditor(QMainWindow):
    def __init__(self, initial_file=None):
        super().__init__()
        self.setWindowTitle("⧉ PANDORA WEB EDITOR")
        self.resize(1400, 900)

        self.current_file = None    # Pfad zu einer geladenen einzelnen .html-Datei (Legacy)
        self.current_folder = None  # Pfad zum Projektordner (index.html + assets/…)
        self._dirty = False

        self._build_ui()
        self._build_actions()
        self._build_toolbar()
        self._build_statusbar()

        # Entprellung: Vorschau erst 200ms nach der letzten Änderung aktualisieren
        self.update_timer = QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(200)
        self.update_timer.timeout.connect(self._update_preview)

        self.html_edit.textChanged.connect(self._on_text_changed)
        self.css_edit.textChanged.connect(self._on_text_changed)
        self.js_edit.textChanged.connect(self._on_text_changed)

        if initial_file and os.path.isdir(initial_file):
            self._load_folder(initial_file)
        elif initial_file and os.path.isfile(initial_file):
            self._load_path(initial_file)
        else:
            self.html_edit.setPlainText(DEFAULT_HTML)
            self.css_edit.setPlainText(DEFAULT_CSS)
            self.js_edit.setPlainText(DEFAULT_JS)
            self._dirty = False

        self._update_preview()

    # -------------------- UI-Aufbau --------------------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(6, 6, 6, 6)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        outer.addWidget(main_splitter)

        # --- Obere Hälfte: drei Editoren nebeneinander ---
        editors_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.html_edit = CodeEditor()
        self.html_highlighter = HtmlHighlighter(self.html_edit.document())
        html_box = self._wrap_in_group("HTML", self.html_edit)

        self.css_edit = CodeEditor()
        self.css_highlighter = CssHighlighter(self.css_edit.document())
        css_box = self._wrap_in_group("CSS", self.css_edit)

        self.js_edit = CodeEditor()
        self.js_highlighter = JsHighlighter(self.js_edit.document())
        js_box = self._wrap_in_group("JAVASCRIPT", self.js_edit)

        editors_splitter.addWidget(html_box)
        editors_splitter.addWidget(css_box)
        editors_splitter.addWidget(js_box)
        editors_splitter.setSizes([400, 400, 400])

        # --- Untere Hälfte: Live-Vorschau ---
        preview_box = QGroupBox("LIVE-VORSCHAU")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(6, 14, 6, 6)

        if HAVE_WEBENGINE:
            self.preview = QWebEngineView()
            preview_layout.addWidget(self.preview)
        else:
            self.preview = None
            hint = QLabel(
                "QWebEngineView ist nicht verfügbar.\n"
                "Bitte installieren: pip install PyQt6-WebEngine --break-system-packages"
            )
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_layout.addWidget(hint)

        main_splitter.addWidget(editors_splitter)
        main_splitter.addWidget(preview_box)
        main_splitter.setSizes([450, 450])

    def _wrap_in_group(self, title, editor):
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(6, 14, 6, 6)
        lay.addWidget(editor)
        return box

    def _build_actions(self):
        self.act_new = QAction("🆕 Neu", self, shortcut="Ctrl+N", triggered=self.new_project)
        self.act_open_folder = QAction(
            "📂 Projekt-Ordner öffnen…", self, shortcut="Ctrl+O",
            triggered=self.open_project_folder
        )
        self.act_open_html = QAction(
            "📄 Einzelne HTML öffnen…", self, triggered=self.open_single_html
        )
        self.act_save = QAction(
            "💾 Speichern", self, shortcut="Ctrl+S", triggered=self.save_project_folder
        )
        self.act_save_as = QAction(
            "💾 Speichern unter…", self, shortcut="Ctrl+Shift+S",
            triggered=self.save_project_folder_as
        )
        self.act_export_html = QAction("📤 Als einzelne HTML exportieren…", self, triggered=self.export_html)
        self.act_refresh = QAction("🔄 Vorschau aktualisieren", self, shortcut="F5", triggered=self._update_preview)

        self.act_auto_refresh = QAction("⚡ Auto-Vorschau", self, checkable=True)
        self.act_auto_refresh.setChecked(True)

    def _build_toolbar(self):
        tb = QToolBar("Werkzeugleiste")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        self.addToolBar(tb)
        tb.addAction(self.act_new)
        tb.addAction(self.act_open_folder)
        tb.addAction(self.act_open_html)
        tb.addSeparator()
        tb.addAction(self.act_save)
        tb.addAction(self.act_save_as)
        tb.addAction(self.act_export_html)
        tb.addSeparator()
        tb.addAction(self.act_refresh)
        tb.addAction(self.act_auto_refresh)

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Bereit.", 3000)

    # -------------------- Echtzeit-Logik --------------------
    def _on_text_changed(self):
        self._dirty = True
        self._update_title()
        if self.act_auto_refresh.isChecked():
            # Timer bei jeder Änderung neu starten -> aktualisiert erst,
            # sobald 200ms lang nichts mehr getippt wurde (entprellt)
            self.update_timer.start()

    def _combined_html(self):
        """Für die Live-Vorschau: alles inline in ein Dokument gepackt,
        funktioniert unabhängig davon, ob schon gespeichert wurde."""
        html = self.html_edit.toPlainText()
        css = self.css_edit.toPlainText()
        js = self.js_edit.toPlainText()
        return (
            "<!DOCTYPE html>\n<html lang=\"de\">\n<head>\n"
            "<meta charset=\"UTF-8\">\n"
            f"<style>\n{css}\n</style>\n"
            "</head>\n<body>\n"
            f"{html}\n"
            f"<script>\n{js}\n</script>\n"
            "</body>\n</html>\n"
        )

    def _linked_index_html(self):
        """Für den Export/das Speichern als Projektordner: index.html
        referenziert assets/style/style.css und assets/script/script.js
        statt sie inline einzubetten."""
        html = self.html_edit.toPlainText()
        return (
            "<!DOCTYPE html>\n<html lang=\"de\">\n<head>\n"
            "<meta charset=\"UTF-8\">\n"
            f"<link rel=\"stylesheet\" href=\"{CSS_HREF}\">\n"
            "</head>\n<body>\n"
            f"{html}\n"
            f"<script src=\"{JS_SRC}\"></script>\n"
            "</body>\n</html>\n"
        )

    def _update_preview(self):
        if self.preview is None:
            return
        combined = self._combined_html()
        base_dir = self.current_folder or os.getcwd()
        base_url = QUrl.fromLocalFile(base_dir + os.sep)
        self.preview.setHtml(combined, base_url)
        self.status.showMessage("Vorschau aktualisiert.", 1500)

    # -------------------- Datei-Operationen (Projektordner) --------------------
    def new_project(self):
        if not self._confirm_discard():
            return
        self.html_edit.setPlainText(DEFAULT_HTML)
        self.css_edit.setPlainText(DEFAULT_CSS)
        self.js_edit.setPlainText(DEFAULT_JS)
        self.current_file = None
        self.current_folder = None
        self._dirty = False
        self._update_title()
        self._update_preview()

    def _confirm_discard(self):
        if not self._dirty:
            return True
        reply = QMessageBox.question(
            self, "Ungespeicherte Änderungen",
            "Es gibt ungespeicherte Änderungen. Trotzdem fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    def open_project_folder(self):
        """Öffnet einen Projektordner mit index.html / assets/style/style.css
        / assets/script/script.js (fehlende Dateien werden als leer geladen)."""
        if not self._confirm_discard():
            return
        folder = QFileDialog.getExistingDirectory(self, "Projekt-Ordner öffnen")
        if folder:
            self._load_folder(folder)

    def _load_folder(self, folder):
        try:
            index_path = os.path.join(folder, "index.html")
            css_path = os.path.join(folder, CSS_REL_PATH)
            js_path = os.path.join(folder, JS_REL_PATH)

            html = ""
            if os.path.isfile(index_path):
                with open(index_path, "r", encoding="utf-8") as f:
                    html, _css_unused, _js_unused = self._split_html_document(f.read())

            css = ""
            if os.path.isfile(css_path):
                with open(css_path, "r", encoding="utf-8") as f:
                    css = f.read()

            js = ""
            if os.path.isfile(js_path):
                with open(js_path, "r", encoding="utf-8") as f:
                    js = f.read()

            self.html_edit.setPlainText(html)
            self.css_edit.setPlainText(css)
            self.js_edit.setPlainText(js)

            self.current_file = None
            self.current_folder = folder
            self._dirty = False
            self._update_title()
            self._update_preview()
            self.status.showMessage(f"Projekt geladen: {folder}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Ladefehler", f"Projektordner konnte nicht geladen werden:\n{e}")

    def open_single_html(self):
        """Öffnet eine einzelne, bereits vorhandene .html-Datei (z.B. Alt-
        bestand) und extrahiert Inline-<style>/<script> in die CSS-/JS-
        Spalte. Zum getrennten Speichern anschließend 'Speichern unter…'
        verwenden."""
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "HTML-Datei öffnen", "", "HTML-Datei (*.html *.htm);;Alle Dateien (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            html, css, js = self._split_html_document(content)
            self.html_edit.setPlainText(html)
            self.css_edit.setPlainText(css)
            self.js_edit.setPlainText(js)

            self.current_file = path
            self.current_folder = None
            self._dirty = False
            self._update_title()
            self._update_preview()
            self.status.showMessage(f"Geladen: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Ladefehler", f"Datei konnte nicht geladen werden:\n{e}")

    @staticmethod
    def _split_html_document(content):
        """Extrahiert <style>- und <script>-Inhalte aus einer vollständigen
        HTML-Datei, damit sie in die getrennten CSS-/JS-Spalten geladen
        werden können. Der restliche Body-Inhalt bleibt in der HTML-Spalte.
        Verlinkte <link rel="stylesheet"> / <script src> (wie sie
        _linked_index_html erzeugt) werden dabei einfach entfernt, da CSS/JS
        in diesem Fall separat aus den zugehörigen Dateien gelesen werden."""
        css_parts = re.findall(r"<style[^>]*>(.*?)</style>", content, re.DOTALL | re.IGNORECASE)
        js_parts = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", content, re.DOTALL | re.IGNORECASE)

        body_match = re.search(r"<body[^>]*>(.*?)</body>", content, re.DOTALL | re.IGNORECASE)
        html_body = body_match.group(1) if body_match else content

        html_body = re.sub(r"<style[^>]*>.*?</style>", "", html_body, flags=re.DOTALL | re.IGNORECASE)
        html_body = re.sub(r"<script[^>]*>.*?</script>", "", html_body, flags=re.DOTALL | re.IGNORECASE)
        html_body = re.sub(r'<link[^>]*rel=["\']stylesheet["\'][^>]*>', "", html_body, flags=re.IGNORECASE)

        css = "\n".join(p.strip() for p in css_parts).strip()
        js = "\n".join(p.strip() for p in js_parts).strip()
        return html_body.strip(), css, js

    def save_project_folder(self):
        if self.current_folder:
            self._save_to_folder(self.current_folder)
        else:
            self.save_project_folder_as()

    def save_project_folder_as(self):
        folder = QFileDialog.getExistingDirectory(self, "Projekt-Ordner wählen (oder anlegen)")
        if folder:
            self._save_to_folder(folder)

    def _save_to_folder(self, folder):
        """Schreibt die drei Dateien getrennt:
             <folder>/index.html
             <folder>/assets/style/style.css
             <folder>/assets/script/script.js
        """
        css_path = os.path.join(folder, CSS_REL_PATH)
        js_path = os.path.join(folder, JS_REL_PATH)
        index_path = os.path.join(folder, "index.html")
        try:
            os.makedirs(os.path.dirname(css_path), exist_ok=True)
            os.makedirs(os.path.dirname(js_path), exist_ok=True)

            with open(index_path, "w", encoding="utf-8") as f:
                f.write(self._linked_index_html())
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(self.css_edit.toPlainText())
            with open(js_path, "w", encoding="utf-8") as f:
                f.write(self.js_edit.toPlainText())

            self.current_file = None
            self.current_folder = folder
            self._dirty = False
            self._update_title()
            self.status.showMessage(
                f"Gespeichert: {index_path}, {CSS_REL_PATH}, {JS_REL_PATH}", 6000
            )
        except Exception as e:
            QMessageBox.critical(self, "Speicherfehler", f"Projekt konnte nicht gespeichert werden:\n{e}")

    def export_html(self):
        """Exportiert zusätzlich eine einzelne, portable HTML-Datei mit
        allem inline (für schnelles Teilen/Anhängen)."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Als einzelne HTML exportieren", "", "HTML-Datei (*.html)"
        )
        if not path:
            return
        if not path.lower().endswith((".html", ".htm")):
            path += ".html"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._combined_html())
            self.status.showMessage(f"Exportiert: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Exportfehler", f"Konnte HTML nicht schreiben:\n{e}")

    def _update_title(self):
        if self.current_folder:
            name = os.path.basename(os.path.normpath(self.current_folder)) + "/"
        elif self.current_file:
            name = os.path.basename(self.current_file)
        else:
            name = "Unbenanntes Projekt"
        star = "*" if self._dirty else ""
        self.setWindowTitle(f"⧉ PANDORA WEB EDITOR — {name}{star}")

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()


# ------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Pandora Web Editor")
    parser.add_argument("file", nargs="?", help="Projektordner oder .html-Datei zum direkten Öffnen")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyleSheet(PANDORA_QSS)

    if not HAVE_WEBENGINE:
        QMessageBox.warning(
            None, "Fehlende Abhängigkeit",
            "QWebEngineView (PyQt6-WebEngine) ist nicht installiert.\n"
            "Die Editoren funktionieren, die Live-Vorschau bleibt aber leer.\n\n"
            "Installation: pip install PyQt6-WebEngine --break-system-packages"
        )

    win = PandoraWebEditor(initial_file=args.file)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
