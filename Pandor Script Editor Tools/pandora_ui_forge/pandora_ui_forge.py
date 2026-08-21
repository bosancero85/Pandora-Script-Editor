#!/usr/bin/env python3
"""
Pandora® UI Forge
------------------
Visueller PyQt6 Design-Editor: Canvas (Drag & Drop) + synchroner Code-Editor.
Erlaubt das Erstellen neuer PyQt6-Frontends per Drag & Drop sowie das Öffnen
und Analysieren bestehender .py-Dateien (Best-Effort AST-Parsing).

AKI_SystemDown® / Pandora® Ecosystem
"""

import sys
import os
import ast
import re
import uuid
import traceback
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QSplitter, QListWidget, QListWidgetItem, QLabel, QPushButton, QLineEdit,
    QCheckBox, QComboBox, QTextEdit, QPlainTextEdit, QSlider, QProgressBar,
    QRadioButton, QSpinBox, QGroupBox, QTabWidget, QFileDialog, QMessageBox,
    QToolBar, QStatusBar, QFrame, QSizePolicy, QGraphicsDropShadowEffect,
    QGraphicsBlurEffect, QGraphicsColorizeEffect, QGraphicsOpacityEffect,
    QColorDialog, QDateEdit, QTimeEdit, QDial, QLCDNumber, QDoubleSpinBox,
    QToolButton, QCalendarWidget, QTableWidget, QScrollBar, QDialogButtonBox,
    QKeySequenceEdit, QFontComboBox, QCommandLinkButton, QTreeWidget,
    QTreeWidgetItem, QStackedWidget, QToolBox, QScrollArea
)
from PyQt6.QtGui import (
    QDrag, QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QAction,
    QCursor
)
from PyQt6.QtCore import (
    Qt, QMimeData, QPoint, pyqtSignal, QThread, QEvent, QRegularExpression,
    QObject, QPropertyAnimation, QEasingCurve
)


# ======================================================================
# 1. DATENMODELL
# ======================================================================

@dataclass
class WidgetSpec:
    """Beschreibt ein auf dem Canvas platziertes Widget (Design-Modell)."""
    uid: str
    widget_type: str
    object_name: str
    x: int
    y: int
    w: int
    h: int
    text: str = ""
    # -- Optik, individuell pro Widget im Properties-Panel editierbar --
    border_color: str = "#3a2a55"
    border_radius: int = 8
    border_style: str = "solid"    # solid | dashed | dotted | double
    background_color: str = ""     # leer = Theme-Standard (kein Override)
    text_color: str = ""           # leer = Theme-Standard (kein Override)
    font_size: int = 0             # 0 = Theme-Standard
    font_bold: bool = False
    font_italic: bool = False
    underline: bool = False
    text_align: str = "left"       # left | center | right
    padding: int = 0
    bg_opacity: int = 100          # 0-100 %, Alpha-Kanal der Hintergrundfarbe (unabhängig vom Effekt!)
    shadow_offset_x: int = 0       # nur für effect_type == "glow" relevant
    shadow_offset_y: int = 0
    effect_type: str = "none"      # "none" | "glow" | "blur" | "colorize" | "opacity"
    effect_color: str = "#00e5ff"  # nur für glow/colorize relevant
    effect_strength: int = 0       # 0-100, Bedeutung je nach effect_type (siehe build_graphics_effect)


# Verfügbare Widget-Typen: Anzeigename -> (Klasse, Standardbreite, -höhe, Standardtext)
WIDGET_CLASSES = {
    "QPushButton": QPushButton,
    "QLabel": QLabel,
    "QLineEdit": QLineEdit,
    "QTextEdit": QTextEdit,
    "QCheckBox": QCheckBox,
    "QRadioButton": QRadioButton,
    "QComboBox": QComboBox,
    "QSpinBox": QSpinBox,
    "QDoubleSpinBox": QDoubleSpinBox,
    "QSlider": QSlider,
    "QProgressBar": QProgressBar,
    "QGroupBox": QGroupBox,
    "QToolButton": QToolButton,
    "QDateEdit": QDateEdit,
    "QTimeEdit": QTimeEdit,
    "QDial": QDial,
    "QLCDNumber": QLCDNumber,
    "QCalendarWidget": QCalendarWidget,
    "QTableWidget": QTableWidget,
    "QListWidget": QListWidget,
    "QFrame": QFrame,
    "QTabWidget": QTabWidget,
    "QScrollBar": QScrollBar,
    "QDialogButtonBox": QDialogButtonBox,
    "QKeySequenceEdit": QKeySequenceEdit,
    "QFontComboBox": QFontComboBox,
    "QCommandLinkButton": QCommandLinkButton,
    "QTreeWidget": QTreeWidget,
    "QPlainTextEdit": QPlainTextEdit,
    "QStackedWidget": QStackedWidget,
    "QToolBox": QToolBox,
    "QScrollArea": QScrollArea,
    # -- Varianten: nutzen dieselbe Qt-Klasse, aber andere Vorkonfiguration --
    "QLineEdit_Password": QLineEdit,
    "QLineEdit_Search": QLineEdit,
    "QFrame_HLine": QFrame,
    "QFrame_VLine": QFrame,
}

# Für Varianten-Pseudotypen: welcher echte PyQt6-Klassenname beim Code-Export
# verwendet werden muss (es gibt keine Klasse "QLineEdit_Password" o.ä.).
EXPORT_CLASS_NAMES = {
    "QLineEdit_Password": "QLineEdit",
    "QLineEdit_Search": "QLineEdit",
    "QFrame_HLine": "QFrame",
    "QFrame_VLine": "QFrame",
}

PALETTE_DEFINITIONS = [
    # (Anzeigename, Widget-Typ, Standardbreite, Standardhöhe, Standardtext)
    ("Button", "QPushButton", 110, 34, "Button"),
    ("Befehls-Button", "QCommandLinkButton", 180, 50, "Option wählen"),
    ("Toolbutton", "QToolButton", 90, 32, "Tool"),
    ("Label", "QLabel", 110, 24, "Label"),
    ("Textzeile", "QLineEdit", 150, 30, ""),
    ("Textfeld (mehrzeilig)", "QTextEdit", 180, 90, ""),
    ("Text-/Log-Feld", "QPlainTextEdit", 200, 100, ""),
    ("Checkbox", "QCheckBox", 110, 24, "Checkbox"),
    ("Radiobutton", "QRadioButton", 110, 24, "Radio"),
    ("Combobox", "QComboBox", 130, 30, ""),
    ("Schriftart-Auswahl", "QFontComboBox", 160, 30, ""),
    ("Zahlenfeld (int)", "QSpinBox", 90, 30, ""),
    ("Zahlenfeld (dezimal)", "QDoubleSpinBox", 100, 30, ""),
    ("Slider", "QSlider", 150, 26, ""),
    ("Scrollbar", "QScrollBar", 160, 20, ""),
    ("Fortschrittsbalken", "QProgressBar", 150, 24, ""),
    ("Gruppenbox", "QGroupBox", 190, 110, "Gruppe"),
    ("Datum-Auswahl", "QDateEdit", 140, 30, ""),
    ("Uhrzeit-Auswahl", "QTimeEdit", 120, 30, ""),
    ("Tastenkombination", "QKeySequenceEdit", 150, 30, ""),
    ("Drehregler", "QDial", 80, 80, ""),
    ("Digitalanzeige", "QLCDNumber", 130, 45, ""),
    ("Kalender", "QCalendarWidget", 260, 200, ""),
    ("Tabelle", "QTableWidget", 220, 150, ""),
    ("Listenfeld", "QListWidget", 160, 130, ""),
    ("Baumansicht", "QTreeWidget", 220, 170, ""),
    ("Tab-Container", "QTabWidget", 240, 160, ""),
    ("Seiten-Stapel", "QStackedWidget", 220, 140, ""),
    ("Werkzeugkasten", "QToolBox", 220, 170, ""),
    ("Scroll-Bereich", "QScrollArea", 220, 150, ""),
    ("Dialog-Buttonleiste", "QDialogButtonBox", 180, 36, ""),
    ("Rahmen/Panel", "QFrame", 180, 90, ""),
    ("Passwortfeld", "QLineEdit_Password", 150, 30, ""),
    ("Suchfeld", "QLineEdit_Search", 160, 30, ""),
    ("Trennlinie (horizontal)", "QFrame_HLine", 180, 4, ""),
    ("Trennlinie (vertikal)", "QFrame_VLine", 4, 140, ""),
]

DEFAULT_SIZES = {name: (w, h) for _, name, w, h, _ in PALETTE_DEFINITIONS}
DEFAULT_TEXTS = {name: t for _, name, _, _, t in PALETTE_DEFINITIONS}

TEXT_SETTER_WIDGETS = (QPushButton, QLabel, QCheckBox, QRadioButton, QLineEdit, QToolButton)

MIME_WIDGET_TYPE = "application/x-pandora-widget-type"


def apply_widget_text(widget: QWidget, text: str) -> None:
    """Setzt Anzeigetext je nach Widget-Typ auf die passende Weise.
    QGroupBox hat kein setText() -> setTitle() ist hier Pflicht, sonst AttributeError/Absturz.
    QTextEdit/QPlainTextEdit sind KEINE gemeinsame Unterklasse -> beide explizit prüfen."""
    if isinstance(widget, QGroupBox):
        widget.setTitle(text)
    elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
        widget.setPlainText(text)
    elif isinstance(widget, TEXT_SETTER_WIDGETS):
        widget.setText(text)


def make_glow(color_hex: str, blur: int = 24, x_offset: int = 0, y_offset: int = 0,
              alpha: int = 200) -> QGraphicsDropShadowEffect:
    """Erzeugt einen Neon-Glow-Effekt (QSS kennt kein box-shadow, daher hier über
    QGraphicsDropShadowEffect). Bewusst nur auf statische/kleine Widgets angewendet,
    NICHT auf den Canvas selbst, da der bei jedem Drag-Frame neu gezeichnet wird und
    ein Effekt dort spürbar ruckeln würde."""
    effect = QGraphicsDropShadowEffect()
    color = QColor(color_hex)
    color.setAlpha(alpha)
    effect.setColor(color)
    effect.setBlurRadius(blur)
    effect.setOffset(x_offset, y_offset)
    return effect


class HoverGlowFilter(QObject):
    """Verpasst einem Widget beim Hover einen weich eingeblendeten Neon-Glow.
    QSS kennt keine Transitions, daher hier über QPropertyAnimation auf die
    blurRadius-Property des QGraphicsDropShadowEffect gelöst -> der Glow wächst
    beim Hover-Enter sanft auf und blendet beim Leave wieder sanft aus, statt
    abrupt zu erscheinen/verschwinden."""

    def __init__(self, color: str = "#00e5ff", max_blur: int = 26, duration_ms: int = 180,
                 parent=None):
        super().__init__(parent)
        self._color = color
        self._max_blur = max_blur
        self._duration = duration_ms

    def eventFilter(self, obj, event) -> bool:
        if event.type() == QEvent.Type.Enter and obj.isEnabled():
            effect = make_glow(self._color, blur=0, alpha=200)
            obj.setGraphicsEffect(effect)
            anim = QPropertyAnimation(effect, b"blurRadius", obj)
            anim.setDuration(self._duration)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(0)
            anim.setEndValue(self._max_blur)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
            obj._hover_glow_anim = anim  # Referenz halten, sonst GC-Abbruch mitten in der Animation
        elif event.type() == QEvent.Type.Leave:
            effect = obj.graphicsEffect()
            if isinstance(effect, QGraphicsDropShadowEffect):
                anim = QPropertyAnimation(effect, b"blurRadius", obj)
                anim.setDuration(self._duration)
                anim.setEasingCurve(QEasingCurve.Type.InCubic)
                anim.setStartValue(effect.blurRadius())
                anim.setEndValue(0)
                anim.finished.connect(lambda w=obj: w.setGraphicsEffect(None))
                anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
                obj._hover_glow_anim = anim
        return False


