#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pandora® - PCB Editor
by AKI_SystemDown® ©2026

Ein PyQt6-basierter Leiterplatten-Editor im Pandora-Cyberpunk-Stil.
Zielplattform: Raspberry Pi 4B (8GB RAM) / Kali Linux.

Architektur (ein-Datei-MVP, modular strukturiert für spätere Aufteilung):
    - PandoraTheme        : Farbpalette & globales Stylesheet
    - Layer / LayerStack  : Layerverwaltung (Top/Bottom Copper, Silk, Drill, Outline)
    - Netlist             : Netz-/Ratsnest-Verwaltung
    - Graphics-Items       : Pad, Via, Trace, Footprint, BoardOutline (QGraphicsItem)
    - PcbScene / PcbView   : QGraphicsScene/View mit Raster, Snap, Zoom
    - LayersDock           : Sichtbarkeit & aktiver Layer
    - PropertiesDock       : Eigenschaften des ausgewählten Elements
    - ProjectIO            : Speichern/Laden als .pandora (JSON)
    - GerberX2Exporter     : vollständiger Gerber-X2- (RS-274X + Attribute)
                             und Excellon-Drill-Export
    - MainWindow           : Menüs, Toolbars, Undo/Redo, Statusleiste
"""

import sys
import json
import math
import heapq
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsScene, QGraphicsView, QGraphicsItem,
    QGraphicsRectItem, QGraphicsEllipseItem, QGraphicsPathItem, QGraphicsLineItem,
    QGraphicsItemGroup, QGraphicsPolygonItem, QDockWidget, QListWidget,
    QListWidgetItem, QToolBar, QStatusBar, QFileDialog, QMessageBox, QLabel,
    QVBoxLayout, QHBoxLayout, QWidget, QFormLayout, QDoubleSpinBox, QComboBox,
    QLineEdit, QPushButton, QCheckBox, QColorDialog, QSpinBox, QGroupBox,
    QButtonGroup, QRadioButton, QSplitter, QTreeWidget, QTreeWidgetItem,
    QMenu, QInputDialog, QToolButton, QSizePolicy, QGraphicsSimpleTextItem,
    QDialog
)
from PyQt6.QtGui import (
    QAction, QColor, QPen, QBrush, QPainter, QPainterPath, QPolygonF, QIcon,
    QKeySequence, QUndoStack, QUndoCommand, QFont, QCursor, QTransform
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF, pyqtSignal, QSizeF


# ─────────────────────────────────────────────────────────────────────────
# THEME - Pandora Cyberpunk Look
# ─────────────────────────────────────────────────────────────────────────

class PandoraTheme:
    BG_DARKEST = "#0a0a12"
    BG_DARK = "#12121c"
    BG_PANEL = "#181826"
    BG_HOVER = "#232338"
    BORDER = "#2e2e44"
    ACCENT_CYAN = "#00e5ff"
    ACCENT_MAGENTA = "#ff2ec4"
    ACCENT_PURPLE = "#8a2eff"
    TEXT_PRIMARY = "#e6f1ff"
    TEXT_MUTED = "#7d86a8"
    COPPER_TOP = "#ff9d2e"
    COPPER_BOTTOM = "#2ec4ff"
    SILK_TOP = "#e6f1ff"
    SILK_BOTTOM = "#c9a0ff"
    DRILL = "#ff2ec4"
    OUTLINE = "#ffd23f"
    GRID_MINOR = "#1c1c2c"
    GRID_MAJOR = "#2a2a44"

    STYLESHEET = f"""
    QMainWindow, QWidget {{
        background-color: {BG_DARK};
        color: {TEXT_PRIMARY};
        font-family: 'Segoe UI', 'Ubuntu', sans-serif;
        font-size: 10pt;
    }}
    QDockWidget {{
        titlebar-close-icon: none;
        color: {ACCENT_CYAN};
        font-weight: bold;
    }}
    QDockWidget::title {{
        background: {BG_PANEL};
        padding: 6px;
        border-bottom: 1px solid {ACCENT_CYAN};
    }}
    QToolBar {{
        background: {BG_DARKEST};
        border-bottom: 1px solid {BORDER};
        spacing: 4px;
        padding: 3px;
    }}
    QStatusBar {{
        background: {BG_DARKEST};
        color: {ACCENT_CYAN};
        border-top: 1px solid {BORDER};
    }}
    QListWidget, QTreeWidget {{
        background: {BG_PANEL};
        border: 1px solid {BORDER};
        alternate-background-color: {BG_DARK};
    }}
    QListWidget::item:selected, QTreeWidget::item:selected {{
        background: {ACCENT_PURPLE};
        color: white;
    }}
    QPushButton {{
        background: {BG_PANEL};
        border: 1px solid {ACCENT_CYAN};
        border-radius: 4px;
        padding: 5px 10px;
        color: {ACCENT_CYAN};
    }}
    QPushButton:hover {{ background: {BG_HOVER}; }}
    QPushButton:pressed {{ background: {ACCENT_PURPLE}; color: white; }}
    QPushButton:checked {{
        background: {ACCENT_MAGENTA};
        color: white;
        border-color: {ACCENT_MAGENTA};
    }}
    QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {{
        background: {BG_PANEL};
        border: 1px solid {BORDER};
        border-radius: 3px;
        padding: 3px;
        color: {TEXT_PRIMARY};
    }}
    QComboBox:focus, QDoubleSpinBox:focus, QLineEdit:focus {{
        border: 1px solid {ACCENT_CYAN};
    }}
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: 4px;
        margin-top: 10px;
        color: {ACCENT_CYAN};
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    QMenuBar {{ background: {BG_DARKEST}; }}
    QMenuBar::item:selected {{ background: {ACCENT_PURPLE}; }}
    QMenu {{ background: {BG_PANEL}; border: 1px solid {ACCENT_CYAN}; }}
    QMenu::item:selected {{ background: {ACCENT_PURPLE}; }}
    """


# ─────────────────────────────────────────────────────────────────────────
# DATENMODELL
# ─────────────────────────────────────────────────────────────────────────

MM_TO_PX = 10.0  # 1mm = 10px Darstellungsmaßstab (Grid = 1.27mm Standard-Raster)


class LayerType(Enum):
    TOP_COPPER = "Top Copper"
    BOTTOM_COPPER = "Bottom Copper"
    TOP_SILK = "Top Silkscreen"
    BOTTOM_SILK = "Bottom Silkscreen"
    DRILL = "Drill"
    BOARD_OUTLINE = "Board Outline"


LAYER_COLORS = {
    LayerType.TOP_COPPER: PandoraTheme.COPPER_TOP,
    LayerType.BOTTOM_COPPER: PandoraTheme.COPPER_BOTTOM,
    LayerType.TOP_SILK: PandoraTheme.SILK_TOP,
    LayerType.BOTTOM_SILK: PandoraTheme.SILK_BOTTOM,
    LayerType.DRILL: PandoraTheme.DRILL,
    LayerType.BOARD_OUTLINE: PandoraTheme.OUTLINE,
}


@dataclass
class Layer:
    ltype: LayerType
    visible: bool = True
    locked: bool = False

    @property
    def name(self):
        return self.ltype.value

    @property
    def color(self):
        return LAYER_COLORS[self.ltype]


class LayerStack:
    def __init__(self):
        self.layers = [Layer(lt) for lt in LayerType]
        self.active_index = 0

    def active(self) -> Layer:
        return self.layers[self.active_index]

    def by_type(self, ltype: LayerType) -> Layer:
        return next(l for l in self.layers if l.ltype == ltype)


class Net:
    """Ein elektrisches Netz, das mehrere Pads/Vias/Traces verbindet."""
    def __init__(self, name: str, color: str = None):
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.color = color or PandoraTheme.ACCENT_CYAN

    def to_dict(self):
        return {"id": self.id, "name": self.name, "color": self.color}


class Netlist:
    def __init__(self):
        self.nets: dict[str, Net] = {}

    def add_net(self, name: str) -> Net:
        if name in [n.name for n in self.nets.values()]:
            return next(n for n in self.nets.values() if n.name == name)
        net = Net(name)
        self.nets[net.id] = net
        return net

    def remove_net(self, net_id: str):
        self.nets.pop(net_id, None)


# ─────────────────────────────────────────────────────────────────────────
# FOOTPRINT-BIBLIOTHEK
# ─────────────────────────────────────────────────────────────────────────
# Echte Footprints statt generischer Platzhalter: jede Definition enthält
# reale Pad-Geometrie (Position/Größe/Form/Bohrung je Pin, in mm relativ zum
# Footprint-Ursprung) und einen Silkscreen-Körperumriss. Die Pads werden beim
# Platzieren als echte PadItem-Instanzen erzeugt und sind damit netzfähig
# (Ratsnest/DRC/Gerber-Export funktionieren wie bei frei platzierten Pads).
#
# Hinweis: Die Maße sind praxistaugliche Näherungswerte (angelehnt an
# gängige IPC-Footprint-Generatoren), keine datenblattgeprüften Fertigungs-
# Footprints. Für produktive Fertigung bitte gegen das Datenblatt prüfen.

@dataclass
class FootprintPad:
    x: float
    y: float
    w: float
    h: float
    shape: str = "rect"       # rect | round | oval
    drill: float = 0.0        # 0 = SMD, >0 = durchkontaktiert (THT)
    number: str = "1"


@dataclass
class FootprintDef:
    key: str
    name: str
    category: str
    ref_prefix: str
    pads: list
    body_poly: list           # Liste von (x_mm, y_mm) - Silkscreen-Körperumriss
    description: str = ""


def _rect_poly(w, h):
    return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]


def _two_pad_chip(pitch, pad_w, pad_h, body_w, body_h):
    pads = [
        FootprintPad(-pitch / 2, 0, pad_w, pad_h, "rect", 0.0, "1"),
        FootprintPad(pitch / 2, 0, pad_w, pad_h, "rect", 0.0, "2"),
    ]
    return pads, _rect_poly(body_w, body_h)


def _sot23_3(pitch=1.9, pad_w=0.9, pad_h=1.1, span=2.6, body_w=1.6, body_h=3.0):
    pads = [
        FootprintPad(-pitch / 2, span / 2, pad_w, pad_h, "rect", 0.0, "1"),
        FootprintPad(pitch / 2, span / 2, pad_w, pad_h, "rect", 0.0, "2"),
        FootprintPad(0, -span / 2, pad_w, pad_h, "round", 0.0, "3"),
    ]
    return pads, _rect_poly(body_w, body_h)


def _sot23_5(pitch=0.95, pad_w=0.4, pad_h=0.9, span=2.8, body_w=1.6, body_h=3.0):
    pads = []
    for i, x in enumerate((-pitch, 0.0, pitch), start=1):
        pads.append(FootprintPad(x, span / 2, pad_w, pad_h,
                                  "round" if i == 1 else "rect", 0.0, str(i)))
    for i, x in enumerate((pitch / 2, -pitch / 2), start=4):
        pads.append(FootprintPad(x, -span / 2, pad_w, pad_h, "rect", 0.0, str(i)))
    return pads, _rect_poly(body_w, body_h)


def _sot223(pitch=2.3, pad_w=1.2, pad_h=1.6, span=6.2, tab_w=3.2, tab_h=2.2,
            body_w=6.7, body_h=3.6):
    pads = [
        FootprintPad(-pitch, span / 2, pad_w, pad_h, "round", 0.0, "1"),
        FootprintPad(0, span / 2, pad_w, pad_h, "rect", 0.0, "2"),
        FootprintPad(pitch, span / 2, pad_w, pad_h, "rect", 0.0, "3"),
        FootprintPad(0, -span / 2, tab_w, tab_h, "rect", 0.0, "4"),
    ]
    return pads, _rect_poly(body_w, body_h)


def _dual_row_ic(pin_count, pitch, row_spacing, pad_w, pad_h, body_w, body_h, drill=0.0):
    pads = []
    half = pin_count // 2
    y0 = -(half - 1) * pitch / 2
    for i in range(half):
        y = y0 + i * pitch
        pads.append(FootprintPad(-row_spacing / 2, y, pad_w, pad_h,
                                  "rect" if i == 0 else "round", drill, str(i + 1)))
    for i in range(half):
        y = y0 + (half - 1 - i) * pitch
        pads.append(FootprintPad(row_spacing / 2, y, pad_w, pad_h, "round", drill,
                                  str(half + i + 1)))
    return pads, _rect_poly(body_w, body_h)


def _single_row_header(pin_count, pitch=2.54, pad_dia=1.7, drill=1.0):
    y0 = -(pin_count - 1) * pitch / 2
    pads = [FootprintPad(0, y0 + i * pitch, pad_dia, pad_dia,
                          "rect" if i == 0 else "round", drill, str(i + 1))
            for i in range(pin_count)]
    body_h = (pin_count - 1) * pitch + pitch
    return pads, _rect_poly(pitch + 0.8, body_h)


def _dual_row_header(pins_per_row, pitch=2.54, row_spacing=2.54, pad_dia=1.7, drill=1.0):
    y0 = -(pins_per_row - 1) * pitch / 2
    pads = []
    for i in range(pins_per_row):
        y = y0 + i * pitch
        pads.append(FootprintPad(-row_spacing / 2, y, pad_dia, pad_dia,
                                  "rect" if i == 0 else "round", drill, str(2 * i + 1)))
        pads.append(FootprintPad(row_spacing / 2, y, pad_dia, pad_dia, "round", drill,
                                  str(2 * i + 2)))
    body_h = (pins_per_row - 1) * pitch + pitch
    body_w = row_spacing + pitch
    return pads, _rect_poly(body_w, body_h)


def _to220_3(pitch=2.54, pad_dia=1.8, drill=1.1):
    pads = [FootprintPad(x, 0, pad_dia, pad_dia, "rect" if i == 0 else "round", drill, str(i + 1))
            for i, x in enumerate((-pitch, 0.0, pitch))]
    body = [(-5.0, -6.5), (5.0, -6.5), (5.0, -1.3), (-5.0, -1.3)]
    return pads, body


def _mounting_hole(dia=3.2):
    pad_dia = dia + 1.2
    pads = [FootprintPad(0, 0, pad_dia, pad_dia, "round", dia, "1")]
    return pads, _rect_poly(pad_dia + 0.4, pad_dia + 0.4)


def _legacy_generic_def(w_mm, h_mm, pin_count):
    """Rekonstruiert alte Projekte (vor der Footprint-Bibliothek) mit echten,
    netzfähigen Pads statt der früheren rein optischen Platzhalter-Pins."""
    per_side = max(1, pin_count // 2)
    spacing = h_mm / (per_side + 1)
    pads, n = [], 1
    for i in range(per_side):
        y = -h_mm / 2 + spacing * (i + 1)
        for x in (-w_mm / 2 - 0.5, w_mm / 2 + 0.5):
            pads.append(FootprintPad(x, y, 1.2, 0.8, "rect", 0.0, str(n)))
            n += 1
    return FootprintDef("LEGACY", "Generischer Footprint (Alt-Projekt)", "Legacy", "U",
                         pads, _rect_poly(w_mm, h_mm),
                         "Automatisch aus einem Projekt im alten Format rekonstruiert.")


def _build_footprint_library() -> dict:
    lib = {}

    def add(key, name, category, ref_prefix, gen, description=""):
        pads, body = gen
        lib[key] = FootprintDef(key, name, category, ref_prefix, pads, body, description)

    # -- SMD-Passiv (Chip R/C/LED) ------------------------------------------------
    chip_sizes = {
        "0402": (0.95, 0.55, 0.65, 1.0, 0.5),
        "0603": (1.6, 0.9, 0.95, 1.6, 0.8),
        "0805": (1.9, 1.15, 1.3, 2.0, 1.25),
        "1206": (3.0, 1.15, 1.8, 3.2, 1.6),
    }
    for size, (pitch, pad_w, pad_h, body_w, body_h) in chip_sizes.items():
        add(f"R_{size}", f"Widerstand {size} (SMD)", "SMD Passiv", "R",
            _two_pad_chip(pitch, pad_w, pad_h, body_w, body_h),
            "Zweipoliges Chip-Pad-Paar, IPC-nahe Näherungswerte.")
        add(f"C_{size}", f"Kondensator {size} (SMD)", "SMD Passiv", "C",
            _two_pad_chip(pitch, pad_w, pad_h, body_w, body_h),
            "Zweipoliges Chip-Pad-Paar, IPC-nahe Näherungswerte.")
    for size in ("0805", "1206"):
        pitch, pad_w, pad_h, body_w, body_h = chip_sizes[size]
        add(f"LED_{size}", f"LED {size} (SMD)", "SMD Passiv", "LED",
            _two_pad_chip(pitch, pad_w, pad_h, body_w, body_h),
            "Pin 1 = Kathode (Zuordnung projektabhängig).")

    # -- SMD-Diode/Transistor ------------------------------------------------------
    add("SOD_123", "Diode SOD-123", "SMD Diode/Transistor", "D",
        _two_pad_chip(3.7, 1.2, 1.4, 4.0, 1.8), "Pin 1 = Kathode.")
    add("SOT_23", "Transistor SOT-23", "SMD Diode/Transistor", "Q",
        _sot23_3(), "3-Pin-Kleinsignaltransistor/-diode.")
    add("SOT_23_5", "IC SOT-23-5", "SMD Diode/Transistor", "U",
        _sot23_5(), "5-Pin (z. B. kleine Regler/Komparatoren).")
    add("SOT_223", "Transistor/Regler SOT-223", "SMD Diode/Transistor", "Q",
        _sot223(), "3 Signalpins + große Tab-Masse/-Kühlfläche (Pin 4).")

    # -- SMD-IC (Gehäuse mit zwei Pin-Reihen) --------------------------------------
    ic_specs = {
        "SOIC": dict(pitch=1.27, row_spacing=5.4, pad_w=0.6, pad_h=1.55),
        "TSSOP": dict(pitch=0.65, row_spacing=4.4, pad_w=0.4, pad_h=1.2),
    }
    for family, pins_list, body_w in (("SOIC", (8, 14, 16), None), ("TSSOP", (8, 16), None)):
        spec = ic_specs[family]
        for pins in pins_list:
            half = pins // 2
            body_h = (half - 1) * spec["pitch"] + 2.0
            add(f"{family}_{pins}", f"{family}-{pins}", "SMD IC", "U",
                _dual_row_ic(pins, spec["pitch"], spec["row_spacing"], spec["pad_w"],
                             spec["pad_h"], spec["row_spacing"] - 1.2, body_h),
                f"{pins}-Pin Gull-Wing-IC, {spec['pitch']}mm Pitch.")

    # -- THT: DIP / TO-220 / Bohrlöcher --------------------------------------------
    for pins in (8, 14, 16):
        half = pins // 2
        body_h = (half - 1) * 2.54 + 2.5
        add(f"DIP_{pins}", f"DIP-{pins}", "THT", "U",
            _dual_row_ic(pins, 2.54, 7.62, 1.6, 1.6, 6.35, body_h, drill=0.8),
            f"{pins}-Pin bedrahtetes IC, 2.54mm Pitch / 7.62mm Reihenabstand.")
    add("TO220_3", "TO-220 (3-Pin)", "THT", "Q",
        _to220_3(), "Bedrahteter Transistor/Regler mit Kühlkörper-Tab.")
    add("MOUNTHOLE_M3", "Bohrung M3", "Mechanik", "H",
        _mounting_hole(3.2), "Unbestückte Befestigungsbohrung, 3.2mm.")
    add("MOUNTHOLE_M2_5", "Bohrung M2.5", "Mechanik", "H",
        _mounting_hole(2.7), "Unbestückte Befestigungsbohrung, 2.7mm.")

    # -- Stiftleisten (1-reihig 2..10 Pins, 2-reihig 5/10 Pins je Reihe) -----------
    for pins in range(2, 11):
        add(f"PINHDR_1X{pins:02d}", f"Stiftleiste 1x{pins:02d}", "Stiftleisten", "J",
            _single_row_header(pins), "Einreihige 2.54mm-Stiftleiste.")
    for pins in (5, 10):
        add(f"PINHDR_2X{pins:02d}", f"Stiftleiste 2x{pins:02d}", "Stiftleisten", "J",
            _dual_row_header(pins), "Zweireihige 2.54mm-Stiftleiste.")

    return lib


FOOTPRINT_LIBRARY = _build_footprint_library()


# ─────────────────────────────────────────────────────────────────────────
# GRAPHICS ITEMS
# ─────────────────────────────────────────────────────────────────────────

class PandoraItemMixin:
    """Gemeinsame Metadaten für alle PCB-Elemente."""
    def init_meta(self, kind: str, layer: LayerType, net_id: str = None):
        self.pandora_id = str(uuid.uuid4())[:8]
        self.kind = kind
        self.layer_type = layer
        self.net_id = net_id
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def to_dict(self):
        raise NotImplementedError


class PadItem(PandoraItemMixin, QGraphicsRectItem):
    """SMD- oder THT-Pad."""
    def __init__(self, x, y, w=1.6, h=1.6, shape="rect", layer=LayerType.TOP_COPPER,
                 drill=0.0, net_id=None):
        super().__init__(-w * MM_TO_PX / 2, -h * MM_TO_PX / 2, w * MM_TO_PX, h * MM_TO_PX)
        self.init_meta("pad", layer, net_id)
        self.setPos(x * MM_TO_PX, y * MM_TO_PX)
        self.width_mm, self.height_mm = w, h
        self.shape = shape  # rect | round | oval
        self.drill_mm = drill
        color = QColor(LAYER_COLORS[layer])
        self.setBrush(QBrush(color))
        self.setPen(QPen(color.lighter(140), 0.5))
        if shape == "round":
            self.setRect(-w * MM_TO_PX / 2, -h * MM_TO_PX / 2, w * MM_TO_PX, h * MM_TO_PX)

    def paint(self, painter, option, widget=None):
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        if self.shape in ("round", "oval"):
            painter.drawEllipse(self.rect())
        else:
            painter.drawRect(self.rect())
        if self.drill_mm > 0:
            painter.setBrush(QBrush(QColor(PandoraTheme.BG_DARKEST)))
            r = self.drill_mm * MM_TO_PX / 2
            painter.drawEllipse(QPointF(0, 0), r, r)
        if self.isSelected():
            painter.setPen(QPen(QColor(PandoraTheme.ACCENT_MAGENTA), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect().adjusted(-2, -2, 2, 2))

    def to_dict(self):
        p = self.pos()
        return {"type": "pad", "id": self.pandora_id, "x": p.x() / MM_TO_PX,
                "y": p.y() / MM_TO_PX, "w": self.width_mm, "h": self.height_mm,
                "shape": self.shape, "layer": self.layer_type.value,
                "drill": self.drill_mm, "net": self.net_id}


class ViaItem(PandoraItemMixin, QGraphicsEllipseItem):
    """Via zwischen Top- und Bottom-Copper."""
    def __init__(self, x, y, dia=0.6, drill=0.3, net_id=None):
        r = dia * MM_TO_PX / 2
        super().__init__(-r, -r, dia * MM_TO_PX, dia * MM_TO_PX)
        self.init_meta("via", LayerType.TOP_COPPER, net_id)
        self.setPos(x * MM_TO_PX, y * MM_TO_PX)
        self.dia_mm, self.drill_mm = dia, drill
        self.setBrush(QBrush(QColor(PandoraTheme.ACCENT_PURPLE)))
        self.setPen(QPen(QColor(PandoraTheme.ACCENT_CYAN), 0.6))

    def to_dict(self):
        p = self.pos()
        return {"type": "via", "id": self.pandora_id, "x": p.x() / MM_TO_PX,
                "y": p.y() / MM_TO_PX, "dia": self.dia_mm, "drill": self.drill_mm,
                "net": self.net_id}


class TraceItem(PandoraItemMixin, QGraphicsPathItem):
    """Mehrsegment-Leiterbahn auf einem Copper-Layer."""
    def __init__(self, points_mm: list, width_mm=0.25, layer=LayerType.TOP_COPPER, net_id=None):
        super().__init__()
        self.init_meta("trace", layer, net_id)
        self.points_mm = points_mm
        self.width_mm = width_mm
        self._rebuild_path()
        color = QColor(LAYER_COLORS[layer])
        pen = QPen(color, width_mm * MM_TO_PX)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)

    def _rebuild_path(self):
        path = QPainterPath()
        if self.points_mm:
            path.moveTo(self.points_mm[0][0] * MM_TO_PX, self.points_mm[0][1] * MM_TO_PX)
            for pt in self.points_mm[1:]:
                path.lineTo(pt[0] * MM_TO_PX, pt[1] * MM_TO_PX)
        self.setPath(path)

    def add_point(self, x_mm, y_mm):
        self.points_mm.append((x_mm, y_mm))
        self._rebuild_path()

    def to_dict(self):
        return {"type": "trace", "id": self.pandora_id, "points": self.points_mm,
                "width": self.width_mm, "layer": self.layer_type.value, "net": self.net_id}


class FootprintItem(PandoraItemMixin, QGraphicsItemGroup):
    """Footprint aus der Footprint-Bibliothek: Silkscreen-Körper + echte,
    netzfähige Pads (PadItem-Kindelemente) + Referenzbezeichner.

    Die Pads sind bewusst nicht einzeln selektierbar/verschiebbar (sie bleiben
    fest im Footprint-Raster) - die Netzzuweisung je Pin erfolgt über das
    Eigenschaften-Dock der Footprint-Gruppe ("Pins"-Abschnitt), sobald der
    Footprint ausgewählt ist."""

    def __init__(self, x, y, footprint_key="R_0603", ref="U1", value="", rot=0.0,
                 layer=LayerType.TOP_SILK, fp_def_override=None):
        super().__init__()
        self.init_meta("footprint", layer)
        self.footprint_key = footprint_key
        self.ref, self.value = ref, value
        self.fp_def = fp_def_override or FOOTPRINT_LIBRARY.get(footprint_key) \
            or FOOTPRINT_LIBRARY["R_0603"]
        self.pad_items = []
        self._build()
        self.setPos(x * MM_TO_PX, y * MM_TO_PX)
        if rot:
            self.setRotation(rot)

    def _build(self):
        fp = self.fp_def
        poly = QPolygonF([QPointF(px * MM_TO_PX, py * MM_TO_PX) for px, py in fp.body_poly])
        body = QGraphicsPolygonItem(poly)
        body.setPen(QPen(QColor(PandoraTheme.SILK_TOP), 0.8))
        body.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.addToGroup(body)

        for pad_def in fp.pads:
            pad = PadItem(pad_def.x, pad_def.y, pad_def.w, pad_def.h, pad_def.shape,
                          layer=LayerType.TOP_COPPER, drill=pad_def.drill)
            pad.pin_number = pad_def.number
            pad.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            pad.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            self.addToGroup(pad)
            self.pad_items.append(pad)

        xs = [p[0] for p in fp.body_poly]
        ys = [p[1] for p in fp.body_poly]
        self.ref_label = QGraphicsSimpleTextItem(self.ref)
        font = QFont("Segoe UI")
        font.setPixelSize(9)
        self.ref_label.setFont(font)
        self.ref_label.setBrush(QBrush(QColor(PandoraTheme.SILK_TOP)))
        self.ref_label.setPos(min(xs) * MM_TO_PX, (min(ys) - 1.6) * MM_TO_PX)
        self.addToGroup(self.ref_label)

    def set_ref(self, ref: str):
        self.ref = ref
        self.ref_label.setText(ref)

    def set_value(self, value: str):
        self.value = value

    def to_dict(self):
        p = self.pos()
        pad_nets = {pad.pin_number: pad.net_id for pad in self.pad_items if pad.net_id}
        return {"type": "footprint", "id": self.pandora_id, "x": p.x() / MM_TO_PX,
                "y": p.y() / MM_TO_PX, "rot": self.rotation(),
                "footprint_key": self.footprint_key, "ref": self.ref, "value": self.value,
                "pad_nets": pad_nets}


class BoardOutlineItem(PandoraItemMixin, QGraphicsPolygonItem):
    def __init__(self, points_mm: list):
        poly = QPolygonF([QPointF(x * MM_TO_PX, y * MM_TO_PX) for x, y in points_mm])
        super().__init__(poly)
        self.init_meta("outline", LayerType.BOARD_OUTLINE)
        self.points_mm = points_mm
        pen = QPen(QColor(PandoraTheme.OUTLINE), 1.2)
        self.setPen(pen)
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    def to_dict(self):
        return {"type": "outline", "id": self.pandora_id, "points": self.points_mm}


# ─────────────────────────────────────────────────────────────────────────
# UNDO / REDO COMMANDS
# ─────────────────────────────────────────────────────────────────────────

class AddItemCommand(QUndoCommand):
    def __init__(self, scene, item, description="Element hinzufügen"):
        super().__init__(description)
        self.scene, self.item = scene, item

    def redo(self):
        self.scene.addItem(self.item)

    def undo(self):
        self.scene.removeItem(self.item)


class DeleteItemsCommand(QUndoCommand):
    def __init__(self, scene, items, description="Element löschen"):
        super().__init__(description)
        self.scene, self.items = scene, list(items)

    def redo(self):
        for it in self.items:
            self.scene.removeItem(it)

    def undo(self):
        for it in self.items:
            self.scene.addItem(it)


class MoveItemCommand(QUndoCommand):
    def __init__(self, item, old_pos, new_pos, description="Element verschieben"):
        super().__init__(description)
        self.item, self.old_pos, self.new_pos = item, old_pos, new_pos

    def redo(self):
        self.item.setPos(self.new_pos)

    def undo(self):
        self.item.setPos(self.old_pos)


class RotateItemsCommand(QUndoCommand):
    def __init__(self, items, delta_deg=90.0, description="Bauteil drehen"):
        super().__init__(description)
        self.items = list(items)
        self.delta = delta_deg

    def redo(self):
        for it in self.items:
            it.setRotation((it.rotation() + self.delta) % 360)

    def undo(self):
        for it in self.items:
            it.setRotation((it.rotation() - self.delta) % 360)


# ─────────────────────────────────────────────────────────────────────────
# SCENE / VIEW
# ─────────────────────────────────────────────────────────────────────────

class ToolMode(Enum):
    SELECT = "Auswählen"
    TRACE = "Leiterbahn"
    PAD = "Pad"
    VIA = "Via"
    FOOTPRINT = "Footprint"
    OUTLINE = "Board-Umriss"


class RatsnestLineItem(QGraphicsLineItem):
    """Gestrichelte Luftlinie (Airwire) zwischen zwei unverbundenen Punkten eines Netzes.
    Rein visuell - kein PandoraItemMixin, wird nie serialisiert oder selektiert."""
    def __init__(self, x1, y1, x2, y2, color=PandoraTheme.ACCENT_CYAN):
        super().__init__(x1 * MM_TO_PX, y1 * MM_TO_PX, x2 * MM_TO_PX, y2 * MM_TO_PX)
        self.is_ratsnest = True
        pen = QPen(QColor(color), 0.6)
        pen.setStyle(Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setZValue(1000)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)


class RatsnestEngine:
    """Berechnet Luftlinien (Ratsnest) je Netz: verbindet alle Pads/Vias eines Netzes
    per Minimal-Spannbaum (MST), unter Berücksichtigung bereits vorhandener Traces
    (deren Endpunkte gelten als bereits verbunden)."""

    TOLERANCE_MM = 0.05

    @staticmethod
    def compute(scene) -> list:
        segments = []  # (net_id, (x1,y1), (x2,y2), color)
        for net_id, net in scene.netlist.nets.items():
            points = []
            for item in scene.items():
                if getattr(item, "net_id", None) == net_id and isinstance(item, (PadItem, ViaItem)):
                    p = item.pos()
                    points.append((p.x() / MM_TO_PX, p.y() / MM_TO_PX))
            n = len(points)
            if n < 2:
                continue

            parent = list(range(n))

            def find(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i

            def union(i, j):
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj

            tol = RatsnestEngine.TOLERANCE_MM
            for item in scene.items():
                if isinstance(item, TraceItem) and item.net_id == net_id and len(item.points_mm) >= 2:
                    start, end = item.points_mm[0], item.points_mm[-1]
                    si = ei = None
                    for idx, (x, y) in enumerate(points):
                        if abs(x - start[0]) < tol and abs(y - start[1]) < tol:
                            si = idx
                        if abs(x - end[0]) < tol and abs(y - end[1]) < tol:
                            ei = idx
                    if si is not None and ei is not None:
                        union(si, ei)

            edges = []
            for i in range(n):
                for j in range(i + 1, n):
                    d = math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1])
                    edges.append((d, i, j))
            edges.sort(key=lambda e: e[0])
            for d, i, j in edges:
                if find(i) != find(j):
                    union(i, j)
                    segments.append((net_id, points[i], points[j], net.color))
        return segments


@dataclass
class DRCViolation:
    rule: str
    message: str
    items: list = field(default_factory=list)
    severity: str = "error"  # error | warning


class DesignRuleChecker:
    """Vereinfachte DRC-Prüfungen: Mindest-Leiterbahnbreite, Mindest-Bohrdurchmesser
    und Mindestabstand (Clearance) zwischen Kupfer-Elementen unterschiedlicher Netze
    auf demselben Layer. Abstandsberechnung erfolgt über Bounding-Box-Distanz
    (Näherung, kein exaktes Polygon-Clearance-Modell)."""

    @staticmethod
    def _rect_distance_mm(a, b) -> float:
        ra, rb = a.sceneBoundingRect(), b.sceneBoundingRect()
        dx = max(rb.left() - ra.right(), ra.left() - rb.right(), 0.0)
        dy = max(rb.top() - ra.bottom(), ra.top() - rb.bottom(), 0.0)
        return math.hypot(dx, dy) / MM_TO_PX

    @staticmethod
    def run(scene, min_clearance_mm=0.2, min_trace_width_mm=0.15, min_drill_mm=0.2) -> list:
        violations = []

        for item in scene.items():
            if isinstance(item, TraceItem) and item.width_mm < min_trace_width_mm:
                violations.append(DRCViolation(
                    "Mindest-Leiterbahnbreite",
                    f"Trace {item.pandora_id} auf {item.layer_type.value}: "
                    f"{item.width_mm:.3f}mm < erlaubt {min_trace_width_mm:.3f}mm",
                    [item]))
            if isinstance(item, (PadItem, ViaItem)) and getattr(item, "drill_mm", 0) > 0:
                if item.drill_mm < min_drill_mm:
                    violations.append(DRCViolation(
                        "Mindest-Bohrdurchmesser",
                        f"{item.kind.capitalize()} {item.pandora_id}: "
                        f"Bohrung {item.drill_mm:.3f}mm < erlaubt {min_drill_mm:.3f}mm",
                        [item]))

        copper_items = [it for it in scene.items()
                        if isinstance(it, (PadItem, ViaItem, TraceItem))
                        and getattr(it, "layer_type", None) in (LayerType.TOP_COPPER, LayerType.BOTTOM_COPPER)]
        for i in range(len(copper_items)):
            for j in range(i + 1, len(copper_items)):
                a, b = copper_items[i], copper_items[j]
                if a.layer_type != b.layer_type:
                    continue
                if a.net_id and b.net_id and a.net_id == b.net_id:
                    continue
                dist = DesignRuleChecker._rect_distance_mm(a, b)
                if dist < min_clearance_mm:
                    violations.append(DRCViolation(
                        "Mindestabstand (Clearance)",
                        f"{a.kind} {a.pandora_id} zu {b.kind} {b.pandora_id} auf "
                        f"{a.layer_type.value}: {dist:.3f}mm < erlaubt {min_clearance_mm:.3f}mm",
                        [a, b]))
        return violations


class PcbScene(QGraphicsScene):
    net_changed = pyqtSignal()

    def __init__(self, layer_stack: LayerStack, netlist: Netlist, undo_stack: QUndoStack):
        super().__init__()
        self.layer_stack = layer_stack
        self.netlist = netlist
        self.undo_stack = undo_stack
        self.grid_mm = 1.27
        self.setSceneRect(-500, -500, 2000, 2000)
        self.setBackgroundBrush(QBrush(QColor(PandoraTheme.BG_DARKEST)))
        self._active_trace = None
        self.ratsnest_visible = True
        self._ratsnest_items = []

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        step = self.grid_mm * MM_TO_PX
        if step <= 0:
            return
        # Float-Modulo statt int(step) verwenden: bei sehr kleinem Raster
        # (< 0.1mm) wurde int(step) sonst zu 0 und verursachte einen
        # ZeroDivisionError beim Neuzeichnen (Absturz beim Platzieren,
        # da jedes addItem() ein Repaint auslöst).
        left = rect.left() - (rect.left() % step)
        top = rect.top() - (rect.top() % step)
        minor = QPen(QColor(PandoraTheme.GRID_MINOR), 0.5)
        major = QPen(QColor(PandoraTheme.GRID_MAJOR), 0.8)
        x = left
        i = 0
        while x < rect.right():
            painter.setPen(major if i % 10 == 0 else minor)
            painter.drawLine(QLineF(x, rect.top(), x, rect.bottom()))
            x += step
            i += 1
        y = top
        i = 0
        while y < rect.bottom():
            painter.setPen(major if i % 10 == 0 else minor)
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
            y += step
            i += 1

    def snap(self, pos: QPointF) -> QPointF:
        step = self.grid_mm * MM_TO_PX
        return QPointF(round(pos.x() / step) * step, round(pos.y() / step) * step)

    def layer_visible(self, ltype: LayerType) -> bool:
        return self.layer_stack.by_type(ltype).visible

    def update_ratsnest(self):
        for it in self._ratsnest_items:
            self.removeItem(it)
        self._ratsnest_items = []
        if not self.ratsnest_visible:
            return
        for net_id, p1, p2, color in RatsnestEngine.compute(self):
            line = RatsnestLineItem(p1[0], p1[1], p2[0], p2[1], color)
            self.addItem(line)
            self._ratsnest_items.append(line)

    def set_ratsnest_visible(self, visible: bool):
        self.ratsnest_visible = visible
        self.update_ratsnest()


class PcbView(QGraphicsView):
    coords_changed = pyqtSignal(float, float)

    def __init__(self, scene: PcbScene):
        super().__init__(scene)
        self.pcb_scene = scene
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setMouseTracking(True)
        self.tool_mode = ToolMode.SELECT
        self.zoom_level = 1.0
        self._pending_trace_layer = LayerType.TOP_COPPER
        self._trace_points = []
        self._temp_trace_item = None
        self.footprint_factory = None  # von MainWindow gesetzt: callable(x_mm, y_mm)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_level *= factor
        self.scale(factor, factor)

    def mouseMoveEvent(self, event):
        pt = self.mapToScene(event.pos())
        self.coords_changed.emit(pt.x() / MM_TO_PX, pt.y() / MM_TO_PX)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        scene_pos = self.pcb_scene.snap(self.mapToScene(event.pos()))
        if self.tool_mode == ToolMode.SELECT:
            super().mousePressEvent(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        x_mm, y_mm = scene_pos.x() / MM_TO_PX, scene_pos.y() / MM_TO_PX

        if self.tool_mode == ToolMode.PAD:
            item = PadItem(x_mm, y_mm, layer=self.pcb_scene.layer_stack.active().ltype)
            self.pcb_scene.undo_stack.push(AddItemCommand(self.pcb_scene, item, "Pad platzieren"))
        elif self.tool_mode == ToolMode.VIA:
            item = ViaItem(x_mm, y_mm)
            self.pcb_scene.undo_stack.push(AddItemCommand(self.pcb_scene, item, "Via platzieren"))
        elif self.tool_mode == ToolMode.FOOTPRINT:
            if self.footprint_factory:
                self.footprint_factory(x_mm, y_mm)
        elif self.tool_mode == ToolMode.TRACE:
            self._trace_points.append((x_mm, y_mm))
            if len(self._trace_points) == 1:
                self._temp_trace_item = TraceItem(list(self._trace_points),
                                                   layer=self.pcb_scene.layer_stack.active().ltype)
                self.pcb_scene.addItem(self._temp_trace_item)
            else:
                self._temp_trace_item.add_point(x_mm, y_mm)
        elif self.tool_mode == ToolMode.OUTLINE:
            self._trace_points.append((x_mm, y_mm))
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self.tool_mode == ToolMode.TRACE and self._temp_trace_item:
            self.pcb_scene.undo_stack.push(
                AddItemCommand(self.pcb_scene, self._temp_trace_item, "Leiterbahn fertigstellen"))
            self._temp_trace_item = None
            self._trace_points = []
        elif self.tool_mode == ToolMode.OUTLINE and len(self._trace_points) >= 3:
            item = BoardOutlineItem(list(self._trace_points))
            self.pcb_scene.undo_stack.push(AddItemCommand(self.pcb_scene, item, "Board-Umriss abschließen"))
            self._trace_points = []
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.tool_mode == ToolMode.SELECT:
            self.pcb_scene.update_ratsnest()

    def set_tool(self, mode: ToolMode):
        self.tool_mode = mode
        self._trace_points = []
        self._temp_trace_item = None
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag if mode == ToolMode.SELECT
                          else QGraphicsView.DragMode.NoDrag)


# ─────────────────────────────────────────────────────────────────────────
# DOCKS
# ─────────────────────────────────────────────────────────────────────────

class LayersDock(QDockWidget):
    layer_visibility_changed = pyqtSignal()
    active_layer_changed = pyqtSignal(int)

    def __init__(self, layer_stack: LayerStack):
        super().__init__("Layer")
        self.layer_stack = layer_stack
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        for i, layer in enumerate(layer_stack.layers):
            item = QListWidgetItem(layer.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setForeground(QColor(layer.color))
            self.list.addItem(item)
        self.list.setCurrentRow(0)
        self.list.itemChanged.connect(self._on_item_changed)
        self.list.currentRowChanged.connect(self._on_active_changed)
        container = QWidget()
        lay = QVBoxLayout(container)
        lay.addWidget(QLabel("Sichtbarkeit & aktiver Layer:"))
        lay.addWidget(self.list)
        self.setWidget(container)

    def _on_item_changed(self, item: QListWidgetItem):
        row = self.list.row(item)
        self.layer_stack.layers[row].visible = item.checkState() == Qt.CheckState.Checked
        self.layer_visibility_changed.emit()

    def _on_active_changed(self, row):
        if row >= 0:
            self.layer_stack.active_index = row
            self.active_layer_changed.emit(row)


class PropertiesDock(QDockWidget):
    net_assigned = pyqtSignal(object, object)  # (item, net_id_or_None)

    def __init__(self, netlist: Netlist):
        super().__init__("Eigenschaften")
        self.netlist = netlist
        self.container = QWidget()
        self.form = QFormLayout(self.container)
        self.setWidget(self.container)
        self._current_item = None
        self.placeholder = QLabel("Kein Element ausgewählt.")
        self.form.addRow(self.placeholder)

    def show_item(self, item):
        while self.form.rowCount():
            self.form.removeRow(0)
        self._current_item = item
        if item is None:
            self.form.addRow(QLabel("Kein Element ausgewählt."))
            return
        self.form.addRow("Typ:", QLabel(getattr(item, "kind", "?")))
        self.form.addRow("ID:", QLabel(getattr(item, "pandora_id", "-")))
        pos = item.pos()
        x_spin, y_spin = QDoubleSpinBox(), QDoubleSpinBox()
        for s in (x_spin, y_spin):
            s.setRange(-1000, 1000)
            s.setSuffix(" mm")
        x_spin.setValue(pos.x() / MM_TO_PX)
        y_spin.setValue(pos.y() / MM_TO_PX)
        x_spin.valueChanged.connect(lambda v: item.setPos(v * MM_TO_PX, item.pos().y()))
        y_spin.valueChanged.connect(lambda v: item.setPos(item.pos().x(), v * MM_TO_PX))
        self.form.addRow("X:", x_spin)
        self.form.addRow("Y:", y_spin)
        if hasattr(item, "layer_type"):
            self.form.addRow("Layer:", QLabel(item.layer_type.value))
        if hasattr(item, "net_id") and item.kind in ("pad", "via", "trace"):
            self.form.addRow("Netz:", self._make_net_combo(item))
        if item.kind == "footprint":
            self.form.addRow("Footprint:", QLabel(item.footprint_key))
            ref_edit = QLineEdit(item.ref)
            ref_edit.textChanged.connect(lambda v, it=item: it.set_ref(v))
            self.form.addRow("Ref:", ref_edit)
            value_edit = QLineEdit(item.value)
            value_edit.textChanged.connect(lambda v, it=item: it.set_value(v))
            self.form.addRow("Wert:", value_edit)
            rot_spin = QSpinBox()
            rot_spin.setRange(0, 270)
            rot_spin.setSingleStep(90)
            rot_spin.setSuffix("°")
            rot_spin.setValue(int(item.rotation()) % 360)
            rot_spin.valueChanged.connect(lambda v, it=item: it.setRotation(v))
            self.form.addRow("Rotation:", rot_spin)
            if item.pad_items:
                self.form.addRow(QLabel("— Pins —"))
                for pad in item.pad_items:
                    self.form.addRow(f"Pin {pad.pin_number}:", self._make_net_combo(pad))

    def _make_net_combo(self, item) -> QComboBox:
        combo = QComboBox()
        combo.addItem("— kein Netz —", None)
        current_row = 0
        for i, net in enumerate(self.netlist.nets.values(), start=1):
            combo.addItem(net.name, net.id)
            if item.net_id == net.id:
                current_row = i
        combo.setCurrentIndex(current_row)
        combo.currentIndexChanged.connect(
            lambda _, it=item, cb=combo: self.net_assigned.emit(it, cb.currentData()))
        return combo


class FootprintLibraryDock(QDockWidget):
    """Bibliotheks-Browser: Auswahl nach Kategorie/Suche setzt den aktiven
    Footprint für das Footprint-Werkzeug (nächster Klick auf dem Board)."""
    footprint_chosen = pyqtSignal(str)  # footprint_key

    def __init__(self):
        super().__init__("Footprint-Bibliothek")
        container = QWidget()
        lay = QVBoxLayout(container)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Footprint suchen…")
        self.search.textChanged.connect(self._filter)
        lay.addWidget(self.search)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self.tree)

        lay.addWidget(QLabel("Wert für nächste Platzierung (optional):"))
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("z. B. 10k, 100nF, LM358…")
        lay.addWidget(self.value_edit)

        self.info_label = QLabel("Kein Footprint gewählt.")
        self.info_label.setWordWrap(True)
        lay.addWidget(self.info_label)

        self.setWidget(container)
        self.selected_key = None
        self._populate()

    def _populate(self):
        self.tree.clear()
        cats = {}
        for key, fp in FOOTPRINT_LIBRARY.items():
            cat_item = cats.get(fp.category)
            if cat_item is None:
                cat_item = QTreeWidgetItem([fp.category])
                cat_item.setForeground(0, QColor(PandoraTheme.ACCENT_CYAN))
                self.tree.addTopLevelItem(cat_item)
                cats[fp.category] = cat_item
            child = QTreeWidgetItem([fp.name])
            child.setData(0, Qt.ItemDataRole.UserRole, key)
            cat_item.addChild(child)
        self.tree.expandAll()

    def _filter(self, text):
        text = text.lower().strip()
        for i in range(self.tree.topLevelItemCount()):
            cat = self.tree.topLevelItem(i)
            visible = 0
            for j in range(cat.childCount()):
                child = cat.child(j)
                match = text in child.text(0).lower()
                child.setHidden(not match)
                visible += int(match)
            cat.setHidden(text != "" and visible == 0)

    def _on_item_clicked(self, item: QTreeWidgetItem, _col):
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            return
        self.selected_key = key
        fp = FOOTPRINT_LIBRARY[key]
        self.info_label.setText(f"{fp.name} — {len(fp.pads)} Pin(s) — Ref-Präfix „{fp.ref_prefix}“\n"
                                 f"{fp.description}")
        self.footprint_chosen.emit(key)


class DRCDock(QDockWidget):
    violation_selected = pyqtSignal(object)  # DRCViolation

    def __init__(self):
        super().__init__("Design Rule Check")
        container = QWidget()
        lay = QVBoxLayout(container)

        rules_box = QGroupBox("Regeln")
        rules_form = QFormLayout(rules_box)
        self.clearance_spin = QDoubleSpinBox()
        self.clearance_spin.setRange(0.05, 5.0)
        self.clearance_spin.setSingleStep(0.05)
        self.clearance_spin.setValue(0.2)
        self.clearance_spin.setSuffix(" mm")
        self.trace_width_spin = QDoubleSpinBox()
        self.trace_width_spin.setRange(0.05, 5.0)
        self.trace_width_spin.setSingleStep(0.05)
        self.trace_width_spin.setValue(0.15)
        self.trace_width_spin.setSuffix(" mm")
        self.drill_spin = QDoubleSpinBox()
        self.drill_spin.setRange(0.05, 5.0)
        self.drill_spin.setSingleStep(0.05)
        self.drill_spin.setValue(0.2)
        self.drill_spin.setSuffix(" mm")
        rules_form.addRow("Min. Clearance:", self.clearance_spin)
        rules_form.addRow("Min. Trace-Breite:", self.trace_width_spin)
        rules_form.addRow("Min. Bohrung:", self.drill_spin)
        lay.addWidget(rules_box)

        self.run_button = QPushButton("DRC ausführen")
        lay.addWidget(self.run_button)

        self.summary_label = QLabel("Noch nicht ausgeführt.")
        lay.addWidget(self.summary_label)

        self.list = QListWidget()
        self.list.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self.list)

        self.setWidget(container)
        self._violations = []

    def _on_item_clicked(self, list_item: QListWidgetItem):
        idx = self.list.row(list_item)
        if 0 <= idx < len(self._violations):
            self.violation_selected.emit(self._violations[idx])

    def show_violations(self, violations: list):
        self._violations = violations
        self.list.clear()
        for v in violations:
            entry = QListWidgetItem(f"[{v.rule}] {v.message}")
            entry.setForeground(QColor(PandoraTheme.ACCENT_MAGENTA if v.severity == "error"
                                        else PandoraTheme.OUTLINE))
            self.list.addItem(entry)
        if violations:
            self.summary_label.setText(f"{len(violations)} Regelverstoß/-verstöße gefunden.")
        else:
            self.summary_label.setText("Keine Regelverstöße gefunden. ✓")


# ─────────────────────────────────────────────────────────────────────────
# AUTOROUTER (Grid-/Maze-Router mit A*)
# ─────────────────────────────────────────────────────────────────────────

class GridAutorouter:
    """Einfacher rasterbasierter Autorouter (Lee-/A*-Maze-Router).

    Für jede offene Ratsnest-Verbindung wird ein Raster über die Baugruppe gelegt,
    auf dem Kupfer-Elemente fremder Netze (inkl. Clearance-Puffer) als Hindernis
    markiert werden. A* mit 8-Wege-Bewegung sucht den kürzesten freien Pfad; das
    Ergebnis wird kollinear vereinfacht und als TraceItem eingefügt.

    Einschränkungen (MVP): kein Vias-Layer-Wechsel während des Routings (ein Layer
    pro Lauf), kein Push-and-Shove, kein Rip-up/Re-Route bei Sackgassen, Raster
    wird pro Segment neu aufgebaut (einfach, aber nicht performance-optimal bei
    sehr vielen Netzen)."""

    DIRECTIONS_8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def __init__(self, scene: PcbScene, cell_mm=0.3, clearance_mm=0.25,
                 trace_width_mm=0.25, max_cells=300_000):
        self.scene = scene
        self.cell_mm = cell_mm
        self.clearance_mm = clearance_mm
        self.trace_width_mm = trace_width_mm
        self.max_cells = max_cells

    def _bounds_px(self) -> QRectF:
        outline = next((it for it in self.scene.items() if isinstance(it, BoardOutlineItem)), None)
        rect = outline.sceneBoundingRect() if outline else self.scene.itemsBoundingRect()
        margin = 5 * MM_TO_PX
        return rect.adjusted(-margin, -margin, margin, margin)

    def _rasterize_obstacles(self, layer_type: LayerType, ignore_net_id):
        rect = self._bounds_px()
        cell_px = self.cell_mm * MM_TO_PX
        cols = max(1, int(rect.width() / cell_px) + 1)
        rows = max(1, int(rect.height() / cell_px) + 1)
        if cols * rows > self.max_cells:
            raise RuntimeError(f"Raster zu groß ({cols}x{rows} Zellen) - Zellgröße erhöhen.")
        blocked = bytearray(cols * rows)
        ox, oy = rect.left(), rect.top()
        clearance_px = self.clearance_mm * MM_TO_PX

        def mark(scene_rect: QRectF):
            r = scene_rect.adjusted(-clearance_px, -clearance_px, clearance_px, clearance_px)
            c0 = max(0, int((r.left() - ox) / cell_px))
            c1 = min(cols - 1, int((r.right() - ox) / cell_px))
            r0 = max(0, int((r.top() - oy) / cell_px))
            r1 = min(rows - 1, int((r.bottom() - oy) / cell_px))
            for rr in range(r0, r1 + 1):
                base = rr * cols
                for cc in range(c0, c1 + 1):
                    blocked[base + cc] = 1

        for item in self.scene.items():
            if getattr(item, "layer_type", None) != layer_type:
                continue
            if not isinstance(item, (PadItem, ViaItem, TraceItem)):
                continue
            if ignore_net_id is not None and getattr(item, "net_id", None) == ignore_net_id:
                continue
            mark(item.sceneBoundingRect())

        return blocked, cols, rows, ox, oy, cell_px

    def route_segment(self, net_id, p1_mm, p2_mm, layer_type: LayerType):
        blocked, cols, rows, ox, oy, cell_px = self._rasterize_obstacles(layer_type, net_id)

        def to_cell(pt_mm):
            c = int((pt_mm[0] * MM_TO_PX - ox) / cell_px)
            r = int((pt_mm[1] * MM_TO_PX - oy) / cell_px)
            return max(0, min(cols - 1, c)), max(0, min(rows - 1, r))

        def unblock_around(cell):
            cc0, rr0 = cell
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    cc, rr = cc0 + dc, rr0 + dr
                    if 0 <= cc < cols and 0 <= rr < rows:
                        blocked[rr * cols + cc] = 0

        start, goal = to_cell(p1_mm), to_cell(p2_mm)
        unblock_around(start)
        unblock_around(goal)

        path_cells = self._astar(blocked, cols, rows, start, goal)
        if path_cells is None:
            return None

        points = []
        for (c, r) in path_cells:
            x_mm = (ox + c * cell_px + cell_px / 2) / MM_TO_PX
            y_mm = (oy + r * cell_px + cell_px / 2) / MM_TO_PX
            points.append((x_mm, y_mm))
        points[0] = p1_mm
        points[-1] = p2_mm
        return self._simplify(points)

    def _astar(self, blocked, cols, rows, start, goal):
        def heuristic(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])

        open_heap = [(heuristic(start, goal), 0.0, start)]
        came_from = {start: None}
        best_cost = {start: 0.0}
        visited = set()

        while open_heap:
            _, g, current = heapq.heappop(open_heap)
            if current in visited:
                continue
            visited.add(current)
            if current == goal:
                path = []
                node = current
                while node is not None:
                    path.append(node)
                    node = came_from[node]
                path.reverse()
                return path
            cx, cy = current
            for dx, dy in self.DIRECTIONS_8:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < cols and 0 <= ny < rows):
                    continue
                if blocked[ny * cols + nx]:
                    continue
                neighbor = (nx, ny)
                if neighbor in visited:
                    continue
                ng = g + math.hypot(dx, dy)
                if ng < best_cost.get(neighbor, float("inf")):
                    best_cost[neighbor] = ng
                    came_from[neighbor] = current
                    heapq.heappush(open_heap, (ng + heuristic(neighbor, goal), ng, neighbor))
        return None

    @staticmethod
    def _simplify(points):
        if len(points) <= 2:
            return points
        simplified = [points[0]]
        for i in range(1, len(points) - 1):
            x0, y0 = simplified[-1]
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            cross = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
            if abs(cross) > 1e-6:
                simplified.append(points[i])
        simplified.append(points[-1])
        return simplified


class AutorouterDock(QDockWidget):
    def __init__(self):
        super().__init__("Autorouter")
        container = QWidget()
        lay = QVBoxLayout(container)

        settings_box = QGroupBox("Einstellungen")
        form = QFormLayout(settings_box)
        self.layer_combo = QComboBox()
        self.layer_combo.addItems(["Top Copper", "Bottom Copper"])
        self.cell_spin = QDoubleSpinBox()
        self.cell_spin.setRange(0.05, 2.0)
        self.cell_spin.setSingleStep(0.05)
        self.cell_spin.setValue(0.3)
        self.cell_spin.setSuffix(" mm")
        self.clearance_spin = QDoubleSpinBox()
        self.clearance_spin.setRange(0.05, 5.0)
        self.clearance_spin.setSingleStep(0.05)
        self.clearance_spin.setValue(0.25)
        self.clearance_spin.setSuffix(" mm")
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(0.05, 5.0)
        self.width_spin.setSingleStep(0.05)
        self.width_spin.setValue(0.25)
        self.width_spin.setSuffix(" mm")
        form.addRow("Ziel-Layer:", self.layer_combo)
        form.addRow("Raster-Zellgröße:", self.cell_spin)
        form.addRow("Min. Clearance:", self.clearance_spin)
        form.addRow("Trace-Breite:", self.width_spin)
        lay.addWidget(settings_box)

        self.run_button = QPushButton("Autorouter ausführen")
        lay.addWidget(self.run_button)

        self.summary_label = QLabel("Noch nicht ausgeführt.")
        lay.addWidget(self.summary_label)

        self.log_list = QListWidget()
        lay.addWidget(self.log_list)

        self.setWidget(container)

    def show_log(self, lines, routed, failed):
        self.log_list.clear()
        for line in lines:
            item = QListWidgetItem(line)
            if line.startswith("✗"):
                item.setForeground(QColor(PandoraTheme.ACCENT_MAGENTA))
            else:
                item.setForeground(QColor(PandoraTheme.ACCENT_CYAN))
            self.log_list.addItem(item)
        self.summary_label.setText(f"{routed} geroutet, {failed} fehlgeschlagen.")


# ─────────────────────────────────────────────────────────────────────────
# PROJECT IO
# ─────────────────────────────────────────────────────────────────────────

class ProjectIO:
    @staticmethod
    def save(path: str, scene: PcbScene):
        data = {
            "meta": {
                "app": "Pandora® - PCB Editor",
                "author": "AKI_SystemDown®",
                "created": datetime.utcnow().isoformat(),
                "version": "0.1.0-mvp",
            },
            "nets": [n.to_dict() for n in scene.netlist.nets.values()],
            "items": [],
        }
        for item in scene.items():
            if item.parentItem() is not None:
                continue  # Pads etc. innerhalb eines Footprints - werden über dessen to_dict gespeichert
            if hasattr(item, "to_dict"):
                data["items"].append(item.to_dict())
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def load(path: str, scene: PcbScene):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        scene.clear()
        scene.netlist.nets.clear()
        for n in data.get("nets", []):
            net = Net(n["name"], n.get("color"))
            net.id = n["id"]
            scene.netlist.nets[net.id] = net
        for d in data.get("items", []):
            item = ProjectIO._item_from_dict(d)
            if item:
                scene.addItem(item)

    @staticmethod
    def _item_from_dict(d):
        t = d["type"]
        if t == "pad":
            return PadItem(d["x"], d["y"], d["w"], d["h"], d["shape"],
                            LayerType(d["layer"]), d.get("drill", 0.0), d.get("net"))
        if t == "via":
            return ViaItem(d["x"], d["y"], d["dia"], d["drill"], d.get("net"))
        if t == "trace":
            return TraceItem(d["points"], d["width"], LayerType(d["layer"]), d.get("net"))
        if t == "footprint":
            key = d.get("footprint_key")
            if key and key in FOOTPRINT_LIBRARY:
                item = FootprintItem(d["x"], d["y"], key, d.get("ref", "U?"),
                                      d.get("value", ""), d.get("rot", 0.0))
            else:
                # Alt-Projektformat (vor der Footprint-Bibliothek): w/h/pins statt footprint_key
                fp_def = _legacy_generic_def(d.get("w", 5.0), d.get("h", 5.0), d.get("pins", 8))
                item = FootprintItem(d["x"], d["y"], "LEGACY", d.get("ref", "U?"),
                                      d.get("value", ""), d.get("rot", 0.0),
                                      fp_def_override=fp_def)
            for pin_no, net_id in d.get("pad_nets", {}).items():
                for pad in item.pad_items:
                    if pad.pin_number == pin_no:
                        pad.net_id = net_id
            return item
        if t == "outline":
            return BoardOutlineItem(d["points"])
        return None


# ─────────────────────────────────────────────────────────────────────────
# GERBER X2 + EXCELLON EXPORT (vollständig)
# ─────────────────────────────────────────────────────────────────────────
# Erzeugt je Layer eine eigenständige, spezifikationskonforme RS-274X-Datei
# mit Gerber-X2-Dateiattributen (%TF.*%) und Aperturfunktions-Attributen
# (%TA.AperFunction*%/%TD*%) sowie eine separate Excellon-Bohrdatei (PTH).
# Referenzen: Gerber Format Specification (Ucamco) Rev. aktuell, Excellon
# Format (XNC/METRIC, Werkzeugtabelle + G05-Bohrbefehle).
#
# Koordinatenformat: %FSLAX46Y46*% (Leading-Zero-Suppression, 4 Vorkomma-,
# 6 Nachkommastellen, Einheit mm) → interner Skalierungsfaktor 10^6.
# Die interne Szene nutzt mm mit nach unten wachsender Y-Achse (Qt-Konvention);
# beim Export wird Y gespiegelt (mathematisch positiv nach oben, Gerber-Norm).

class GerberApertureTable:
    """Verwaltet D-Code-Zuweisung + Apertur-Definitionen (inkl. X2-AperFunction-
    Attributen) für eine einzelne Gerber-Datei. Gleiche Form/Größe/Funktion
    bekommt denselben D-Code (kein doppeltes Anlegen)."""

    def __init__(self, start_dcode: int = 10):
        self._next = start_dcode
        self._cache: dict = {}
        self._def_lines: list[str] = []

    def get(self, shape: str, params: tuple, aper_function: str = None) -> int:
        key = (shape, params, aper_function)
        if key in self._cache:
            return self._cache[key]
        code = self._next
        self._next += 1
        self._cache[key] = code
        if aper_function:
            self._def_lines.append(f"%TA.AperFunction,{aper_function}*%")
        if shape == "C":
            (dia,) = params
            self._def_lines.append(f"%ADD{code}C,{max(dia, 0.01):.4f}*%")
        elif shape == "R":
            w, h = params
            self._def_lines.append(f"%ADD{code}R,{max(w, 0.01):.4f}X{max(h, 0.01):.4f}*%")
        elif shape == "O":
            w, h = params
            self._def_lines.append(f"%ADD{code}O,{max(w, 0.01):.4f}X{max(h, 0.01):.4f}*%")
        else:
            raise ValueError(f"Unbekannte Aperturform: {shape}")
        if aper_function:
            self._def_lines.append("%TD*%")
        return code

    def def_lines(self) -> list[str]:
        return list(self._def_lines)


class GerberX2Exporter:
    """
    Vollständiger Gerber-X2-Export (RS-274X + Datei-/Aperturattribute) je
    Layer, plus separater Excellon-Bohrdatei für alle durchkontaktierten
    Bohrungen (Vias + THT-Pads).

    Erzeugte Dateien (bei export_all):
        pandora_top_copper.gbr     - %TF.FileFunction,Copper,L1,Top%
        pandora_bottom_copper.gbr  - %TF.FileFunction,Copper,L2,Bot%
        pandora_top_silk.gbr       - %TF.FileFunction,Legend,Top%
        pandora_bottom_silk.gbr    - %TF.FileFunction,Legend,Bot%
        pandora_outline.gbr        - %TF.FileFunction,Profile,NP%
        pandora_drill_pth.drl      - Excellon, METRIC, PTH (Vias + THT-Pads)

    Einschränkungen (siehe README-Roadmap): Footprint-Pads liegen intern immer
    auf Top-Copper (keine echten Multi-Layer-THT-Pads); alle Bohrungen mit
    drill_mm > 0 werden als durchkontaktiert (PTH) exportiert, eine NPTH-
    Trennung (z. B. reine Befestigungsbohrungen) findet nicht statt.
    """

    GEN_SOFTWARE = "%TF.GenerationSoftware,AKI_SystemDown,Pandora PCB Editor,0.2.0*%"
    COORD_SCALE = 1_000_000  # 4.6-Format -> 6 Nachkommastellen

    # -- Hilfsfunktionen -----------------------------------------------------
    @staticmethod
    def _now_iso() -> str:
        return datetime.now().astimezone().replace(microsecond=0).isoformat()

    @staticmethod
    def _fmt(v_mm: float) -> str:
        """mm -> Gerber-Ganzzahl im 4.6-Format (Leading-Zero-Suppression)."""
        return str(int(round(v_mm * GerberX2Exporter.COORD_SCALE)))

    @staticmethod
    def _abs_mm(item) -> tuple:
        """Absolute Board-Position (mm, Gerber-Y nach oben) eines Items -
        via scenePos(), damit auch Footprint-Kind-Pads (Gruppen-Kinder mit
        Rotation/Offset) korrekt aufgelöst werden."""
        sp = item.scenePos()
        return sp.x() / MM_TO_PX, -sp.y() / MM_TO_PX

    @staticmethod
    def _header(file_function: str, extra_tf: list = None) -> list:
        lines = [
            GerberX2Exporter.GEN_SOFTWARE,
            f"%TF.CreationDate,{GerberX2Exporter._now_iso()}*%",
            "%TF.Part,Single*%",
            f"%TF.FileFunction,{file_function}*%",
        ]
        if extra_tf:
            lines.extend(extra_tf)
        lines += ["%FSLAX46Y46*%", "%MOMM*%",
                  "G04 Pandora PCB Editor - Gerber X2 Export*", "G01*"]
        return lines

    @staticmethod
    def _footer() -> list:
        return ["M02*"]

    @staticmethod
    def _pad_aperture(apertures: "GerberApertureTable", pad, aper_function: str) -> int:
        shape, w, h = pad.shape, pad.width_mm, pad.height_mm
        if shape == "round" and abs(w - h) < 1e-6:
            return apertures.get("C", (round(w, 4),), aper_function)
        if shape in ("round", "oval"):
            return apertures.get("O", (round(w, 4), round(h, 4)), aper_function)
        return apertures.get("R", (round(w, 4), round(h, 4)), aper_function)

    # -- Copper-Layer ---------------------------------------------------------
    @staticmethod
    def export_copper_layer(scene: "PcbScene", ltype: LayerType, out_path: str):
        assert ltype in (LayerType.TOP_COPPER, LayerType.BOTTOM_COPPER)
        side = "Top" if ltype == LayerType.TOP_COPPER else "Bot"
        layer_no = "L1" if ltype == LayerType.TOP_COPPER else "L2"
        header = GerberX2Exporter._header(
            f"Copper,{layer_no},{side}", ["%TF.FilePolarity,Positive*%"])

        apertures = GerberApertureTable()
        body: list[str] = []
        last_dcode = None

        def select(code):
            nonlocal last_dcode
            if code != last_dcode:
                body.append(f"D{code}*")
                last_dcode = code

        for item in scene.items():
            kind = getattr(item, "kind", None)
            if getattr(item, "layer_type", None) != ltype:
                continue
            if kind == "pad":
                aper_func = "ComponentPad" if item.drill_mm > 0 else "SMDPad,CuDef"
                code = GerberX2Exporter._pad_aperture(apertures, item, aper_func)
                x, y = GerberX2Exporter._abs_mm(item)
                select(code)
                body.append(f"X{GerberX2Exporter._fmt(x)}Y{GerberX2Exporter._fmt(y)}D03*")
            elif kind == "via":
                code = apertures.get("C", (round(item.dia_mm, 4),), "Via")
                x, y = GerberX2Exporter._abs_mm(item)
                select(code)
                body.append(f"X{GerberX2Exporter._fmt(x)}Y{GerberX2Exporter._fmt(y)}D03*")
            elif kind == "trace":
                code = apertures.get("C", (round(item.width_mm, 4),), "Conductor")
                pts = item.points_mm
                if not pts:
                    continue
                select(code)
                x0, y0 = pts[0][0], -pts[0][1]
                body.append(f"X{GerberX2Exporter._fmt(x0)}Y{GerberX2Exporter._fmt(y0)}D02*")
                for (px, py) in pts[1:]:
                    x, y = px, -py
                    body.append(f"X{GerberX2Exporter._fmt(x)}Y{GerberX2Exporter._fmt(y)}D01*")

        full = header + apertures.def_lines() + body + GerberX2Exporter._footer()
        Path(out_path).write_text("\n".join(full) + "\n", encoding="utf-8")

    # -- Silkscreen-Layer -------------------------------------------------------
    @staticmethod
    def export_silk_layer(scene: "PcbScene", ltype: LayerType, out_path: str):
        assert ltype in (LayerType.TOP_SILK, LayerType.BOTTOM_SILK)
        side = "Top" if ltype == LayerType.TOP_SILK else "Bot"
        header = GerberX2Exporter._header(f"Legend,{side}")

        apertures = GerberApertureTable()
        code = apertures.get("C", (0.15,), "Legend")
        body: list[str] = [f"D{code}*"]

        for item in scene.items():
            if getattr(item, "kind", None) != "footprint":
                continue
            if item.layer_type != ltype:
                continue
            fp = item.fp_def
            body.append(f"G04 Bauteil {item.ref} ({fp.name})*")
            poly = fp.body_poly
            if len(poly) < 2:
                continue
            pts_scene = [item.mapToScene(px * MM_TO_PX, py * MM_TO_PX) for px, py in poly]
            pts_mm = [(p.x() / MM_TO_PX, -p.y() / MM_TO_PX) for p in pts_scene]
            closed = pts_mm + [pts_mm[0]]
            x0, y0 = closed[0]
            body.append(f"X{GerberX2Exporter._fmt(x0)}Y{GerberX2Exporter._fmt(y0)}D02*")
            for (x, y) in closed[1:]:
                body.append(f"X{GerberX2Exporter._fmt(x)}Y{GerberX2Exporter._fmt(y)}D01*")

        full = header + apertures.def_lines() + body + GerberX2Exporter._footer()
        Path(out_path).write_text("\n".join(full) + "\n", encoding="utf-8")

    # -- Board-Outline / Profile ------------------------------------------------
    @staticmethod
    def export_outline_layer(scene: "PcbScene", out_path: str):
        header = GerberX2Exporter._header("Profile,NP")
        apertures = GerberApertureTable()
        code = apertures.get("C", (0.10,))
        body: list[str] = [f"D{code}*"]

        for item in scene.items():
            if getattr(item, "kind", None) != "outline":
                continue
            pts = item.points_mm
            if len(pts) < 2:
                continue
            closed = list(pts) + [pts[0]]
            x0, y0 = closed[0][0], -closed[0][1]
            body.append(f"X{GerberX2Exporter._fmt(x0)}Y{GerberX2Exporter._fmt(y0)}D02*")
            for (px, py) in closed[1:]:
                x, y = px, -py
                body.append(f"X{GerberX2Exporter._fmt(x)}Y{GerberX2Exporter._fmt(y)}D01*")

        full = header + apertures.def_lines() + body + GerberX2Exporter._footer()
        Path(out_path).write_text("\n".join(full) + "\n", encoding="utf-8")

    # -- Excellon-Bohrdatei (PTH) -------------------------------------------------
    @staticmethod
    def export_excellon(scene: "PcbScene", out_path: str):
        holes = []  # (x_mm, y_mm, drill_dia_mm)
        for item in scene.items():
            kind = getattr(item, "kind", None)
            if kind == "via":
                x, y = GerberX2Exporter._abs_mm(item)
                holes.append((x, y, item.drill_mm))
            elif kind == "pad" and item.drill_mm > 0:
                x, y = GerberX2Exporter._abs_mm(item)
                holes.append((x, y, item.drill_mm))

        by_tool: dict = {}
        for x, y, d in holes:
            by_tool.setdefault(round(d, 3), []).append((x, y))
        tools = sorted(by_tool.keys())

        lines = [
            "M48",
            "; Pandora PCB Editor - Excellon-Bohrdatei (PTH, durchkontaktiert)",
            f"; Erzeugt {GerberX2Exporter._now_iso()}",
            f"; Werkzeuge: {len(tools)}, Bohrungen gesamt: {len(holes)}",
            "METRIC,LZ",
        ]
        for i, dia in enumerate(tools, start=1):
            lines.append(f"T{i:02d}C{max(dia, 0.05):.3f}")
        lines.append("%")
        lines.append("G90")  # Absolutkoordinaten
        lines.append("G05")  # Bohrmodus
        for i, dia in enumerate(tools, start=1):
            lines.append(f"T{i:02d}")
            for x, y in by_tool[dia]:
                lines.append(f"X{x:.3f}Y{y:.3f}")
        lines.append("M30")
        Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")

    # -- Gesamtexport -------------------------------------------------------
    @staticmethod
    def export_all(scene: "PcbScene", directory: str) -> list:
        """Exportiert den vollständigen Layer-Satz + Excellon-Drill nach
        `directory`. Gibt die Liste der erzeugten Dateipfade zurück."""
        d = Path(directory)
        out = {
            "top_copper": d / "pandora_top_copper.gbr",
            "bottom_copper": d / "pandora_bottom_copper.gbr",
            "top_silk": d / "pandora_top_silk.gbr",
            "bottom_silk": d / "pandora_bottom_silk.gbr",
            "outline": d / "pandora_outline.gbr",
            "drill_pth": d / "pandora_drill_pth.drl",
        }
        GerberX2Exporter.export_copper_layer(scene, LayerType.TOP_COPPER, str(out["top_copper"]))
        GerberX2Exporter.export_copper_layer(scene, LayerType.BOTTOM_COPPER, str(out["bottom_copper"]))
        GerberX2Exporter.export_silk_layer(scene, LayerType.TOP_SILK, str(out["top_silk"]))
        GerberX2Exporter.export_silk_layer(scene, LayerType.BOTTOM_SILK, str(out["bottom_silk"]))
        GerberX2Exporter.export_outline_layer(scene, str(out["outline"]))
        GerberX2Exporter.export_excellon(scene, str(out["drill_pth"]))
        return [str(p) for p in out.values()]


# Rückwärtskompatibler Alias (alter Klassenname im Menü-/Rest-Code referenziert).
GerberExporter = GerberX2Exporter


# ─────────────────────────────────────────────────────────────────────────
# 3D-VORSCHAU
# ─────────────────────────────────────────────────────────────────────────
# Leichtgewichtige 3D-Vorschau des Boards, gerendert mit matplotlib (mplot3d).
# Kein vollwertiger PCB-3D-Renderer (kein STEP/Bauteilkörper-Import), aber
# ausreichend für einen schnellen visuellen Eindruck: Board-Substrat (extrudiert
# aus dem Board-Umriss), Kupfer-Layer (Pads/Vias/Traces, Top orange / Bottom
# blau, analog zur 2D-Ansicht), Bohrungen als ausgesparte Zylinder sowie
# Footprint-Silkscreen-Umrisse. Frei drehbar/zoombar per Maus (mplot3d-
# Standardsteuerung), zusätzlich Buttons für Oben/Unten/Isometrisch.

BOARD_THICKNESS_MM = 1.6       # Standard-FR4-Stärke
COPPER_THICKNESS_MM = 0.035    # ~1oz Kupferauflage
SILK_LINE_WIDTH_MM = 0.15

try:
    import matplotlib
    matplotlib.use("QtAgg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as _FigureCanvas
    from matplotlib.figure import Figure as _Figure
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection as _Poly3DCollection
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False


class Preview3DDialog(QDialog):
    """Zeigt eine 3D-Vorschau der aktuellen Szene in einem eigenen Fenster."""

    def __init__(self, scene: "PcbScene", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Pandora® - 3D-Vorschau")
        self.resize(1000, 750)
        self.scene = scene

        layout = QVBoxLayout(self)

        if not MATPLOTLIB_AVAILABLE:
            hint = QLabel(
                "Für die 3D-Vorschau wird matplotlib benötigt.\n\n"
                "Installation:\n"
                "    pip install matplotlib --break-system-packages\n\n"
                "Anschließend Pandora PCB Editor neu starten."
            )
            hint.setWordWrap(True)
            layout.addWidget(hint)
            return

        self.figure = _Figure(facecolor=PandoraTheme.BG_DARKEST)
        self.canvas = _FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        btn_row = QHBoxLayout()
        iso_btn = QPushButton("Isometrisch")
        iso_btn.clicked.connect(lambda: self._set_view(28, -60))
        top_btn = QPushButton("Oben (Bestückungsseite)")
        top_btn.clicked.connect(lambda: self._set_view(89, -90))
        bottom_btn = QPushButton("Unten")
        bottom_btn.clicked.connect(lambda: self._set_view(-89, -90))
        refresh_btn = QPushButton("Neu berechnen")
        refresh_btn.clicked.connect(self._render)
        for b in (iso_btn, top_btn, bottom_btn, refresh_btn):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.ax = self.figure.add_subplot(111, projection="3d")
        self._render()

    def _set_view(self, elev, azim):
        self.ax.view_init(elev=elev, azim=azim)
        self.canvas.draw_idle()

    # -- Geometrie-Hilfsfunktionen ---------------------------------------
    @staticmethod
    def _abs_xy_mm(item):
        """Absolute Board-Koordinate (mm, Y nach oben) via scenePos() - löst
        auch Footprint-Kind-Pads (Gruppen-Kinder mit Rotation) korrekt auf,
        analog zu GerberX2Exporter._abs_mm()."""
        sp = item.scenePos()
        return sp.x() / MM_TO_PX, -sp.y() / MM_TO_PX

    def _add_polygon_prism(self, points_mm, z0, z1, color, alpha=1.0):
        """Extrudiert ein 2D-Polygon zu einem Prisma (Deckel/Boden + Seiten)."""
        if len(points_mm) < 3:
            return
        bottom = [(x, y, z0) for x, y in points_mm]
        top = [(x, y, z1) for x, y in points_mm]
        faces = [bottom, top]
        n = len(points_mm)
        for i in range(n):
            j = (i + 1) % n
            faces.append([bottom[i], bottom[j], top[j], top[i]])
        self.ax.add_collection3d(
            _Poly3DCollection(faces, facecolor=color, edgecolor="none", alpha=alpha))

    def _add_box(self, cx, cy, z0, z1, w, h, color):
        hw, hh = w / 2, h / 2
        pts = [(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)]
        self._add_polygon_prism(pts, z0, z1, color)

    def _add_cylinder(self, cx, cy, z0, z1, radius, color, segments=14):
        pts = [(cx + radius * math.cos(2 * math.pi * i / segments),
                cy + radius * math.sin(2 * math.pi * i / segments)) for i in range(segments)]
        self._add_polygon_prism(pts, z0, z1, color)

    def _add_ribbon(self, points_mm, width_mm, z0, z1, color):
        """Extrudiert eine Mehrsegment-Linie (Trace/Silk-Umriss) segmentweise
        als flaches Band mit Ober-/Unterseite."""
        hw = max(width_mm, 0.05) / 2
        for (x1, y1), (x2, y2) in zip(points_mm, points_mm[1:]):
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy)
            if length < 1e-6:
                continue
            nx, ny = -dy / length * hw, dx / length * hw
            quad_top = [(x1 + nx, y1 + ny, z1), (x2 + nx, y2 + ny, z1),
                        (x2 - nx, y2 - ny, z1), (x1 - nx, y1 - ny, z1)]
            quad_bot = [(x1 + nx, y1 + ny, z0), (x2 + nx, y2 + ny, z0),
                        (x2 - nx, y2 - ny, z0), (x1 - nx, y1 - ny, z0)]
            self.ax.add_collection3d(
                _Poly3DCollection([quad_top, quad_bot], facecolor=color, edgecolor="none"))

    # -- Hauptrender -------------------------------------------------------
    def _render(self):
        self.ax.clear()
        self.figure.patch.set_facecolor(PandoraTheme.BG_DARKEST)
        try:
            self.ax.set_facecolor(PandoraTheme.BG_DARKEST)
            for axis in (self.ax.xaxis, self.ax.yaxis, self.ax.zaxis):
                axis.set_pane_color((0.04, 0.04, 0.07, 1.0))
        except Exception:
            pass
        self.ax.grid(False)

        outline_item = next((it for it in self.scene.items()
                              if getattr(it, "kind", None) == "outline"), None)
        if outline_item is not None:
            outline_pts = list(outline_item.points_mm)
        else:
            # Kein Board-Umriss gezeichnet: Bounding-Box aller Elemente + Rand
            rect = self.scene.itemsBoundingRect()
            if rect.isNull() or rect.width() < 1 or rect.height() < 1:
                rect = QRectF(0, 0, 40 * MM_TO_PX, 30 * MM_TO_PX)
            margin = 2.0
            x0, y0 = rect.left() / MM_TO_PX - margin, -rect.bottom() / MM_TO_PX - margin
            x1, y1 = rect.right() / MM_TO_PX + margin, -rect.top() / MM_TO_PX + margin
            outline_pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

        z_bot, z_top = 0.0, BOARD_THICKNESS_MM
        z_cu_bot0, z_cu_bot1 = -COPPER_THICKNESS_MM, 0.0
        z_cu_top0, z_cu_top1 = z_top, z_top + COPPER_THICKNESS_MM

        # Board-Substrat (FR4, dunkelgrün)
        self._add_polygon_prism(outline_pts, z_bot, z_top, "#0e4d2e", alpha=0.95)

        for item in self.scene.items():
            kind = getattr(item, "kind", None)
            if kind == "pad":
                x, y = self._abs_xy_mm(item)
                is_top = item.layer_type == LayerType.TOP_COPPER
                z0, z1 = (z_cu_top0, z_cu_top1) if is_top else (z_cu_bot0, z_cu_bot1)
                color = PandoraTheme.COPPER_TOP if is_top else PandoraTheme.COPPER_BOTTOM
                self._add_box(x, y, z0, z1, max(item.width_mm, 0.1), max(item.height_mm, 0.1), color)
                if item.drill_mm > 0:
                    self._add_cylinder(x, y, z_cu_bot0, z_cu_top1, item.drill_mm / 2,
                                        PandoraTheme.BG_DARKEST)
            elif kind == "via":
                x, y = self._abs_xy_mm(item)
                self._add_cylinder(x, y, z_cu_bot0, z_cu_top1, item.dia_mm / 2,
                                    PandoraTheme.ACCENT_PURPLE)
                self._add_cylinder(x, y, z_cu_bot0, z_cu_top1, item.drill_mm / 2,
                                    PandoraTheme.BG_DARKEST)
            elif kind == "trace":
                pts = [(px, -py) for px, py in item.points_mm]
                is_top = item.layer_type == LayerType.TOP_COPPER
                z0, z1 = (z_cu_top0, z_cu_top1) if is_top else (z_cu_bot0, z_cu_bot1)
                color = PandoraTheme.COPPER_TOP if is_top else PandoraTheme.COPPER_BOTTOM
                self._add_ribbon(pts, item.width_mm, z0, z1, color)
            elif kind == "footprint":
                fp = item.fp_def
                if len(fp.body_poly) >= 2:
                    scene_pts = [item.mapToScene(px * MM_TO_PX, py * MM_TO_PX) for px, py in fp.body_poly]
                    pts = [(p.x() / MM_TO_PX, -p.y() / MM_TO_PX) for p in scene_pts]
                    closed = pts + [pts[0]]
                    is_top = item.layer_type == LayerType.TOP_SILK
                    color = PandoraTheme.SILK_TOP if is_top else PandoraTheme.SILK_BOTTOM
                    z0 = z_cu_top1 if is_top else z_cu_bot0 - 0.02
                    z1 = z0 + 0.02
                    self._add_ribbon(closed, SILK_LINE_WIDTH_MM, z0, z1, color)

        xs = [p[0] for p in outline_pts]
        ys = [p[1] for p in outline_pts]
        span = max(max(xs) - min(xs), max(ys) - min(ys), 10.0)
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        self.ax.set_xlim(cx - span / 1.6, cx + span / 1.6)
        self.ax.set_ylim(cy - span / 1.6, cy + span / 1.6)
        self.ax.set_zlim(-span / 6, span / 6)
        try:
            self.ax.set_box_aspect((1, 1, 0.35))
        except Exception:
            pass
        self.ax.set_xlabel("X (mm)", color=PandoraTheme.TEXT_MUTED)
        self.ax.set_ylabel("Y (mm)", color=PandoraTheme.TEXT_MUTED)
        self.ax.set_zlabel("Z (mm)", color=PandoraTheme.TEXT_MUTED)
        self.ax.view_init(elev=28, azim=-60)
        self.canvas.draw_idle()


# ─────────────────────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pandora® - PCB Editor | by AKI_SystemDown® ©2026")
        self.resize(1400, 900)
        icon_path = Path(__file__).resolve().parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.layer_stack = LayerStack()
        self.netlist = Netlist()
        self.undo_stack = QUndoStack(self)
        self.scene = PcbScene(self.layer_stack, self.netlist, self.undo_stack)
        self.view = PcbView(self.scene)
        self.setCentralWidget(self.view)
        self.current_path = None
        self.active_footprint_key = None
        self._ref_counters = {}

        self._build_docks()
        self._build_toolbar()
        self._build_menu()
        self._build_statusbar()

        self.scene.selectionChanged.connect(self._on_selection_changed)
        self.view.coords_changed.connect(self._on_coords_changed)
        self.undo_stack.indexChanged.connect(lambda _: self.scene.update_ratsnest())
        self.scene.update_ratsnest()

    # -- UI Aufbau -------------------------------------------------------
    def _build_docks(self):
        self.layers_dock = LayersDock(self.layer_stack)
        self.layers_dock.layer_visibility_changed.connect(self._apply_layer_visibility)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.layers_dock)

        self.fp_lib_dock = FootprintLibraryDock()
        self.fp_lib_dock.footprint_chosen.connect(self._on_footprint_chosen)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.fp_lib_dock)
        self.tabifyDockWidget(self.layers_dock, self.fp_lib_dock)
        self.view.footprint_factory = self._create_footprint_at

        self.props_dock = PropertiesDock(self.netlist)
        self.props_dock.net_assigned.connect(self._on_net_assigned)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.props_dock)

        self.drc_dock = DRCDock()
        self.drc_dock.run_button.clicked.connect(self._run_drc)
        self.drc_dock.violation_selected.connect(self._on_violation_selected)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.drc_dock)

        self.autorouter_dock = AutorouterDock()
        self.autorouter_dock.run_button.clicked.connect(self._run_autorouter)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.autorouter_dock)
        self.tabifyDockWidget(self.drc_dock, self.autorouter_dock)

    def _build_toolbar(self):
        tb = QToolBar("Werkzeuge")
        tb.setMovable(False)
        self.addToolBar(tb)

        def add_tool(label, mode):
            act = QAction(label, self)
            act.setCheckable(True)
            act.triggered.connect(lambda: (self.view.set_tool(mode), self._sync_tool_actions(act)))
            tb.addAction(act)
            self._tool_actions.append(act)
            return act

        self._tool_actions = []
        add_tool("Auswählen", ToolMode.SELECT).setChecked(True)
        add_tool("Leiterbahn", ToolMode.TRACE)
        add_tool("Pad", ToolMode.PAD)
        add_tool("Via", ToolMode.VIA)
        self._footprint_tool_action = add_tool("Footprint", ToolMode.FOOTPRINT)
        add_tool("Board-Umriss", ToolMode.OUTLINE)

        tb.addSeparator()
        rotate_act = QAction("Bauteil drehen", self)
        rotate_act.setShortcut(QKeySequence("Ctrl+R"))
        rotate_act.triggered.connect(self._rotate_selected)
        tb.addAction(rotate_act)

        tb.addSeparator()
        grid_label = QLabel(" Raster (mm): ")
        tb.addWidget(grid_label)
        grid_spin = QDoubleSpinBox()
        grid_spin.setRange(0.05, 10.0)
        grid_spin.setSingleStep(0.05)
        grid_spin.setValue(self.scene.grid_mm)
        grid_spin.valueChanged.connect(self._set_grid)
        tb.addWidget(grid_spin)

        tb.addSeparator()
        del_act = QAction("Löschen", self)
        del_act.setShortcut(QKeySequence.StandardKey.Delete)
        del_act.triggered.connect(self._delete_selected)
        tb.addAction(del_act)

        tb.addSeparator()
        ratsnest_act = QAction("Ratsnest", self)
        ratsnest_act.setCheckable(True)
        ratsnest_act.setChecked(True)
        ratsnest_act.triggered.connect(self.scene.set_ratsnest_visible)
        tb.addAction(ratsnest_act)

        tb.addSeparator()
        preview3d_tb_act = QAction("3D-Vorschau", self)
        preview3d_tb_act.setToolTip("3D-Vorschau des Boards öffnen (Strg+3)")
        preview3d_tb_act.triggered.connect(self._open_3d_preview)
        tb.addAction(preview3d_tb_act)

    def _sync_tool_actions(self, active_act):
        for act in self._tool_actions:
            act.setChecked(act is active_act)

    def _build_menu(self):
        menu = self.menuBar()
        file_menu = menu.addMenu("&Projekt")
        new_act = QAction("Neu", self); new_act.triggered.connect(self._new_project)
        open_act = QAction("Öffnen…", self); open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._open_project)
        save_act = QAction("Speichern…", self); save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self._save_project)
        export_act = QAction("Gerber X2 / Excellon-Export…", self)
        export_act.triggered.connect(self._export_gerber)
        for a in (new_act, open_act, save_act, export_act):
            file_menu.addAction(a)

        edit_menu = menu.addMenu("&Bearbeiten")
        undo_act = self.undo_stack.createUndoAction(self, "Rückgängig")
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        redo_act = self.undo_stack.createRedoAction(self, "Wiederholen")
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(undo_act)
        edit_menu.addAction(redo_act)

        net_menu = menu.addMenu("&Netzliste")
        add_net_act = QAction("Neues Netz…", self)
        add_net_act.triggered.connect(self._add_net_dialog)
        net_menu.addAction(add_net_act)

        tools_menu = menu.addMenu("&Werkzeuge")
        drc_act = QAction("DRC ausführen", self)
        drc_act.triggered.connect(self._run_drc)
        tools_menu.addAction(drc_act)
        ratsnest_refresh_act = QAction("Ratsnest aktualisieren", self)
        ratsnest_refresh_act.triggered.connect(self.scene.update_ratsnest)
        tools_menu.addAction(ratsnest_refresh_act)
        autoroute_act = QAction("Autorouter ausführen", self)
        autoroute_act.triggered.connect(self._run_autorouter)
        tools_menu.addAction(autoroute_act)
        tools_menu.addSeparator()
        preview3d_act = QAction("3D-Vorschau…", self)
        preview3d_act.setShortcut(QKeySequence("Ctrl+3"))
        preview3d_act.triggered.connect(self._open_3d_preview)
        tools_menu.addAction(preview3d_act)

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.coord_label = QLabel("X: 0.00mm  Y: 0.00mm")
        self.status.addWidget(self.coord_label)
        self.status.addPermanentWidget(QLabel("Pandora® - PCB Editor v0.1.0-mvp"))

    # -- Callbacks ---------------------------------------------------------
    def _on_coords_changed(self, x, y):
        self.coord_label.setText(f"X: {x:.2f}mm  Y: {y:.2f}mm")

    def _on_selection_changed(self):
        items = self.scene.selectedItems()
        self.props_dock.show_item(items[0] if items else None)

    def _apply_layer_visibility(self):
        for item in self.scene.items():
            ltype = getattr(item, "layer_type", None)
            if ltype is not None:
                item.setVisible(self.layer_stack.by_type(ltype).visible)

    def _set_grid(self, val):
        self.scene.grid_mm = val
        self.scene.update()

    def _delete_selected(self):
        items = self.scene.selectedItems()
        if items:
            self.undo_stack.push(DeleteItemsCommand(self.scene, items))

    def _add_net_dialog(self):
        name, ok = QInputDialog.getText(self, "Neues Netz", "Netzname:")
        if ok and name:
            self.netlist.add_net(name)

    def _on_net_assigned(self, item, net_id):
        item.net_id = net_id
        self.scene.update_ratsnest()

    def _on_footprint_chosen(self, key):
        self.active_footprint_key = key
        self.view.set_tool(ToolMode.FOOTPRINT)
        self._sync_tool_actions(self._footprint_tool_action)
        self.status.showMessage(f"Footprint „{FOOTPRINT_LIBRARY[key].name}“ gewählt – "
                                 f"auf dem Board platzieren.", 4000)

    def _create_footprint_at(self, x_mm, y_mm):
        key = self.active_footprint_key
        if not key:
            self.status.showMessage("Bitte zuerst einen Footprint aus der Bibliothek wählen.", 4000)
            return
        fp = FOOTPRINT_LIBRARY[key]
        n = self._ref_counters.get(fp.ref_prefix, 0) + 1
        self._ref_counters[fp.ref_prefix] = n
        ref = f"{fp.ref_prefix}{n}"
        value = self.fp_lib_dock.value_edit.text().strip()
        item = FootprintItem(x_mm, y_mm, key, ref, value)
        self.undo_stack.push(AddItemCommand(self.scene, item, f"Footprint {ref} platzieren"))

    def _rotate_selected(self):
        items = [it for it in self.scene.selectedItems()]
        if items:
            self.undo_stack.push(RotateItemsCommand(items, 90.0, "Bauteil drehen"))

    def _recompute_ref_counters(self):
        self._ref_counters = {}
        for item in self.scene.items():
            if getattr(item, "kind", None) != "footprint":
                continue
            m = re.match(r"([A-Za-z_]+)(\d+)$", item.ref or "")
            if m:
                prefix, num = m.group(1), int(m.group(2))
                self._ref_counters[prefix] = max(self._ref_counters.get(prefix, 0), num)

    def _run_drc(self):
        violations = DesignRuleChecker.run(
            self.scene,
            min_clearance_mm=self.drc_dock.clearance_spin.value(),
            min_trace_width_mm=self.drc_dock.trace_width_spin.value(),
            min_drill_mm=self.drc_dock.drill_spin.value(),
        )
        self.drc_dock.show_violations(violations)
        self.status.showMessage(f"DRC abgeschlossen: {len(violations)} Verstoß/Verstöße", 4000)

    def _on_violation_selected(self, violation: DRCViolation):
        self.scene.clearSelection()
        for item in violation.items:
            item.setSelected(True)
        if violation.items:
            rect = violation.items[0].sceneBoundingRect()
            for it in violation.items[1:]:
                rect = rect.united(it.sceneBoundingRect())
            self.view.fitInView(rect.adjusted(-40, -40, 40, 40), Qt.AspectRatioMode.KeepAspectRatio)

    def _run_autorouter(self):
        layer = (LayerType.TOP_COPPER if self.autorouter_dock.layer_combo.currentText() == "Top Copper"
                 else LayerType.BOTTOM_COPPER)
        segments = RatsnestEngine.compute(self.scene)
        if not segments:
            QMessageBox.information(self, "Autorouter", "Keine offenen Verbindungen (Ratsnest) vorhanden.")
            return

        router = GridAutorouter(
            self.scene,
            cell_mm=self.autorouter_dock.cell_spin.value(),
            clearance_mm=self.autorouter_dock.clearance_spin.value(),
            trace_width_mm=self.autorouter_dock.width_spin.value(),
        )

        log_lines, routed, failed = [], 0, 0
        self.undo_stack.beginMacro("Autorouter")
        try:
            for net_id, p1, p2, _color in segments:
                net_name = self.netlist.nets[net_id].name if net_id in self.netlist.nets else net_id
                try:
                    path = router.route_segment(net_id, p1, p2, layer)
                except RuntimeError as e:
                    log_lines.append(f"✗ {net_name}: {e}")
                    failed += 1
                    continue
                if path is None:
                    log_lines.append(f"✗ {net_name}: kein freier Pfad gefunden")
                    failed += 1
                    continue
                trace = TraceItem(path, router.trace_width_mm, layer, net_id)
                self.undo_stack.push(AddItemCommand(self.scene, trace, f"Autoroute {net_name}"))
                log_lines.append(f"✓ {net_name}: {len(path)} Stützpunkte")
                routed += 1
        finally:
            self.undo_stack.endMacro()

        self.scene.update_ratsnest()
        self.autorouter_dock.show_log(log_lines, routed, failed)
        self.status.showMessage(f"Autorouter: {routed} geroutet, {failed} fehlgeschlagen", 5000)

    def _open_3d_preview(self):
        dlg = Preview3DDialog(self.scene, self)
        dlg.exec()

    # -- Projekt I/O ---------------------------------------------------------
    def _new_project(self):
        if QMessageBox.question(self, "Neues Projekt",
                                 "Aktuelles Projekt verwerfen und neu beginnen?") == QMessageBox.StandardButton.Yes:
            self.scene.clear()
            self.netlist.nets.clear()
            self.current_path = None
            self._ref_counters = {}

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Projekt öffnen", "", "Pandora PCB (*.pandora *.json)")
        if path:
            try:
                ProjectIO.load(path, self.scene)
                self.current_path = path
                self._recompute_ref_counters()
                self.scene.update_ratsnest()
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Projekt konnte nicht geladen werden:\n{e}")

    def _save_project(self):
        path = self.current_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(self, "Projekt speichern", "projekt.pandora",
                                                   "Pandora PCB (*.pandora)")
        if path:
            try:
                ProjectIO.save(path, self.scene)
                self.current_path = path
                self.status.showMessage(f"Gespeichert: {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Speichern fehlgeschlagen:\n{e}")

    def _export_gerber(self):
        directory = QFileDialog.getExistingDirectory(self, "Export-Verzeichnis wählen")
        if not directory:
            return
        try:
            paths = GerberX2Exporter.export_all(self.scene, directory)
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Gerber/Excellon-Export fehlgeschlagen:\n{e}")
            return
        dateiliste = "\n".join(f"• {Path(p).name}" for p in paths)
        QMessageBox.information(
            self, "Export abgeschlossen",
            f"Gerber X2 + Excellon wurden nach\n{directory}\nexportiert:\n\n{dateiliste}")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(PandoraTheme.STYLESHEET)
    icon_path = Path(__file__).resolve().parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
