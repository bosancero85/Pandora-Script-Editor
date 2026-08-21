#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pandora® Script Editor
-----------------------
Ein schlanker, benutzerfreundlicher Python-Script-Editor auf Basis von PyQt6.

Funktionen:
  - Mehrere Dateien in Tabs
  - Zeilennummern + aktuelle Zeile hervorgehoben
  - Python-Syntaxhervorhebung
  - Neu / Öffnen / Speichern / Speichern unter
  - Rückgängig / Wiederholen / Ausschneiden / Kopieren / Einfügen
  - Suchen & Ersetzen
  - Skript ausführen (per Subprocess) mit Ausgabe-Konsole
  - Zoom (Schriftgröße ändern)
  - Split-Screen: zwei Editor-Bereiche nebeneinander oder übereinander,
    jeweils mit eigenen Tabs für mehrere Dateien
  - Dunkles, modernes Erscheinungsbild
  - Statusleiste mit Zeile/Spalte und Dateistatus
  - Projekt-Panel: Ordner öffnen, Dateibaum, Navigation, Neu/Umbenennen/Löschen
  - Code-Intelligenz: Autovervollständigung (Wortschatz + optional Jedi bei
    installiertem "jedi"-Paket, Strg+Leertaste für kontextbezogene Vorschläge)
  - Linting & Fehlerprüfung: laufende Hintergrundprüfung (Syntaxfehler immer
    über "ast", zusätzlich Stil-/Logikwarnungen über optionales "pyflakes"),
    Wellenlinien im Editor, "Probleme"-Panel mit Sprung zur Fehlerzeile
  - Git-Integration: Repository-Status, Staged/Unstaged-Dateien, Stagen/
    Unstagen/Verwerfen, Diff-Ansicht, Commit, Push, Pull (per "git"-CLI)
  - Gemini-Integration ("gemini-3.5-flash"): Code erklären, verbessern/
    reparieren, aus Beschreibung generieren, freier Chat-Prompt; zusätzlicher
    Kontext aus mehreren offenen Dateien und/oder einem ganzen Ordner wählbar
  - Interaktive Python-Konsole (persistenter Namensraum, Verlauf mit ↑/↓)
  - Icon-Theme: FontAwesome-Icons über optionales "qtawesome"-Paket
    (mit Emoji-Fallback, falls nicht installiert)

Start:  python pandora_script_editor.py
Benötigt: PyQt6  (pip install PyQt6)
Optional: jedi       (pip install jedi)       -> kontextbezogene Autovervollständigung
Optional: pyflakes   (pip install pyflakes)   -> erweiterte Lint-Warnungen
Optional: qtawesome  (pip install qtawesome)  -> FontAwesome-Icon-Theme
Optional: git-CLI im PATH                      -> für die Git-Integration
"""

import os
import sys
import re
import io
import ast
import json
import keyword
import builtins as builtins_module
import contextlib
import traceback
import subprocess
import importlib.util
import urllib.request
import urllib.error
import code as code_module

from PyQt6.QtCore import (
    Qt,
    QRect,
    QSize,
    QRegularExpression,
    QProcess,
    QThread,
    pyqtSignal,
    QStringListModel,
    QTimer,
)
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QTextFormat,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QKeySequence,
    QAction,
    QIcon,
    QTextCursor,
    QFileSystemModel,
    QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QPlainTextEdit,
    QWidget,
    QTextEdit,
    QTabWidget,
    QFileDialog,
    QMessageBox,
    QToolBar,
    QStatusBar,
    QDockWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialog,
    QCheckBox,
    QGridLayout,
    QFontDialog,
    QSplitter,
    QTreeView,
    QCompleter,
    QMenu,
    QInputDialog,
    QAbstractItemView,
    QTextBrowser,
    QListWidget,
    QListWidgetItem,
    QFormLayout,
    QDialogButtonBox,
)

try:
    import jedi  # optional: kontextbezogene Autovervollständigung

    HAVE_JEDI = True
except ImportError:
    HAVE_JEDI = False

try:
    from pyflakes.api import check as _pyflakes_check  # optional: Lint-Warnungen

    HAVE_PYFLAKES = True
except ImportError:
    HAVE_PYFLAKES = False

try:
    import qtawesome as qta  # optional: FontAwesome-Icon-Theme

    HAVE_QTAWESOME = True
except ImportError:
    HAVE_QTAWESOME = False

APP_NAME = "Pandora® Script Editor"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".pandora_script_editor.json")
GEMINI_MODEL = "gemini-3.5-flash"
GIT_TIMEOUT_SECONDS = 20
GIT_CLONE_TIMEOUT_SECONDS = 300
ICON_COLOR = "#d4d4d4"

# Config-Schlüssel für die externen Pandora-Tools (JSON/YAML- & SQL-Config-Editor).
# Gespeichert wird jeweils der Pfad zum Einstiegs-Skript, damit er nicht bei
# jedem Start erneut abgefragt werden muss.
CFG_KEY_JSON_YAML_EDITOR = "json_yaml_editor_path"
CFG_KEY_SQL_CONFIG_EDITOR = "sql_config_editor_path"
CFG_KEY_WEB_EDITOR = "web_editor_path"
CFG_KEY_SNIPPET_VAULT = "snippet_vault_path"
CFG_KEY_CRYPTO_TOOL = "crypto_tool_path"
CFG_KEY_UI_ASSET_COLOR_STUDIO = "ui_asset_color_studio_path"
CFG_KEY_UI_FORGE = "ui_forge_path"
CFG_KEY_ENV_DEPENDENCY_MANAGER = "env_dependency_manager_path"
CFG_KEY_PCB_EDITOR = "pcb_editor_path"
CFG_KEY_MD_EDITOR = "md_editor_path"
CFG_KEY_STRUCTURE_CREATOR = "structure_creator_path"

# Datei-Filter für die Tool-Auswahldialoge der eigenständig (als Subprozess)
# gestarteten Tools: akzeptiert sowohl Python-Quellskripte (*.py) als auch
# fertige Programm-Builds (*.exe unter Windows, z.B. das Ergebnis eines
# PyInstaller-`--onedir`-Builds - dort liegt die relevante Datei im jeweiligen
# dist\<Toolname>\<Toolname>.exe). Unter Linux/macOS erzeugt PyInstaller eine
# ausführbare Datei ohne Endung; diese lässt sich über "Alle Dateien" auswählen.
TOOL_ENTRYPOINT_FILTER = (
    "Pandora-Tool (*.py *.exe);;"
    "Python-Datei (*.py);;"
    "Programm (*.exe);;"
    "Alle Dateien (*)"
)


# ----------------------------------------------------------------------
# Icon-Theme (QtAwesome/FontAwesome, mit Emoji-Fallback)
# ----------------------------------------------------------------------
def themed_icon(fa_name, color=ICON_COLOR):
    """Liefert ein QIcon aus QtAwesome, falls installiert - sonst ein leeres
    (Widgets zeigen dann einfach keinen Icon-Glyphen, nur Text)."""
    if HAVE_QTAWESOME and fa_name:
        try:
            return qta.icon(fa_name, color=color)
        except Exception:
            pass
    return QIcon()


def themed(fa_name, label, emoji_fallback="", color=ICON_COLOR):
    """Kombiniert FontAwesome-Icon + reinen Text (QtAwesome installiert) oder
    Emoji-Text als Fallback. Gibt (QIcon, Anzeigetext) zurück - passend als
    Argumente für QAction(icon, text, ...) bzw. QPushButton(icon, text)."""
    if HAVE_QTAWESOME:
        return themed_icon(fa_name, color), label
    text = f"{emoji_fallback} {label}".strip() if emoji_fallback else label
    return QIcon(), text


PY_KEYWORDS = list(keyword.kwlist)
PY_BUILTINS = [n for n in dir(builtins_module) if not n.startswith("_")]
BASE_WORDLIST = sorted(set(PY_KEYWORDS) | set(PY_BUILTINS))


# ----------------------------------------------------------------------
# Konfiguration (z. B. Gemini-API-Key) persistent speichern
# ----------------------------------------------------------------------
def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ----------------------------------------------------------------------
# Git-Hilfsfunktionen (arbeiten direkt mit der "git"-Kommandozeile)
# ----------------------------------------------------------------------
def run_git(args, cwd, timeout=None):
    """Führt einen Git-Befehl aus und liefert (returncode, stdout, stderr)."""
    if timeout is None:
        timeout = GIT_TIMEOUT_SECONDS
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "„git“ wurde nicht gefunden. Ist Git installiert und im PATH?"
    except subprocess.TimeoutExpired:
        return -1, "", "Git-Befehl hat das Zeitlimit überschritten."
    except Exception as e:
        return -1, "", str(e)


def find_git_root(path):
    """Ermittelt das Wurzelverzeichnis des Git-Repositories zu einem Pfad."""
    if not path:
        return None
    directory = path if os.path.isdir(path) else os.path.dirname(path)
    if not directory or not os.path.isdir(directory):
        return None
    code, out, _ = run_git(["rev-parse", "--show-toplevel"], cwd=directory)
    if code == 0 and out.strip():
        return os.path.normpath(out.strip())
    return None


# ----------------------------------------------------------------------
# Zeilennummern-Bereich
# ----------------------------------------------------------------------
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


# ----------------------------------------------------------------------
# Code-Editor mit Zeilennummern + Autovervollständigung
# ----------------------------------------------------------------------
class CodeEditor(QPlainTextEdit):
    lintRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)

        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.highlight_current_line)
        self.textChanged.connect(self._refresh_completer_words)

        self.setFont(QFont("Consolas", 12))
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.completer = None
        self._file_path = None  # wird von MainWindow gesetzt/benutzt

        # ---- Linting: entprellte Hintergrundprüfung nach Tippstopp ----
        self._lint_issues = []
        self._lint_selections = []
        self._lint_timer = QTimer(self)
        self._lint_timer.setSingleShot(True)
        self._lint_timer.setInterval(700)
        self._lint_timer.timeout.connect(self.lintRequested.emit)
        self.textChanged.connect(self._lint_timer.start)

        self.update_line_number_area_width(0)
        self.highlight_current_line()

    # ---------------- Zeilennummern ----------------
    def line_number_area_width(self):
        digits = len(str(max(1, self.blockCount())))
        space = 12 + self.fontMetrics().horizontalAdvance("9") * digits
        return space

    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0, rect.y(), self.line_number_area.width(), rect.height()
            )
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#1e1f26"))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#5c6370"))
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 8,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def highlight_current_line(self):
        extra_selections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            line_color = QColor("#2a2d38")
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extra_selections.append(selection)
        extra_selections.extend(self._lint_selections)
        self.setExtraSelections(extra_selections)

    # ---------------- Linting ----------------
    def set_lint_issues(self, issues):
        """Speichert die aktuellen Lint-Ergebnisse und zeichnet Wellenlinien
        unter den betroffenen Zeilen."""
        self._lint_issues = issues
        selections = []
        for issue in issues:
            block = self.document().findBlockByNumber(max(0, issue.get("line", 1) - 1))
            if not block.isValid():
                continue
            cursor = QTextCursor(block)
            cursor.movePosition(
                QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor
            )
            if not cursor.hasSelection():
                cursor.movePosition(QTextCursor.MoveOperation.EndOfBlock)

            fmt = QTextCharFormat()
            fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            fmt.setUnderlineColor(
                QColor("#f14c4c")
                if issue.get("severity") == "error"
                else QColor("#d7ba7d")
            )
            fmt.setToolTip(issue.get("message", ""))

            selection = QTextEdit.ExtraSelection()
            selection.format = fmt
            selection.cursor = cursor
            selections.append(selection)

        self._lint_selections = selections
        self.highlight_current_line()

    def lint_issue_count(self, severity=None):
        if severity is None:
            return len(self._lint_issues)
        return sum(1 for i in self._lint_issues if i.get("severity") == severity)

    def zoom(self, delta):
        font = self.font()
        new_size = max(6, font.pointSize() + delta)
        font.setPointSize(new_size)
        self.setFont(font)

    # ---------------- Autovervollständigung ----------------
    def set_completer(self, completer):
        if self.completer is not None:
            try:
                self.completer.activated.disconnect(self.insert_completion)
            except (TypeError, RuntimeError):
                pass
        self.completer = completer
        completer.setWidget(self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.activated.connect(self.insert_completion)
        self._refresh_completer_words()

    def _refresh_completer_words(self):
        if self.completer is None:
            return
        model = self.completer.model()
        if not isinstance(model, QStringListModel):
            return
        words = set(BASE_WORDLIST)
        words |= set(
            re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ_][A-Za-z0-9À-ÖØ-öø-ÿ_]*", self.toPlainText())
        )
        model.setStringList(sorted(words))

    def text_under_cursor(self):
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        return cursor.selectedText()

    def insert_completion(self, completion):
        if self.completer is None or self.completer.widget() is not self:
            return
        cursor = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        cursor.movePosition(QTextCursor.MoveOperation.Left)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfWord)
        cursor.insertText(completion[-extra:])
        self.setTextCursor(cursor)

    def _jedi_completions(self):
        if not HAVE_JEDI:
            return None
        try:
            cursor = self.textCursor()
            line = cursor.blockNumber() + 1
            column = cursor.positionInBlock()
            script = jedi.Script(
                code=self.toPlainText(), path=self._file_path or "unbenannt.py"
            )
            completions = script.complete(line, column)
            return [
                c.name for c in completions if c.name and not c.name.startswith("__")
            ]
        except Exception:
            return None

    def keyPressEvent(self, event):
        if self.completer is not None and self.completer.popup().isVisible():
            if event.key() in (
                Qt.Key.Key_Enter,
                Qt.Key.Key_Return,
                Qt.Key.Key_Escape,
                Qt.Key.Key_Tab,
                Qt.Key.Key_Backtab,
            ):
                event.ignore()
                return

        is_shortcut = (
            event.modifiers() == Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_Space
        )
        if not is_shortcut:
            super().keyPressEvent(event)

        if self.completer is None:
            return

        ctrl_or_shift = event.modifiers() in (
            Qt.KeyboardModifier.ControlModifier,
            Qt.KeyboardModifier.ShiftModifier,
        )
        if ctrl_or_shift and not event.text() and not is_shortcut:
            return

        end_of_word = "~!@#$%^&*()_+{}|:\"<>?,./;'[]\\-= \t\n"
        has_modifier = (
            event.modifiers() != Qt.KeyboardModifier.NoModifier
        ) and not ctrl_or_shift
        completion_prefix = self.text_under_cursor()

        if is_shortcut:
            jedi_words = self._jedi_completions()
            model = self.completer.model()
            if jedi_words and isinstance(model, QStringListModel):
                model.setStringList(sorted(set(jedi_words) | set(BASE_WORDLIST)))
            else:
                self._refresh_completer_words()
        elif (
            has_modifier
            or not event.text()
            or len(completion_prefix) < 2
            or (event.text() and event.text()[-1] in end_of_word)
        ):
            self.completer.popup().hide()
            return

        if completion_prefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completion_prefix)
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(
            self.completer.popup().sizeHintForColumn(0)
            + self.completer.popup().verticalScrollBar().sizeHint().width()
        )
        self.completer.complete(cr)


# ----------------------------------------------------------------------
# Python-Syntaxhervorhebung
# ----------------------------------------------------------------------
class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            f.setFontItalic(italic)
            return f

        keywords = [
            "False",
            "None",
            "True",
            "and",
            "as",
            "assert",
            "async",
            "await",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
            "match",
            "case",
        ]
        keyword_fmt = fmt("#c586c0", bold=True)
        for kw in keywords:
            pattern = QRegularExpression(r"\b" + kw + r"\b")
            self.rules.append((pattern, keyword_fmt))

        builtins = [
            "print",
            "len",
            "range",
            "int",
            "str",
            "float",
            "list",
            "dict",
            "set",
            "tuple",
            "bool",
            "object",
            "type",
            "super",
            "self",
            "open",
            "enumerate",
            "zip",
            "map",
            "filter",
            "isinstance",
            "sorted",
            "sum",
            "min",
            "max",
            "abs",
            "input",
            "Exception",
        ]
        builtin_fmt = fmt("#4ec9b0")
        for bi in builtins:
            pattern = QRegularExpression(r"\b" + bi + r"\b")
            self.rules.append((pattern, builtin_fmt))

        self.rules.append((QRegularExpression(r"@\w+"), fmt("#dcdcaa")))
        self.rules.append(
            (QRegularExpression(r"\bdef\s+(\w+)"), fmt("#dcdcaa", bold=True))
        )
        self.rules.append(
            (QRegularExpression(r"\bclass\s+(\w+)"), fmt("#4ec9b0", bold=True))
        )
        self.rules.append((QRegularExpression(r"\b[0-9]+\.?[0-9]*\b"), fmt("#b5cea8")))
        self.rules.append(
            (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), fmt("#ce9178"))
        )
        self.rules.append(
            (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), fmt("#ce9178"))
        )
        self.rules.append((QRegularExpression(r"#[^\n]*"), fmt("#6a9955", italic=True)))

        self.tri_single = QRegularExpression(r"'''")
        self.tri_double = QRegularExpression(r'"""')
        self.string_fmt = fmt("#ce9178")

    def highlightBlock(self, text):
        for pattern, fmt_ in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt_)

        self.setCurrentBlockState(0)
        in_multiline = self.match_triple_quote(text, self.tri_double, 1)
        if not in_multiline:
            self.match_triple_quote(text, self.tri_single, 2)

    def match_triple_quote(self, text, pattern, state):
        """Markiert mehrzeilige '''...'''- bzw. \"\"\"...\"\"\"-Strings.
        Gibt True zurück, wenn der Block am Ende noch innerhalb eines
        offenen Dreifach-Strings dieses Typs endet."""
        start_index = 0
        if self.previousBlockState() != state:
            match = pattern.match(text)
            start_index = match.capturedStart() if match.hasMatch() else -1

        while start_index >= 0:
            match = pattern.match(text, start_index + 3)
            end_index = match.capturedStart() if match.hasMatch() else -1

            if end_index == -1:
                self.setCurrentBlockState(state)
                length = len(text) - start_index
                self.setFormat(start_index, length, self.string_fmt)
                return True
            else:
                length = end_index - start_index + 3
                self.setFormat(start_index, length, self.string_fmt)
                next_match = pattern.match(text, start_index + length)
                start_index = (
                    next_match.capturedStart() if next_match.hasMatch() else -1
                )

        return False