def attach_hover_glow(widget: QWidget, color: str = "#00e5ff", max_blur: int = 26) -> None:
    """Hängt einen HoverGlowFilter an ein Widget. Der Filter wird als Kind des
    Widgets angelegt, damit er mit diesem zusammen zerstört wird."""
    widget.installEventFilter(HoverGlowFilter(color=color, max_blur=max_blur, parent=widget))


def build_graphics_effect(spec: WidgetSpec):
    """Zentrale Fabrik für den Optik-Effekt eines Canvas-Widgets. Ein QWidget kann
    IMMER NUR EINEN QGraphicsEffect gleichzeitig tragen -> effect_type ist bewusst
    ein exklusiver Auswahltyp, keine Kombination mehrerer Effekte.

    effect_strength (0-100) hat für jeden Typ dieselbe Bedeutung: 0 = kein Effekt,
    100 = maximale Ausprägung. Das macht die Properties-Panel-Bedienung einheitlich.
    """
    if spec.effect_type == "none" or spec.effect_strength <= 0:
        return None

    if spec.effect_type == "glow":
        blur = max(4, int(spec.effect_strength * 0.6))
        return make_glow(spec.effect_color, blur=blur,
                          x_offset=spec.shadow_offset_x, y_offset=spec.shadow_offset_y, alpha=210)

    if spec.effect_type == "blur":
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(max(1.0, spec.effect_strength * 0.3))
        return effect

    if spec.effect_type == "colorize":
        effect = QGraphicsColorizeEffect()
        effect.setColor(QColor(spec.effect_color))
        effect.setStrength(spec.effect_strength / 100.0)
        return effect

    if spec.effect_type == "opacity":
        effect = QGraphicsOpacityEffect()
        effect.setOpacity(max(0.0, 1.0 - spec.effect_strength / 100.0))
        return effect

    return None


def build_stylesheet(spec: WidgetSpec) -> str:
    """Baut das kombinierte Instanz-Stylesheet eines Canvas-Widgets aus allen
    Optik-Feldern zusammen (Rahmen, Hintergrund, Text, Schrift).
    Die Hintergrund-Deckkraft läuft bewusst über den Alpha-Kanal der Farbe (rgba),
    NICHT über den QGraphicsEffect -> dadurch mit Glow/Blur/Colorize kombinierbar,
    ohne mit der 'nur 1 Effekt pro Widget'-Beschränkung zu kollidieren."""
    parts = [
        f"border: 2px {spec.border_style} {spec.border_color};",
        f"border-radius: {spec.border_radius}px;",
    ]
    if spec.background_color:
        c = QColor(spec.background_color)
        c.setAlpha(max(0, min(255, round(spec.bg_opacity / 100 * 255))))
        parts.append(f"background-color: rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()});")
    if spec.text_color:
        parts.append(f"color: {spec.text_color};")
    if spec.font_size > 0:
        parts.append(f"font-size: {spec.font_size}px;")
    if spec.font_bold:
        parts.append("font-weight: bold;")
    if spec.font_italic:
        parts.append("font-style: italic;")
    if spec.underline:
        parts.append("text-decoration: underline;")
    if spec.padding > 0:
        parts.append(f"padding: {spec.padding}px;")
    return " ".join(parts)


TEXT_ALIGN_MAP = {
    "left": Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    "center": Qt.AlignmentFlag.AlignCenter,
    "right": Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
}


def apply_widget_style(widget: QWidget, spec: WidgetSpec) -> None:
    """Wendet Rahmen/Hintergrund/Text/Schrift sowie den gewählten Optik-Effekt
    individuell auf ein Canvas-Widget an. Läuft über eine Instanz-Stylesheet
    (überschreibt gezielt diese Properties, der Rest kommt aus dem globalen Theme)."""
    widget.setStyleSheet(build_stylesheet(spec))
    widget.setGraphicsEffect(build_graphics_effect(spec))
    if hasattr(widget, "setAlignment"):
        try:
            widget.setAlignment(TEXT_ALIGN_MAP.get(spec.text_align, TEXT_ALIGN_MAP["left"]))
        except Exception:
            pass  # nicht jedes Widget mit setAlignment akzeptiert dieselbe Flag-Kombination


def seed_widget_defaults(widget: QWidget, widget_type: str) -> None:
    """Füllt einige Widget-Typen beim Anlegen mit sinnvollem Platzhalterinhalt,
    damit sie auf dem Canvas nicht komplett leer bzw. falsch orientiert wirken."""
    if widget_type == "QTableWidget" and isinstance(widget, QTableWidget):
        widget.setRowCount(3)
        widget.setColumnCount(3)
    elif widget_type == "QListWidget" and isinstance(widget, QListWidget):
        widget.addItems(["Eintrag 1", "Eintrag 2", "Eintrag 3"])
    elif widget_type == "QTabWidget" and isinstance(widget, QTabWidget):
        widget.addTab(QWidget(), "Tab 1")
        widget.addTab(QWidget(), "Tab 2")
    elif widget_type == "QScrollBar" and isinstance(widget, QScrollBar):
        widget.setOrientation(Qt.Orientation.Horizontal)
    elif widget_type == "QDialogButtonBox" and isinstance(widget, QDialogButtonBox):
        widget.setStandardButtons(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
    elif widget_type == "QTreeWidget" and isinstance(widget, QTreeWidget):
        widget.setHeaderLabels(["Name", "Typ"])
        top = QTreeWidgetItem(["Ordner", "Verzeichnis"])
        top.addChild(QTreeWidgetItem(["datei.txt", "Text"]))
        widget.addTopLevelItem(top)
        widget.expandAll()
    elif widget_type == "QSplitter" and isinstance(widget, QSplitter):
        widget.addWidget(QFrame())
        widget.addWidget(QFrame())
    elif widget_type == "QStackedWidget" and isinstance(widget, QStackedWidget):
        widget.addWidget(QWidget())
        widget.addWidget(QWidget())
    elif widget_type == "QToolBox" and isinstance(widget, QToolBox):
        widget.addItem(QWidget(), "Seite 1")
        widget.addItem(QWidget(), "Seite 2")
    elif widget_type == "QScrollArea" and isinstance(widget, QScrollArea):
        inner = QWidget()
        inner.setMinimumSize(400, 400)
        widget.setWidget(inner)
        widget.setWidgetResizable(True)
    elif widget_type == "QLineEdit_Password" and isinstance(widget, QLineEdit):
        widget.setEchoMode(QLineEdit.EchoMode.Password)
        widget.setPlaceholderText("Passwort")
    elif widget_type == "QLineEdit_Search" and isinstance(widget, QLineEdit):
        widget.setClearButtonEnabled(True)
        widget.setPlaceholderText("Suchen …")
    elif widget_type == "QFrame_HLine" and isinstance(widget, QFrame):
        widget.setFrameShape(QFrame.Shape.HLine)
        widget.setFrameShadow(QFrame.Shadow.Sunken)
    elif widget_type == "QFrame_VLine" and isinstance(widget, QFrame):
        widget.setFrameShape(QFrame.Shape.VLine)
        widget.setFrameShadow(QFrame.Shadow.Sunken)


# ======================================================================
# 2. AST-WORKER (Thread) - liest bestehende .py-Dateien, ohne die UI zu blockieren
# ======================================================================

# ----------------------------------------------------------------------
# Hilfsfunktionen für den Re-Import (Code -> WidgetSpec).
#
# Der bisherige Parser hat NUR Widget-Typ, Objekt-Name und setGeometry()
# ausgelesen. Alles andere, was generate_code() tatsächlich schreibt -
# .setText()/.setTitle()/.setPlainText(), .setStyleSheet() (Rahmen,
# Hintergrund, Text-/Schriftfarbe, Schrift, Padding), .setAlignment() und
# die QGraphicsDropShadowEffect/-Blur/-Colorize/-Opacity-Blöcke - ging beim
# erneuten Öffnen einer exportierten Datei verloren: das Fenster ließ sich
# zwar öffnen, aber jedes Widget kam optisch komplett zurückgesetzt auf dem
# Canvas an (keine Farben, kein Effekt, kein Text) -> "nicht nachbearbeitbar".
# Die folgenden Helfer lesen genau die Gegenstücke zu build_stylesheet(),
# build_graphics_effect() und apply_widget_text() wieder ein.
# ----------------------------------------------------------------------

_CSS_COLOR_RE = r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]*\))"
_BORDER_RE = re.compile(rf"(\d+)px\s+(solid|dashed|dotted|double)\s+{_CSS_COLOR_RE}")
_RGBA_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)")


def _rgba_to_hex_and_opacity(value: str) -> tuple[str, int]:
    """Wandelt 'rgba(r, g, b, a)' in (Hex-Farbe, Deckkraft-Prozent) um.
    Einfaches '#hex' kommt unverändert mit Deckkraft 100 zurück."""
    m = _RGBA_RE.match(value.strip())
    if not m:
        return value.strip(), 100
    r, g, b = (int(m.group(i)) for i in (1, 2, 3))
    a = int(m.group(4)) if m.group(4) else 255
    opacity = max(0, min(100, round(a / 255 * 100)))
    return f"#{r:02x}{g:02x}{b:02x}", opacity


def _apply_stylesheet_text_to_spec(spec: "WidgetSpec", css_text: str) -> None:
    """Parst ein von build_stylesheet() erzeugtes Inline-Stylesheet zurück
    in die einzelnen Optik-Felder eines WidgetSpec (Gegenstück zu
    build_stylesheet() in Modul 1)."""
    border_match = _BORDER_RE.search(css_text)
    if border_match:
        spec.border_style = border_match.group(2)
        spec.border_color = border_match.group(3)

    for declaration in css_text.split(";"):
        if ":" not in declaration:
            continue
        prop, _, value = declaration.partition(":")
        prop = prop.strip().lower()
        value = value.strip()
        if not value:
            continue
        if prop == "border-radius":
            try:
                spec.border_radius = int(value.replace("px", "").strip())
            except ValueError:
                pass
        elif prop == "background-color":
            hex_color, opacity = _rgba_to_hex_and_opacity(value)
            spec.background_color = hex_color
            spec.bg_opacity = opacity
        elif prop == "color":
            spec.text_color = value
        elif prop == "font-size":
            try:
                spec.font_size = int(value.replace("px", "").strip())
            except ValueError:
                pass
        elif prop == "font-weight" and "bold" in value:
            spec.font_bold = True
        elif prop == "font-style" and "italic" in value:
            spec.font_italic = True
        elif prop == "text-decoration" and "underline" in value:
            spec.underline = True
        elif prop == "padding":
            try:
                spec.padding = int(value.replace("px", "").strip())
            except ValueError:
                pass


def _alignment_expr_to_key(node: ast.AST) -> Optional[str]:
    """Liest eine setAlignment(...)-Ausdrucksbaum (z.B. Qt.AlignmentFlag.AlignRight
    | Qt.AlignmentFlag.AlignVCenter) und ordnet sie left/center/right zu -
    Gegenstück zu TEXT_ALIGN_MAP in Modul 1."""
    attrs = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
    if "AlignCenter" in attrs:
        return "center"
    if "AlignRight" in attrs:
        return "right"
    if "AlignLeft" in attrs:
        return "left"
    return None


_EFFECT_CLASS_KIND = {
    "QGraphicsDropShadowEffect": "glow",
    "QGraphicsBlurEffect": "blur",
    "QGraphicsColorizeEffect": "colorize",
    "QGraphicsOpacityEffect": "opacity",
}


def _flatten_statements(node: ast.AST):
    """Gibt alle Statements eines Baums in (weitgehend) Ausführungsreihenfolge
    zurück - wird für die Effekt-Erkennung gebraucht, da diese über mehrere
    aufeinanderfolgende Zeilen hinweg denselben Hilfsvariablen-Namen
    (z.B. '_color') wiederverwendet und daher NICHT über ast.walk()
    (keine garantierte Reihenfolge) ausgewertet werden darf."""
    for attr in ("body", "orelse", "finalbody"):
        for stmt in getattr(node, attr, []) or []:
            yield stmt
            yield from _flatten_statements(stmt)


