# -*- coding: utf-8 -*-
"""
editor.py
Pandora® md Editor - Hauptfenster
by AKI_SystemDown®

Split-Screen Markdown-Editor:
  links  -> QTextEdit (Eingabe, Syntax-Highlighting)
  rechts -> QWebEngineView (Live-HTML-Vorschau)
"""

import os
import sys

import markdown

from PyQt6.QtCore import Qt, QUrl, QTimer, QMarginsF
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QPageLayout, QPageSize
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTextEdit,
    QLabel, QFrame, QFileDialog, QMessageBox, QToolBar, QStatusBar,
    QApplication, QSizePolicy
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

from highlighter import MarkdownHighlighter
from theme import PANDORA_DARKRED_QSS, PREVIEW_HTML_TEMPLATE
from help_dialog import MarkdownHelpDialog

APP_NAME = "Pandora® md Editor"
APP_VERSION = "1.0"
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")

MD_EXTENSIONS = [
    "extra",          # tables, fenced_code, footnotes, abbr, etc.
    "codehilite",      # Pygments-Syntax-Highlighting im HTML-Export
    "toc",
    "sane_lists",
    "nl2br",
]

MD_EXTENSION_CONFIGS = {
    "codehilite": {
        "css_class": "codehilite",
        "guess_lang": True,
    }
}


class PandoraMdEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file_path = None
        self.unsaved_changes = False
        self._help_dialog = None

        self._build_ui()
        self._build_actions()
        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()
        self._connect_signals()

        self._render_preview()
        self._update_title()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 860)
        if os.path.exists(LOGO_PATH):
            self.setWindowIcon(QIcon(LOGO_PATH))

        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(6)

        # Kopfzeile mit Logo + Titel
        header = QHBoxLayout()
        logo_label = QLabel()
        if os.path.exists(LOGO_PATH):
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(LOGO_PATH).scaledToHeight(
                32, Qt.TransformationMode.SmoothTransformation
            )
            logo_label.setPixmap(pix)
        title_label = QLabel(f"  {APP_NAME}")
        title_label.setStyleSheet(
            "font-size: 15pt; font-weight: bold; color: #e8574f; "
            "letter-spacing: 2px;"
        )
        header.addWidget(logo_label)
        header.addWidget(title_label)
        header.addStretch()

        # Header in ein eigenes Widget packen und dessen Hoehe auf den
        # tatsaechlichen Inhalt beschraenken, damit die Kopfzeile im
        # root_layout nicht ungewollt Extra-Platz zugewiesen bekommt.
        header_widget = QWidget()
        header_widget.setLayout(header)
        header_widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        root_layout.addWidget(header_widget, 0)

        # Splitter: Editor links / Vorschau rechts
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # --- linke Seite: Editor ---
        left_widget = QWidget()
        left_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_title = QLabel(">_ MARKDOWN INPUT")
        left_title.setObjectName("PaneTitle")
        left_title.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.editor = QTextEdit()
        self.editor.setAcceptRichText(False)
        self.editor.setPlaceholderText(
            "# Willkommen bei Pandora® md Editor\n\n"
            "Schreibe hier deinen Markdown-Text ...\n"
        )
        self.editor.setFont(self._mono_font())
        self.editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.highlighter = MarkdownHighlighter(self.editor.document())
        left_layout.addWidget(left_title, 0)
        left_layout.addWidget(self.editor, 1)

        # --- rechte Seite: Live-Vorschau ---
        right_widget = QWidget()
        right_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_title = QLabel(">_ LIVE PREVIEW")
        right_title.setObjectName("PaneTitle")
        right_title.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )

        preview_frame = QFrame()
        preview_frame.setObjectName("PreviewFrame")
        preview_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        preview_frame_layout = QVBoxLayout(preview_frame)
        preview_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.preview = QWebEngineView()
        self.preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        preview_frame_layout.addWidget(self.preview)

        right_layout.addWidget(right_title, 0)
        right_layout.addWidget(preview_frame, 1)

        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setSizes([700, 700])
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        root_layout.addWidget(self.splitter, 1)
        self.setCentralWidget(central)

    def _mono_font(self):
        from PyQt6.QtGui import QFont
        f = QFont("Consolas")
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPointSize(11)
        return f

    # ------------------------------------------------------------------
    # Actions / Menue / Toolbar
    # ------------------------------------------------------------------
    def _build_actions(self):
        self.act_open = QAction("&Öffnen …", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self.open_file)

        self.act_save = QAction("&Speichern", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self.save_file)

        self.act_save_as = QAction("Speichern &unter …", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self.save_file_as)

        self.act_export_pdf = QAction("Als &PDF exportieren …", self)
        self.act_export_pdf.setShortcut("Ctrl+P")
        self.act_export_pdf.triggered.connect(self.export_pdf)

        self.act_export_html = QAction("Als &HTML exportieren …", self)
        self.act_export_html.triggered.connect(self.export_html)

        self.act_new = QAction("&Neu", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.triggered.connect(self.new_file)

        self.act_exit = QAction("&Beenden", self)
        self.act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_exit.triggered.connect(self.close)

        self.act_about = QAction("Über Pandora® md Editor", self)
        self.act_about.triggered.connect(self.show_about)

        self.act_md_help = QAction("&Markdown-Syntax-Hilfe …", self)
        self.act_md_help.setShortcut(QKeySequence.StandardKey.HelpContents)
        self.act_md_help.setToolTip(
            "Übersicht aller Markdown-Vorzeichen (# für Überschrift, "
            "** für Fett, etc.) mit Erklärung und Beispiel"
        )
        self.act_md_help.triggered.connect(self.show_markdown_help)

    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&Datei")
        file_menu.addAction(self.act_new)
        file_menu.addAction(self.act_open)
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_export_pdf)
        file_menu.addAction(self.act_export_html)
        file_menu.addSeparator()
        file_menu.addAction(self.act_exit)

        help_menu = menubar.addMenu("&Hilfe")
        help_menu.addAction(self.act_md_help)
        help_menu.addSeparator()
        help_menu.addAction(self.act_about)

    def _build_toolbar(self):
        toolbar = QToolBar("Hauptwerkzeugleiste")
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())
        self.addToolBar(toolbar)

        toolbar.addAction(self.act_new)
        toolbar.addAction(self.act_open)
        toolbar.addAction(self.act_save)
        toolbar.addAction(self.act_save_as)
        toolbar.addSeparator()
        toolbar.addAction(self.act_export_pdf)
        toolbar.addAction(self.act_export_html)
        toolbar.addSeparator()
        toolbar.addAction(self.act_md_help)

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Bereit.")

    # ------------------------------------------------------------------
    # Signale
    # ------------------------------------------------------------------
    def _connect_signals(self):
        # Entprellung: Vorschau nicht bei JEDEM Tastendruck, sondern
        # 150ms nach der letzten Aenderung neu rendern (fluessiger bei
        # langen Dokumenten).
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._debounce.timeout.connect(self._render_preview)

        self.editor.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self):
        self.unsaved_changes = True
        self._update_title()
        self._debounce.start()

    # ------------------------------------------------------------------
    # Markdown -> HTML Live-Vorschau
    # ------------------------------------------------------------------
    def _render_preview(self):
        raw_md = self.editor.toPlainText()
        try:
            html_body = markdown.markdown(
                raw_md,
                extensions=MD_EXTENSIONS,
                extension_configs=MD_EXTENSION_CONFIGS,
            )
        except Exception as e:
            html_body = f"<p style='color:#ff6b5c;'>Fehler beim Parsen: {e}</p>"

        full_html = PREVIEW_HTML_TEMPLATE.format(body=html_body)
        base_url = QUrl.fromLocalFile(
            (os.path.dirname(self.current_file_path) if self.current_file_path
             else os.getcwd()) + os.sep
        )
        self.preview.setHtml(full_html, base_url)

    # ------------------------------------------------------------------
    # Datei-Operationen
    # ------------------------------------------------------------------
    def new_file(self):
        if not self._confirm_discard_changes():
            return
        self.editor.clear()
        self.current_file_path = None
        self.unsaved_changes = False
        self._update_title()
        self.status.showMessage("Neues Dokument erstellt.", 3000)

    def open_file(self):
        if not self._confirm_discard_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Markdown-Datei öffnen", "", "Markdown-Dateien (*.md *.markdown);;Alle Dateien (*)"
        )
        if not path:
            return
        self.open_path(path)

    def open_path(self, path):
        """Lädt eine Markdown-Datei direkt anhand ihres Pfades (ohne
        Dateidialog). Wird sowohl von open_file() als auch beim Start per
        Kommandozeilen-Argument verwendet (z.B. wenn der Pandora Script
        Editor eine aktive .md-Datei an dieses Werkzeug übergibt)."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Datei konnte nicht geöffnet werden:\n{e}")
            return

        self.editor.blockSignals(True)
        self.editor.setPlainText(content)
        self.editor.blockSignals(False)

        self.current_file_path = path
        self.unsaved_changes = False
        self._render_preview()
        self._update_title()
        self.status.showMessage(f"Geöffnet: {path}", 4000)

    def save_file(self):
        if self.current_file_path is None:
            self.save_file_as()
            return
        self._write_to_path(self.current_file_path)

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Markdown-Datei speichern unter", "dokument.md",
            "Markdown-Dateien (*.md);;Alle Dateien (*)"
        )
        if not path:
            return
        if not path.lower().endswith((".md", ".markdown")):
            path += ".md"
        self._write_to_path(path)

    def _write_to_path(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Datei konnte nicht gespeichert werden:\n{e}")
            return
        self.current_file_path = path
        self.unsaved_changes = False
        self._update_title()
        self.status.showMessage(f"Gespeichert: {path}", 4000)

    # ------------------------------------------------------------------
    # Export: PDF / HTML
    # ------------------------------------------------------------------
    def export_pdf(self):
        default_name = "dokument.pdf"
        if self.current_file_path:
            base = os.path.splitext(os.path.basename(self.current_file_path))[0]
            default_name = base + ".pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Als PDF exportieren", default_name, "PDF-Dateien (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        page_layout = QPageLayout(
            QPageSize(QPageSize.PageSizeId.A4),
            QPageLayout.Orientation.Portrait,
            QMarginsF(15, 15, 15, 15)
        )

        def _on_finished(filepath, ok):
            if ok:
                self.status.showMessage(f"PDF exportiert: {filepath}", 5000)
            else:
                QMessageBox.critical(self, "Fehler", "PDF-Export ist fehlgeschlagen.")

        self.preview.page().printToPdf(path, page_layout)
        # printToPdf ist asynchron; pdfPrintingFinished liefert das Ergebnis
        try:
            self.preview.page().pdfPrintingFinished.disconnect()
        except TypeError:
            pass
        self.preview.page().pdfPrintingFinished.connect(_on_finished)
        self.status.showMessage("PDF wird erzeugt …")

    def export_html(self):
        default_name = "dokument.html"
        if self.current_file_path:
            base = os.path.splitext(os.path.basename(self.current_file_path))[0]
            default_name = base + ".html"
        path, _ = QFileDialog.getSaveFileName(
            self, "Als HTML exportieren", default_name, "HTML-Dateien (*.html)"
        )
        if not path:
            return
        if not path.lower().endswith(".html"):
            path += ".html"

        html_body = markdown.markdown(
            self.editor.toPlainText(),
            extensions=MD_EXTENSIONS,
            extension_configs=MD_EXTENSION_CONFIGS,
        )
        full_html = PREVIEW_HTML_TEMPLATE.format(body=html_body)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(full_html)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"HTML konnte nicht gespeichert werden:\n{e}")
            return
        self.status.showMessage(f"HTML exportiert: {path}", 5000)

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    def _confirm_discard_changes(self):
        if not self.unsaved_changes:
            return True
        reply = QMessageBox.question(
            self, "Ungespeicherte Änderungen",
            "Es gibt ungespeicherte Änderungen. Trotzdem fortfahren?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    def _update_title(self):
        name = os.path.basename(self.current_file_path) if self.current_file_path else "Unbenannt"
        star = " *" if self.unsaved_changes else ""
        self.setWindowTitle(f"{name}{star} — {APP_NAME}")

    def show_about(self):
        QMessageBox.about(
            self, f"Über {APP_NAME}",
            f"<h3 style='color:#e8574f;'>{APP_NAME}</h3>"
            f"<p>Version {APP_VERSION}</p>"
            f"<p>Split-Screen Markdown-Editor mit Live-Vorschau, "
            f"Syntax-Highlighting und PDF-Export.</p>"
            f"<p>by <b>AKI_SystemDown®</b> — Teil der Pandora-Projektreihe</p>"
        )

    def show_markdown_help(self):
        """Öffnet das Markdown-Syntax-Hilfe-Fenster (Spickzettel aller
        Vorzeichen wie '#' für Überschriften, '**' für Fett, etc.).
        Das Fenster bleibt nicht-modal und wird nur einmal erzeugt, damit
        es beim erneuten Klick auf den Hilfe-Button nur nach vorne geholt
        statt neu aufgebaut wird."""
        if self._help_dialog is None:
            self._help_dialog = MarkdownHelpDialog(self)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def closeEvent(self, event):
        if self._confirm_discard_changes():
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyleSheet(PANDORA_DARKRED_QSS)
    window = PandoraMdEditor()
    window.show()

    # Optionales Kommandozeilen-Argument: Pfad zu einer .md-Datei, die
    # sofort geöffnet werden soll (z.B. wenn der Pandora Script Editor
    # dieses Werkzeug mit der aktuell aktiven Markdown-Datei aufruft).
    if len(sys.argv) > 1:
        arg_path = sys.argv[1]
        if os.path.isfile(arg_path):
            window.open_path(arg_path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