# ----------------------------------------------------------------------
# Linting & Fehlerprüfung
# ----------------------------------------------------------------------
class _PyflakesIssueCollector:
    """Sammelt pyflakes-Meldungen als einfache dicts statt sie zu drucken."""

    def __init__(self):
        self.issues = []

    def unexpectedError(self, filename, msg):
        self.issues.append(
            {"line": 1, "col": 1, "message": str(msg), "severity": "error"}
        )

    def syntaxError(self, filename, msg, lineno, offset, text):
        self.issues.append(
            {
                "line": lineno or 1,
                "col": (offset or 1),
                "message": str(msg),
                "severity": "error",
            }
        )

    def flake(self, message):
        try:
            text = message.message % message.message_args
        except Exception:
            text = str(message)
        self.issues.append(
            {
                "line": getattr(message, "lineno", 1),
                "col": getattr(message, "col", 0) + 1,
                "message": text,
                "severity": "warning",
            }
        )


def lint_source(source, filename=None):
    """Prüft Python-Quelltext auf Syntaxfehler (immer) und Stil-/Logikwarnungen
    (nur wenn "pyflakes" installiert ist). Gibt eine Liste von
    {"line", "col", "message", "severity"}-Einträgen zurück."""
    filename = filename or "unbenannt.py"
    issues = []

    try:
        ast.parse(source, filename=filename)
    except SyntaxError as e:
        issues.append(
            {
                "line": e.lineno or 1,
                "col": e.offset or 1,
                "message": f"SyntaxError: {e.msg}",
                "severity": "error",
            }
        )
        return issues  # bei ungültiger Syntax bringt eine weitere Prüfung nichts
    except Exception as e:
        issues.append({"line": 1, "col": 1, "message": str(e), "severity": "error"})
        return issues

    if HAVE_PYFLAKES:
        collector = _PyflakesIssueCollector()
        try:
            _pyflakes_check(source, filename, collector)
        except Exception:
            pass  # Lint-Warnungen sind optional; Abstürze hier nie eskalieren
        issues.extend(collector.issues)

    issues.sort(key=lambda i: (i["line"], i["col"]))
    return issues


class LintWorker(QThread):
    """Führt lint_source() im Hintergrund aus, damit die UI nicht blockiert."""

    finished_lint = pyqtSignal(list)

    def __init__(self, source, filename, parent=None):
        super().__init__(parent)
        self.source = source
        self.filename = filename

    def run(self):
        issues = lint_source(self.source, self.filename)
        self.finished_lint.emit(issues)


# ----------------------------------------------------------------------
# Suchen & Ersetzen Dialog
# ----------------------------------------------------------------------
class FindReplaceDialog(QDialog):
    def __init__(self, editor_getter, parent=None):
        super().__init__(parent)
        self.editor_getter = editor_getter
        self.setWindowTitle("Suchen & Ersetzen")
        self.setMinimumWidth(380)

        layout = QGridLayout(self)

        self.find_edit = QLineEdit()
        self.replace_edit = QLineEdit()
        self.case_check = QCheckBox("Groß-/Kleinschreibung beachten")

        layout.addWidget(QLabel("Suchen:"), 0, 0)
        layout.addWidget(self.find_edit, 0, 1, 1, 3)
        layout.addWidget(QLabel("Ersetzen:"), 1, 0)
        layout.addWidget(self.replace_edit, 1, 1, 1, 3)
        layout.addWidget(self.case_check, 2, 0, 1, 2)

        btn_find = QPushButton("Weiter suchen")
        btn_replace = QPushButton("Ersetzen")
        btn_replace_all = QPushButton("Alle ersetzen")

        # autoDefault deaktivieren: verhindert, dass Qt beim Enter-Druck in
        # den Eingabefeldern selbstständig irgendeinen Button "anklickt"
        # (bzw. den Dialog bei fehlendem Default-Button schließt).
        for b in (btn_find, btn_replace, btn_replace_all):
            b.setAutoDefault(False)
            b.setDefault(False)

        btn_find.clicked.connect(self.find_next)
        btn_replace.clicked.connect(self.replace_one)
        btn_replace_all.clicked.connect(self.replace_all)

        layout.addWidget(btn_find, 3, 1)
        layout.addWidget(btn_replace, 3, 2)
        layout.addWidget(btn_replace_all, 3, 3)

        # Enter in den Eingabefeldern soll gezielt "Weiter suchen" auslösen,
        # statt dem (fehleranfälligen) Default-Button-Mechanismus von QDialog
        # überlassen zu werden.
        self.find_edit.returnPressed.connect(self.find_next)
        self.replace_edit.returnPressed.connect(self.replace_one)

    def _flags(self):
        # WICHTIG: In PyQt6 existiert QPlainTextEdit.FindFlag NICHT mehr
        # (Unterschied zu PyQt5). Das Enum liegt in QTextDocument. Die
        # falsche Referenz führte zu einem AttributeError beim Suchen, der
        # mangels Exception-Handling die ganze Anwendung abstürzen ließ.
        flags = QTextDocument.FindFlag(0)
        if self.case_check.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        return flags

    def _reveal_editor(self, editor):
        """Macht den Tab/die Pane des Editors sichtbar und holt das
        Hauptfenster in den Vordergrund, damit der Treffer tatsächlich
        zu sehen ist (statt still in einem inaktiven Tab zu passieren)."""
        pane = getattr(editor, "_pane", None)
        if pane is not None:
            idx = pane.indexOf(editor)
            if idx != -1:
                pane.setCurrentIndex(idx)
        editor.setFocus()
        main_window = self.parent()
        if main_window is not None:
            main_window.raise_()
            main_window.activateWindow()
        self.raise_()
        self.activateWindow()

    def find_next(self):
        editor = self.editor_getter()
        if not editor:
            return
        text = self.find_edit.text()
        if not text:
            return
        found = editor.find(text, self._flags())
        if not found:
            # Von vorne suchen (Wrap-around), falls ab Cursorposition
            # nichts mehr gefunden wurde.
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            editor.setTextCursor(cursor)
            found = editor.find(text, self._flags())
        if found:
            self._reveal_editor(editor)
        else:
            QMessageBox.information(self, "Suchen", f"„{text}“ wurde nicht gefunden.")

    def replace_one(self):
        editor = self.editor_getter()
        if not editor:
            return
        find_text = self.find_edit.text()
        if not find_text:
            return
        cursor = editor.textCursor()
        selected = cursor.selectedText()
        case_sensitive = self.case_check.isChecked()
        matches = (
            (selected == find_text)
            if case_sensitive
            else (selected.lower() == find_text.lower())
        )
        if cursor.hasSelection() and matches:
            cursor.insertText(self.replace_edit.text())
            editor.setTextCursor(cursor)
        self.find_next()

    def replace_all(self):
        editor = self.editor_getter()
        if not editor:
            return
        find_text = self.find_edit.text()
        replace_text = self.replace_edit.text()
        if not find_text:
            return
        content = editor.toPlainText()
        flags = re.IGNORECASE if not self.case_check.isChecked() else 0
        new_content, count = re.subn(
            re.escape(find_text),
            replace_text.replace("\\", "\\\\"),
            content,
            flags=flags,
        )
        if count:
            editor.setPlainText(new_content)
            self._reveal_editor(editor)
        QMessageBox.information(
            self, "Alle ersetzen", f"{count} Ersetzung(en) durchgeführt."
        )