def _self_attr_call(node: ast.AST) -> Optional[tuple[str, str, list]]:
    """Erkennt `self.<name>.<method>(<args>)` und gibt (name, method, args)
    zurück, sonst None."""
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
        return None
    call = node.value
    func = call.func
    if not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)
            and isinstance(func.value.value, ast.Name) and func.value.value.id == "self"):
        return None
    return func.value.attr, func.attr, call.args


def _parse_text_calls(statements, specs_by_name: dict) -> None:
    """Liest .setText()/.setTitle()/.setPlainText()-Aufrufe zurück in spec.text."""
    for stmt in statements:
        hit = _self_attr_call(stmt)
        if hit is None:
            continue
        name, method, args = hit
        if method not in ("setText", "setTitle", "setPlainText"):
            continue
        spec = specs_by_name.get(name)
        if spec is None or not args:
            continue
        arg = args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            spec.text = arg.value


def _parse_stylesheet_calls(statements, specs_by_name: dict) -> None:
    """Liest self.<name>.setStyleSheet("...") zurück (bewusst NICHT
    self.setStyleSheet(...) - das ist das globale Fenster-Theme, keine
    Widget-Eigenschaft)."""
    for stmt in statements:
        hit = _self_attr_call(stmt)
        if hit is None:
            continue
        name, method, args = hit
        if method != "setStyleSheet":
            continue
        spec = specs_by_name.get(name)
        if spec is None or not args:
            continue
        arg = args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            _apply_stylesheet_text_to_spec(spec, arg.value)


def _parse_alignment_calls(statements, specs_by_name: dict) -> None:
    """Liest self.<name>.setAlignment(...) zurück in spec.text_align."""
    for stmt in statements:
        hit = _self_attr_call(stmt)
        if hit is None:
            continue
        name, method, args = hit
        if method != "setAlignment":
            continue
        spec = specs_by_name.get(name)
        if spec is None or not args:
            continue
        key = _alignment_expr_to_key(args[0])
        if key is not None:
            spec.text_align = key


def _parse_effect_blocks(statements, specs_by_name: dict) -> None:
    """Liest die von generate_code() erzeugten QGraphicsDropShadowEffect/
    -Blur/-Colorize/-Opacity-Blöcke zurück (Gegenstück zu
    build_graphics_effect() in Modul 1). Läuft linear über die Statements,
    weil derselbe Hilfsvariablen-Name (z.B. '_color') zwischen mehreren
    Widget-Blöcken wiederverwendet wird - die Zuordnung ist daher nur in
    Programmreihenfolge korrekt auflösbar."""
    color_vars: dict[str, str] = {}
    effects: dict[str, dict] = {}

    def resolve_color(arg: ast.AST) -> Optional[str]:
        if isinstance(arg, ast.Name):
            return color_vars.get(arg.id)
        if (isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name)
                and arg.func.id == "QColor" and arg.args
                and isinstance(arg.args[0], ast.Constant)):
            return arg.args[0].value
        return None

    def const_num(arg: ast.AST):
        return arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)) else None

    for stmt in statements:
        # '<var> = QColor("#hex")'
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)
                and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name)
                and stmt.value.func.id == "QColor" and stmt.value.args
                and isinstance(stmt.value.args[0], ast.Constant)):
            color_vars[stmt.targets[0].id] = stmt.value.args[0].value
            continue

        # 'self.<name>_effect = QGraphicsXxxEffect()'
        if (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Attribute)
                and isinstance(stmt.targets[0].value, ast.Name) and stmt.targets[0].value.id == "self"
                and isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name)
                and stmt.value.func.id in _EFFECT_CLASS_KIND):
            effects[stmt.targets[0].attr] = {
                "kind": _EFFECT_CLASS_KIND[stmt.value.func.id],
                "color": None, "blur": None, "offset": (0, 0), "strength": None,
            }
            continue

        hit = _self_attr_call(stmt)
        if hit is None:
            continue
        name, method, args = hit

        if name in effects and method == "setColor" and args:
            color = resolve_color(args[0])
            if color:
                effects[name]["color"] = color
        elif name in effects and method == "setBlurRadius" and args:
            val = const_num(args[0])
            if val is not None:
                effects[name]["blur"] = val
        elif name in effects and method == "setOffset" and len(args) == 2:
            ox, oy = const_num(args[0]), const_num(args[1])
            if ox is not None and oy is not None:
                effects[name]["offset"] = (int(ox), int(oy))
        elif name in effects and method == "setStrength" and args:
            val = const_num(args[0])
            if val is not None:
                effects[name]["strength"] = float(val) * 100.0
        elif name in effects and method == "setOpacity" and args:
            val = const_num(args[0])
            if val is not None:
                effects[name]["strength"] = (1.0 - float(val)) * 100.0
        elif method == "setGraphicsEffect" and args:
            arg = args[0]
            if not (isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name)
                    and arg.value.id == "self"):
                continue
            effect_name = arg.attr
            info = effects.get(effect_name)
            spec = specs_by_name.get(name)
            if info is None or spec is None:
                continue
            spec.effect_type = info["kind"]
            if info["kind"] == "glow":
                blur = info["blur"] or 0
                spec.effect_strength = max(0, min(100, round(blur / 0.6)))
                spec.effect_color = info["color"] or spec.effect_color
                spec.shadow_offset_x, spec.shadow_offset_y = info["offset"]
            elif info["kind"] == "blur":
                blur = info["blur"] or 0
                spec.effect_strength = max(0, min(100, round(blur / 0.3)))
            elif info["kind"] == "colorize":
                spec.effect_color = info["color"] or spec.effect_color
                spec.effect_strength = max(0, min(100, round(info["strength"] or 0)))
            elif info["kind"] == "opacity":
                spec.effect_strength = max(0, min(100, round(info["strength"] or 0)))


def parse_source_to_specs(source_code: str) -> list["WidgetSpec"]:
    """Parst kompletten Python-Quellcode (typischerweise von generate_code()
    erzeugt, aber auch von Hand editierter Code funktioniert best-effort)
    zurück in eine Liste von WidgetSpec - das vollständige Gegenstück zu
    generate_code(). Wird sowohl vom AstParseWorker (Editor: Datei öffnen)
    als auch für Tests direkt genutzt."""
    tree = ast.parse(source_code)
    statements = list(_flatten_statements(tree))
    specs_by_name: dict[str, WidgetSpec] = {}
    cursor_y = 20

    # 1) self.<name> = <WidgetKlasse>(...) -> Basis-Specs (Typ, Name, Platzhalter-Geometrie)
    for stmt in statements:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
            continue
        target = stmt.targets[0]
        if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == "self"):
            continue
        call = stmt.value
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)):
            continue
        widget_type = call.func.id
        if widget_type not in WIDGET_CLASSES:
            continue
        object_name = target.attr
        default_w, default_h = DEFAULT_SIZES.get(widget_type, (120, 30))
        specs_by_name[object_name] = WidgetSpec(
            uid=str(uuid.uuid4()), widget_type=widget_type, object_name=object_name,
            x=20, y=cursor_y, w=default_w, h=default_h,
        )
        cursor_y += default_h + 14

    # 2) setGeometry(x, y, w, h)
    for stmt in statements:
        hit = _self_attr_call(stmt)
        if hit is None:
            continue
        name, method, args = hit
        if method != "setGeometry" or name not in specs_by_name or len(args) != 4:
            continue
        values = [a.value for a in args if isinstance(a, ast.Constant) and isinstance(a.value, int)]
        if len(values) == 4:
            spec = specs_by_name[name]
            spec.x, spec.y, spec.w, spec.h = values

    # 3) Text, Optik-Stylesheet, Ausrichtung, Grafik-Effekte
    _parse_text_calls(statements, specs_by_name)
    _parse_stylesheet_calls(statements, specs_by_name)
    _parse_alignment_calls(statements, specs_by_name)
    _parse_effect_blocks(statements, specs_by_name)

    return list(specs_by_name.values())


# Erkennungsmuster für Layout-Manager / Container-Konstrukte, die der
# Formular-Designer-Parser oben NICHT versteht (er kennt nur direkte
# self.<n> = <Widgetklasse>(...) + setGeometry()). Wird genutzt, um den
# Nutzer zu warnen, statt ihn mit einem leeren/unvollständigen Canvas
# im Unklaren zu lassen.
_LAYOUT_USAGE_PATTERN = re.compile(
    r"\b(QVBoxLayout|QHBoxLayout|QGridLayout|QFormLayout|QSplitter)\s*\("
    r"|\.addLayout\s*\("
    r"|\.setLayout\s*\("
)


def source_uses_layout_managers(source_code: str) -> bool:
    """True, wenn der Code erkennbar mit Qt-Layout-Managern (statt fester
    Positionierung per setGeometry) arbeitet. Solche Dateien lassen sich
    im Formular-Designer-Canvas von UI Forge nur unvollständig abbilden."""
    return bool(_LAYOUT_USAGE_PATTERN.search(source_code))


class AstParseWorker(QThread):
    """Analysiert Python-Quellcode im Hintergrund und extrahiert Widget-Zuweisungen
    der Form `self.<name> = <WidgetKlasse>(...)` inkl. nachfolgender setGeometry-Aufrufe."""

    parsed = pyqtSignal(list)   # list[WidgetSpec]
    failed = pyqtSignal(str)

    def __init__(self, source_code: str, parent=None):
        super().__init__(parent)
        self.source_code = source_code

    def run(self) -> None:
        try:
            specs = parse_source_to_specs(self.source_code)
            self.parsed.emit(specs)
        except Exception as exc:  # AST-Fehler in fehlerhaftem Code abfangen
            self.failed.emit(str(exc))


# ======================================================================
# 3. SYNTAX-HIGHLIGHTER FÜR DEN CODE-EDITOR
# ======================================================================

