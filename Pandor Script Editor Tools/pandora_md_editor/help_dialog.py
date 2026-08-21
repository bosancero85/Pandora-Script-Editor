# -*- coding: utf-8 -*-
"""
help_dialog.py
Pandora® md Editor - Markdown-Syntax-Hilfe
by AKI_SystemDown®

Zeigt ein eigenständiges Fenster mit einer Übersicht aller gängigen
Markdown-Vorzeichen/Syntax-Elemente (Überschriften, Listen, Betonung,
Links, Code, Tabellen, etc.) inkl. kurzer Erklärung und Beispiel.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLineEdit,
)

APP_TITLE = "Markdown-Syntax-Hilfe"

# Jeder Eintrag: (Kategorie, Vorzeichen/Syntax, Erklärung, Beispiel)
MARKDOWN_REFERENCE = [
    ("Überschriften", "# Text", "Überschrift 1. Ordnung (größte Überschrift)", "# Kapitel"),
    ("Überschriften", "## Text", "Überschrift 2. Ordnung", "## Abschnitt"),
    ("Überschriften", "### Text", "Überschrift 3. Ordnung", "### Unterabschnitt"),
    ("Überschriften", "#### … ###### Text", "Überschriften 4. bis 6. Ordnung (immer kleiner)", "#### Detail"),

    ("Betonung", "*Text* oder _Text_", "Kursiv", "*wichtig*"),
    ("Betonung", "**Text** oder __Text__", "Fett", "**sehr wichtig**"),
    ("Betonung", "***Text***", "Fett und kursiv kombiniert", "***extrem wichtig***"),
    ("Betonung", "~~Text~~", "Durchgestrichen", "~~veraltet~~"),

    ("Listen", "- Text  oder  * Text", "Ungeordnete Liste (Aufzählung)", "- Punkt eins\n- Punkt zwei"),
    ("Listen", "1. Text", "Geordnete Liste (nummeriert)", "1. Erstens\n2. Zweitens"),
    ("Listen", "  - Text", "Verschachtelte Liste (2 Leerzeichen einrücken)", "- Ebene 1\n  - Ebene 2"),
    ("Listen", "- [ ] Text", "Offene Checkbox / Aufgabe", "- [ ] Erledigen"),
    ("Listen", "- [x] Text", "Erledigte Checkbox / Aufgabe", "- [x] Fertig"),

    ("Links & Bilder", "[Text](URL)", "Verlinkter Text", "[Pandora](https://example.com)"),
    ("Links & Bilder", "![Alt-Text](Bildpfad)", "Bild einbetten", "![Logo](logo.png)"),
    ("Links & Bilder", "<https://url>", "Automatisch klickbarer Link", "<https://example.com>"),

    ("Code", "`Text`", "Inline-Code (im Fließtext)", "Nutze `print()`"),
    ("Code", "```\nCode\n```", "Codeblock (mehrzeilig, optional mit Sprache)", "```python\nprint('Hi')\n```"),
    ("Code", "    Text", "Codeblock über 4 Leerzeichen Einrückung", "    x = 1"),

    ("Zitate & Trenner", "> Text", "Blockzitat", "> Das ist ein Zitat."),
    ("Zitate & Trenner", "---  oder  ***  oder  ___", "Horizontale Trennlinie", "---"),

    ("Tabellen", "| Spalte 1 | Spalte 2 |\n|---|---|\n| a | b |", "Tabelle mit Kopfzeile und Trennzeile", "| Name | Alter |\n|---|---|\n| Aki | 30 |"),

    ("Sonstiges", "Text  \\\nText", "Zeilenumbruch (zwei Leerzeichen oder Backslash am Zeilenende)", "Zeile 1  \nZeile 2"),
    ("Sonstiges", "Text[^1]\n\n[^1]: Fußnote", "Fußnote", "Aussage[^1]\n\n[^1]: Quelle."),
    ("Sonstiges", "\\*Text\\*", "Sonderzeichen escapen (Markdown-Syntax deaktivieren)", "\\*kein Kursiv\\*"),
]


class MarkdownHelpDialog(QDialog):
    """Eigenständiges Hilfe-Fenster mit einer durchsuchbaren Tabelle aller
    Markdown-Vorzeichen, Erklärungen und Beispiele."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_TITLE)
        self.resize(820, 620)
        self.setModal(False)

        self._build_ui()
        self._populate_table()

    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"<h2 style='color:#e8574f; margin:0;'>{APP_TITLE}</h2>")
        layout.addWidget(title)

        subtitle = QLabel(
            "Übersicht aller gängigen Markdown-Vorzeichen mit Erklärung und Beispiel."
        )
        subtitle.setStyleSheet("color:#c9a3a3;")
        layout.addWidget(subtitle)

        search_row = QHBoxLayout()
        search_label = QLabel("Suche:")
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("z. B. Tabelle, Fett, Link …")
        self.search_field.textChanged.connect(self._filter_table)
        search_row.addWidget(search_label)
        search_row.addWidget(self.search_field)
        layout.addLayout(search_row)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Kategorie", "Vorzeichen / Syntax", "Erklärung", "Beispiel"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.close)
        close_row.addWidget(self.btn_close)
        layout.addLayout(close_row)

    # ------------------------------------------------------------------
    def _populate_table(self):
        self.table.setRowCount(len(MARKDOWN_REFERENCE))
        for row, (category, syntax, explanation, example) in enumerate(MARKDOWN_REFERENCE):
            item_cat = QTableWidgetItem(category)
            item_syntax = QTableWidgetItem(syntax)
            item_syntax.setFont(self._mono_font())
            item_expl = QTableWidgetItem(explanation)
            item_example = QTableWidgetItem(example)
            item_example.setFont(self._mono_font())

            for item in (item_cat, item_syntax, item_expl, item_example):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row, 0, item_cat)
            self.table.setItem(row, 1, item_syntax)
            self.table.setItem(row, 2, item_expl)
            self.table.setItem(row, 3, item_example)
        self.table.resizeRowsToContents()

    def _mono_font(self):
        from PyQt6.QtGui import QFont
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        return f

    # ------------------------------------------------------------------
    def _filter_table(self, text):
        text = text.strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            match = any(
                text in (self.table.item(row, col).text().lower())
                for col in range(self.table.columnCount())
            )
            self.table.setRowHidden(row, not match)