# ----------------------------------------------------------------------
# Projekt-Panel: Dateibaum + Navigation
# ----------------------------------------------------------------------
class ProjectPanel(QDockWidget):
    fileDoubleClicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Projekt", parent)
        self.setObjectName("ProjectPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.project_root = None

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        header = QHBoxLayout()
        btn_open = QPushButton("📁 Open Folder…")
        btn_open.clicked.connect(self.open_folder)
        btn_refresh = QPushButton("⟳")
        btn_refresh.setFixedWidth(32)
        btn_refresh.setToolTip("Aktualisieren")
        btn_refresh.clicked.connect(self.refresh)
        header.addWidget(btn_open)
        header.addWidget(btn_refresh)
        layout.addLayout(header)

        self.lbl_root = QLabel("Kein Projekt geöffnet")
        self.lbl_root.setWordWrap(True)
        self.lbl_root.setStyleSheet("color:#9aa0ab; font-size:11px;")
        layout.addWidget(self.lbl_root)

        self.model = QFileSystemModel()
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(False)
        for col in (1, 2, 3):
            self.tree.hideColumn(col)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.doubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

        self.setWidget(container)

    def open_folder(self, path=None):
        if not path:
            path = QFileDialog.getExistingDirectory(self, "Projektordner wählen")
        if not path:
            return
        self.project_root = path
        self.model.setRootPath(path)
        self.tree.setRootIndex(self.model.index(path))
        self.lbl_root.setText(path)
        self.show()
        self.raise_()

    def refresh(self):
        if self.project_root:
            self.model.setRootPath("")
            self.model.setRootPath(self.project_root)
            self.tree.setRootIndex(self.model.index(self.project_root))

    def _on_double_click(self, index):
        path = self.model.filePath(index)
        if os.path.isfile(path):
            self.fileDoubleClicked.emit(path)

    def _show_context_menu(self, pos):
        index = self.tree.indexAt(pos)
        base_path = self.model.filePath(index) if index.isValid() else self.project_root
        if base_path and os.path.isfile(base_path):
            base_path = os.path.dirname(base_path)
        if not base_path:
            base_path = self.project_root

        menu = QMenu(self)
        ic, tx = themed("fa5s.file", "New File…", emoji_fallback="📄")
        act_new_file = menu.addAction(ic, tx)
        ic, tx = themed("fa5s.folder", "New Folder…", emoji_fallback="📁")
        act_new_folder = menu.addAction(ic, tx)
        menu.addSeparator()
        ic, tx = themed("fa5s.edit", "Umbenennen…", emoji_fallback="✏")
        act_rename = menu.addAction(ic, tx)
        ic, tx = themed("fa5s.trash", "Löschen", emoji_fallback="🗑")
        act_delete = menu.addAction(ic, tx)
        menu.addSeparator()
        ic, tx = themed("fa5s.sync", "Aktualisieren", emoji_fallback="⟳")
        act_refresh = menu.addAction(ic, tx)

        if base_path is None:
            act_new_file.setEnabled(False)
            act_new_folder.setEnabled(False)
        if not index.isValid():
            act_rename.setEnabled(False)
            act_delete.setEnabled(False)

        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        try:
            if chosen == act_new_file:
                name, ok = QInputDialog.getText(self, "New File", "Filename:")
                if ok and name:
                    open(os.path.join(base_path, name), "a", encoding="utf-8").close()
            elif chosen == act_new_folder:
                name, ok = QInputDialog.getText(self, "New Folder", "Foldername:")
                if ok and name:
                    os.makedirs(os.path.join(base_path, name), exist_ok=True)
            elif chosen == act_rename and index.isValid():
                old_path = self.model.filePath(index)
                name, ok = QInputDialog.getText(
                    self, "Rename", "New Name:", text=os.path.basename(old_path)
                )
                if ok and name:
                    os.rename(old_path, os.path.join(os.path.dirname(old_path), name))
            elif chosen == act_delete and index.isValid():
                path = self.model.filePath(index)
                res = QMessageBox.question(
                    self,
                    "Löschen",
                    f"„{os.path.basename(path)}“ wirklich löschen?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if res == QMessageBox.StandardButton.Yes:
                    if os.path.isdir(path):
                        import shutil

                        shutil.rmtree(path)
                    else:
                        os.remove(path)
            elif chosen == act_refresh:
                self.refresh()
        except OSError as e:
            QMessageBox.warning(self, "Projekt", f"Vorgang fehlgeschlagen:\n{e}")


# ----------------------------------------------------------------------
# Probleme-Panel (Linting-Ergebnisse)
# ----------------------------------------------------------------------
class ProblemsPanel(QDockWidget):
    """Zeigt die Lint-Ergebnisse der aktuellen Datei; Doppelklick springt
    zur betroffenen Zeile im Editor."""

    issueActivated = pyqtSignal(int, int)  # line, col (1-basiert)

    def __init__(self, parent=None):
        super().__init__("Probleme", parent)
        self.setObjectName("ProblemsPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        self.summary_label = QLabel("Keine Probleme")
        self.summary_label.setStyleSheet("color:#9aa0ab; font-size:11px;")
        layout.addWidget(self.summary_label)

        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self._on_item_activated)
        self.list_widget.itemDoubleClicked.connect(self._on_item_activated)
        layout.addWidget(self.list_widget)

        self.setWidget(container)

    def show_issues(self, issues, file_label=""):
        self.list_widget.clear()
        errors = sum(1 for i in issues if i.get("severity") == "error")
        warnings = sum(1 for i in issues if i.get("severity") == "warning")

        if not issues:
            self.summary_label.setText(
                f"✅ Keine Probleme{' – ' + file_label if file_label else ''}"
            )
        else:
            self.summary_label.setText(
                f"🔴 {errors} Fehler   🟡 {warnings} Warnungen"
                + (f"  –  {file_label}" if file_label else "")
            )

        for issue in issues:
            is_error = issue.get("severity") == "error"
            line = issue.get("line", 1)
            col = issue.get("col", 1)
            if HAVE_QTAWESOME:
                fa_name = (
                    "fa5s.times-circle" if is_error else "fa5s.exclamation-triangle"
                )
                color = "#f14c4c" if is_error else "#d7ba7d"
                text = f"Zeile {line}, Spalte {col}: {issue.get('message', '')}"
                item = QListWidgetItem(themed_icon(fa_name, color=color), text)
            else:
                prefix = "❌" if is_error else "⚠"
                text = (
                    f"{prefix}  Zeile {line}, Spalte {col}: {issue.get('message', '')}"
                )
                item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, (line, col))
            self.list_widget.addItem(item)

    def clear_issues(self, message="Keine Datei geöffnet"):
        self.list_widget.clear()
        self.summary_label.setText(message)

    def _on_item_activated(self, item):
        line, col = item.data(Qt.ItemDataRole.UserRole)
        self.issueActivated.emit(line, col)


# ----------------------------------------------------------------------
# Git-Panel
# ----------------------------------------------------------------------
class GitWorker(QThread):
    """Führt einen einzelnen Git-Befehl asynchron aus."""

    finished_run = pyqtSignal(str, int, str, str)  # action, code, stdout, stderr

    def __init__(self, action, args, cwd, parent=None):
        super().__init__(parent)
        self.action = action
        self.args = args
        self.cwd = cwd

    def run(self):
        code, out, err = run_git(self.args, self.cwd)
        self.finished_run.emit(self.action, code, out, err)


class GitCloneWorker(QThread):
    """Führt 'git clone' asynchron aus (deutlich längeres Timeout als
    normale Status-/Commit-Befehle, da Repos groß sein können)."""

    finished_run = pyqtSignal(int, str, str, str)  # code, stdout, stderr, dest_path

    def __init__(self, url, dest_path, parent=None):
        super().__init__(parent)
        self.url = url
        self.dest_path = dest_path

    def run(self):
        parent_dir = os.path.dirname(self.dest_path) or "."
        code, out, err = run_git(
            ["clone", "--progress", self.url, self.dest_path],
            cwd=parent_dir,
            timeout=GIT_CLONE_TIMEOUT_SECONDS,
        )
        self.finished_run.emit(code, out, err, self.dest_path)


class GitHubReposDialog(QDialog):
    """Listet die Repositories des eigenen GitHub-Accounts über die
    GitHub-REST-API auf (benötigt einen Personal Access Token, da die
    Endpunkte für den authentifizierten Nutzer sonst nichts liefern) und
    ermöglicht, ein ausgewähltes Repo zu klonen."""

    repoSelectedForClone = pyqtSignal(str, str)  # clone_url, vorgeschlagener Ordnername

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GitHub-Repositories")
        self.resize(560, 480)
        self._repos = []

        layout = QVBoxLayout(self)

        token_row = QHBoxLayout()
        token_row.addWidget(QLabel("Personal Access Token:"))
        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("ghp_… oder github_pat_…")
        cfg = load_config()
        self.token_edit.setText(cfg.get("github_token", ""))
        self.token_edit.returnPressed.connect(self._load_repos)
        token_row.addWidget(self.token_edit, 1)
        layout.addLayout(token_row)

        hint = QLabel(
            "Token erstellen unter github.com → Settings → Developer settings → "
            "Personal access tokens → Fine-grained/Classic (Scope „repo“ genügt). "
            "Der Token wird lokal in ~/.pandora_script_editor.json gespeichert."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#9aa0ab; font-size:11px;")
        layout.addWidget(hint)

        self.btn_load = QPushButton(
            *themed("fa5s.sync", "Repositories laden", emoji_fallback="⟳")
        )
        self.btn_load.clicked.connect(self._load_repos)
        layout.addWidget(self.btn_load)

        self.list_repos = QListWidget()
        layout.addWidget(self.list_repos, 1)

        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color:#9aa0ab; font-size:11px;")
        layout.addWidget(self.lbl_status)

        btn_row = QHBoxLayout()
        self.btn_clone = QPushButton(
            *themed("fa5s.download", "Ausgewähltes Repo klonen…", emoji_fallback="⬇")
        )
        self.btn_clone.clicked.connect(self._clone_selected)
        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_clone)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

        if self.token_edit.text().strip():
            self._load_repos()

    def _save_token(self):
        cfg = load_config()
        cfg["github_token"] = self.token_edit.text().strip()
        save_config(cfg)

    def _load_repos(self):
        token = self.token_edit.text().strip()
        if not token:
            self.lbl_status.setText(
                "Bitte zuerst einen Personal Access Token eingeben - ohne "
                "Token kennt die GitHub-API deinen Account nicht."
            )
            return

        self._save_token()
        self.list_repos.clear()
        self.lbl_status.setText("Lade Repositories…")
        self.btn_load.setEnabled(False)
        QApplication.processEvents()

        try:
            repos = self._fetch_all_repos(token)
        except urllib.error.HTTPError as e:
            self.btn_load.setEnabled(True)
            if e.code == 401:
                self.lbl_status.setText(
                    "Ungültiger oder abgelaufener Token (401 Unauthorized)."
                )
            else:
                self.lbl_status.setText(f"GitHub-API-Fehler: HTTP {e.code}")
            return
        except urllib.error.URLError as e:
            self.btn_load.setEnabled(True)
            self.lbl_status.setText(f"Keine Verbindung zu GitHub möglich: {e.reason}")
            return
        except Exception as e:
            self.btn_load.setEnabled(True)
            self.lbl_status.setText(f"Fehler beim Laden: {e}")
            return

        self.btn_load.setEnabled(True)
        self._repos = repos
        for repo in repos:
            marker = "🔒" if repo.get("private") else "🌐"
            label = f"{marker} {repo['full_name']}"
            if repo.get("description"):
                label += f"  —  {repo['description']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, repo)
            self.list_repos.addItem(item)
        self.lbl_status.setText(
            f"{len(repos)} Repository(s) gefunden."
            if repos
            else "Keine Repositories gefunden."
        )

    def _fetch_all_repos(self, token):
        repos = []
        page = 1
        while True:
            url = f"https://api.github.com/user/repos?per_page=100&page={page}&sort=updated&affiliation=owner,collaborator,organization_member"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/vnd.github+json")
            req.add_header("X-GitHub-Api-Version", "2022-11-28")
            req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if not data:
                break
            for r in data:
                repos.append(
                    {
                        "full_name": r.get("full_name", ""),
                        "clone_url": r.get("clone_url", ""),
                        "private": r.get("private", False),
                        "description": r.get("description") or "",
                    }
                )
            if len(data) < 100:
                break
            page += 1
            if page > 10:  # Sicherheitslimit: max. 1000 Repos
                break
        return repos

    def _clone_selected(self):
        item = self.list_repos.currentItem()
        if not item:
            QMessageBox.information(
                self, "GitHub-Repos", "Bitte zuerst ein Repository auswählen."
            )
            return
        repo = item.data(Qt.ItemDataRole.UserRole)
        self.repoSelectedForClone.emit(
            repo["clone_url"], repo["full_name"].split("/")[-1]
        )
        self.accept()


class GitPanel(QDockWidget):
    """Schlankes Git-Panel: Status, Stagen/Unstagen/Verwerfen, Diff,
    Commit, Push, Pull - basierend auf der "git"-Kommandozeile."""

    def __init__(self, show_output_callable, parent=None, on_repo_opened=None):
        super().__init__("Git", parent)
        self.setObjectName("GitPanel")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.show_output = show_output_callable
        self.on_repo_opened = on_repo_opened
        self.repo_root = None
        self._workers = (
            []
        )  # Referenzen halten, damit Threads nicht vorzeitig gc'ed werden

        container = QWidget()
        v = QVBoxLayout(container)

        self.lbl_repo = QLabel("Kein Git-Repository erkannt")
        self.lbl_repo.setWordWrap(True)
        self.lbl_repo.setStyleSheet("color:#9aa0ab; font-size:11px;")
        v.addWidget(self.lbl_repo)

        # ---- Repository holen: Klonen von URL oder aus eigenem GitHub-Account ----
        clone_row = QHBoxLayout()
        self.btn_clone_url = QPushButton(
            *themed("fa5s.link", "Von URL klonen…", emoji_fallback="🔗")
        )
        self.btn_clone_github = QPushButton(
            *themed("fa5s.github", "GitHub-Repos…", emoji_fallback="🐙")
        )
        self.btn_clone_url.setToolTip(
            "Ein beliebiges Git-Repository per URL klonen (kein Token nötig)."
        )
        self.btn_clone_github.setToolTip(
            "Eigene GitHub-Repositories auflisten und klonen (Personal Access Token nötig)."
        )
        self.btn_clone_url.clicked.connect(self._clone_from_url)
        self.btn_clone_github.clicked.connect(self._open_github_repos)
        clone_row.addWidget(self.btn_clone_url)
        clone_row.addWidget(self.btn_clone_github)
        v.addLayout(clone_row)

        self.lbl_branch = QLabel("")
        self.lbl_branch.setStyleSheet("color:#4ec9b0; font-weight:bold;")
        v.addWidget(self.lbl_branch)

        btn_row = QHBoxLayout()
        self.btn_refresh = QPushButton(
            *themed("fa5s.sync", "Aktualisieren", emoji_fallback="⟳")
        )
        self.btn_stage_all = QPushButton(
            *themed("fa5s.plus", "Alle stagen", emoji_fallback="+")
        )
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_stage_all.clicked.connect(self._stage_all)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_stage_all)
        v.addLayout(btn_row)

        v.addWidget(QLabel("Änderungen (Rechtsklick für Aktionen):"))
        self.list_changes = QListWidget()
        self.list_changes.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_changes.customContextMenuRequested.connect(self._show_context_menu)
        self.list_changes.itemDoubleClicked.connect(self._diff_item)
        v.addWidget(self.list_changes, 1)

        self.commit_edit = QLineEdit()
        self.commit_edit.setPlaceholderText("Commit-Nachricht…")
        self.commit_edit.returnPressed.connect(self._commit)
        v.addWidget(self.commit_edit)

        commit_row = QHBoxLayout()
        self.btn_commit = QPushButton(
            *themed("fa5s.check", "Commit", emoji_fallback="✔")
        )
        self.btn_commit.clicked.connect(self._commit)
        commit_row.addWidget(self.btn_commit)
        v.addLayout(commit_row)

        sync_row = QHBoxLayout()
        self.btn_pull = QPushButton(
            *themed("fa5s.arrow-down", "Pull", emoji_fallback="⇩")
        )
        self.btn_push = QPushButton(
            *themed("fa5s.arrow-up", "Push", emoji_fallback="⇧")
        )
        self.btn_pull.clicked.connect(lambda: self._run("pull", ["pull"]))
        self.btn_push.clicked.connect(lambda: self._run("push", ["push"]))
        sync_row.addWidget(self.btn_pull)
        sync_row.addWidget(self.btn_push)
        v.addLayout(sync_row)

        self.setWidget(container)
        self._set_repo_actions_enabled(False)

    # ---------------- Repository ----------------
    def set_repo_path(self, path):
        """Erkennt das Git-Repository zu einem Datei- oder Ordnerpfad neu."""
        self.repo_root = find_git_root(path)
        if self.repo_root:
            self.lbl_repo.setText(self.repo_root)
        else:
            self.lbl_repo.setText("Kein Git-Repository erkannt")
        self._set_repo_actions_enabled(bool(self.repo_root))
        self.refresh()

    def _set_repo_actions_enabled(self, enabled):
        for w in (
            self.btn_refresh,
            self.btn_stage_all,
            self.btn_commit,
            self.btn_pull,
            self.btn_push,
            self.commit_edit,
            self.list_changes,
        ):
            w.setEnabled(enabled)

    # ---------------- Klonen (URL / GitHub) ----------------
    def _clone_from_url(self):
        url, ok = QInputDialog.getText(
            self, "Von URL klonen", "Git-Repository-URL (https://… oder git@…):"
        )
        if not ok or not url.strip():
            return
        self._prompt_destination_and_clone(url.strip())

    def _open_github_repos(self):
        dialog = GitHubReposDialog(self)
        dialog.repoSelectedForClone.connect(
            lambda clone_url, name: self._prompt_destination_and_clone(
                clone_url, suggested_name=name
            )
        )
        dialog.exec()

    def _prompt_destination_and_clone(self, url, suggested_name=None):
        parent_dir = QFileDialog.getExistingDirectory(
            self, "Zielordner wählen (Repository wird als Unterordner angelegt)"
        )
        if not parent_dir:
            return
        name = suggested_name or url.rstrip("/").split("/")[-1]
        if name.endswith(".git"):
            name = name[:-4]
        name = name.strip() or "repository"
        dest = os.path.join(parent_dir, name)
        if os.path.exists(dest):
            QMessageBox.warning(
                self,
                "Klonen",
                f"Der Ordner „{dest}“ existiert bereits. Bitte einen anderen Zielordner wählen.",
            )
            return
        self._start_clone(url, dest)

    def _start_clone(self, url, dest):
        self.show_output(f"Klone {url}\nnach {dest} …")
        self.btn_clone_url.setEnabled(False)
        self.btn_clone_github.setEnabled(False)
        worker = GitCloneWorker(url, dest, self)
        worker.finished_run.connect(self._on_clone_finished)
        worker.finished.connect(
            lambda w=worker: self._workers.remove(w) if w in self._workers else None
        )
        self._workers.append(worker)
        worker.start()

    def _on_clone_finished(self, code, out, err, dest):
        self.btn_clone_url.setEnabled(True)
        self.btn_clone_github.setEnabled(True)
        self.show_output((out or "") + (("\n" + err) if err else ""))
        if code == 0:
            QMessageBox.information(
                self, "Klonen", f"Repository erfolgreich geklont nach:\n{dest}"
            )
            if self.on_repo_opened:
                self.on_repo_opened(dest)
        else:
            QMessageBox.critical(
                self,
                "Klonen fehlgeschlagen",
                err.strip() if err else "Unbekannter Fehler beim Klonen.",
            )

    def refresh(self):
        if not self.repo_root:
            self.list_changes.clear()
            self.lbl_branch.setText("")
            return
        self._run("status", ["status", "--porcelain=v1", "-b"])

    # ---------------- Aktionen ----------------
    def _run(self, action, args):
        if not self.repo_root:
            return
        worker = GitWorker(action, args, self.repo_root, self)
        worker.finished_run.connect(self._on_result)
        worker.finished.connect(
            lambda w=worker: self._workers.remove(w) if w in self._workers else None
        )
        self._workers.append(worker)
        worker.start()

    def _selected_paths(self):
        paths = []
        for item in self.list_changes.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                paths.append(data[0])
        return paths

    def _stage_all(self):
        self._run("add", ["add", "-A"])

    def _stage_selected(self):
        paths = self._selected_paths()
        if paths:
            self._run("add", ["add", "--"] + paths)

    def _unstage_selected(self):
        paths = self._selected_paths()
        if paths:
            self._run("unstage", ["restore", "--staged", "--"] + paths)

    def _discard_selected(self):
        paths = self._selected_paths()
        if not paths:
            return
        res = QMessageBox.question(
            self,
            "Git",
            f"Änderungen an {len(paths)} Datei(en) wirklich verwerfen?\nDies kann nicht rückgängig gemacht werden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if res == QMessageBox.StandardButton.Yes:
            self._run("discard", ["checkout", "--"] + paths)

    def _diff_item(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        path, staged = data
        args = ["diff", "--", path] if not staged else ["diff", "--cached", "--", path]
        self._run("diff", args)

    def _commit(self):
        message = self.commit_edit.text().strip()
        if not message:
            QMessageBox.information(
                self, "Git", "Bitte eine Commit-Nachricht eingeben."
            )
            return
        self._run("commit", ["commit", "-m", message])

    def _show_context_menu(self, pos):
        item = self.list_changes.itemAt(pos)
        menu = QMenu(self)
        ic, tx = themed("fa5s.plus", "Stagen", emoji_fallback="+")
        act_stage = menu.addAction(ic, tx)
        ic, tx = themed("fa5s.minus", "Unstagen", emoji_fallback="-")
        act_unstage = menu.addAction(ic, tx)
        ic, tx = themed("fa5s.undo", "Änderungen verwerfen", emoji_fallback="↺")
        act_discard = menu.addAction(ic, tx)
        menu.addSeparator()
        ic, tx = themed("fa5s.search", "Diff anzeigen", emoji_fallback="🔍")
        act_diff = menu.addAction(ic, tx)

        has_selection = item is not None and bool(self.list_changes.selectedItems())
        act_stage.setEnabled(has_selection)
        act_unstage.setEnabled(has_selection)
        act_discard.setEnabled(has_selection)
        act_diff.setEnabled(item is not None)

        chosen = menu.exec(self.list_changes.viewport().mapToGlobal(pos))
        if chosen == act_stage:
            self._stage_selected()
        elif chosen == act_unstage:
            self._unstage_selected()
        elif chosen == act_discard:
            self._discard_selected()
        elif chosen == act_diff and item is not None:
            self._diff_item(item)

    # ---------------- Ergebnisverarbeitung ----------------
    def _on_result(self, action, code, out, err):
        if action == "status":
            self._populate_status(code, out, err)
            return

        if code != 0:
            self.show_output(f"$ git {action}\n{err or out or 'Unbekannter Fehler.'}")
        else:
            if action == "diff":
                self.show_output(out if out.strip() else "(keine Unterschiede)")
            elif action == "commit":
                self.show_output(out or "Commit erstellt.")
                self.commit_edit.clear()
            elif action in ("push", "pull"):
                self.show_output(out + ("\n" + err if err else ""))
            # Nach Zustandsänderungen den Status neu laden
        if action != "diff":
            self.refresh()

    def _populate_status(self, code, out, err):
        self.list_changes.clear()
        if code != 0:
            self.lbl_branch.setText("")
            self.show_output(f"$ git status\n{err or 'Fehler beim Lesen des Status.'}")
            return

        lines = out.splitlines()
        if lines and lines[0].startswith("##"):
            branch_info = lines[0][2:].strip()
            self.lbl_branch.setText(f"⎇ {branch_info}")
            lines = lines[1:]
        else:
            self.lbl_branch.setText("⎇ (kein Branch)")

        if not lines:
            self.list_changes.addItem("✅ Keine Änderungen")
            return

        status_names = {
            "M": "geändert",
            "A": "hinzugefügt",
            "D": "gelöscht",
            "R": "umbenannt",
            "C": "kopiert",
            "U": "Konflikt",
            "?": "unversioniert",
        }
        for line in lines:
            if len(line) < 4:
                continue
            index_status, work_status = line[0], line[1]
            path = line[3:]
            staged = index_status not in (" ", "?")
            code_letter = index_status if staged else work_status
            label = status_names.get(code_letter, code_letter)
            prefix = "●" if staged else "○"
            item = QListWidgetItem(f"{prefix} [{label}] {path}")
            item.setData(Qt.ItemDataRole.UserRole, (path, staged))
            if not staged and index_status == "?":
                item.setData(Qt.ItemDataRole.UserRole, (path, False))
            self.list_changes.addItem(item)


# ----------------------------------------------------------------------
# Interaktive Python-Konsole
# ----------------------------------------------------------------------
class InteractiveConsole(QPlainTextEdit):
    PROMPT_PRIMARY = ">>> "
    PROMPT_CONTINUE = "... "

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Consolas", 11))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.namespace = {"__name__": "__console__", "clear": self._cmd_clear}
        self._interpreter = code_module.InteractiveInterpreter(self.namespace)
        self._buffer = ""
        self._history = []
        self._history_idx = 0
        self._prompt_pos = 0
        self._write_banner()

    def _cmd_clear(self):
        self.clear()
        self._buffer = ""
        self._new_prompt()
        return None

    def _write_banner(self):
        self.setPlainText(
            f"Pandora® Interaktive Python-Konsole (Python {sys.version.split()[0]})\n"
            "Variablen bleiben zwischen Eingaben erhalten. clear() leert den Bildschirm.\n"
        )
        self._new_prompt()

    def load_script_into_namespace(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            self.namespace["__file__"] = path
            with contextlib.redirect_stdout(io.StringIO()) as out:
                exec(compile(source, path, "exec"), self.namespace)
            self._print_line(
                f"[Skript '{os.path.basename(path)}' in Konsolen-Namensraum geladen]"
            )
            text = out.getvalue()
            if text:
                self._print_line(text.rstrip("\n"))
        except Exception:
            self._print_line(traceback.format_exc().rstrip("\n"))
        self._new_prompt()

    def _print_line(self, text):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        current = self.toPlainText()
        prefix = "" if (not current or current.endswith("\n")) else "\n"
        self.insertPlainText(prefix + text + "\n")

    def _new_prompt(self, continuation=False):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        current = self.toPlainText()
        prefix = "" if (not current or current.endswith("\n")) else "\n"
        prompt = self.PROMPT_CONTINUE if continuation else self.PROMPT_PRIMARY
        self.insertPlainText(prefix + prompt)
        self.moveCursor(QTextCursor.MoveOperation.End)
        self._prompt_pos = self.textCursor().position()

    def _current_input(self):
        return self.toPlainText()[self._prompt_pos :]

    def keyPressEvent(self, event):
        cursor = self.textCursor()
        if cursor.position() < self._prompt_pos or (
            cursor.hasSelection() and cursor.selectionStart() < self._prompt_pos
        ):
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._execute_current_input()
            return
        if (
            event.key() == Qt.Key.Key_Backspace
            and self.textCursor().position() <= self._prompt_pos
        ):
            return
        if event.key() == Qt.Key.Key_Home:
            c = self.textCursor()
            c.setPosition(self._prompt_pos)
            self.setTextCursor(c)
            return
        if event.key() == Qt.Key.Key_Up:
            self._history_navigate(-1)
            return
        if event.key() == Qt.Key.Key_Down:
            self._history_navigate(1)
            return
        super().keyPressEvent(event)

    def _execute_current_input(self):
        line = self._current_input()
        if line.strip():
            self._history.append(line)
        self._history_idx = len(self._history)

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.insertPlainText("\n")

        self._buffer = (self._buffer + "\n" + line) if self._buffer else line

        stdout = io.StringIO()
        needs_more = False
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
                needs_more = self._interpreter.runsource(self._buffer, "<konsole>")
        except Exception:
            stdout.write(traceback.format_exc())
            needs_more = False

        output = stdout.getvalue()
        if output:
            self.insertPlainText(output if output.endswith("\n") else output + "\n")

        if needs_more:
            self._new_prompt(continuation=True)
        else:
            self._buffer = ""
            self._new_prompt(continuation=False)

    def _history_navigate(self, direction):
        if not self._history:
            return
        self._history_idx = max(
            0, min(len(self._history), self._history_idx + direction)
        )
        cursor = self.textCursor()
        cursor.setPosition(self._prompt_pos)
        cursor.movePosition(
            QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor
        )
        cursor.removeSelectedText()
        if self._history_idx < len(self._history):
            cursor.insertText(self._history[self._history_idx])


# ----------------------------------------------------------------------
# Kontext-Auswahl für Gemini (mehrere offene Dateien und/oder ein Ordner)
# ----------------------------------------------------------------------
class ContextSelectDialog(QDialog):
    """Lässt den Benutzer offene Dateien und/oder alle Python-Dateien eines
    Ordners als zusätzlichen Kontext für Gemini-Anfragen auswählen."""

    MAX_FOLDER_FILES = 40
    MAX_FILE_CHARS = 60_000
    SKIP_DIR_NAMES = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "env",
        "node_modules",
        ".idea",
        ".vscode",
    }

    def __init__(self, open_files, preselected_paths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gemini-Kontext wählen")
        self.setMinimumSize(440, 440)
        self.selected_files = []

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Offene Dateien und hinzugefügte Ordner (Häkchen = im Kontext enthalten):"
            )
        )

        self.list_widget = QListWidget()
        for f in open_files:
            suffix = f"  ({f['path']})" if f.get("path") else "  (ungespeichert)"
            item = QListWidgetItem(f["label"] + suffix)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if f.get("path") in preselected_paths
                else Qt.CheckState.Unchecked
            )
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        folder_row = QHBoxLayout()
        ic, tx = themed("fa5s.folder-plus", "Ordner hinzufügen…")
        self.btn_add_folder = QPushButton(ic, tx)
        self.btn_add_folder.clicked.connect(self._add_folder)
        folder_row.addWidget(self.btn_add_folder)
        folder_row.addStretch(1)
        layout.addLayout(folder_row)

        self.folder_status = QLabel("")
        self.folder_status.setWordWrap(True)
        self.folder_status.setStyleSheet("color:#9aa0ab; font-size:11px;")
        layout.addWidget(self.folder_status)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Abbrechen")
        btn_cancel.clicked.connect(self.reject)
        ic, tx = themed("fa5s.check", "Übernehmen")
        btn_ok = QPushButton(ic, tx)
        btn_ok.clicked.connect(self._accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

    def _add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Ordner als Kontext hinzufügen")
        if not path:
            return

        collected = []
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIR_NAMES]
            for name in sorted(files):
                if name.endswith(".py"):
                    collected.append(os.path.join(root, name))
                    if len(collected) >= self.MAX_FOLDER_FILES:
                        break
            if len(collected) >= self.MAX_FOLDER_FILES:
                break

        added = 0
        for full_path in collected:
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue
            if len(content) > self.MAX_FILE_CHARS:
                content = content[: self.MAX_FILE_CHARS] + "\n# … (Datei gekürzt) …"
            rel = os.path.relpath(full_path, path)
            entry = {"label": rel, "path": full_path, "content": content}
            item = QListWidgetItem(f"{rel}  ({os.path.basename(path)}/)")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.list_widget.addItem(item)
            added += 1

        note = f"{added} Python-Datei(en) aus „{path}“ hinzugefügt."
        if len(collected) >= self.MAX_FOLDER_FILES:
            note += f" (auf {self.MAX_FOLDER_FILES} Dateien begrenzt)"
        self.folder_status.setText(note)

    def _accept(self):
        self.selected_files = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data:
                    self.selected_files.append(data)
        self.accept()