class PythonHighlighter(QSyntaxHighlighter):
    """Einfaches, performantes Python-Syntax-Highlighting für den Code-Editor."""

    KEYWORDS = [
        "def", "class", "return", "if", "elif", "else", "for", "while", "import",
        "from", "as", "with", "try", "except", "finally", "raise", "pass", "break",
        "continue", "in", "is", "not", "and", "or", "None", "True", "False", "self",
        "lambda", "yield", "global", "nonlocal", "assert", "del",
    ]

    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        keyword_fmt = QTextCharFormat()
        keyword_fmt.setForeground(QColor("#ff00c8"))
        keyword_fmt.setFontWeight(QFont.Weight.Bold)
        for kw in self.KEYWORDS:
            pattern = QRegularExpression(rf"\b{kw}\b")
            self._rules.append((pattern, keyword_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#00e5ff"))
        self._rules.append((QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), string_fmt))
        self._rules.append((QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), string_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#6c7086"))
        comment_fmt.setFontItalic(True)
        self._rules.append((QRegularExpression(r"#[^\n]*"), comment_fmt))

        classdef_fmt = QTextCharFormat()
        classdef_fmt.setForeground(QColor("#c792ea"))
        self._rules.append((QRegularExpression(r"\bclass\s+(\w+)"), classdef_fmt))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


# ======================================================================
# 4. WIDGET-PALETTE (links, Drag-Quelle)
# ======================================================================

class PaletteListWidget(QListWidget):
    """Liste der verfügbaren Widget-Typen; Einträge lassen sich auf den Canvas ziehen."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("palette_list")
        self.setDragEnabled(True)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        for label, widget_type, *_ in PALETTE_DEFINITIONS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, widget_type)
            self.addItem(item)

    def startDrag(self, supportedActions) -> None:
        item = self.currentItem()
        if item is None:
            return
        widget_type = item.data(Qt.ItemDataRole.UserRole)
        mime = QMimeData()
        mime.setData(MIME_WIDGET_TYPE, widget_type.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


# ======================================================================
# 5. DESIGN-CANVAS (Mitte, Drop-Ziel + freie Platzierung)
# ======================================================================

class DesignCanvas(QWidget):
    """Formularfläche: Widgets werden hier per Drag & Drop platziert, verschoben
    und über eine Ecken-Griffleiste in der Größe verändert. Freies Platzieren via
    setGeometry() ist hier architektonisch gewollt (Formular-Designer-Modus)."""

    selection_changed = pyqtSignal(object)   # WidgetSpec | None
    layout_changed = pyqtSignal()            # nach Move/Resize/Add/Remove

    HANDLE_SIZE = 12
    MIN_SIZE = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("design_canvas")
        self.setAcceptDrops(True)
        self.setMinimumSize(500, 400)

        self.widgets: dict[QWidget, WidgetSpec] = {}
        self.selected_widget: Optional[QWidget] = None

        self._drag_mode: Optional[str] = None   # "move" | "resize" | None
        self._press_global = QPoint()
        self._orig_pos = QPoint()
        self._orig_size = (0, 0)

        self.selection_marker = QFrame(self)
        self.selection_marker.setObjectName("selection_marker")
        self.selection_marker.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.selection_marker.setGraphicsEffect(make_glow("#00e5ff", blur=28, alpha=190))
        self.selection_marker.hide()

        self.resize_handle = QFrame(self)
        self.resize_handle.setObjectName("resize_handle")
        self.resize_handle.setFixedSize(self.HANDLE_SIZE, self.HANDLE_SIZE)
        self.resize_handle.setCursor(QCursor(Qt.CursorShape.SizeFDiagCursor))
        self.resize_handle.setGraphicsEffect(make_glow("#ff00c8", blur=18, alpha=220))
        self.resize_handle.hide()
        self.resize_handle.installEventFilter(self)

    # -- Drag & Drop von der Palette -----------------------------------
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_WIDGET_TYPE):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(MIME_WIDGET_TYPE):
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasFormat(MIME_WIDGET_TYPE):
            return
        widget_type = bytes(event.mimeData().data(MIME_WIDGET_TYPE)).decode("utf-8")
        pos = event.position().toPoint()
        self.add_widget(widget_type, pos.x(), pos.y())
        event.acceptProposedAction()

    # -- Widgets erzeugen / entfernen ------------------------------------
    def add_widget(self, widget_type: str, x: int, y: int) -> None:
        cls = WIDGET_CLASSES.get(widget_type)
        if cls is None:
            return
        w, h = DEFAULT_SIZES.get(widget_type, (120, 30))
        instance = cls(self)
        instance.setGeometry(max(0, x - w // 2), max(0, y - h // 2), w, h)
        apply_widget_text(instance, DEFAULT_TEXTS.get(widget_type, ""))
        seed_widget_defaults(instance, widget_type)
        instance.installEventFilter(self)
        instance.show()

        count = sum(1 for s in self.widgets.values() if s.widget_type == widget_type)
        object_name = f"{widget_type[1:].lower()}_{count + 1}"

        spec = WidgetSpec(
            uid=str(uuid.uuid4()), widget_type=widget_type, object_name=object_name,
            x=instance.x(), y=instance.y(), w=w, h=h,
            text=DEFAULT_TEXTS.get(widget_type, ""),
        )
        apply_widget_style(instance, spec)
        self.widgets[instance] = spec
        self.select_widget(instance)
        self.layout_changed.emit()

    def remove_selected(self) -> None:
        if self.selected_widget is None:
            return
        widget = self.selected_widget
        self.widgets.pop(widget, None)
        widget.deleteLater()
        self.select_widget(None)
        self.layout_changed.emit()

    def clear_all(self) -> None:
        for widget in list(self.widgets.keys()):
            widget.deleteLater()
        self.widgets.clear()
        self.select_widget(None)
        self.layout_changed.emit()

    def load_specs(self, specs: list[WidgetSpec]) -> None:
        """Baut den Canvas aus einer Liste von WidgetSpec neu auf (z.B. nach AST-Import)."""
        self.clear_all()
        for spec in specs:
            cls = WIDGET_CLASSES.get(spec.widget_type)
            if cls is None:
                continue
            instance = cls(self)
            instance.setGeometry(spec.x, spec.y, spec.w, spec.h)
            apply_widget_text(instance, spec.text)
            apply_widget_style(instance, spec)
            seed_widget_defaults(instance, spec.widget_type)
            instance.installEventFilter(self)
            instance.show()
            self.widgets[instance] = spec
        self.layout_changed.emit()

    # -- Auswahl ----------------------------------------------------------
    def select_widget(self, widget: Optional[QWidget]) -> None:
        self.selected_widget = widget
        if widget is None:
            self.selection_marker.hide()
            self.resize_handle.hide()
            self.selection_changed.emit(None)
            return
        self._update_selection_visuals()
        self.selection_changed.emit(self.widgets[widget])

    def _update_selection_visuals(self) -> None:
        widget = self.selected_widget
        if widget is None:
            return
        geo = widget.geometry()
        self.selection_marker.setGeometry(geo.adjusted(-3, -3, 3, 3))
        self.selection_marker.show()
        self.selection_marker.raise_()
        self.resize_handle.move(geo.right() - self.HANDLE_SIZE // 2,
                                 geo.bottom() - self.HANDLE_SIZE // 2)
        self.resize_handle.show()
        self.resize_handle.raise_()

    def update_spec_for(self, widget: QWidget) -> None:
        spec = self.widgets.get(widget)
        if spec is None:
            return
        spec.x, spec.y = widget.x(), widget.y()
        spec.w, spec.h = widget.width(), widget.height()

    # -- Maus-Interaktion (Move / Resize) über Event-Filter ---------------
    def eventFilter(self, obj, event) -> bool:
        etype = event.type()

        if obj is self.resize_handle:
            if etype == QEvent.Type.MouseButtonPress:
                self._drag_mode = "resize"
                self._press_global = event.globalPosition().toPoint()
                widget = self.selected_widget
                if widget:
                    self._orig_size = (widget.width(), widget.height())
                return True
            if etype == QEvent.Type.MouseMove and self._drag_mode == "resize":
                self._perform_resize(event.globalPosition().toPoint())
                return True
            if etype == QEvent.Type.MouseButtonRelease and self._drag_mode == "resize":
                self._drag_mode = None
                if self.selected_widget:
                    self.update_spec_for(self.selected_widget)
                self.layout_changed.emit()
                return True

        elif obj in self.widgets:
            if etype == QEvent.Type.MouseButtonPress:
                self.select_widget(obj)
                self._drag_mode = "move"
                self._press_global = event.globalPosition().toPoint()
                self._orig_pos = obj.pos()
                return True
            if etype == QEvent.Type.MouseMove and self._drag_mode == "move" and obj is self.selected_widget:
                self._perform_move(event.globalPosition().toPoint())
                return True
            if etype == QEvent.Type.MouseButtonRelease and self._drag_mode == "move":
                self._drag_mode = None
                self.update_spec_for(obj)
                self.layout_changed.emit()
                return True

        return super().eventFilter(obj, event)

    def _perform_move(self, global_pos: QPoint) -> None:
        widget = self.selected_widget
        if widget is None:
            return
        delta = global_pos - self._press_global
        new_pos = self._orig_pos + delta
        new_x = max(0, min(new_pos.x(), self.width() - widget.width()))
        new_y = max(0, min(new_pos.y(), self.height() - widget.height()))
        widget.move(new_x, new_y)
        self._update_selection_visuals()

    def _perform_resize(self, global_pos: QPoint) -> None:
        widget = self.selected_widget
        if widget is None:
            return
        delta = global_pos - self._press_global
        new_w = max(self.MIN_SIZE, self._orig_size[0] + delta.x())
        new_h = max(self.MIN_SIZE, self._orig_size[1] + delta.y())
        widget.resize(new_w, new_h)
        self._update_selection_visuals()

    def mousePressEvent(self, event) -> None:
        # Klick auf leere Fläche => Auswahl aufheben
        self.select_widget(None)
        super().mousePressEvent(event)


# ======================================================================
# 6. PROPERTIES-PANEL (rechts)
# ======================================================================

class PropertiesPanel(QWidget):
    """Zeigt und bearbeitet die Eigenschaften des aktuell gewählten Canvas-Widgets."""

    spec_edited = pyqtSignal()
    delete_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("properties_panel")
        self._current_widget: Optional[QWidget] = None
        self._current_spec: Optional[WidgetSpec] = None
        self._updating = False
        # Verhindert, dass der Inhalt (viele Formularzeilen) das Panel und damit
        # das ganze Hauptfenster in der Höhe/Breite aufbläht -> Panel bleibt frei
        # skalierbar, überschüssiger Inhalt wandert stattdessen in die Scrollbar.
        self.setMinimumWidth(0)
        self.setMinimumHeight(0)
        self.init_ui()

    def init_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("properties_scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("properties_scroll_content")
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        title = QLabel("Eigenschaften")
        title.setObjectName("panel_title")
        title.setGraphicsEffect(make_glow("#ff00c8", blur=14, alpha=130))
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)

        self.type_label = QLabel("–")
        self.type_label.setObjectName("type_label")
        attach_hover_glow(self.type_label, color="#ff53d6", max_blur=16)
        form.addRow("Typ:", self.type_label)

        self.name_input = QLineEdit()
        self.name_input.setObjectName("name_input")
        self.name_input.editingFinished.connect(self._on_name_changed)
        form.addRow("Objektname:", self.name_input)

        self.text_input = QLineEdit()
        self.text_input.setObjectName("text_input")
        self.text_input.editingFinished.connect(self._on_text_changed)
        form.addRow("Text:", self.text_input)

        self.x_input = QSpinBox()
        self.x_input.setObjectName("x_input")
        self.x_input.setRange(0, 5000)
        self.x_input.valueChanged.connect(self._on_geometry_changed)
        form.addRow("X:", self.x_input)

        self.y_input = QSpinBox()
        self.y_input.setObjectName("y_input")
        self.y_input.setRange(0, 5000)
        self.y_input.valueChanged.connect(self._on_geometry_changed)
        form.addRow("Y:", self.y_input)

        self.w_input = QSpinBox()
        self.w_input.setObjectName("w_input")
        self.w_input.setRange(10, 5000)
        self.w_input.valueChanged.connect(self._on_geometry_changed)
        form.addRow("Breite:", self.w_input)

        self.h_input = QSpinBox()
        self.h_input.setObjectName("h_input")
        self.h_input.setRange(10, 5000)
        self.h_input.valueChanged.connect(self._on_geometry_changed)
        form.addRow("Höhe:", self.h_input)

        layout.addLayout(form)

        optics_title = QLabel("Optik")
        optics_title.setObjectName("panel_title")
        optics_title.setGraphicsEffect(make_glow("#ff00c8", blur=14, alpha=130))
        layout.addWidget(optics_title)

        optics_form = QFormLayout()
        optics_form.setSpacing(8)

        self.border_color_btn = QPushButton()
        self.border_color_btn.setObjectName("border_color_swatch")
        self.border_color_btn.setFixedHeight(26)
        self.border_color_btn.clicked.connect(self._pick_border_color)
        attach_hover_glow(self.border_color_btn, color="#8a2be2", max_blur=22)
        optics_form.addRow("Rahmenfarbe:", self.border_color_btn)

        self.border_style_combo = QComboBox()
        self.border_style_combo.setObjectName("border_style_combo")
        self.border_style_combo.addItem("Durchgezogen", "solid")
        self.border_style_combo.addItem("Gestrichelt", "dashed")
        self.border_style_combo.addItem("Gepunktet", "dotted")
        self.border_style_combo.addItem("Doppelt", "double")
        self.border_style_combo.currentIndexChanged.connect(self._on_style_changed)
        attach_hover_glow(self.border_style_combo, color="#8a2be2", max_blur=16)
        optics_form.addRow("Rahmenstil:", self.border_style_combo)

        self.border_radius_input = QSpinBox()
        self.border_radius_input.setObjectName("border_radius_input")
        self.border_radius_input.setRange(0, 60)
        self.border_radius_input.valueChanged.connect(self._on_style_changed)
        optics_form.addRow("Rahmenradius:", self.border_radius_input)

        bg_row, self.bg_color_btn, self.bg_reset_btn = self._build_color_row(
            self._pick_bg_color, self._reset_bg_color
        )
        optics_form.addRow("Hintergrund:", bg_row)

        self.bg_opacity_input = QSpinBox()
        self.bg_opacity_input.setObjectName("bg_opacity_input")
        self.bg_opacity_input.setRange(0, 100)
        self.bg_opacity_input.setSuffix(" %")
        self.bg_opacity_input.valueChanged.connect(self._on_style_changed)
        optics_form.addRow("Hintergrund-Deckkraft:", self.bg_opacity_input)

        text_row, self.text_color_btn, self.text_reset_btn = self._build_color_row(
            self._pick_text_color, self._reset_text_color
        )
        optics_form.addRow("Textfarbe:", text_row)

        self.font_size_input = QSpinBox()
        self.font_size_input.setObjectName("font_size_input")
        self.font_size_input.setRange(0, 48)
        self.font_size_input.setSpecialValueText("Standard")
        self.font_size_input.setSuffix(" px")
        self.font_size_input.valueChanged.connect(self._on_style_changed)
        optics_form.addRow("Schriftgröße:", self.font_size_input)

        font_style_row = QWidget()
        font_style_layout = QHBoxLayout(font_style_row)
        font_style_layout.setContentsMargins(0, 0, 0, 0)
        font_style_layout.setSpacing(14)
        self.bold_checkbox = QCheckBox("Fett")
        self.bold_checkbox.setObjectName("bold_checkbox")
        self.bold_checkbox.stateChanged.connect(self._on_style_changed)
        self.italic_checkbox = QCheckBox("Kursiv")
        self.italic_checkbox.setObjectName("italic_checkbox")
        self.italic_checkbox.stateChanged.connect(self._on_style_changed)
        self.underline_checkbox = QCheckBox("Unterstr.")
        self.underline_checkbox.setObjectName("underline_checkbox")
        self.underline_checkbox.stateChanged.connect(self._on_style_changed)
        font_style_layout.addWidget(self.bold_checkbox)
        font_style_layout.addWidget(self.italic_checkbox)
        font_style_layout.addWidget(self.underline_checkbox)
        font_style_layout.addStretch()
        optics_form.addRow("Schriftstil:", font_style_row)

        self.align_combo = QComboBox()
        self.align_combo.setObjectName("align_combo")
        self.align_combo.addItem("Links", "left")
        self.align_combo.addItem("Mitte", "center")
        self.align_combo.addItem("Rechts", "right")
        self.align_combo.currentIndexChanged.connect(self._on_style_changed)
        attach_hover_glow(self.align_combo, color="#00e5ff", max_blur=16)
        optics_form.addRow("Ausrichtung:", self.align_combo)

        self.padding_input = QSpinBox()
        self.padding_input.setObjectName("padding_input")
        self.padding_input.setRange(0, 40)
        self.padding_input.setSuffix(" px")
        self.padding_input.valueChanged.connect(self._on_style_changed)
        optics_form.addRow("Innenabstand:", self.padding_input)

        self.effect_combo = QComboBox()
        self.effect_combo.setObjectName("effect_combo")
        self.effect_combo.addItem("Kein Effekt", "none")
        self.effect_combo.addItem("Glow (Schatten)", "glow")
        self.effect_combo.addItem("Blur (Unschärfe)", "blur")
        self.effect_combo.addItem("Einfärbung", "colorize")
        self.effect_combo.addItem("Transparenz", "opacity")
        self.effect_combo.currentIndexChanged.connect(self._on_effect_type_changed)
        attach_hover_glow(self.effect_combo, color="#ff00c8", max_blur=18)
        optics_form.addRow("Effekt:", self.effect_combo)

        self.effect_color_label = QLabel("Effekt-Farbe:")
        self.effect_color_btn = QPushButton()
        self.effect_color_btn.setObjectName("effect_color_swatch")
        self.effect_color_btn.setFixedHeight(26)
        self.effect_color_btn.clicked.connect(self._pick_effect_color)
        attach_hover_glow(self.effect_color_btn, color="#ff00c8", max_blur=22)
        optics_form.addRow(self.effect_color_label, self.effect_color_btn)

        self.effect_strength_input = QSpinBox()
        self.effect_strength_input.setObjectName("effect_strength_input")
        self.effect_strength_input.setRange(0, 100)
        self.effect_strength_input.setSuffix(" %")
        self.effect_strength_input.valueChanged.connect(self._on_effect_strength_changed)
        optics_form.addRow("Effekt-Stärke:", self.effect_strength_input)

        self.shadow_offset_label = QLabel("Schatten-Versatz:")
        shadow_row = QWidget()
        shadow_layout = QHBoxLayout(shadow_row)
        shadow_layout.setContentsMargins(0, 0, 0, 0)
        shadow_layout.setSpacing(6)
        self.shadow_x_input = QSpinBox()
        self.shadow_x_input.setObjectName("shadow_x_input")
        self.shadow_x_input.setRange(-60, 60)
        self.shadow_x_input.setPrefix("X ")
        self.shadow_x_input.valueChanged.connect(self._on_style_changed)
        self.shadow_y_input = QSpinBox()
        self.shadow_y_input.setObjectName("shadow_y_input")
        self.shadow_y_input.setRange(-60, 60)
        self.shadow_y_input.setPrefix("Y ")
        self.shadow_y_input.valueChanged.connect(self._on_style_changed)
        shadow_layout.addWidget(self.shadow_x_input)
        shadow_layout.addWidget(self.shadow_y_input)
        self.shadow_row = shadow_row
        optics_form.addRow(self.shadow_offset_label, shadow_row)

        layout.addLayout(optics_form)
        layout.addStretch()

        self.delete_btn = QPushButton("Widget löschen")
        self.delete_btn.setObjectName("delete_btn")
        self.delete_btn.clicked.connect(self.delete_requested.emit)
        attach_hover_glow(self.delete_btn, color="#ff2f7a", max_blur=28)
        layout.addWidget(self.delete_btn)

        self.set_enabled_state(False)

    def set_enabled_state(self, enabled: bool) -> None:
        for w in (self.name_input, self.text_input, self.x_input,
                  self.y_input, self.w_input, self.h_input, self.delete_btn,
                  self.border_color_btn, self.border_style_combo, self.border_radius_input,
                  self.bg_color_btn, self.bg_reset_btn, self.bg_opacity_input,
                  self.text_color_btn, self.text_reset_btn,
                  self.font_size_input, self.bold_checkbox, self.italic_checkbox,
                  self.underline_checkbox, self.align_combo, self.padding_input,
                  self.effect_combo, self.effect_strength_input):
            w.setEnabled(enabled)
        show_color = enabled and self.effect_combo.currentData() in ("glow", "colorize")
        self.effect_color_btn.setEnabled(show_color)
        self.effect_color_label.setVisible(show_color)
        self.effect_color_btn.setVisible(show_color)
        show_shadow = enabled and self.effect_combo.currentData() == "glow"
        self.shadow_offset_label.setVisible(show_shadow)
        self.shadow_row.setVisible(show_shadow)

    @staticmethod
    def _build_color_row(pick_slot, reset_slot) -> tuple[QWidget, QPushButton, QPushButton]:
        """Baut eine Farbauswahl-Zeile: Swatch-Button + kleiner Reset-Button
        (setzt die Farbe zurück auf 'Theme-Standard', also keinen Override)."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        swatch = QPushButton()
        swatch.setFixedHeight(26)
        swatch.clicked.connect(pick_slot)
        attach_hover_glow(swatch, color="#00e5ff", max_blur=20)
        reset_btn = QPushButton("✕")
        reset_btn.setObjectName("color_reset_btn")
        reset_btn.setFixedSize(26, 26)
        reset_btn.setToolTip("Zurücksetzen auf Theme-Standard")
        attach_hover_glow(reset_btn, color="#ff53d6", max_blur=16)
        reset_btn.clicked.connect(reset_slot)
        row.addWidget(swatch, 1)
        row.addWidget(reset_btn)
        return container, swatch, reset_btn

    def load(self, widget: Optional[QWidget], spec: Optional[WidgetSpec]) -> None:
        self._current_widget = widget
        self._current_spec = spec
        self._updating = True
        if spec is None:
            self.type_label.setText("–")
            self.name_input.clear()
            self.text_input.clear()
            for sb in (self.x_input, self.y_input, self.w_input, self.h_input):
                sb.setValue(0)
            self._set_swatch(self.border_color_btn, "#3a2a55")
            self.border_style_combo.setCurrentIndex(0)
            self.border_radius_input.setValue(8)
            self._set_swatch(self.bg_color_btn, "")
            self.bg_opacity_input.setValue(100)
            self._set_swatch(self.text_color_btn, "")
            self.font_size_input.setValue(0)
            self.bold_checkbox.setChecked(False)
            self.italic_checkbox.setChecked(False)
            self.underline_checkbox.setChecked(False)
            self.align_combo.setCurrentIndex(0)
            self.padding_input.setValue(0)
            self.effect_combo.setCurrentIndex(0)
            self._set_swatch(self.effect_color_btn, "#00e5ff")
            self.effect_strength_input.setValue(0)
            self.shadow_x_input.setValue(0)
            self.shadow_y_input.setValue(0)
            self.set_enabled_state(False)
        else:
            self.type_label.setText(spec.widget_type)
            self.name_input.setText(spec.object_name)
            self.text_input.setText(spec.text)
            self.x_input.setValue(spec.x)
            self.y_input.setValue(spec.y)
            self.w_input.setValue(spec.w)
            self.h_input.setValue(spec.h)
            self._set_swatch(self.border_color_btn, spec.border_color)
            style_idx = self.border_style_combo.findData(spec.border_style)
            self.border_style_combo.setCurrentIndex(style_idx if style_idx >= 0 else 0)
            self.border_radius_input.setValue(spec.border_radius)
            self._set_swatch(self.bg_color_btn, spec.background_color)
            self.bg_opacity_input.setValue(spec.bg_opacity)
            self._set_swatch(self.text_color_btn, spec.text_color)
            self.font_size_input.setValue(spec.font_size)
            self.bold_checkbox.setChecked(spec.font_bold)
            self.italic_checkbox.setChecked(spec.font_italic)
            self.underline_checkbox.setChecked(spec.underline)
            align_idx = self.align_combo.findData(spec.text_align)
            self.align_combo.setCurrentIndex(align_idx if align_idx >= 0 else 0)
            self.padding_input.setValue(spec.padding)
            idx = self.effect_combo.findData(spec.effect_type)
            self.effect_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self._set_swatch(self.effect_color_btn, spec.effect_color)
            self.effect_strength_input.setValue(spec.effect_strength)
            self.shadow_x_input.setValue(spec.shadow_offset_x)
            self.shadow_y_input.setValue(spec.shadow_offset_y)
            self.set_enabled_state(True)
        self._updating = False

    @staticmethod
    def _set_swatch(button: QPushButton, color_hex: str) -> None:
        if color_hex:
            button.setStyleSheet(
                f"background-color: {color_hex}; border: 1px solid #3a2a55; border-radius: 6px;"
            )
            button.setText(color_hex)
        else:
            button.setStyleSheet(
                "background-color: #12121f; border: 1px dashed #3a2a55; border-radius: 6px; color: #7a7a92;"
            )
            button.setText("Standard")

    def _on_name_changed(self) -> None:
        if self._current_spec is None or self._updating:
            return
        self._current_spec.object_name = self.name_input.text().strip() or self._current_spec.object_name
        self.spec_edited.emit()

    def _on_text_changed(self) -> None:
        if self._current_spec is None or self._current_widget is None or self._updating:
            return
        self._current_spec.text = self.text_input.text()
        apply_widget_text(self._current_widget, self._current_spec.text)
        self.spec_edited.emit()

    def _on_geometry_changed(self) -> None:
        if self._current_spec is None or self._current_widget is None or self._updating:
            return
        x, y = self.x_input.value(), self.y_input.value()
        w, h = self.w_input.value(), self.h_input.value()
        self._current_widget.setGeometry(x, y, w, h)
        self._current_spec.x, self._current_spec.y = x, y
        self._current_spec.w, self._current_spec.h = w, h
        self.spec_edited.emit()

    def _pick_border_color(self) -> None:
        if self._current_spec is None:
            return
        color = QColorDialog.getColor(QColor(self._current_spec.border_color), self, "Rahmenfarbe wählen")
        if not color.isValid():
            return
        self._current_spec.border_color = color.name()
        self._set_swatch(self.border_color_btn, color.name())
        self._push_style()

    def _pick_effect_color(self) -> None:
        if self._current_spec is None:
            return
        color = QColorDialog.getColor(QColor(self._current_spec.effect_color), self, "Effekt-Farbe wählen")
        if not color.isValid():
            return
        self._current_spec.effect_color = color.name()
        self._set_swatch(self.effect_color_btn, color.name())
        self._push_style()

    def _on_effect_type_changed(self) -> None:
        if self._current_spec is None or self._updating:
            return
        self._current_spec.effect_type = self.effect_combo.currentData()
        self.set_enabled_state(True)
        self._push_style()

    def _on_effect_strength_changed(self) -> None:
        if self._current_spec is None or self._updating:
            return
        self._current_spec.effect_strength = self.effect_strength_input.value()
        self._push_style()

    def _pick_bg_color(self) -> None:
        if self._current_spec is None:
            return
        start = self._current_spec.background_color or "#101018"
        color = QColorDialog.getColor(QColor(start), self, "Hintergrundfarbe wählen")
        if not color.isValid():
            return
        self._current_spec.background_color = color.name()
        self._set_swatch(self.bg_color_btn, color.name())
        self._push_style()

    def _reset_bg_color(self) -> None:
        if self._current_spec is None:
            return
        self._current_spec.background_color = ""
        self._set_swatch(self.bg_color_btn, "")
        self._push_style()

    def _pick_text_color(self) -> None:
        if self._current_spec is None:
            return
        start = self._current_spec.text_color or "#e6e6f0"
        color = QColorDialog.getColor(QColor(start), self, "Textfarbe wählen")
        if not color.isValid():
            return
        self._current_spec.text_color = color.name()
        self._set_swatch(self.text_color_btn, color.name())
        self._push_style()

    def _reset_text_color(self) -> None:
        if self._current_spec is None:
            return
        self._current_spec.text_color = ""
        self._set_swatch(self.text_color_btn, "")
        self._push_style()

    def _on_style_changed(self) -> None:
        if self._current_spec is None or self._updating:
            return
        self._current_spec.border_radius = self.border_radius_input.value()
        self._current_spec.border_style = self.border_style_combo.currentData()
        self._current_spec.bg_opacity = self.bg_opacity_input.value()
        self._current_spec.font_size = self.font_size_input.value()
        self._current_spec.font_bold = self.bold_checkbox.isChecked()
        self._current_spec.font_italic = self.italic_checkbox.isChecked()
        self._current_spec.underline = self.underline_checkbox.isChecked()
        self._current_spec.text_align = self.align_combo.currentData()
        self._current_spec.padding = self.padding_input.value()
        self._current_spec.shadow_offset_x = self.shadow_x_input.value()
        self._current_spec.shadow_offset_y = self.shadow_y_input.value()
        self._push_style()

    def _push_style(self) -> None:
        if self._current_widget is None or self._current_spec is None:
            return
        apply_widget_style(self._current_widget, self._current_spec)
        self.spec_edited.emit()


# ======================================================================
# 7. CODE-GENERATOR
# ======================================================================

# ----------------------------------------------------------------------
# Basis-Theme für EXPORTIERTEN Code / Vorschau.
#
# WICHTIG: Der Canvas-Look kommt nicht nur aus den Instanz-Stylesheets der
# einzelnen Widgets (build_stylesheet/apply_widget_style), sondern zu einem
# großen Teil aus dem GLOBALEN STYLE_SHEET, das im Editor auf das ganze
# MainWindow gesetzt wird (siehe STYLE_SHEET unten) und auf alle Canvas-
# Widgets herabkaskadiert (Standardfarben für QPushButton, QLineEdit,
# QCheckBox, QProgressBar, ...). generate_code() hat dieses globale Theme
# bisher NICHT mit exportiert -> exportierter Code / "Vorschau ausführen"
# sah dadurch für alle nicht explizit im Properties-Panel überschriebenen
# Eigenschaften komplett anders aus als der Canvas (Standard-Qt-Grau statt
# Pandora-Theme). Diese Konstante enthält deshalb die typselektor-basierten
# (also NICHT editor-chrome-spezifischen) Regeln aus STYLE_SHEET als
# eigenständige Kopie, damit sie unabhängig vom Editor-UI in generierten
# Code eingebettet werden kann.
# ----------------------------------------------------------------------
EXPORT_THEME_QSS = """
QMainWindow, #central_widget {
    background-color: #0b0b12;
}

QWidget {
    color: #e6e6f0;
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #181828;
    border: 1px solid #3a2a55;
    border-radius: 8px;
    padding: 6px 9px;
    selection-background-color: #8a2be2;
}

QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {
    border: 1px solid #5a3a75;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QTextEdit:focus, QPlainTextEdit:focus {
    border: 2px solid #00e5ff;
    padding: 5px 8px;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 #201a35, stop:1 #17122a);
    border: 1px solid #3a2a55;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    color: #e6e6f0;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 #2e1a45, stop:1 #241035);
    border: 1px solid #ff00c8;
    color: #ff53d6;
}

QPushButton:pressed {
    background-color: #350f45;
    border: 1px solid #ff53d6;
}

QCheckBox, QRadioButton {
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #3a2a55;
    background-color: #181828;
}

QCheckBox::indicator {
    border-radius: 4px;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #00e5ff;
    border: 1px solid #00e5ff;
}

QProgressBar {
    background-color: #181828;
    border: 1px solid #3a2a55;
    border-radius: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 #8a2be2, stop:1 #ff00c8);
    border-radius: 8px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #2a2a45;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #00e5ff;
    width: 15px;
    margin: -6px 0;
    border-radius: 8px;
    border: 1px solid #0b0b12;
}

QGroupBox {
    border: 1px solid #3a2a55;
    border-radius: 10px;
    margin-top: 12px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #00e5ff;
}
"""


def generate_code(specs: list[WidgetSpec], class_name: str = "GeneratedWindow") -> str:
    """Erzeugt vollständigen, lauffähigen PyQt6-Code aus den Canvas-WidgetSpecs.

    HINWEIS: setGeometry() wird hier bewusst genutzt (Formular-Designer-Ausgabe,
    analog zu Qt Designer ohne Layout). Für produktiven Code empfiehlt sich das
    spätere manuelle Überführen in QVBoxLayout/QGridLayout.
    """
    used_types = sorted({EXPORT_CLASS_NAMES.get(s.widget_type, s.widget_type) for s in specs}) or ["QWidget"]

    def _has_effect(kind: str) -> bool:
        return any(s.effect_type == kind and s.effect_strength > 0 for s in specs)

    ALIGNMENT_CAPABLE = {"QLabel", "QLineEdit", "QProgressBar"}
    ALIGN_EXPR = {
        "left": "Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter",
        "center": "Qt.AlignmentFlag.AlignCenter",
        "right": "Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter",
    }
    needs_glow = _has_effect("glow")
    needs_blur = _has_effect("blur")
    needs_colorize = _has_effect("colorize")
    needs_opacity = _has_effect("opacity")
    needs_color_import = needs_glow or needs_colorize
    needs_alignment = any(
        EXPORT_CLASS_NAMES.get(s.widget_type, s.widget_type) in ALIGNMENT_CAPABLE for s in specs
    )
    needs_qt_core = needs_alignment or any(spec.widget_type == "QScrollBar" for spec in specs)
    needs_tree_item = any(spec.widget_type == "QTreeWidget" for spec in specs)
    needs_frame = any(spec.widget_type == "QSplitter" for spec in specs)

    widgets_imports = ["QApplication", "QMainWindow", "QWidget"] + used_types
    if needs_glow:
        widgets_imports.append("QGraphicsDropShadowEffect")
    if needs_blur:
        widgets_imports.append("QGraphicsBlurEffect")
    if needs_colorize:
        widgets_imports.append("QGraphicsColorizeEffect")
    if needs_opacity:
        widgets_imports.append("QGraphicsOpacityEffect")
    if needs_tree_item:
        widgets_imports.append("QTreeWidgetItem")
    if needs_frame and "QFrame" not in widgets_imports:
        widgets_imports.append("QFrame")
    imports_line = f"from PyQt6.QtWidgets import {', '.join(widgets_imports)}"

    lines = [
        "#!/usr/bin/env python3",
        '"""Automatisch generiert mit Pandora® UI Forge."""',
        "",
        "import sys",
        imports_line,
    ]
    if needs_color_import:
        lines.append("from PyQt6.QtGui import QColor")
    if needs_qt_core:
        lines.append("from PyQt6.QtCore import Qt")
    lines += [
        "",
        "",
        f"class {class_name}(QMainWindow):",
        f'    """Mit Pandora® UI Forge entworfenes Fenster."""',
        "",
        "    def __init__(self):",
        "        super().__init__()",
        f'        self.setWindowTitle("{class_name}")',
        "        self.resize(800, 600)",
        "        self.init_ui()",
        "",
        "    def init_ui(self) -> None:",
        "        central_widget = QWidget()",
        '        central_widget.setObjectName("central_widget")',
        "        self.setCentralWidget(central_widget)",
        f'        self.setStyleSheet("""{EXPORT_THEME_QSS}""")',
        "",
    ]

    if not specs:
        lines.append("        # (noch keine Widgets auf dem Canvas platziert)")
    for spec in specs:
        export_class = EXPORT_CLASS_NAMES.get(spec.widget_type, spec.widget_type)
        lines.append(f"        self.{spec.object_name} = {export_class}(central_widget)")
        if spec.text and spec.widget_type == "QGroupBox":
            escaped = spec.text.replace('"', '\\"')
            lines.append(f'        self.{spec.object_name}.setTitle("{escaped}")')
        elif spec.text and spec.widget_type in ("QTextEdit", "QPlainTextEdit"):
            escaped = spec.text.replace('"', '\\"')
            lines.append(f'        self.{spec.object_name}.setPlainText("{escaped}")')
        elif spec.text and export_class in [c.__name__ for c in TEXT_SETTER_WIDGETS]:
            escaped = spec.text.replace('"', '\\"')
            lines.append(f'        self.{spec.object_name}.setText("{escaped}")')
        if spec.widget_type == "QTableWidget":
            lines.append(f"        self.{spec.object_name}.setRowCount(3)")
            lines.append(f"        self.{spec.object_name}.setColumnCount(3)")
        elif spec.widget_type == "QListWidget":
            lines.append(f'        self.{spec.object_name}.addItems(["Eintrag 1", "Eintrag 2", "Eintrag 3"])')
        elif spec.widget_type == "QTabWidget":
            lines.append(f"        self.{spec.object_name}.addTab(QWidget(), \"Tab 1\")")
            lines.append(f"        self.{spec.object_name}.addTab(QWidget(), \"Tab 2\")")
        elif spec.widget_type == "QScrollBar":
            lines.append(f"        self.{spec.object_name}.setOrientation(Qt.Orientation.Horizontal)")
        elif spec.widget_type == "QDialogButtonBox":
            lines.append(
                f"        self.{spec.object_name}.setStandardButtons("
                f"QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)"
            )
        elif spec.widget_type == "QTreeWidget":
            lines.append(f'        self.{spec.object_name}.setHeaderLabels(["Name", "Typ"])')
            lines.append(f"        _top = QTreeWidgetItem([\"Ordner\", \"Verzeichnis\"])")
            lines.append(f'        _top.addChild(QTreeWidgetItem(["datei.txt", "Text"]))')
            lines.append(f"        self.{spec.object_name}.addTopLevelItem(_top)")
            lines.append(f"        self.{spec.object_name}.expandAll()")
        elif spec.widget_type == "QSplitter":
            lines.append(f"        self.{spec.object_name}.addWidget(QFrame())")
            lines.append(f"        self.{spec.object_name}.addWidget(QFrame())")
        elif spec.widget_type == "QStackedWidget":
            lines.append(f"        self.{spec.object_name}.addWidget(QWidget())")
            lines.append(f"        self.{spec.object_name}.addWidget(QWidget())")
        elif spec.widget_type == "QToolBox":
            lines.append(f"        self.{spec.object_name}.addItem(QWidget(), \"Seite 1\")")
            lines.append(f"        self.{spec.object_name}.addItem(QWidget(), \"Seite 2\")")
        elif spec.widget_type == "QScrollArea":
            lines.append(f"        self.{spec.object_name}_inner = QWidget()")
            lines.append(f"        self.{spec.object_name}_inner.setMinimumSize(400, 400)")
            lines.append(f"        self.{spec.object_name}.setWidget(self.{spec.object_name}_inner)")
            lines.append(f"        self.{spec.object_name}.setWidgetResizable(True)")
        elif spec.widget_type == "QLineEdit_Password":
            lines.append(f"        self.{spec.object_name}.setEchoMode(QLineEdit.EchoMode.Password)")
            lines.append(f'        self.{spec.object_name}.setPlaceholderText("Passwort")')
        elif spec.widget_type == "QLineEdit_Search":
            lines.append(f"        self.{spec.object_name}.setClearButtonEnabled(True)")
            lines.append(f'        self.{spec.object_name}.setPlaceholderText("Suchen …")')
        elif spec.widget_type == "QFrame_HLine":
            lines.append(f"        self.{spec.object_name}.setFrameShape(QFrame.Shape.HLine)")
            lines.append(f"        self.{spec.object_name}.setFrameShadow(QFrame.Shadow.Sunken)")
        elif spec.widget_type == "QFrame_VLine":
            lines.append(f"        self.{spec.object_name}.setFrameShape(QFrame.Shape.VLine)")
            lines.append(f"        self.{spec.object_name}.setFrameShadow(QFrame.Shadow.Sunken)")
        lines.append(
            f"        self.{spec.object_name}.setGeometry"
            f"({spec.x}, {spec.y}, {spec.w}, {spec.h})"
        )
        # Rahmen / Hintergrund / Text / Schrift (individuell im Properties-Panel gesetzt)
        style_css = build_stylesheet(spec).replace('"', '\\"')
        lines.append(f'        self.{spec.object_name}.setStyleSheet("{style_css}")')
        if export_class in ALIGNMENT_CAPABLE:
            lines.append(f"        self.{spec.object_name}.setAlignment({ALIGN_EXPR[spec.text_align]})")
        if spec.effect_type == "glow" and spec.effect_strength > 0:
            blur = max(4, int(spec.effect_strength * 0.6))
            name = spec.object_name
            lines.append(f"        self.{name}_effect = QGraphicsDropShadowEffect()")
            lines.append(f'        _color = QColor("{spec.effect_color}")')
            lines.append("        _color.setAlpha(210)")
            lines.append(f"        self.{name}_effect.setColor(_color)")
            lines.append(f"        self.{name}_effect.setBlurRadius({blur})")
            lines.append(f"        self.{name}_effect.setOffset({spec.shadow_offset_x}, {spec.shadow_offset_y})")
            lines.append(f"        self.{name}.setGraphicsEffect(self.{name}_effect)")
        elif spec.effect_type == "blur" and spec.effect_strength > 0:
            name = spec.object_name
            radius = max(1.0, spec.effect_strength * 0.3)
            lines.append(f"        self.{name}_effect = QGraphicsBlurEffect()")
            lines.append(f"        self.{name}_effect.setBlurRadius({radius})")
            lines.append(f"        self.{name}.setGraphicsEffect(self.{name}_effect)")
        elif spec.effect_type == "colorize" and spec.effect_strength > 0:
            name = spec.object_name
            strength = spec.effect_strength / 100.0
            lines.append(f"        self.{name}_effect = QGraphicsColorizeEffect()")
            lines.append(f'        self.{name}_effect.setColor(QColor("{spec.effect_color}"))')
            lines.append(f"        self.{name}_effect.setStrength({strength:.2f})")
            lines.append(f"        self.{name}.setGraphicsEffect(self.{name}_effect)")
        elif spec.effect_type == "opacity" and spec.effect_strength > 0:
            name = spec.object_name
            opacity = max(0.0, 1.0 - spec.effect_strength / 100.0)
            lines.append(f"        self.{name}_effect = QGraphicsOpacityEffect()")
            lines.append(f"        self.{name}_effect.setOpacity({opacity:.2f})")
            lines.append(f"        self.{name}.setGraphicsEffect(self.{name}_effect)")
        lines.append("")

    lines += [
        "",
        'if __name__ == "__main__":',
        "    app = QApplication(sys.argv)",
        f"    window = {class_name}()",
        "    window.show()",
        "    sys.exit(app.exec())",
        "",
    ]
    return "\n".join(lines)


# ======================================================================
# 8. HAUPTFENSTER
# ======================================================================

class MainWindow(QMainWindow):
    """Hauptfenster des Pandora® UI Forge Design-Editors."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pandora® UI Forge — PyQt6 Design-Editor")
        self.resize(1400, 860)

        self._parse_worker: Optional[AstParseWorker] = None
        self._preview_instances: list[QWidget] = []
        self._loaded_file_path: Optional[str] = None
        self._loaded_file_uses_layouts: bool = False

        self.init_ui()
        self.setStyleSheet(STYLE_SHEET)

    # -- UI-Aufbau ----------------------------------------------------
    def init_ui(self) -> None:
        self._build_toolbar()
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Bereit.")

        central = QWidget()
        central.setObjectName("central_widget")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("main_splitter")
        splitter.setHandleWidth(3)

        # -- linke Spalte: Palette -------------------------------------
        palette_container = QWidget()
        palette_layout = QVBoxLayout(palette_container)
        palette_layout.setContentsMargins(12, 12, 12, 12)
        palette_layout.setSpacing(8)
        palette_title = QLabel("Widget-Palette")
        palette_title.setObjectName("panel_title")
        palette_layout.addWidget(palette_title)
        self.palette_list = PaletteListWidget()
        self.palette_list.setGraphicsEffect(make_glow("#8a2be2", blur=20, alpha=110))
        palette_layout.addWidget(self.palette_list)
        hint = QLabel("Ziehe ein Element auf den Canvas.")
        hint.setObjectName("hint_label")
        hint.setWordWrap(True)
        palette_layout.addWidget(hint)

        # -- Mitte: Canvas + Code-Editor als Tabs -----------------------
        center_tabs = QTabWidget()
        center_tabs.setObjectName("center_tabs")

        canvas_wrapper = QWidget()
        canvas_layout = QVBoxLayout(canvas_wrapper)
        canvas_layout.setContentsMargins(12, 12, 12, 12)
        self.canvas = DesignCanvas()
        canvas_layout.addWidget(self.canvas)
        center_tabs.addTab(canvas_wrapper, "🎨 Canvas")

        code_wrapper = QWidget()
        code_layout = QVBoxLayout(code_wrapper)
        code_layout.setContentsMargins(12, 12, 12, 12)
        self.code_editor = QPlainTextEdit()
        self.code_editor.setObjectName("code_editor")
        self.code_editor.setFont(QFont("Consolas", 11))
        PythonHighlighter(self.code_editor.document())
        code_layout.addWidget(self.code_editor)
        center_tabs.addTab(code_wrapper, "💻 Code")

        self.center_tabs = center_tabs

        # -- rechte Spalte: Properties -----------------------------------
        self.properties_panel = PropertiesPanel()
        self.properties_panel.setGraphicsEffect(make_glow("#ff00c8", blur=22, x_offset=-3, alpha=100))

        splitter.addWidget(palette_container)
        splitter.addWidget(center_tabs)
        splitter.addWidget(self.properties_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([220, 900, 280])

        root_layout.addWidget(splitter)

        # -- Signale verbinden --------------------------------------------
        self.canvas.selection_changed.connect(self._on_selection_changed)
        self.canvas.layout_changed.connect(self._on_layout_changed)
        self.properties_panel.spec_edited.connect(self._on_layout_changed)
        self.properties_panel.delete_requested.connect(self.canvas.remove_selected)
        self._delete_action.triggered.disconnect()
        self._delete_action.triggered.connect(self.canvas.remove_selected)

        self._on_layout_changed()  # initialer Code-Preview

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Werkzeuge")
        toolbar.setObjectName("main_toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_action = QAction("Neu", self)
        new_action.triggered.connect(self._on_new)
        toolbar.addAction(new_action)

        open_action = QAction("Öffnen…", self)
        open_action.triggered.connect(self._on_open_file)
        toolbar.addAction(open_action)

        save_action = QAction("Code speichern…", self)
        save_action.triggered.connect(self._on_save_code)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        run_action = QAction("▶ Vorschau ausführen", self)
        run_action.triggered.connect(self._on_run_preview)
        toolbar.addAction(run_action)

        toolbar.addSeparator()

        delete_action = QAction("Auswahl löschen", self)
        delete_action.triggered.connect(lambda: None)  # wird nach Canvas-Erzeugung neu verbunden
        toolbar.addAction(delete_action)
        self._delete_action = delete_action

    # -- Slots ----------------------------------------------------------
    def _on_selection_changed(self, spec: Optional[WidgetSpec]) -> None:
        widget = self.canvas.selected_widget
        self.properties_panel.load(widget, spec)

    def _on_layout_changed(self) -> None:
        specs = list(self.canvas.widgets.values())
        code = generate_code(specs)
        # Nur aktualisieren, wenn der Nutzer nicht gerade manuell im Code-Tab tippt
        if self.center_tabs.currentIndex() == 0:
            self.code_editor.blockSignals(True)
            self.code_editor.setPlainText(code)
            self.code_editor.blockSignals(False)
        self.statusBar().showMessage(f"{len(specs)} Widget(s) auf dem Canvas.")

    def _on_new(self) -> None:
        confirm = QMessageBox.question(
            self, "Neu beginnen",
            "Aktuellen Canvas leeren und neu starten?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.canvas.clear_all()
            self._loaded_file_path = None
            self._loaded_file_uses_layouts = False
            self._on_layout_changed()

    def _on_open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Python-Datei öffnen", "", "Python-Dateien (*.py)")
        if not path:
            return
        self.open_python_file(path)

    def open_python_file(self, path: str) -> None:
        """Lädt eine .py-Datei in den Code-Editor und stößt die Hintergrund-
        Analyse an. Wird sowohl von "Datei öffnen" als auch beim Start mit
        einem Kommandozeilen-Argument (z.B. aus dem Pandora Script Editor
        heraus, Werkzeuge → UI Forge) verwendet."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError as exc:
            QMessageBox.critical(self, "Fehler beim Öffnen", str(exc))
            return

        self._loaded_file_path = path
        self._loaded_file_uses_layouts = source_uses_layout_managers(source)
        self.code_editor.setPlainText(source)
        self.center_tabs.setCurrentIndex(1)
        self.statusBar().showMessage(f"Analysiere {path} …")

        # Analyse im Hintergrund-Thread, damit die UI responsiv bleibt
        self._parse_worker = AstParseWorker(source)
        self._parse_worker.parsed.connect(self._on_parsed)
        self._parse_worker.failed.connect(self._on_parse_failed)
        self._parse_worker.start()

    def _on_parsed(self, specs: list[WidgetSpec]) -> None:
        if specs:
            self.canvas.load_specs(specs)
            self.center_tabs.setCurrentIndex(0)
            self.statusBar().showMessage(f"{len(specs)} Widget(s) aus Datei übernommen.")
        else:
            self.statusBar().showMessage("Keine erkennbaren self.<name> = QWidget(...)-Zuweisungen gefunden.")

        if getattr(self, "_loaded_file_uses_layouts", False):
            n = len(specs)
            QMessageBox.warning(
                self,
                "Layout-basierte Datei erkannt",
                "Diese Datei baut ihre Oberfläche erkennbar mit Qt-Layout-Managern "
                "auf (QVBoxLayout/QHBoxLayout/QGridLayout/QFormLayout/QSplitter, "
                "addLayout()/setLayout()).\n\n"
                "UI Forge ist ein Formular-Designer für absolut positionierte "
                "Widgets (setGeometry) und versteht nur direkte Zuweisungen der "
                f"Form self.<name> = <Widgetklasse>(...). Gefunden wurden hier nur "
                f"{n} Widget(s) - Container, Layouts und ggf. Spezial-Widgets "
                "(z.B. QWebEngineView) fehlen auf dem Canvas.\n\n"
                "WICHTIG: Wird von hier aus gespeichert, generiert UI Forge die "
                "komplette Datei neu als flaches, absolut positioniertes Formular "
                "und überschreibt damit Layout-Struktur, Menüs/Actions und die "
                "restliche Programmlogik der Originaldatei.\n\n"
                "Empfehlung: Nur zur Ansicht/als Ausgangspunkt nutzen und über "
                "\"Speichern unter…\" in eine NEUE Datei exportieren - nicht die "
                "Originaldatei überschreiben.",
            )

    def _on_parse_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Analyse fehlgeschlagen",
                             f"Die Datei konnte nicht analysiert werden:\n{message}")

    def _on_save_code(self) -> None:
        default_path = self._loaded_file_path or "generated_window.py"
        path, _ = QFileDialog.getSaveFileName(self, "Code speichern", default_path, "Python-Dateien (*.py)")
        if not path:
            return

        # Zusätzliche Sicherheitsabfrage: die geladene Originaldatei nutzte
        # Layout-Manager (die UI Forge nicht abbilden kann) und der Nutzer
        # ist dabei, genau diese Datei zu überschreiben -> Layout, Menüs/
        # Actions und restliche Programmlogik würden dabei verloren gehen.
        if (
            self._loaded_file_uses_layouts
            and self._loaded_file_path
            and os.path.abspath(path) == os.path.abspath(self._loaded_file_path)
        ):
            confirm = QMessageBox.warning(
                self,
                "Originaldatei überschreiben?",
                "Die geladene Datei nutzt Qt-Layout-Manager, die UI Forge nicht "
                "unterstützt. Wenn du jetzt hier speicherst, wird die komplette "
                "Datei durch das neu generierte, absolut positionierte Formular "
                "ersetzt - Layout, Menüs/Actions und die restliche Programmlogik "
                "der Originaldatei gehen dabei verloren.\n\n"
                "Wirklich überschreiben? Tipp: Wähle stattdessen einen anderen "
                "Dateinamen, um die Originaldatei zu erhalten.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.code_editor.toPlainText())
        except OSError as exc:
            QMessageBox.critical(self, "Fehler beim Speichern", str(exc))
            return
        self.statusBar().showMessage(f"Gespeichert: {path}")

    def _on_run_preview(self) -> None:
        source = self.code_editor.toPlainText()
        namespace: dict = {}
        try:
            compiled = compile(source, "<pandora_ui_forge_preview>", "exec")
            exec(compiled, namespace)  # noqa: S102 - bewusste Vorschau-Ausführung im Editor
        except Exception:
            QMessageBox.critical(self, "Fehler in der Vorschau", traceback.format_exc())
            return

        window_cls = None
        for value in namespace.values():
            if isinstance(value, type) and issubclass(value, QMainWindow) and value is not QMainWindow:
                window_cls = value
                break

        if window_cls is None:
            QMessageBox.information(
                self, "Keine Klasse gefunden",
                "Es wurde keine QMainWindow-Unterklasse im Code gefunden."
            )
            return

        try:
            instance = window_cls()
            instance.show()
            self._preview_instances.append(instance)  # Referenz halten (kein GC)
        except Exception:
            QMessageBox.critical(self, "Fehler beim Start der Vorschau", traceback.format_exc())


# ======================================================================
# 9. STYLESHEET — Pandora® Cyberpunk Dark Theme
# ======================================================================

STYLE_SHEET = """
QMainWindow, #central_widget {
    background-color: #0b0b12;
}

QWidget {
    color: #e6e6f0;
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
}

#panel_title {
    font-size: 15px;
    font-weight: 700;
    color: #00e5ff;
    padding-bottom: 4px;
}

#hint_label {
    color: #7a7a92;
    font-size: 11px;
}

/* ---------- Toolbar: violette Grundfarbe, magenta Hover-Glow-Border ---------- */
QToolBar#main_toolbar {
    background-color: #101018;
    border: none;
    border-bottom: 1px solid #2a2a45;
    padding: 8px;
    spacing: 8px;
}

QToolBar QToolButton {
    background-color: #17172a;
    color: #e6e6f0;
    border: 1px solid #3a2a55;
    border-radius: 8px;
    padding: 7px 14px;
}

QToolBar QToolButton:hover {
    background-color: #241a3d;
    border: 1px solid #ff00c8;
    color: #ff53d6;
}

QToolBar QToolButton:pressed {
    background-color: #350f45;
    border: 1px solid #ff00c8;
}

QSplitter::handle {
    background-color: #1c1c2e;
}

QSplitter::handle:hover {
    background-color: #8a2be2;
}

/* ---------- Palette (violett) ---------- */
QListWidget#palette_list {
    background-color: #12121f;
    border: 1px solid #3a2a55;
    border-radius: 12px;
    padding: 6px;
}

QListWidget#palette_list::item {
    padding: 9px 10px;
    border-radius: 8px;
    margin: 2px 0px;
    border: 1px solid transparent;
}

QListWidget#palette_list::item:hover {
    background-color: #1c1830;
    color: #00e5ff;
    border: 1px solid #2a2a55;
}

QListWidget#palette_list::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 #2a1740, stop:1 #3a1450);
    color: #ff53d6;
    border: 1px solid #ff00c8;
}

/* ---------- Tabs (Canvas / Code) ---------- */
QTabWidget#center_tabs::pane {
    border: 1px solid #2a2a45;
    border-radius: 12px;
    background-color: #0d0d16;
}

QTabBar::tab {
    background-color: #101018;
    color: #9a9ab0;
    padding: 9px 20px;
    border: 1px solid #23233a;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    margin-right: 3px;
}

QTabBar::tab:hover {
    color: #00e5ff;
}

QTabBar::tab:selected {
    background-color: #1c1830;
    color: #00e5ff;
    border: 1px solid #8a2be2;
    border-bottom: none;
}

/* ---------- Canvas: gestrichelter Cyan-Rahmen, dezentes Raster ---------- */
#design_canvas {
    background-color: #111118;
    background-image:
        linear-gradient(0deg, transparent 24px, #1a1a2b 25px),
        linear-gradient(90deg, transparent 24px, #1a1a2b 25px);
    border: 2px dashed #16788a;
    border-radius: 10px;
}

/* ---------- Auswahl / Resize (Glow kommt aus QGraphicsDropShadowEffect) ---------- */
#selection_marker {
    border: 2px solid #00e5ff;
    border-radius: 5px;
    background: transparent;
}

#resize_handle {
    background-color: #ff00c8;
    border: 1px solid #ffb3ec;
    border-radius: 4px;
}

/* ---------- Properties-Panel (magenta) ---------- */
#properties_panel {
    background-color: #12121f;
    border-left: 1px solid #4a1a3a;
    border-radius: 0px;
}

#properties_scroll, #properties_scroll_content {
    background: transparent;
    border: none;
}

#type_label {
    color: #ff53d6;
    font-weight: 600;
}

/* ---------- Scrollbar der rechten Sidebar (violett -> cyan bei Hover) ---------- */
#properties_scroll QScrollBar:vertical {
    background: #0e0e18;
    width: 11px;
    margin: 2px 2px 2px 0px;
    border-radius: 5px;
}

#properties_scroll QScrollBar::handle:vertical {
    background: #3a2a55;
    min-height: 30px;
    border-radius: 5px;
    border: 1px solid #2a1a3a;
}

#properties_scroll QScrollBar::handle:vertical:hover {
    background: #8a2be2;
    border: 1px solid #00e5ff;
}

#properties_scroll QScrollBar::handle:vertical:pressed {
    background: #ff00c8;
    border: 1px solid #ff53d6;
}

#properties_scroll QScrollBar::add-line:vertical,
#properties_scroll QScrollBar::sub-line:vertical {
    height: 0px;
    border: none;
    background: none;
}

#properties_scroll QScrollBar::add-page:vertical,
#properties_scroll QScrollBar::sub-page:vertical {
    background: none;
}

/* ---------- Zusätzliche Hover-Effekte in der Properties-Sidebar ---------- */
#properties_panel QLabel:hover {
    color: #00e5ff;
}

#properties_panel QSpinBox::up-button,
#properties_panel QSpinBox::down-button {
    background-color: #1c1830;
    border: none;
    width: 16px;
}

#properties_panel QSpinBox::up-button:hover,
#properties_panel QSpinBox::down-button:hover {
    background-color: #8a2be2;
}

#properties_panel QCheckBox::indicator:hover,
#properties_panel QRadioButton::indicator:hover {
    border: 1px solid #00e5ff;
    background-color: #1c1830;
}

#properties_panel QComboBox:hover,
#properties_panel QLineEdit:hover,
#properties_panel QSpinBox:hover {
    border: 1px solid #ff00c8;
}

#panel_title:hover {
    color: #ff53d6;
}

/* ---------- Eingabefelder: violette Ruhe-Border, Cyan-Glow bei Fokus ---------- */
QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {
    background-color: #181828;
    border: 1px solid #3a2a55;
    border-radius: 8px;
    padding: 6px 9px;
    selection-background-color: #8a2be2;
}

QLineEdit:hover, QSpinBox:hover, QComboBox:hover {
    border: 1px solid #5a3a75;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 2px solid #00e5ff;
    padding: 5px 8px;
}

#code_editor {
    border: 1px solid #3a2a55;
    border-radius: 10px;
}

/* ---------- Buttons: violett -> magenta Hover ---------- */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 #201a35, stop:1 #17122a);
    border: 1px solid #3a2a55;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                 stop:0 #2e1a45, stop:1 #241035);
    border: 1px solid #ff00c8;
    color: #ff53d6;
}

QPushButton:pressed {
    background-color: #350f45;
    border: 1px solid #ff53d6;
}

#delete_btn {
    background-color: #2a0f18;
    border: 1px solid #6a1f3a;
    color: #ff6b9d;
}

#delete_btn:hover {
    background-color: #40121f;
    border: 1px solid #ff2f7a;
    color: #ff8fb5;
}

/* Farb-Swatches: eigene Hintergrundfarbe wird per Python gesetzt, hier nur Rahmen/Text fixieren */
#border_color_swatch, #effect_color_swatch {
    font-size: 10px;
    font-weight: 700;
    color: #ffffff;
}

#border_color_swatch:hover, #effect_color_swatch:hover {
    border: 1px solid #00e5ff;
}

QCheckBox, QRadioButton {
    spacing: 8px;
}

QCheckBox::indicator, QRadioButton::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #3a2a55;
    background-color: #181828;
}

QCheckBox::indicator {
    border-radius: 4px;
}

QRadioButton::indicator {
    border-radius: 8px;
}

QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #00e5ff;
    border: 1px solid #00e5ff;
}

QProgressBar {
    background-color: #181828;
    border: 1px solid #3a2a55;
    border-radius: 8px;
    text-align: center;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                 stop:0 #8a2be2, stop:1 #ff00c8);
    border-radius: 8px;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #2a2a45;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #00e5ff;
    width: 15px;
    margin: -6px 0;
    border-radius: 8px;
    border: 1px solid #0b0b12;
}

QStatusBar {
    background-color: #101018;
    color: #7a7a92;
    border-top: 1px solid #2a2a45;
}

QGroupBox {
    border: 1px solid #3a2a55;
    border-radius: 10px;
    margin-top: 12px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #00e5ff;
}
"""


# ======================================================================
# 10. EINSTIEGSPUNKT
# ======================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    # Wird UI Forge mit einem Dateipfad als Argument gestartet (z.B. vom
    # Pandora Script Editor aus über Werkzeuge -> UI Forge, mit aktiver
    # .py-Datei), wird diese Datei automatisch geöffnet und analysiert -
    # genau wie über "Datei öffnen", inkl. der Layout-Warnung falls nötig.
    cli_args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if cli_args:
        window.open_python_file(cli_args[0])

    sys.exit(app.exec())