# ----------------------------------------------------------------------
# Gemini-Integration (gemini-3.5-flash)
# ----------------------------------------------------------------------
class GeminiWorker(QThread):
    finished_ok = pyqtSignal(str)
    finished_err = pyqtSignal(str)

    def __init__(self, api_key, prompt, model=GEMINI_MODEL, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.prompt = prompt
        self.model = model

    def run(self):
        try:
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent?key={self.api_key}"
            )
            payload = json.dumps(
                {"contents": [{"parts": [{"text": self.prompt}]}]}
            ).encode("utf-8")
            req = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            candidates = data.get("candidates") or []
            if not candidates:
                reason = data.get("promptFeedback", {}).get("blockReason", "Unbekannt")
                self.finished_err.emit(f"Keine Antwort erhalten (Grund: {reason}).")
                return
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            self.finished_ok.emit(text)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            self.finished_err.emit(f"HTTP-Fehler {e.code}:\n{body}")
        except urllib.error.URLError as e:
            self.finished_err.emit(f"Netzwerkfehler: {e.reason}")
        except Exception as e:
            self.finished_err.emit(str(e))


class GeminiPanel(QDockWidget):
    def __init__(self, get_editor_callable, list_open_files_callable=None, parent=None):
        super().__init__("Gemini AI", parent)
        self.setObjectName("GeminiPanel")
        self.get_editor = get_editor_callable
        self.list_open_files = list_open_files_callable
        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._worker = None
        self._current_mode = "chat"
        self._last_response_code = ""
        self.context_files = (
            []
        )  # [{"label","path","content"}, …] - zusätzlicher Kontext

        container = QWidget()
        v = QVBoxLayout(container)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API-Key:"))
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("Gemini API-Key")
        cfg = load_config()
        self.key_edit.setText(cfg.get("gemini_api_key", ""))
        self.key_edit.editingFinished.connect(self._save_key)
        key_row.addWidget(self.key_edit, 1)
        v.addLayout(key_row)

        v.addWidget(QLabel(f"Modell: {GEMINI_MODEL}"))

        # ---- Kontext-Management: mehrere offene Dateien / ein Ordner ----
        context_row = QHBoxLayout()
        ic, tx = themed("fa5s.paperclip", "Kontext wählen…", emoji_fallback="📎")
        self.btn_context = QPushButton(ic, tx)
        self.btn_context.setToolTip(
            "Offene Dateien und/oder einen ganzen Ordner als zusätzlichen "
            "Kontext für Gemini auswählen (z. B. um Zusammenhänge zwischen "
            "mehreren Dateien zu erklären)."
        )
        self.btn_context.clicked.connect(self._choose_context)
        ic, tx = themed("fa5s.times", "", emoji_fallback="✕")
        self.btn_context_clear = QPushButton(ic, tx)
        self.btn_context_clear.setToolTip("Kontext leeren")
        self.btn_context_clear.setFixedWidth(32)
        self.btn_context_clear.clicked.connect(self._clear_context)
        context_row.addWidget(self.btn_context, 1)
        context_row.addWidget(self.btn_context_clear)
        v.addLayout(context_row)

        self.context_label = QLabel("Kein zusätzlicher Kontext ausgewählt")
        self.context_label.setWordWrap(True)
        self.context_label.setStyleSheet("color:#9aa0ab; font-size:11px;")
        v.addWidget(self.context_label)

        btn_row = QHBoxLayout()
        ic, tx = themed("fa5s.search", "Erklären", emoji_fallback="🔍")
        self.btn_explain = QPushButton(ic, tx)
        ic, tx = themed("fa5s.wrench", "Verbessern", emoji_fallback="🛠")
        self.btn_fix = QPushButton(ic, tx)
        ic, tx = themed("fa5s.magic", "Generieren", emoji_fallback="✨")
        self.btn_gen = QPushButton(ic, tx)
        self.btn_explain.clicked.connect(lambda: self._ask("explain"))
        self.btn_fix.clicked.connect(lambda: self._ask("fix"))
        self.btn_gen.clicked.connect(lambda: self._ask("generate"))
        btn_row.addWidget(self.btn_explain)
        btn_row.addWidget(self.btn_fix)
        btn_row.addWidget(self.btn_gen)
        v.addLayout(btn_row)

        self.prompt_edit = QLineEdit()
        self.prompt_edit.setPlaceholderText(
            "Frage/Beschreibung eingeben, z. B. 'Erkläre, wie main.py und utils.py "
            "zusammenhängen' (Enter = Senden)"
        )
        self.prompt_edit.returnPressed.connect(lambda: self._ask("chat"))
        v.addWidget(self.prompt_edit)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#9aa0ab; font-size:11px;")
        v.addWidget(self.status_label)

        self.response_view = QTextBrowser()
        v.addWidget(self.response_view, 1)

        ic, tx = themed("fa5s.arrow-down", "In Editor einfügen", emoji_fallback="↧")
        self.btn_insert = QPushButton(ic, tx)
        self.btn_insert.clicked.connect(self._insert_into_editor)
        v.addWidget(self.btn_insert)

        self.setWidget(container)

    # ---------------- Kontext-Management ----------------
    def _choose_context(self):
        open_files = self.list_open_files() if self.list_open_files else []
        preselected = {f["path"] for f in self.context_files if f.get("path")}
        dialog = ContextSelectDialog(open_files, preselected, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.context_files = dialog.selected_files
            self._update_context_label()

    def _clear_context(self):
        self.context_files = []
        self._update_context_label()

    def _update_context_label(self):
        if not self.context_files:
            self.context_label.setText("Kein zusätzlicher Kontext ausgewählt")
            return
        names = ", ".join(f["label"] for f in self.context_files[:6])
        if len(self.context_files) > 6:
            names += f" … (+{len(self.context_files) - 6} weitere)"
        self.context_label.setText(
            f"📎 Kontext: {len(self.context_files)} Datei(en) – {names}"
        )

    def _context_preamble(self):
        """Baut einen Prompt-Abschnitt aus den gewählten Kontext-Dateien
        (mit einer Gesamtlängenbegrenzung, damit die Anfrage nicht ausufert)."""
        if not self.context_files:
            return ""
        char_limit = 120_000
        parts = [
            "Zusätzlicher Kontext - weitere Projektdateien (nur zur Einordnung):\n"
        ]
        total = 0
        omitted = 0
        for f in self.context_files:
            block = f"\n### Datei: {f['label']}\n```python\n{f['content']}\n```\n"
            if total + len(block) > char_limit:
                omitted += 1
                continue
            parts.append(block)
            total += len(block)
        if omitted:
            parts.append(
                f"\n[Hinweis: {omitted} weitere Kontext-Datei(en) wegen Längenbegrenzung ausgelassen.]\n"
            )
        parts.append("\n---\n")
        return "".join(parts)

    def _save_key(self):
        cfg = load_config()
        cfg["gemini_api_key"] = self.key_edit.text()
        save_config(cfg)

    def _selected_or_all_code(self):
        editor = self.get_editor()
        if not editor:
            return ""
        cursor = editor.textCursor()
        if cursor.hasSelection():
            return cursor.selectedText().replace("\u2029", "\n")
        return editor.toPlainText()

    def _ask(self, mode):
        api_key = self.key_edit.text().strip()
        if not api_key:
            QMessageBox.warning(
                self, "Gemini AI", "Bitte zuerst einen Gemini-API-Key eingeben."
            )
            return

        code_ctx = self._selected_or_all_code()
        user_prompt = self.prompt_edit.text().strip()
        context_block = self._context_preamble()

        if mode == "explain":
            if not code_ctx.strip():
                QMessageBox.information(
                    self, "Gemini AI", "Kein Code zum Erklären vorhanden."
                )
                return
            prompt = (
                context_block
                + "Erkläre folgenden Python-Code kurz, klar und auf Deutsch:\n\n"
                + code_ctx
            )
        elif mode == "fix":
            if not code_ctx.strip():
                QMessageBox.information(
                    self, "Gemini AI", "Kein Code zum Verbessern vorhanden."
                )
                return
            extra_note = (
                "Die obigen Kontext-Dateien dienen NUR zur Orientierung. "
                if context_block
                else ""
            )
            prompt = (
                context_block
                + "Verbessere/repariere folgenden Python-Code (Bugs, Stil, Lesbarkeit). "
                + extra_note
                + "Gib NUR den vollständigen, korrigierten Code dieser einen Datei zurück - keine "
                "Erklärung, keine Markdown-Codeblock-Markierungen:\n\n" + code_ctx
            )
        elif mode == "generate":
            if not user_prompt:
                QMessageBox.information(
                    self,
                    "Gemini AI",
                    "Bitte im Prompt-Feld beschreiben, was generiert werden soll.",
                )
                return
            extra_note = (
                "Die obigen Kontext-Dateien dienen NUR zur Orientierung. "
                if context_block
                else ""
            )
            prompt = (
                context_block
                + "Schreibe Python-Code für folgende Aufgabe. "
                + extra_note
                + "Gib NUR den Code zurück - keine "
                "Erklärung, keine Markdown-Codeblock-Markierungen. Aufgabe:\n\n"
                + user_prompt
            )
        else:  # chat
            if not user_prompt:
                return
            prompt = context_block + user_prompt
            if code_ctx.strip():
                prompt += "\n\nKontext (aktueller Code):\n" + code_ctx

        self._current_mode = mode
        self.status_label.setText("⏳ Gemini denkt nach…")
        self.response_view.setPlainText("")
        self._set_buttons_enabled(False)

        self._worker = GeminiWorker(api_key, prompt)
        self._worker.finished_ok.connect(self._on_ok)
        self._worker.finished_err.connect(self._on_err)
        self._worker.finished.connect(lambda: self._set_buttons_enabled(True))
        self._worker.start()

    def _set_buttons_enabled(self, enabled):
        for btn in (self.btn_explain, self.btn_fix, self.btn_gen):
            btn.setEnabled(enabled)

    def _on_ok(self, text):
        self.status_label.setText("✅ Antwort erhalten")
        cleaned = re.sub(r"^```[a-zA-Z]*\n?|```\s*$", "", text.strip())
        self._last_response_code = cleaned
        self.response_view.setPlainText(text)

    def _on_err(self, err):
        self.status_label.setText("❌ Fehler")
        self.response_view.setPlainText(err)

    def _insert_into_editor(self):
        editor = self.get_editor()
        if not editor or not self._last_response_code:
            return
        cursor = editor.textCursor()
        if self._current_mode == "fix":
            cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(self._last_response_code)
        editor.setTextCursor(cursor)


# ----------------------------------------------------------------------
# Hauptfenster
# ----------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 820)

        # Split-Screen: self.splitter enthält 1-2 "Panes" (QTabWidget),
        # jede Pane hat ihre eigenen Tabs für mehrere Dateien.
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)
        self.panes = []
        self.active_pane = None
        self.last_focused_editor = None
        first_pane = self._create_pane()
        self.splitter.addWidget(first_pane)

        QApplication.instance().focusChanged.connect(self._on_focus_changed)

        self.process = None

        self._create_output_dock()
        self._create_console_dock()
        self._create_problems_dock()
        self._create_project_panel()
        self._create_git_panel()
        self._create_gemini_panel()
        self._create_actions()
        self._create_menu()
        self._create_toolbar()
        self._create_status_bar()

        self.find_dialog = FindReplaceDialog(self.current_editor, self)

        self._open_startup_files()
        self.apply_dark_theme()

    def _open_startup_files(self):
        """Öffnet Dateien, die beim Start über die Kommandozeile übergeben
        wurden (z.B. durch Doppelklick auf eine Datei, wenn dieser Editor
        als Standardprogramm eingestellt ist). Fällt auf einen leeren Tab
        zurück, wenn keine gültige Datei übergeben wurde."""
        opened_any = False
        for arg in sys.argv[1:]:
            # Kommandozeilen-Flags wie "--foo" ignorieren
            if arg.startswith("-"):
                continue
            if os.path.isfile(arg):
                self.open_file_from_path(arg)
                opened_any = True
        if not opened_any:
            self.new_tab()

    # ---------------- Panes / Split-Screen ----------------
    def _create_pane(self):
        pane = QTabWidget()
        pane.setTabsClosable(True)
        pane.setMovable(True)
        pane.tabCloseRequested.connect(lambda idx, p=pane: self.close_tab(idx, p))
        pane.currentChanged.connect(self.update_status_bar)
        pane.currentChanged.connect(lambda _idx: self._refresh_problems_panel())
        self.panes.append(pane)
        self.active_pane = pane
        return pane

    def _remove_pane(self, pane):
        pane.setParent(None)
        if pane in self.panes:
            self.panes.remove(pane)
        pane.deleteLater()
        if self.active_pane is pane:
            self.active_pane = self.panes[0] if self.panes else None
        if (
            self.last_focused_editor is not None
            and getattr(self.last_focused_editor, "_pane", None) is pane
        ):
            self.last_focused_editor = None

    def _on_focus_changed(self, old, new):
        if isinstance(new, CodeEditor):
            self.last_focused_editor = new
            self.active_pane = getattr(new, "_pane", self.active_pane)
            self.update_status_bar()
            self._refresh_problems_panel()

    def target_pane(self):
        """Die Pane, in der neue/geöffnete Dateien landen sollen."""
        if self.active_pane in self.panes:
            return self.active_pane
        return self.panes[0] if self.panes else None

    def split_view(self, orientation):
        """Teilt die Ansicht (falls noch nicht geteilt) oder ändert die
        Ausrichtung einer bestehenden Teilung."""
        self.splitter.setOrientation(orientation)
        if len(self.panes) == 1:
            source = self.current_editor()
            new_pane = self._create_pane()
            self.splitter.addWidget(new_pane)
            self.splitter.setSizes([1, 1])
            if source is not None:
                self._duplicate_editor_into_pane(source, new_pane)
            else:
                self.new_tab(pane=new_pane)
        self.statusBar().showMessage("Ansicht geteilt", 2000)

    def _duplicate_editor_into_pane(self, source_editor, pane):
        """Öffnet dieselbe Datei (gleiches Dokument) in einer zweiten Pane,
        sodass beide Ansichten synchron bleiben (echter Split-View)."""
        editor = CodeEditor()
        editor.setDocument(source_editor.document())
        editor._file_path = source_editor._file_path
        editor._pane = pane
        self._attach_completer(editor)
        editor.document().modificationChanged.connect(
            lambda changed, e=editor: self.update_tab_title(e)
        )
        editor.cursorPositionChanged.connect(self.update_status_bar)
        editor.lintRequested.connect(lambda e=editor: self.lint_editor(e))
        title = (
            os.path.basename(editor._file_path) if editor._file_path else "Unbenannt"
        )
        index = pane.addTab(editor, title)
        pane.setCurrentIndex(index)
        editor.setFocus()
        self.lint_editor(editor)
        return editor

    def _create_pane_if_missing(self):
        if not self.panes:
            pane = self._create_pane()
            self.splitter.addWidget(pane)
            return pane
        return self.panes[0]

    def update_tab_title(self, editor):
        pane = getattr(editor, "_pane", None)
        if pane is None:
            return
        index = pane.indexOf(editor)
        if index == -1:
            return
        name = os.path.basename(editor._file_path) if editor._file_path else "Unbenannt"
        if editor.document().isModified():
            name += " •"
        pane.setTabText(index, name)

    def close_tab(self, index, pane=None):
        pane = pane or self.target_pane()
        if pane is None:
            return True
        editor = pane.widget(index)
        if isinstance(editor, CodeEditor) and editor.document().isModified():
            res = QMessageBox.question(
                self,
                APP_NAME,
                f"„{pane.tabText(index).rstrip(' •')}"
                + "“ enthält ungespeicherte Änderungen.\nTrotzdem schließen?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if res == QMessageBox.StandardButton.No:
                return False
        pane.removeTab(index)
        if pane.count() == 0:
            if len(self.panes) > 1:
                self._remove_pane(pane)
            else:
                self.new_tab(pane=pane)
        return True

    # ---------------- Autovervollständigung ----------------
    def _attach_completer(self, editor):
        completer = QCompleter()
        completer.setModel(QStringListModel(list(BASE_WORDLIST)))
        editor.set_completer(completer)

    # ---------------- Datei-Operationen ----------------
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "Python-Dateien (*.py);;Alle Dateien (*)"
        )
        if not path:
            return
        self.open_file_from_path(path)

    def open_file_from_path(self, path):
        if not os.path.isfile(path):
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            QMessageBox.warning(
                self, APP_NAME, f"Datei konnte nicht geöffnet werden:\n{e}"
            )
            return
        editor = self.new_tab(path=path, content=content)
        editor.document().setModified(False)
        self.update_tab_title(editor)
        self.git_panel.set_repo_path(path)

    def save_file(self):
        editor = self.current_editor()
        if not editor:
            return
        if not editor._file_path:
            self.save_file_as()
            return
        with open(editor._file_path, "w", encoding="utf-8") as f:
            f.write(editor.toPlainText())
        editor.document().setModified(False)
        self.update_tab_title(editor)
        self.statusBar().showMessage(f"Gespeichert: {editor._file_path}", 3000)

    def save_file_as(self):
        editor = self.current_editor()
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Speichern unter",
            "skript.py",
            "Python-Dateien (*.py);;Alle Dateien (*)",
        )
        if not path:
            return
        editor._file_path = path
        with open(path, "w", encoding="utf-8") as f:
            f.write(editor.toPlainText())
        editor.document().setModified(False)
        self.update_tab_title(editor)
        self.statusBar().showMessage(f"Gespeichert: {path}", 3000)
        if self.project_panel.project_root:
            self.project_panel.refresh()
        if self.git_panel.repo_root is None:
            self.git_panel.set_repo_path(path)

    # ---------------- Skript ausführen ----------------
    def _create_output_dock(self):
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 11))
        self.output_dock = QDockWidget("Ausgabe", self)
        self.output_dock.setObjectName("OutputDock")
        self.output_dock.setWidget(self.output)
        self.output_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.output_dock)

    def _create_console_dock(self):
        self.console = InteractiveConsole()
        self.console_dock = QDockWidget("Interaktive Konsole", self)
        self.console_dock.setObjectName("ConsoleDock")
        self.console_dock.setWidget(self.console)
        self.console_dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.console_dock)
        self.tabifyDockWidget(self.output_dock, self.console_dock)
        self.output_dock.raise_()

    def _create_project_panel(self):
        self.project_panel = ProjectPanel(self)
        self.project_panel.fileDoubleClicked.connect(self.open_file_from_path)
        self.project_panel.fileDoubleClicked.connect(
            lambda path: self.git_panel.set_repo_path(path)
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.project_panel)
        self.project_panel.visibilityChanged.connect(
            lambda _v: self._sync_sidebar_actions()
        )

    def _create_gemini_panel(self):
        self.gemini_panel = GeminiPanel(
            self.current_editor, self._all_open_documents, self
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.gemini_panel)
        self.gemini_panel.visibilityChanged.connect(
            lambda _v: self._sync_sidebar_actions()
        )

    def _all_open_documents(self):
        """Liefert {"label","path","content"} für jedes offene Dokument -
        einmalig, auch wenn dasselbe Dokument im Split-View mehrfach
        angezeigt wird. Dient als Auswahlgrundlage für den Gemini-Kontext."""
        seen_docs = set()
        result = []
        for pane in self.panes:
            for i in range(pane.count()):
                editor = pane.widget(i)
                if not isinstance(editor, CodeEditor):
                    continue
                doc_id = id(editor.document())
                if doc_id in seen_docs:
                    continue
                seen_docs.add(doc_id)
                label = (
                    os.path.basename(editor._file_path)
                    if editor._file_path
                    else pane.tabText(i).rstrip(" •")
                )
                result.append(
                    {
                        "label": label,
                        "path": editor._file_path,
                        "content": editor.toPlainText(),
                    }
                )
        return result

    # ---------------- Linting ----------------
    def _create_problems_dock(self):
        self.problems_panel = ProblemsPanel(self)
        self.problems_panel.setObjectName("ProblemsPanel")
        self.problems_panel.issueActivated.connect(self._go_to_problem)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.problems_panel)
        self.tabifyDockWidget(self.console_dock, self.problems_panel)
        self.output_dock.raise_()

    def lint_editor(self, editor):
        """Startet eine asynchrone Lint-Prüfung für den gegebenen Editor."""
        pane = getattr(editor, "_pane", None)
        if pane is None or pane.indexOf(editor) == -1:
            return
        source = editor.toPlainText()
        worker = LintWorker(source, editor._file_path, self)
        editor._lint_worker = worker  # Referenz halten, bis Ergebnis eintrifft
        worker.finished_lint.connect(
            lambda issues, e=editor: self._apply_lint_results(e, issues)
        )
        worker.start()

    def _apply_lint_results(self, editor, issues):
        editor.set_lint_issues(issues)
        if editor is self.current_editor():
            self._refresh_problems_panel()

    def _refresh_problems_panel(self):
        editor = self.current_editor()
        if editor is None:
            self.problems_panel.clear_issues()
            return
        label = (
            os.path.basename(editor._file_path) if editor._file_path else "Unbenannt"
        )
        self.problems_panel.show_issues(getattr(editor, "_lint_issues", []), label)

    def _go_to_problem(self, line, col):
        editor = self.current_editor()
        if not editor:
            return
        block = editor.document().findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        cursor.movePosition(
            QTextCursor.MoveOperation.Right,
            QTextCursor.MoveMode.MoveAnchor,
            min(max(0, col - 1), max(0, block.length() - 1)),
        )
        editor.setTextCursor(cursor)
        editor.setFocus()
        editor.centerCursor()

    # ---------------- Git ----------------
    def _create_git_panel(self):
        self.git_panel = GitPanel(
            self._show_git_output, self, on_repo_opened=self._open_cloned_repo
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.git_panel)
        self.tabifyDockWidget(self.project_panel, self.git_panel)
        self.project_panel.raise_()
        self.git_panel.visibilityChanged.connect(
            lambda _v: self._sync_sidebar_actions()
        )

    def _open_cloned_repo(self, path):
        """Wird nach erfolgreichem Klonen aufgerufen: öffnet den neuen
        Ordner im Projekt-Panel und verknüpft ihn direkt mit dem Git-Panel."""
        self.project_panel.open_folder(path)
        self.git_panel.set_repo_path(path)

    def _show_git_output(self, text):
        self.output.setPlainText(text)
        self.output_dock.show()
        self.output_dock.raise_()

    def _git_open_repo_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "Git-Repository wählen")
        if path:
            self.git_panel.set_repo_path(path)
            self.git_panel.show()
            self.git_panel.raise_()

    def _git_focus_commit(self):
        self.git_panel.show()
        self.git_panel.raise_()
        self.git_panel.commit_edit.setFocus()

    def load_current_script_into_console(self):
        editor = self.current_editor()
        if not editor:
            return
        if editor.document().isModified() or not editor._file_path:
            self.save_file()
            if not editor._file_path:
                return
        self.console_dock.show()
        self.console_dock.raise_()
        self.console.load_script_into_namespace(editor._file_path)

    def run_script(self):
        editor = self.current_editor()
        if not editor:
            return

        if editor.document().isModified() or not editor._file_path:
            self.save_file()
            if not editor._file_path:
                return

        self.output.clear()
        self.output_dock.show()
        self.output_dock.raise_()
        self.output.appendPlainText(f'$ python "{editor._file_path}"\n')

        if self.process is not None:
            self.process.kill()

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.finished.connect(self._process_finished)
        self.process.start(sys.executable, ["-u", editor._file_path])

    def _read_process_output(self):
        data = (
            self.process.readAllStandardOutput()
            .data()
            .decode("utf-8", errors="replace")
        )
        self.output.moveCursor(QTextCursor.MoveOperation.End)
        self.output.insertPlainText(data)
        self.output.moveCursor(QTextCursor.MoveOperation.End)

    def _process_finished(self, exit_code, _status):
        self.output.appendPlainText(f"\n[Prozess beendet mit Code {exit_code}]")

    def stop_script(self):
        if (
            self.process is not None
            and self.process.state() != QProcess.ProcessState.NotRunning
        ):
            self.process.kill()
            self.output.appendPlainText("\n[Vom Benutzer abgebrochen]")

    # ---------------- Tabs / Editor-Verwaltung ----------------
    def current_editor(self):
        if self.last_focused_editor is not None:
            pane = getattr(self.last_focused_editor, "_pane", None)
            if pane in self.panes and pane.indexOf(self.last_focused_editor) != -1:
                return self.last_focused_editor
        pane = self.target_pane()
        if pane is None:
            return None
        widget = pane.currentWidget()
        return widget if isinstance(widget, CodeEditor) else None

    def new_tab(self, path=None, content="", pane=None):
        pane = pane or self.target_pane() or self._create_pane_if_missing()
        editor = CodeEditor()
        self._attach_completer(editor)
        editor.setPlainText(content)
        highlighter = PythonHighlighter(editor.document())
        editor._highlighter = highlighter
        editor._file_path = path
        editor._pane = pane
        editor.document().modificationChanged.connect(
            lambda changed, e=editor: self.update_tab_title(e)
        )
        editor.cursorPositionChanged.connect(self.update_status_bar)
        editor.lintRequested.connect(lambda e=editor: self.lint_editor(e))

        title = os.path.basename(path) if path else "Unbenannt"
        index = pane.addTab(editor, title)
        pane.setCurrentIndex(index)
        editor.setFocus()
        self.lint_editor(editor)
        return editor

    # ---------------- Aktionen / Menü / Toolbar ----------------
    def _create_actions(self):
        ic, tx = themed("fa5s.file", "&New")
        self.act_new = QAction(
            ic, tx, self, shortcut=QKeySequence.StandardKey.New, triggered=self.new_tab
        )
        ic, tx = themed("fa5s.folder-open", "&Open…")
        self.act_open = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Open,
            triggered=self.open_file,
        )
        ic, tx = themed("fa5s.save", "&Save")
        self.act_save = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Save,
            triggered=self.save_file,
        )
        ic, tx = themed("fa5s.file-export", "Save &as…")
        self.act_save_as = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.SaveAs,
            triggered=self.save_file_as,
        )
        ic, tx = themed("fa5s.times", "Close Tab")
        self.act_close_tab = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Close,
            triggered=self._close_current_tab,
        )
        ic, tx = themed("fa5s.sign-out-alt", "&Exit")
        self.act_exit = QAction(
            ic, tx, self, shortcut=QKeySequence.StandardKey.Quit, triggered=self.close
        )

        ic, tx = themed("fa5s.undo", "Undo")
        self.act_undo = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Undo,
            triggered=lambda: self.current_editor() and self.current_editor().undo(),
        )
        ic, tx = themed("fa5s.redo", "Repeat")
        self.act_redo = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Redo,
            triggered=lambda: self.current_editor() and self.current_editor().redo(),
        )
        ic, tx = themed("fa5s.cut", "Cut")
        self.act_cut = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Cut,
            triggered=lambda: self.current_editor() and self.current_editor().cut(),
        )
        ic, tx = themed("fa5s.copy", "Copy")
        self.act_copy = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Copy,
            triggered=lambda: self.current_editor() and self.current_editor().copy(),
        )
        ic, tx = themed("fa5s.paste", "Paste")
        self.act_paste = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Paste,
            triggered=lambda: self.current_editor() and self.current_editor().paste(),
        )
        ic, tx = themed("fa5s.search", "&Serach/Replace…")
        self.act_find = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.Find,
            triggered=self.show_find_dialog,
        )
        ic, tx = themed("fa5s.magic", "Show suggestion")
        self.act_complete = QAction(
            ic, tx, self, shortcut="Ctrl+Space", triggered=self._trigger_completion
        )

        ic, tx = themed("fa5s.play", "Run", emoji_fallback="▶", color="#89d185")
        self.act_run = QAction(ic, tx, self, shortcut="F5", triggered=self.run_script)
        ic, tx = themed("fa5s.stop", "Stop", emoji_fallback="■", color="#f14c4c")
        self.act_stop = QAction(
            ic, tx, self, shortcut="Shift+F5", triggered=self.stop_script
        )
        ic, tx = themed("fa5s.terminal", "Load in Terminal")
        self.act_load_console = QAction(
            ic,
            tx,
            self,
            shortcut="Ctrl+F5",
            triggered=self.load_current_script_into_console,
        )

        ic, tx = themed("fa5s.search-plus", "Zoom IN")
        self.act_zoom_in = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.ZoomIn,
            triggered=lambda: self.current_editor() and self.current_editor().zoom(1),
        )
        ic, tx = themed("fa5s.search-minus", "Zoom OUT")
        self.act_zoom_out = QAction(
            ic,
            tx,
            self,
            shortcut=QKeySequence.StandardKey.ZoomOut,
            triggered=lambda: self.current_editor() and self.current_editor().zoom(-1),
        )
        ic, tx = themed("fa5s.font", "Font…")
        self.act_font = QAction(ic, tx, self, triggered=self.choose_font)

        ic, tx = themed("fa5s.columns", "Split Vertical")
        self.act_split_h = QAction(
            ic,
            tx,
            self,
            shortcut="Ctrl+\\",
            triggered=lambda: self.split_view(Qt.Orientation.Horizontal),
        )
        ic, tx = themed("fa5s.grip-lines", "Split Horizontal")
        self.act_split_v = QAction(
            ic,
            tx,
            self,
            shortcut="Ctrl+Shift+\\",
            triggered=lambda: self.split_view(Qt.Orientation.Vertical),
        )

        ic, tx = themed("fa5s.folder-plus", "Open Project…")
        self.act_open_project = QAction(
            ic,
            tx,
            self,
            shortcut="Ctrl+K, Ctrl+O",
            triggered=lambda: self.project_panel.open_folder(),
        )

        ic, tx = themed("fa5s.check-double", "Start Debug")
        self.act_lint_now = QAction(
            ic,
            tx,
            self,
            shortcut="Ctrl+Shift+M",
            triggered=lambda: self.current_editor()
            and self.lint_editor(self.current_editor()),
        )

        ic, tx = themed("fa5s.code-branch", "Open Repo…")
        self.act_git_open = QAction(ic, tx, self, triggered=self._git_open_repo_dialog)
        ic, tx = themed("fa5s.sync", "Status aktualisieren")
        self.act_git_refresh = QAction(
            ic,
            tx,
            self,
            shortcut="Ctrl+Shift+G",
            triggered=lambda: self.git_panel.refresh(),
        )
        ic, tx = themed("fa5s.check", "Commit…")
        self.act_git_commit = QAction(ic, tx, self, triggered=self._git_focus_commit)
        ic, tx = themed("fa5s.arrow-up", "Push")
        self.act_git_push = QAction(
            ic, tx, self, triggered=lambda: self.git_panel._run("push", ["push"])
        )
        ic, tx = themed("fa5s.arrow-down", "Pull")
        self.act_git_pull = QAction(
            ic, tx, self, triggered=lambda: self.git_panel._run("pull", ["pull"])
        )

        ic, tx = themed("fa5s.key", "Zugangsdaten ändern…", "🔑")
        self.act_change_credentials = QAction(
            ic, tx, self, triggered=self.change_login_credentials
        )
        self.act_change_credentials.setToolTip(
            "Benutzername/Passwort für den Login-Bildschirm ändern"
        )

        ic, tx = themed("fa5s.info-circle", "Über " + APP_NAME)
        self.act_about = QAction(ic, tx, self, triggered=self.show_about)

        # -- Externe Pandora-Tools (JSON/YAML- & SQL-Config-Editor) --
        ic, tx = themed("fa5s.file-code", "JSON/YAML-Editor", "🗂")
        self.act_tool_json_yaml = QAction(
            ic, tx, self, triggered=self.launch_json_yaml_editor
        )
        self.act_tool_json_yaml.setToolTip("Pandora JSON/YAML Config Editor öffnen")

        ic, tx = themed("fa5s.database", "SQL-Config-Editor", "🗄")
        self.act_tool_sql_config = QAction(
            ic, tx, self, triggered=self.launch_sql_config_editor
        )
        self.act_tool_sql_config.setToolTip(
            "Pandora SQL Config Editor & Validator öffnen"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (JSON/YAML-Editor)…")
        self.act_tool_json_yaml_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_json_yaml_editor(force_repath=True),
        )
        ic, tx = themed("fa5s.edit", "Pfad ändern (SQL-Config-Editor)…")
        self.act_tool_sql_config_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_sql_config_editor(force_repath=True),
        )

        ic, tx = themed("fa5s.globe", "Web-Editor (HTML/CSS/JS)", "🌐")
        self.act_tool_web_editor = QAction(
            ic, tx, self, triggered=self.launch_web_editor
        )
        self.act_tool_web_editor.setToolTip(
            "Pandora Web Editor öffnen (HTML/CSS/JS mit Live-Vorschau)"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (Web-Editor)…")
        self.act_tool_web_editor_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_web_editor(force_repath=True),
        )

        ic, tx = themed("fa5s.key", "Crypto & Encoding Utility", "🔐")
        self.act_tool_crypto = QAction(
            ic, tx, self, triggered=self.launch_crypto_tool
        )
        self.act_tool_crypto.setToolTip(
            "Pandora Crypto & Encoding Utility öffnen (Base64/Hex/URL/HTML, "
            "Hash & HMAC, JWT-Inspector, RegEx-Tester)"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (Crypto & Encoding Utility)…")
        self.act_tool_crypto_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_crypto_tool(force_repath=True),
        )

        ic, tx = themed("fa5s.palette", "UI Asset & Color Studio", "🎨")
        self.act_tool_ui_asset_color_studio = QAction(
            ic, tx, self, triggered=self.launch_ui_asset_color_studio
        )
        self.act_tool_ui_asset_color_studio.setToolTip(
            "Pandora UI Asset & Color Studio öffnen (Farb-Picker & Konverter, "
            "Theming-Variablen-Manager, Icon & Asset Browser)"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (UI Asset & Color Studio)…")
        self.act_tool_ui_asset_color_studio_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_ui_asset_color_studio(force_repath=True),
        )

        ic, tx = themed("fa5s.drafting-compass", "UI Forge", "🎛️")
        self.act_tool_ui_forge = QAction(
            ic, tx, self, triggered=self.launch_ui_forge
        )
        self.act_tool_ui_forge.setToolTip(
            "Pandora UI Forge öffnen (visueller PyQt6 Design-Editor: Canvas "
            "mit Drag & Drop, synchroner Code-Editor, AST-Import bestehender "
            ".py-Dateien, Live-Vorschau)"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (UI Forge)…")
        self.act_tool_ui_forge_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_ui_forge(force_repath=True),
        )

        ic, tx = themed("fa5s.file-alt", "MD Editor", "📝")
        self.act_tool_md_editor = QAction(
            ic, tx, self, triggered=self.launch_md_editor
        )
        self.act_tool_md_editor.setToolTip(
            "Pandora MD Editor öffnen (Split-Screen Markdown-Editor mit "
            "Live-Vorschau, Syntax-Highlighting und PDF-Export)"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (MD Editor)…")
        self.act_tool_md_editor_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_md_editor(force_repath=True),
        )

        ic, tx = themed("fa5s.sitemap", "Structure Creator", "🗂️")
        self.act_tool_structure_creator = QAction(
            ic, tx, self, triggered=self.launch_structure_creator
        )
        self.act_tool_structure_creator.setToolTip(
            "Pandora Structure Creator öffnen (Ordner-/Dateistrukturen aus "
            "einer Baum-Textvorlage an frei wählbarem Zielort erzeugen)"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (Structure Creator)…")
        self.act_tool_structure_creator_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_structure_creator(force_repath=True),
        )

        ic, tx = themed("fa5s.cubes", "Environment & Dependency Manager", "📦")
        self.act_tool_env_dependency_manager = QAction(
            ic, tx, self, triggered=self.launch_env_dependency_manager
        )
        self.act_tool_env_dependency_manager.setToolTip(
            "Pandora Environment & Dependency Manager öffnen (Virtualenv "
            "Control, Package Installer für pip/npm, Abhängigkeits-Übersicht)"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (Environment & Dependency Manager)…")
        self.act_tool_env_dependency_manager_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_env_dependency_manager(force_repath=True),
        )

        ic, tx = themed("fa5s.microchip", "PCB Editor", "🖧")
        self.act_tool_pcb_editor = QAction(
            ic, tx, self, triggered=self.launch_pcb_editor
        )
        self.act_tool_pcb_editor.setToolTip(
            "Pandora PCB Editor öffnen (Leiterplatten-Layout, Gerber-/Excellon-"
            "Export, 3D-Vorschau)"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (PCB Editor)…")
        self.act_tool_pcb_editor_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.launch_pcb_editor(force_repath=True),
        )

        # -- Code Snippet Vault: läuft NICHT als externer Prozess, sondern
        # wird per importlib direkt in diesen Prozess geladen, damit Quick-
        # Insert Text an der Cursor-Position des aktiven Editors einfügen
        # kann (siehe launch_web_editor/launch_json_yaml_editor oben für
        # den Kontrast: die starten jeweils ein eigenes, unabhängiges
        # Fenster als Subprozess).
        ic, tx = themed("fa5s.magic", "Code Snippet Vault…", "🧩")
        self.act_tool_snippet_vault = QAction(
            ic, tx, self, triggered=self.open_snippet_vault
        )
        self.act_tool_snippet_vault.setToolTip(
            "Pandora Code Snippet Vault öffnen (Bibliothek durchsuchen/verwalten)"
        )

        ic, tx = themed("fa5s.bolt", "Schnell-Einfügen (Snippet)…", "⚡")
        self.act_tool_snippet_quick_insert = QAction(
            ic, tx, self, shortcut="Ctrl+Alt+I", triggered=self.quick_insert_snippet
        )
        self.act_tool_snippet_quick_insert.setToolTip(
            "Snippet per Schnellsuche direkt an der Cursor-Position einfügen"
        )

        ic, tx = themed("fa5s.edit", "Pfad ändern (Snippet Vault)…")
        self.act_tool_snippet_vault_repath = QAction(
            ic,
            tx,
            self,
            triggered=lambda: self.open_snippet_vault(force_repath=True),
        )

        ic, tx = themed("fa5s.angle-double-left", "Project show-/hide")
        self.act_toggle_left_sidebar = QAction(
            ic, tx, self, shortcut="Ctrl+B", checkable=True
        )
        self.act_toggle_left_sidebar.setChecked(True)
        self.act_toggle_left_sidebar.toggled.connect(self._toggle_left_sidebar)

        ic, tx = themed("fa5s.angle-double-right", "AI show-/hide")
        self.act_toggle_right_sidebar = QAction(
            ic, tx, self, shortcut="Ctrl+Alt+B", checkable=True
        )
        self.act_toggle_right_sidebar.setChecked(True)
        self.act_toggle_right_sidebar.toggled.connect(self._toggle_right_sidebar)

    def _trigger_completion(self):
        editor = self.current_editor()
        if editor:
            editor.setFocus()

    def _toggle_left_sidebar(self, visible):
        """Blendet die linke Seitenleiste (Projekt- + Git-Panel, als
        Tab-Gruppe zusammengefasst) komplett ein oder aus."""
        self.project_panel.setVisible(visible)
        self.git_panel.setVisible(visible)

    def _toggle_right_sidebar(self, visible):
        """Blendet die rechte Seitenleiste (Gemini-Panel) ein oder aus."""
        self.gemini_panel.setVisible(visible)

    def _sync_sidebar_actions(self):
        """Hält die Toolbar/Menü-Toggle-Buttons synchron, falls Panels
        auf andere Weise (X-Button, toggleViewAction im Menü) geschlossen
        oder wieder geöffnet werden."""
        left_visible = self.project_panel.isVisible() or self.git_panel.isVisible()
        if self.act_toggle_left_sidebar.isChecked() != left_visible:
            self.act_toggle_left_sidebar.blockSignals(True)
            self.act_toggle_left_sidebar.setChecked(left_visible)
            self.act_toggle_left_sidebar.blockSignals(False)

        right_visible = self.gemini_panel.isVisible()
        if self.act_toggle_right_sidebar.isChecked() != right_visible:
            self.act_toggle_right_sidebar.blockSignals(True)
            self.act_toggle_right_sidebar.setChecked(right_visible)
            self.act_toggle_right_sidebar.blockSignals(False)

    def _close_current_tab(self):
        pane = self.target_pane()
        if pane is not None:
            self.close_tab(pane.currentIndex(), pane)

    def _create_menu(self):
        menu = self.menuBar()

        m_file = menu.addMenu("&Datei")
        m_file.addAction(self.act_new)
        m_file.addAction(self.act_open)
        m_file.addAction(self.act_save)
        m_file.addAction(self.act_save_as)
        m_file.addSeparator()
        m_file.addAction(self.act_close_tab)
        m_file.addSeparator()
        m_file.addAction(self.act_exit)

        m_edit = menu.addMenu("&Bearbeiten")
        m_edit.addAction(self.act_undo)
        m_edit.addAction(self.act_redo)
        m_edit.addSeparator()
        m_edit.addAction(self.act_cut)
        m_edit.addAction(self.act_copy)
        m_edit.addAction(self.act_paste)
        m_edit.addSeparator()
        m_edit.addAction(self.act_find)
        m_edit.addAction(self.act_complete)
        m_edit.addSeparator()
        m_edit.addAction(self.act_tool_snippet_quick_insert)

        m_project = menu.addMenu("&Projekt")
        m_project.addAction(self.act_open_project)
        m_project.addAction(self.project_panel.toggleViewAction())

        m_lint = menu.addMenu("&Linting")
        m_lint.addAction(self.act_lint_now)
        m_lint.addAction(self.problems_panel.toggleViewAction())
        pyflakes_status = (
            "aktiv" if HAVE_PYFLAKES else "nicht installiert (nur Syntaxprüfung)"
        )
        m_lint.addSeparator()
        act_lint_info = QAction(f"pyflakes: {pyflakes_status}", self)
        act_lint_info.setEnabled(False)
        m_lint.addAction(act_lint_info)

        m_git = menu.addMenu("&Git")
        m_git.addAction(self.act_git_open)
        m_git.addAction(self.act_git_refresh)
        m_git.addSeparator()
        m_git.addAction(self.act_git_commit)
        m_git.addAction(self.act_git_push)
        m_git.addAction(self.act_git_pull)
        m_git.addSeparator()
        m_git.addAction(self.git_panel.toggleViewAction())

        m_view = menu.addMenu("&Ansicht")
        m_view.addAction(self.act_toggle_left_sidebar)
        m_view.addAction(self.act_toggle_right_sidebar)
        m_view.addSeparator()
        m_view.addAction(self.act_zoom_in)
        m_view.addAction(self.act_zoom_out)
        m_view.addAction(self.act_font)
        m_view.addSeparator()
        m_view.addAction(self.act_split_h)
        m_view.addAction(self.act_split_v)
        m_view.addSeparator()
        m_view.addAction(self.output_dock.toggleViewAction())
        m_view.addAction(self.console_dock.toggleViewAction())
        m_view.addAction(self.gemini_panel.toggleViewAction())

        m_run = menu.addMenu("&Ausführen")
        m_run.addAction(self.act_run)
        m_run.addAction(self.act_stop)
        m_run.addSeparator()
        m_run.addAction(self.act_load_console)

        m_tools = menu.addMenu("&Werkzeuge")
        m_tools.addAction(self.act_tool_json_yaml)
        m_tools.addAction(self.act_tool_sql_config)
        m_tools.addAction(self.act_tool_web_editor)
        m_tools.addAction(self.act_tool_crypto)
        m_tools.addAction(self.act_tool_ui_asset_color_studio)
        m_tools.addAction(self.act_tool_ui_forge)
        m_tools.addAction(self.act_tool_md_editor)
        m_tools.addAction(self.act_tool_structure_creator)
        m_tools.addAction(self.act_tool_env_dependency_manager)
        m_tools.addAction(self.act_tool_pcb_editor)
        m_tools.addSeparator()
        m_tools.addAction(self.act_tool_snippet_vault)
        m_tools.addAction(self.act_tool_snippet_quick_insert)

        m_settings = menu.addMenu("&Einstellungen")
        m_settings.addAction(self.act_change_credentials)

        m_help = menu.addMenu("&Hilfe")
        m_help.addAction(self.act_about)
        m_help.addSeparator()
        m_tool_paths = m_help.addMenu("Werkzeug-Pfade ändern")
        m_tool_paths.addAction(self.act_tool_json_yaml_repath)
        m_tool_paths.addAction(self.act_tool_sql_config_repath)
        m_tool_paths.addAction(self.act_tool_web_editor_repath)
        m_tool_paths.addAction(self.act_tool_crypto_repath)
        m_tool_paths.addAction(self.act_tool_ui_asset_color_studio_repath)
        m_tool_paths.addAction(self.act_tool_ui_forge_repath)
        m_tool_paths.addAction(self.act_tool_md_editor_repath)
        m_tool_paths.addAction(self.act_tool_structure_creator_repath)
        m_tool_paths.addAction(self.act_tool_env_dependency_manager_repath)
        m_tool_paths.addAction(self.act_tool_pcb_editor_repath)
        m_tool_paths.addAction(self.act_tool_snippet_vault_repath)

    def _create_toolbar(self):
        tb = QToolBar("Werkzeugleiste")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        tb.addAction(self.act_new)
        tb.addAction(self.act_open)
        tb.addAction(self.act_save)
        tb.addSeparator()
        tb.addAction(self.act_toggle_left_sidebar)
        tb.addAction(self.act_toggle_right_sidebar)
        tb.addSeparator()
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()
        tb.addAction(self.act_find)
        tb.addSeparator()
        tb.addAction(self.act_open_project)
        tb.addSeparator()
        tb.addAction(self.act_split_h)
        tb.addAction(self.act_split_v)
        tb.addSeparator()
        tb.addAction(self.act_run)
        tb.addAction(self.act_stop)
        tb.addAction(self.act_load_console)
        tb.addSeparator()
        tb.addAction(self.act_tool_json_yaml)
        tb.addAction(self.act_tool_sql_config)
        tb.addAction(self.act_tool_web_editor)
        tb.addAction(self.act_tool_crypto)
        tb.addAction(self.act_tool_ui_asset_color_studio)
        tb.addAction(self.act_tool_env_dependency_manager)
        tb.addAction(self.act_tool_pcb_editor)
        tb.addSeparator()
        tb.addAction(self.act_tool_snippet_vault)
        tb.addAction(self.act_tool_snippet_quick_insert)

    def _create_status_bar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_position = QLabel("Zeile 1, Spalte 1")
        self.lbl_path = QLabel("Unbenannt")
        completion_hint = "Jedi aktiv" if HAVE_JEDI else "Wortvervollständigung"
        self.lbl_completion = QLabel(completion_hint)
        self.status.addPermanentWidget(self.lbl_path, 1)
        self.status.addPermanentWidget(self.lbl_completion)
        self.status.addPermanentWidget(self.lbl_position)

    def update_status_bar(self):
        editor = self.current_editor()
        if not editor:
            return
        cursor = editor.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.columnNumber() + 1
        self.lbl_position.setText(f"Zeile {line}, Spalte {col}")
        self.lbl_path.setText(editor._file_path or "Unbenannt")

    # ---------------- Dialoge ----------------
    def show_find_dialog(self):
        self.find_dialog.editor_getter = self.current_editor
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.activateWindow()

    def choose_font(self):
        editor = self.current_editor()
        if not editor:
            return
        font, ok = QFontDialog.getFont(editor.font(), self)
        if ok:
            for pane in self.panes:
                for i in range(pane.count()):
                    w = pane.widget(i)
                    if isinstance(w, CodeEditor):
                        w.setFont(font)

    # ---------------- Externe Pandora-Tools ----------------
    def _resolve_tool_path(
        self, cfg_key, dialog_title, name_filter, force_repath=False
    ):
        """Ermittelt den Pfad zum Einstiegs-Skript eines externen Pandora-Tools.
        Liest ihn (falls vorhanden) aus der Config, oder fragt den Benutzer
        einmalig über einen Dateidialog und merkt sich die Auswahl dauerhaft.
        Mit force_repath=True wird immer neu nachgefragt (z.B. wenn das Tool
        verschoben wurde)."""
        cfg = load_config()
        path = cfg.get(cfg_key)
        if not force_repath and path and os.path.isfile(path):
            return path

        start_dir = os.path.dirname(path) if path else os.path.expanduser("~")
        chosen, _ = QFileDialog.getOpenFileName(
            self, dialog_title, start_dir, name_filter
        )
        if not chosen:
            return None
        cfg[cfg_key] = chosen
        save_config(cfg)
        return chosen

    def _launch_external_tool(self, script_path, extra_args=None, friendly_name="Tool"):
        """Startet ein externes Pandora-Tool als eigenständigen Prozess (eigene
        QApplication), damit es unabhängig vom Script Editor läuft und es
        keine Namenskonflikte mit dessen Klassen gibt (z.B. eigene
        'MainWindow'-Klassen).

        Unterstützt zwei Arten von Einstiegspunkten:
        - Python-Quellskript (*.py)   -> wird mit demselben Interpreter
          gestartet, der auch den Script Editor ausführt (sys.executable).
        - Eigenständiges Programm/Build (*.exe unter Windows, oder eine
          ausführbare Datei ohne Endung unter Linux/macOS, z.B. das
          Ergebnis eines PyInstaller-`--onedir`-Builds) -> wird direkt
          ausgeführt, ohne Python-Interpreter davor."""
        is_python_script = script_path.lower().endswith(".py")
        try:
            if is_python_script:
                args = [sys.executable, script_path] + list(extra_args or [])
            else:
                if os.name != "nt" and not os.access(script_path, os.X_OK):
                    QMessageBox.critical(
                        self,
                        f"{friendly_name} konnte nicht gestartet werden",
                        f"Die Datei ist nicht ausführbar:\n{script_path}\n\n"
                        f"Unter Linux/macOS ggf. per\n"
                        f"    chmod +x \"{script_path}\"\n"
                        f"ausführbar machen.",
                    )
                    return
                args = [script_path] + list(extra_args or [])
            subprocess.Popen(args, cwd=os.path.dirname(script_path) or None)
            self.statusBar().showMessage(f"{friendly_name} gestartet…", 3000)
        except Exception as e:
            QMessageBox.critical(
                self,
                f"{friendly_name} konnte nicht gestartet werden",
                f"Fehler beim Start:\n{e}",
            )

    def launch_json_yaml_editor(self, force_repath=False):
        """Öffnet den Pandora JSON/YAML Config Editor. Ist gerade eine
        .json/.yaml/.yml-Datei im Editor aktiv, wird sie direkt mitgegeben."""
        path = self._resolve_tool_path(
            CFG_KEY_JSON_YAML_EDITOR,
            "Pandora JSON/YAML Editor auswählen (pandora_config_editor.py)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return

        extra_args = []
        editor = self.current_editor()
        if editor is not None and getattr(editor, "_file_path", None):
            ext = os.path.splitext(editor._file_path)[1].lower()
            if ext in (".json", ".yaml", ".yml"):
                extra_args.append(editor._file_path)

        self._launch_external_tool(path, extra_args, "Pandora JSON/YAML Editor")

    def launch_sql_config_editor(self, force_repath=False):
        """Öffnet den Pandora SQL Config Editor & Validator (main.py des
        pandora_sql_config_editor-Pakets)."""
        path = self._resolve_tool_path(
            CFG_KEY_SQL_CONFIG_EDITOR,
            "main.py des Pandora SQL Config Editors auswählen",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return
        self._launch_external_tool(path, friendly_name="Pandora SQL Config Editor")

    def launch_web_editor(self, force_repath=False):
        """Öffnet den Pandora Web Editor (HTML/CSS/JS mit Live-Vorschau).
        Ist gerade eine .html/.htm-Datei im Editor aktiv, wird sie direkt
        mitgegeben."""
        path = self._resolve_tool_path(
            CFG_KEY_WEB_EDITOR,
            "Pandora Web Editor auswählen (pandora_web_editor.py)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return

        extra_args = []
        editor = self.current_editor()
        if editor is not None and getattr(editor, "_file_path", None):
            file_path = editor._file_path
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".html", ".htm"):
                extra_args.append(file_path)

        self._launch_external_tool(path, extra_args, "Pandora Web Editor")

    def launch_crypto_tool(self, force_repath=False):
        """Öffnet das Pandora Crypto & Encoding Utility (Base64/Hex/URL/
        HTML-Encoder, Hash- & HMAC-Generator, JWT-Inspector, RegEx-Tester).
        Läuft wie der SQL Config Editor als eigenständiger Prozess, da es
        keinen Bezug zu einem bestimmten Dateityp im aktiven Editor hat."""
        path = self._resolve_tool_path(
            CFG_KEY_CRYPTO_TOOL,
            "pandora_crypto_tool.py auswählen (Pandora Crypto & Encoding Utility)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return
        self._launch_external_tool(path, friendly_name="Pandora Crypto & Encoding Utility")

    def launch_ui_asset_color_studio(self, force_repath=False):
        """Öffnet das Pandora UI Asset & Color Studio (Farb-Picker &
        Konverter, Theming-Variablen-Manager, Icon & Asset Browser). Läuft
        wie der SQL Config Editor als eigenständiger Prozess, da es keinen
        Bezug zu einem bestimmten Dateityp im aktiven Editor hat."""
        path = self._resolve_tool_path(
            CFG_KEY_UI_ASSET_COLOR_STUDIO,
            "pandora_ui_asset_color_studio.py auswählen (Pandora UI Asset & Color Studio)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return
        self._launch_external_tool(path, friendly_name="Pandora UI Asset & Color Studio")

    def launch_ui_forge(self, force_repath=False):
        """Öffnet die Pandora UI Forge (visueller PyQt6 Design-Editor mit
        Drag&Drop-Canvas, Live-Code-Generator und AST-Import bestehender
        .py-Dateien). Läuft wie die anderen Werkzeuge als eigenständiger
        Prozess, da es sich um eine vollständig eigenständige PyQt6-
        Anwendung (eigene MainWindow-Klasse) handelt. Ist gerade eine
        .py-Datei im Editor aktiv, wird sie direkt mitgegeben und in
        UI Forge automatisch geöffnet/analysiert."""
        path = self._resolve_tool_path(
            CFG_KEY_UI_FORGE,
            "pandora_ui_forge.py auswählen (Pandora UI Forge)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return

        extra_args = []
        editor = self.current_editor()
        if editor is not None and getattr(editor, "_file_path", None):
            file_path = editor._file_path
            if os.path.splitext(file_path)[1].lower() == ".py":
                extra_args.append(file_path)

        self._launch_external_tool(path, extra_args, "Pandora UI Forge")

    def launch_md_editor(self, force_repath=False):
        """Öffnet den Pandora MD Editor (Split-Screen Markdown-Editor mit
        Live-Vorschau, Syntax-Highlighting und PDF-Export). Ist gerade eine
        .md/.markdown-Datei im Editor aktiv, wird sie direkt mitgegeben.
        Läuft wie die anderen Werkzeuge als eigenständiger Prozess, da es
        sich um eine vollständig eigenständige PyQt6-Anwendung (eigene
        MainWindow-Klasse) handelt."""
        path = self._resolve_tool_path(
            CFG_KEY_MD_EDITOR,
            "main.py des Pandora MD Editors auswählen (pandora_md_editor)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return

        extra_args = []
        editor = self.current_editor()
        if editor is not None and getattr(editor, "_file_path", None):
            file_path = editor._file_path
            ext = os.path.splitext(file_path)[1].lower()
            if ext in (".md", ".markdown"):
                extra_args.append(file_path)

        self._launch_external_tool(path, extra_args, "Pandora MD Editor")

    def launch_structure_creator(self, force_repath=False):
        """Öffnet den Pandora Structure Creator (erzeugt Ordner-/Datei-
        strukturen aus einer Baum-Textvorlage an frei wählbarem Zielort).
        Läuft wie die anderen Werkzeuge als eigenständiger Prozess, da es
        sich um eine vollständig eigenständige PyQt6-Anwendung (eigene
        MainWindow-Klasse) handelt."""
        path = self._resolve_tool_path(
            CFG_KEY_STRUCTURE_CREATOR,
            "main.py des Pandora Structure Creators auswählen (PandoraStructureCreator)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return
        self._launch_external_tool(path, friendly_name="Pandora Structure Creator")

    def launch_env_dependency_manager(self, force_repath=False):
        """Öffnet den Pandora Environment & Dependency Manager (Virtualenv
        Control, Package Installer für pip/npm, Abhängigkeits-Übersicht).
        Läuft wie der SQL Config Editor als eigenständiger Prozess, da es
        keinen Bezug zu einem bestimmten Dateityp im aktiven Editor hat."""
        path = self._resolve_tool_path(
            CFG_KEY_ENV_DEPENDENCY_MANAGER,
            "pandora_env_dependency_manager.py auswählen (Pandora Environment & Dependency Manager)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return
        self._launch_external_tool(path, friendly_name="Pandora Environment & Dependency Manager")

    def launch_pcb_editor(self, force_repath=False):
        """Öffnet den Pandora PCB Editor (Leiterplatten-Layout mit Ratsnest,
        DRC, Autorouter, Gerber-X2-/Excellon-Export und 3D-Vorschau). Läuft
        wie der SQL Config Editor als eigenständiger Prozess, da es sich um
        eine vollständig eigenständige PyQt6-Anwendung (eigene MainWindow-
        Klasse) handelt."""
        path = self._resolve_tool_path(
            CFG_KEY_PCB_EDITOR,
            "pandora_pcb_editor.py auswählen (Pandora PCB Editor)",
            TOOL_ENTRYPOINT_FILTER,
            force_repath=force_repath,
        )
        if not path:
            return
        self._launch_external_tool(path, friendly_name="Pandora PCB Editor")

    # ---------------- Code Snippet Vault (In-Prozess-Integration) ----------------
    def _get_snippet_vault_module(self, force_repath=False):
        """Lädt pandora_snippet_vault.py per importlib DIREKT in diesen
        Prozess (kein subprocess!), damit Quick-Insert Text an der
        Cursor-Position des aktiven Editors einfügen kann. Der geladene
        Modul-Objekt wird zwischengespeichert, solange sich der Pfad nicht
        ändert."""
        path = self._resolve_tool_path(
            CFG_KEY_SNIPPET_VAULT,
            "Pandora Code Snippet Vault auswählen (pandora_snippet_vault.py)",
            # Bewusst nur *.py: wird per importlib als Modul in diesen Prozess
            # geladen (kein subprocess) - ein .exe-Build kann hier nicht
            # eingebunden werden. Für einen --onedir-Build müsste stattdessen
            # weiterhin die .py-Quelldatei des Snippet Vault ausgewählt werden.
            "Python-Datei (*.py)",
            force_repath=force_repath,
        )
        if not path:
            return None

        cached_path = getattr(self, "_snippet_vault_module_path", None)
        cached_module = getattr(self, "_snippet_vault_module", None)
        if not force_repath and cached_module is not None and cached_path == path:
            return cached_module

        try:
            spec = importlib.util.spec_from_file_location(
                "pandora_snippet_vault_dynamic", path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            QMessageBox.critical(
                self, "Snippet Vault konnte nicht geladen werden",
                f"Fehler beim Import von\n{path}:\n\n{e}"
            )
            return None

        self._snippet_vault_module = module
        self._snippet_vault_module_path = path
        self._snippet_vault_store = None  # Bibliothek bei (Neu-)Laden des Moduls neu öffnen
        return module

    def _get_snippet_store(self, module):
        store = getattr(self, "_snippet_vault_store", None)
        if store is None:
            store = module.SnippetStore()
            self._snippet_vault_store = store
        return store

    def _insert_snippet_text(self, editor, text):
        """Fügt den fertig gerenderten Snippet-Text an der aktuellen Cursor-
        Position des übergebenen Editors ein. Mehrzeilige Snippets werden
        dabei auf die aktuelle Zeileneinrückung ausgerichtet, damit sie sich
        sauber in bestehenden, eingerückten Code einfügen."""
        cursor = editor.textCursor()
        current_line = cursor.block().text()
        indent_match = re.match(r"[ \t]*", current_line)
        indent = indent_match.group(0) if indent_match else ""

        lines = text.split("\n")
        if len(lines) > 1:
            text = ("\n" + indent).join(lines)

        cursor.insertText(text)
        editor.setFocus()
        self.statusBar().showMessage("Snippet eingefügt.", 3000)

    def open_snippet_vault(self, force_repath=False):
        """Öffnet den vollständigen Vault-Browser (Suchen/Filtern/Verwalten).
        Ist ein Editor-Tab aktiv, kann direkt daraus eingefügt werden -
        andernfalls landet das gewählte Snippet in der Zwischenablage."""
        module = self._get_snippet_vault_module(force_repath=force_repath)
        if module is None:
            return
        store = self._get_snippet_store(module)

        target_editor = self.current_editor()
        callback = None
        if target_editor is not None:
            callback = lambda text, ed=target_editor: self._insert_snippet_text(ed, text)

        dlg = module.SnippetVaultDialog(store, insert_callback=callback, parent=self)
        dlg.exec()

    def quick_insert_snippet(self):
        """Schnellsuche: öffnet ein schmales Suchfenster, Enter fügt das
        Snippet sofort an der aktuellen Cursor-Position ein."""
        editor = self.current_editor()
        if editor is None:
            QMessageBox.information(
                self, "Kein aktiver Editor",
                "Bitte zuerst einen Datei-Tab öffnen oder erstellen, um ein Snippet einzufügen."
            )
            return

        module = self._get_snippet_vault_module()
        if module is None:
            return
        store = self._get_snippet_store(module)

        popup = module.QuickInsertPopup(
            store,
            insert_callback=lambda text, ed=editor: self._insert_snippet_text(ed, text),
            parent=self,
        )
        popup.exec()

    def change_login_credentials(self):
        """Öffnet einen Dialog, über den Benutzername/Passwort für den
        Login-Bildschirm (login_ui.py) geändert werden können. Aus
        Sicherheitsgründen muss dafür das aktuell gültige Passwort
        bestätigt werden. Die neuen Daten werden in login_config.json
        gespeichert (Passwort nur als SHA-256-Hash)."""
        try:
            from login_ui import load_credentials, save_credentials, _hash_password
        except ImportError:
            QMessageBox.critical(
                self,
                "Nicht verfügbar",
                "login_ui.py wurde nicht gefunden - Zugangsdaten können "
                "nicht geändert werden.",
            )
            return

        current_username, current_password_hash = load_credentials()

        dialog = QDialog(self)
        dialog.setWindowTitle("Zugangsdaten ändern")
        dialog.setMinimumWidth(340)

        form = QFormLayout(dialog)

        edit_current_password = QLineEdit(dialog)
        edit_current_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Aktuelles Passwort:", edit_current_password)

        edit_new_username = QLineEdit(dialog)
        edit_new_username.setText(current_username)
        form.addRow("Neuer Benutzername:", edit_new_username)

        edit_new_password = QLineEdit(dialog)
        edit_new_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Neues Passwort:", edit_new_password)

        edit_new_password_repeat = QLineEdit(dialog)
        edit_new_password_repeat.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Neues Passwort (wiederholen):", edit_new_password_repeat)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Aktuelles Passwort bestätigen
        if _hash_password(edit_current_password.text()) != current_password_hash:
            QMessageBox.critical(
                self, "Login fehlgeschlagen", "Aktuelles Passwort ist falsch."
            )
            return

        new_username = edit_new_username.text().strip()
        new_password = edit_new_password.text()
        new_password_repeat = edit_new_password_repeat.text()

        if not new_username:
            QMessageBox.warning(self, "Ungültige Eingabe", "Benutzername darf nicht leer sein.")
            return
        if not new_password:
            QMessageBox.warning(self, "Ungültige Eingabe", "Neues Passwort darf nicht leer sein.")
            return
        if new_password != new_password_repeat:
            QMessageBox.warning(
                self, "Ungültige Eingabe", "Die beiden Passwort-Eingaben stimmen nicht überein."
            )
            return

        save_credentials(new_username, new_password)
        QMessageBox.information(
            self,
            "Gespeichert",
            "Zugangsdaten wurden aktualisiert.\n\n"
            f"Neuer Benutzername: {new_username}\n"
            "Das neue Passwort gilt ab dem nächsten Login.",
        )

    def show_about(self):
        jedi_status = (
            "aktiv (kontextbezogene Vorschläge via Jedi)"
            if HAVE_JEDI
            else "nicht installiert (nur Wortvervollständigung)"
        )
        pyflakes_status = (
            "aktiv"
            if HAVE_PYFLAKES
            else "nicht installiert (nur Syntaxprüfung via ast)"
        )
        icon_status = (
            "aktiv (FontAwesome via QtAwesome)"
            if HAVE_QTAWESOME
            else "nicht installiert (Emoji-Fallback)"
        )
        QMessageBox.information(
            self,
            "Über " + APP_NAME,
            f"<h3>{APP_NAME}</h3>"
            "<p>Ein schlanker Python-Script-Editor mit PyQt6.</p>"
            "<p>Syntaxhervorhebung · Mehrere Tabs · Suchen &amp; Ersetzen · Skriptausführung · "
            "Projekt-Panel · Autovervollständigung · Linting · Git-Integration · "
            "Gemini-KI (mit Multi-Datei-Kontext) · Interaktive Konsole · "
            "Code Snippet Vault (Quick-Insert per Ctrl+Alt+I)</p>"
            f"<p>Jedi-Autovervollständigung: {jedi_status}<br>"
            f"Lint-Engine (pyflakes): {pyflakes_status}<br>"
            f"Icon-Theme: {icon_status}<br>"
            f"Gemini-Modell: {GEMINI_MODEL}</p>",
        )

    # ---------------- Fenster schließen ----------------
    def closeEvent(self, event):
        checked_documents = set()
        for pane in self.panes:
            for i in range(pane.count()):
                editor = pane.widget(i)
                if (
                    not isinstance(editor, CodeEditor)
                    or not editor.document().isModified()
                ):
                    continue
                doc_id = id(editor.document())
                if doc_id in checked_documents:
                    continue  # bereits bestätigt (z. B. im Split-View dasselbe Dokument)
                checked_documents.add(doc_id)
                pane.setCurrentIndex(i)
                res = QMessageBox.question(
                    self,
                    APP_NAME,
                    f"„{pane.tabText(i).rstrip(' •')}“ enthält ungespeicherte Änderungen.\nTrotzdem beenden?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if res == QMessageBox.StandardButton.No:
                    event.ignore()
                    return
        event.accept()

    # ---------------- Theme ----------------
    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #1b1c22;
                color: #d4d4d4;
            }
            QMenuBar {
                background-color: #23242c;
                color: #d4d4d4;
            }
            QMenuBar::item:selected {
                background-color: #33354a;
            }
            QMenu {
                background-color: #23242c;
                color: #d4d4d4;
                border: 1px solid #33354a;
            }
            QMenu::item:selected {
                background-color: #33354a;
            }
            QToolBar {
                background-color: #23242c;
                border: none;
                spacing: 4px;
                padding: 4px;
            }
            QToolButton {
                color: #d4d4d4;
                padding: 4px 8px;
                border-radius: 6px;
            }
            QToolButton:hover {
                background-color: #33354a;
            }
            QTabWidget::pane {
                border-top: 1px solid #33354a;
            }
            QTabBar::tab {
                background: #23242c;
                color: #b8b8b8;
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #2e303c;
                color: #ffffff;
            }
            QPlainTextEdit {
                background-color: #1e1f26;
                color: #d4d4d4;
                border: none;
                selection-background-color: #3b5070;
            }
            QStatusBar {
                background-color: #23242c;
                color: #9aa0ab;
            }
            QDockWidget {
                color: #d4d4d4;
                titlebar-close-icon: none;
            }
            QDockWidget::title {
                background: #23242c;
                padding: 6px;
            }
            QLineEdit, QLabel, QCheckBox {
                color: #d4d4d4;
            }
            QLineEdit {
                background-color: #1e1f26;
                border: 1px solid #33354a;
                border-radius: 4px;
                padding: 4px;
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
            QTreeView {
                background-color: #1e1f26;
                color: #d4d4d4;
                border: none;
                alternate-background-color: #21222a;
            }
            QTreeView::item:selected {
                background-color: #3b5070;
            }
            QHeaderView::section {
                background-color: #23242c;
                color: #d4d4d4;
                border: none;
                padding: 4px;
            }
            QTextBrowser {
                background-color: #1e1f26;
                color: #d4d4d4;
                border: 1px solid #33354a;
                border-radius: 4px;
            }
            QListView {
                background-color: #23242c;
                color: #d4d4d4;
                border: 1px solid #33354a;
                selection-background-color: #3b5070;
            }
        """)


def _install_excepthook():
    """Fängt unerwartete Exceptions in Qt-Slots ab (z.B. Button-Klicks,
    Enter-Events) und zeigt einen Fehlerdialog, statt die Anwendung
    kommentarlos abstürzen zu lassen."""
    import traceback

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        tb_text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        print(tb_text, file=sys.stderr)
        try:
            QMessageBox.critical(
                None,
                "Unerwarteter Fehler",
                f"Es ist ein unerwarteter Fehler aufgetreten:\n\n{exc_value}\n\n"
                "Details wurden auf der Konsole ausgegeben.",
            )
        except Exception:
            pass

    sys.excepthook = handle_exception


def main():
    _install_excepthook()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)

    # Login-Fenster von login_ui.py vorschalten. Der eigentliche Editor
    # (MainWindow) wird erst nach erfolgreichem Login geoeffnet.
    from login_ui import GeneratedWindow as LoginWindow

    login_window = LoginWindow()

    def _open_editor():
        # Referenz auf app haengen, damit das MainWindow-Objekt nicht
        # vom Garbage Collector eingesammelt wird, sobald _open_editor
        # zu Ende ist.
        app.main_window = MainWindow()
        app.main_window.show()

    login_window.login_success.connect(_open_editor)
    login_window.show()

    # Schliesst der Nutzer das Login-Fenster ohne erfolgreichen Login
    # (Cancel/X), beendet Qt die Anwendung automatisch, da dann kein
    # weiteres Fenster offen ist (quitOnLastWindowClosed, Standard: True).
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
