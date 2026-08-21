#!/usr/bin/env python3
"""
================================================================================
 PANDORA CONFIG EDITOR
 Visueller JSON/YAML Konfigurations-Editor & Validator
 Optimiert für Raspberry Pi 4B (8GB) / Kali Linux
================================================================================

Features:
  - Dynamisch generierte Formulare aus beliebig verschachtelten JSON/YAML-Dateien
  - Zusätzlich: dedizierter visueller Editor für YARA-Regeln (.yar/.yara) —
    Meta-Felder, Strings (Text/Hex/Regex + Modifier) und Condition als eigene
    Formularabschnitte je Regel
  - Live-Code-Vorschau im Split-Screen (mit einfachem Syntax-Highlighting,
    für JSON/YAML sowie für YARA-Syntax)
  - Automatische Schema-Validierung (JSON-Schema, sofern vorhanden) +
    Basis-Typ-Validierung als Fallback; für YARA: Struktur-Checks + optional
    echte Compiler-Validierung, falls yara-python installiert ist
  - Sofortige Fehlermarkierung ungültiger Felder (rote Umrandung)
  - Automatisches Backup vor jedem Speichern (Zeitstempel-Kopie)
  - Dunkles "Pandora"-Neon-Theme (Cyan/Magenta auf Tiefschwarz)

Abhängigkeiten:
  pip install PyQt6 PyYAML jsonschema --break-system-packages
  # optional, für echte YARA-Compiler-Validierung:
  pip install yara-python --break-system-packages

Start:
  python3 pandora_config_editor.py [pfad/zur/config.json|yaml|yar] [--schema schema.json]
================================================================================
"""

import sys
import os
import re
import json
import copy
import shutil
import datetime
import argparse

try:
    import yaml
except ImportError:
    yaml = None

try:
    from jsonschema import Draft7Validator
except ImportError:
    Draft7Validator = None

try:
    import yara
except ImportError:
    yara = None  # optional: yara-python. Falls vorhanden, wird echte Compiler-Validierung genutzt.

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QGroupBox, QLabel, QLineEdit, QCheckBox, QSpinBox, QDoubleSpinBox,
    QComboBox, QPushButton, QScrollArea, QSplitter, QPlainTextEdit,
    QFileDialog, QMessageBox, QToolBar, QStatusBar, QListWidget,
    QListWidgetItem, QSizePolicy, QFrame, QToolButton, QStyle
)
from PyQt6.QtGui import (
    QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QAction, QIcon
)
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression


# ------------------------------------------------------------------------
# PANDORA THEME (Neon-Dark)
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
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0d1520;
    border: 1px solid #1f3a4a;
    border-radius: 4px;
    padding: 4px 6px;
    color: #d7fffb;
    selection-background-color: #00e5ff;
    selection-color: #001014;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #00e5ff;
}
QLineEdit[invalid="true"], QSpinBox[invalid="true"], QComboBox[invalid="true"] {
    border: 1px solid #ff2f6d;
    background-color: #2a0d16;
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
QToolButton {
    background-color: #131a2b;
    border: 1px solid #ff2fd0;
    border-radius: 4px;
    color: #ff2fd0;
    font-weight: bold;
    padding: 2px 8px;
}
QToolButton:hover {
    background-color: #ff2fd0;
    color: #04121a;
}
QScrollArea {
    border: none;
}
QPlainTextEdit {
    background-color: #05080d;
    color: #7de8ff;
    border: 1px solid #1f3a4a;
    border-radius: 4px;
}
QSplitter::handle {
    background-color: #00e5ff;
    width: 3px;
}
QListWidget {
    background-color: #0d1520;
    border: 1px solid #1f3a4a;
}
QLabel#SectionHint {
    color: #6c7d8c;
    font-style: italic;
}
"""


# ------------------------------------------------------------------------
# EINFACHER JSON/YAML SYNTAX-HIGHLIGHTER (für die Live-Vorschau)
# ------------------------------------------------------------------------
class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        key_fmt = QTextCharFormat()
        key_fmt.setForeground(QColor("#ff2fd0"))
        key_fmt.setFontWeight(QFont.Weight.Bold)
        self.rules.append((QRegularExpression(r'"[^"]*"\s*:'), key_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#39ff88"))
        self.rules.append((QRegularExpression(r':\s*"[^"]*"'), string_fmt))

        number_fmt = QTextCharFormat()
        number_fmt.setForeground(QColor("#00e5ff"))
        self.rules.append((QRegularExpression(r'\b-?\d+\.?\d*\b'), number_fmt))

        bool_fmt = QTextCharFormat()
        bool_fmt.setForeground(QColor("#ffd500"))
        self.rules.append((QRegularExpression(r'\b(true|false|null)\b'), bool_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class YaraHighlighter(QSyntaxHighlighter):
    """Einfacher Syntax-Highlighter für YARA-Regeltext in der Live-Vorschau."""

    KEYWORDS = [
        "rule", "private", "global", "meta", "strings", "condition",
        "import", "and", "or", "not", "any", "all", "of", "them", "for",
        "in", "at", "filesize", "entrypoint", "true", "false", "matches",
        "contains", "icontains", "startswith", "endswith", "nocase",
        "wide", "ascii", "fullword", "xor", "base64", "base64wide",
    ]

    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        kw_fmt = QTextCharFormat()
        kw_fmt.setForeground(QColor("#ff2fd0"))
        kw_fmt.setFontWeight(QFont.Weight.Bold)
        for kw in self.KEYWORDS:
            self.rules.append((QRegularExpression(rf'\b{kw}\b'), kw_fmt))

        string_fmt = QTextCharFormat()
        string_fmt.setForeground(QColor("#39ff88"))
        self.rules.append((QRegularExpression(r'"(?:[^"\\]|\\.)*"'), string_fmt))

        id_fmt = QTextCharFormat()
        id_fmt.setForeground(QColor("#00e5ff"))
        self.rules.append((QRegularExpression(r'\$\w+'), id_fmt))

        comment_fmt = QTextCharFormat()
        comment_fmt.setForeground(QColor("#4d6272"))
        comment_fmt.setFontItalic(True)
        self.rules.append((QRegularExpression(r'//[^\n]*'), comment_fmt))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# ------------------------------------------------------------------------
# HILFSFUNKTIONEN: Typ-Erkennung / Konvertierung
# ------------------------------------------------------------------------
def guess_scalar(text):
    """Wandelt einen Freitext-String in den plausibelsten Python-Typ um."""
    t = text.strip()
    if t.lower() == "true":
        return True
    if t.lower() == "false":
        return False
    if t.lower() in ("null", "none", ""):
        return None
    try:
        if "." not in t and "e" not in t.lower():
            return int(t)
        return float(t)
    except ValueError:
        return text


def schema_for_path(schema, path):
    """Versucht, das Sub-Schema für einen gegebenen Pfad (Liste aus Keys/Indizes)
    aus einem JSON-Schema zu ermitteln. Best-effort, kein vollständiger Resolver."""
    if not schema:
        return None
    node = schema
    for part in path:
        if not isinstance(node, dict):
            return None
        if isinstance(part, int):
            node = node.get("items")
        else:
            props = node.get("properties", {})
            node = props.get(part)
        if node is None:
            return None
    return node


# ------------------------------------------------------------------------
# EINZELNES SKALAR-FELD (String/Zahl/Bool/Enum) -> passendes Widget
# ------------------------------------------------------------------------
class ScalarField(QWidget):
    changed = pyqtSignal()

    def __init__(self, value, sub_schema=None, parent=None):
        super().__init__(parent)
        self.value_type = type(value)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        enum_values = None
        if sub_schema and isinstance(sub_schema, dict):
            enum_values = sub_schema.get("enum")

        if enum_values:
            self.widget = QComboBox()
            self.widget.addItems([str(v) for v in enum_values])
            idx = self.widget.findText(str(value))
            if idx >= 0:
                self.widget.setCurrentIndex(idx)
            self.widget.currentIndexChanged.connect(lambda _=None: self.changed.emit())
            self._enum_values = enum_values

        elif isinstance(value, bool):
            self.widget = QCheckBox()
            self.widget.setChecked(value)
            self.widget.stateChanged.connect(lambda _=None: self.changed.emit())

        elif isinstance(value, int):
            self.widget = QSpinBox()
            self.widget.setRange(-2_147_483_648, 2_147_483_647)
            self.widget.setValue(value)
            self.widget.valueChanged.connect(lambda _=None: self.changed.emit())

        elif isinstance(value, float):
            self.widget = QDoubleSpinBox()
            self.widget.setDecimals(6)
            self.widget.setRange(-1e12, 1e12)
            self.widget.setValue(value)
            self.widget.valueChanged.connect(lambda _=None: self.changed.emit())

        else:
            self.widget = QLineEdit("" if value is None else str(value))
            self.widget.setPlaceholderText("null" if value is None else "")
            self.widget.textChanged.connect(lambda _=None: self.changed.emit())

        layout.addWidget(self.widget)

    def get_value(self):
        if isinstance(self.widget, QComboBox):
            text = self.widget.currentText()
            for v in getattr(self, "_enum_values", []):
                if str(v) == text:
                    return v
            return text
        if isinstance(self.widget, QCheckBox):
            return self.widget.isChecked()
        if isinstance(self.widget, (QSpinBox, QDoubleSpinBox)):
            return self.widget.value()
        return guess_scalar(self.widget.text()) if self.value_type not in (str,) else self.widget.text()

    def set_invalid(self, invalid):
        self.widget.setProperty("invalid", "true" if invalid else "false")
        self.widget.style().unpolish(self.widget)
        self.widget.style().polish(self.widget)


# ------------------------------------------------------------------------
# LISTEN-EDITOR (Arrays) mit Hinzufügen/Entfernen von Einträgen
# ------------------------------------------------------------------------
class ListEditor(QWidget):
    changed = pyqtSignal()

    def __init__(self, values, path, schema=None, parent=None):
        super().__init__(parent)
        self.path = path
        self.schema = schema
        self.entry_builders = []
        self._template = copy.deepcopy(values[0]) if values else ""

        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)

        self.items_layout = QVBoxLayout()
        self.outer.addLayout(self.items_layout)

        btn_row = QHBoxLayout()
        add_btn = QToolButton()
        add_btn.setText("＋ Eintrag hinzufügen")
        add_btn.clicked.connect(self.add_entry)
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        self.outer.addLayout(btn_row)

        for v in values:
            self._add_row(v, emit=False)

    def _add_row(self, value, emit=True):
        row = QFrame()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        item_schema = schema_for_path(self.schema, self.path + [0])
        if isinstance(value, dict):
            builder = DynamicFormBuilder(value, self.path + [len(self.entry_builders)],
                                          item_schema, is_root=False)
            builder.changed.connect(self.changed.emit)
            row_layout.addWidget(builder)
            getter = builder.get_data
        else:
            field = ScalarField(value, item_schema)
            field.changed.connect(self.changed.emit)
            row_layout.addWidget(field)
            getter = field.get_value

        remove_btn = QToolButton()
        remove_btn.setText("✕")
        remove_btn.clicked.connect(lambda: self._remove_row(row, getter))
        row_layout.addWidget(remove_btn)

        self.items_layout.addWidget(row)
        self.entry_builders.append((row, getter))
        if emit:
            self.changed.emit()

    def add_entry(self):
        self._add_row(copy.deepcopy(self._template))

    def _remove_row(self, row, getter):
        self.entry_builders = [(r, g) for (r, g) in self.entry_builders if r is not row]
        row.setParent(None)
        row.deleteLater()
        self.changed.emit()

    def get_value(self):
        return [g() for (_, g) in self.entry_builders]


# ------------------------------------------------------------------------
# DYNAMISCHER FORM-BUILDER (rekursiv für verschachtelte dicts)
# ------------------------------------------------------------------------
class DynamicFormBuilder(QWidget):
    changed = pyqtSignal()

    def __init__(self, data, path=None, schema=None, is_root=True, parent=None):
        super().__init__(parent)
        self.path = path or []
        self.schema = schema
        self.fields = {}   # key -> (kind, widget_or_builder)
        self.key_order = list(data.keys())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        form_container = QGroupBox("Konfiguration" if is_root else "")
        form_container.setFlat(not is_root)
        form_layout = QFormLayout()
        form_container_layout = QVBoxLayout(form_container)
        form_container_layout.addLayout(form_layout)

        for key, value in data.items():
            sub_path = self.path + [key]
            sub_schema = schema_for_path(schema, sub_path)

            if isinstance(value, dict):
                box = QGroupBox(key)
                box_layout = QVBoxLayout(box)
                child = DynamicFormBuilder(value, sub_path, schema, is_root=False)
                child.changed.connect(self.changed.emit)
                box_layout.addWidget(child)
                form_layout.addRow(box)
                self.fields[key] = ("dict", child)

            elif isinstance(value, list):
                box = QGroupBox(f"{key}  [Liste]")
                box_layout = QVBoxLayout(box)
                editor = ListEditor(value, sub_path, schema)
                editor.changed.connect(self.changed.emit)
                box_layout.addWidget(editor)
                form_layout.addRow(box)
                self.fields[key] = ("list", editor)

            else:
                field = ScalarField(value, sub_schema)
                field.changed.connect(self.changed.emit)
                label = QLabel(key)
                form_layout.addRow(label, field)
                self.fields[key] = ("scalar", field)

        layout.addWidget(form_container)

    def get_data(self):
        result = {}
        for key in self.key_order:
            kind, obj = self.fields[key]
            if kind == "dict":
                result[key] = obj.get_data()
            elif kind == "list":
                result[key] = obj.get_value()
            else:
                result[key] = obj.get_value()
        return result

    def clear_invalid_markers(self):
        for kind, obj in self.fields.values():
            if kind == "scalar":
                obj.set_invalid(False)
            elif kind == "dict":
                obj.clear_invalid_markers()

    def mark_invalid_path(self, path):
        """path: Liste von Keys/Indizes relativ zu diesem Builder."""
        if not path:
            return
        key = path[0]
        if key not in self.fields:
            return
        kind, obj = self.fields[key]
        if len(path) == 1:
            if kind == "scalar":
                obj.set_invalid(True)
        elif kind == "dict":
            obj.mark_invalid_path(path[1:])


# ------------------------------------------------------------------------
# YARA: PARSER
# ------------------------------------------------------------------------
def strip_yara_comments(text):
    """Entfernt // und /* */ Kommentare, respektiert dabei Anführungszeichen."""
    out = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_yara(text):
    """Parst YARA-Regeltext in eine einfache dict-Struktur:
    {"imports": [...], "rules": [{"name","private","global","tags","meta","strings","condition"}]}
    Best-effort-Parser für den visuellen Editor, kein vollständiger YARA-Grammatik-Parser."""
    clean = strip_yara_comments(text)
    imports = re.findall(r'import\s+"([^"]+)"', clean)

    rules = []
    rule_pattern = re.compile(r'(private\s+)?(global\s+)?rule\s+(\w+)\s*(:\s*([\w\s]+?))?\s*\{')
    for m in rule_pattern.finditer(clean):
        private = bool(m.group(1))
        is_global = bool(m.group(2))
        name = m.group(3)
        tags = (m.group(5) or "").split()

        open_pos = m.end() - 1  # Position der öffnenden '{'
        depth, pos, close_pos = 0, open_pos, None
        while pos < len(clean):
            ch = clean[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    close_pos = pos
                    break
            pos += 1
        if close_pos is None:
            continue  # unvollständige Regel, überspringen

        body = clean[open_pos + 1:close_pos]

        section_re = re.compile(r'\b(meta|strings|condition)\s*:')
        matches = list(section_re.finditer(body))
        sections = {"meta": "", "strings": "", "condition": ""}
        for idx, sm in enumerate(matches):
            label = sm.group(1)
            start = sm.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
            sections[label] = body[start:end]

        meta_list = []
        for line in sections["meta"].splitlines():
            lm = re.match(r'\s*(\w+)\s*=\s*(.+?)\s*$', line)
            if lm:
                key, raw_val = lm.group(1), lm.group(2)
                if raw_val.startswith('"') and raw_val.endswith('"'):
                    val = raw_val[1:-1]
                else:
                    val = guess_scalar(raw_val)
                meta_list.append((key, val))

        strings_list = []
        str_re = re.compile(
            r'\$(\w+)\s*=\s*('
            r'"(?:[^"\\]|\\.)*"'
            r'|\{[^}]*\}'
            r'|/(?:[^/\\]|\\.)*\/'
            r')\s*([\w\s()\-,]*)'
        )
        for sm in str_re.finditer(sections["strings"]):
            sid, raw_val, raw_mods = sm.group(1), sm.group(2), sm.group(3)
            if raw_val.startswith('"'):
                stype, val = "text", raw_val[1:-1]
            elif raw_val.startswith("{"):
                stype, val = "hex", raw_val[1:-1].strip()
            else:
                stype, val = "regex", raw_val[1:-1]
            strings_list.append({
                "id": sid, "type": stype, "value": val,
                "modifiers": raw_mods.split()
            })

        rules.append({
            "name": name, "private": private, "global": is_global,
            "tags": tags, "meta": meta_list, "strings": strings_list,
            "condition": sections["condition"].strip(),
        })

    return {"imports": imports, "rules": rules}


def serialize_yara(yara_data):
    """Baut aus der dict-Struktur wieder gültigen YARA-Regeltext auf."""
    lines = []
    imports = yara_data.get("imports", [])
    for imp in imports:
        lines.append(f'import "{imp}"')
    if imports:
        lines.append("")

    for rule in yara_data.get("rules", []):
        prefix = ""
        if rule.get("private"):
            prefix += "private "
        if rule.get("global"):
            prefix += "global "
        tag_suffix = " : " + " ".join(rule["tags"]) if rule.get("tags") else ""
        lines.append(f'{prefix}rule {rule.get("name") or "UnnamedRule"}{tag_suffix}')
        lines.append("{")

        meta = rule.get("meta", [])
        if meta:
            lines.append("    meta:")
            for k, v in meta:
                if isinstance(v, bool):
                    vs = "true" if v else "false"
                elif isinstance(v, (int, float)):
                    vs = str(v)
                else:
                    vs = f'"{v}"'
                lines.append(f"        {k} = {vs}")
            lines.append("")

        strings = rule.get("strings", [])
        if strings:
            lines.append("    strings:")
            for s in strings:
                if s["type"] == "hex":
                    val = "{ " + s["value"] + " }"
                elif s["type"] == "regex":
                    val = "/" + s["value"] + "/"
                else:
                    val = f'"{s["value"]}"'
                mods = " ".join(s.get("modifiers", []))
                lines.append(f'        ${s["id"]} = {val}{(" " + mods) if mods else ""}')
            lines.append("")

        lines.append("    condition:")
        cond = (rule.get("condition") or "").strip() or "true"
        for cl in cond.splitlines():
            lines.append(f"        {cl}")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def validate_yara_data(yara_data):
    """Liefert (errors: list[str], field_errors: list[(rule_name, invalid_ids_set, condition_invalid)])."""
    errors = []
    field_errors = []

    names = [r.get("name", "") for r in yara_data.get("rules", [])]
    for n in names:
        if not n or not n.isidentifier():
            errors.append(f"Ungültiger Regelname: '{n}'")
    for d in {n for n in names if n and names.count(n) > 1}:
        errors.append(f"Doppelter Regelname: '{d}'")

    for rule in yara_data.get("rules", []):
        rname = rule.get("name") or "?"
        ids = [s["id"] for s in rule.get("strings", [])]
        invalid_ids = set()

        for sid in ids:
            if not sid or not sid.isidentifier():
                errors.append(f"[{rname}] Ungültiger String-Bezeichner: '${sid}'")
                invalid_ids.add(sid)
        for di in {i for i in ids if ids.count(i) > 1}:
            errors.append(f"[{rname}] Doppelter String-Bezeichner: '${di}'")
            invalid_ids.add(di)

        condition = (rule.get("condition") or "").strip()
        condition_invalid = False
        if not condition:
            errors.append(f"[{rname}] Condition darf nicht leer sein")
            condition_invalid = True
        else:
            referenced = set(re.findall(r'\$(\w+)\b', condition))
            defined = set(ids)
            for ref in referenced:
                if ref and ref not in defined:
                    errors.append(f"[{rname}] Condition referenziert unbekannten String: '${ref}'")
                    condition_invalid = True

        field_errors.append((rname, invalid_ids, condition_invalid))

    if yara is not None:
        try:
            yara.compile(source=serialize_yara(yara_data))
        except Exception as e:
            errors.append(f"YARA-Compiler: {e}")

    return errors, field_errors


# ------------------------------------------------------------------------
# YARA: FORMULAR-WIDGETS
# ------------------------------------------------------------------------
class YaraMetaSection(QWidget):
    """Editierbare Liste von meta-Schlüssel/Wert-Paaren einer YARA-Regel."""
    changed = pyqtSignal()

    def __init__(self, meta_list, parent=None):
        super().__init__(parent)
        self.rows = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.rows_layout = QVBoxLayout()
        outer.addLayout(self.rows_layout)

        add_btn = QToolButton()
        add_btn.setText("＋ Meta-Feld")
        add_btn.clicked.connect(lambda: self.add_row("", ""))
        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        for k, v in meta_list:
            self.add_row(k, v, emit=False)

    def add_row(self, key="", value="", emit=True):
        frame = QFrame()
        h = QHBoxLayout(frame)
        h.setContentsMargins(0, 0, 0, 0)
        key_edit = QLineEdit(str(key))
        key_edit.setPlaceholderText("schlüssel")
        val_edit = QLineEdit("" if value is None else str(value))
        val_edit.setPlaceholderText("wert")
        remove_btn = QToolButton()
        remove_btn.setText("✕")
        remove_btn.clicked.connect(lambda: self._remove(frame))
        h.addWidget(key_edit)
        h.addWidget(val_edit)
        h.addWidget(remove_btn)

        key_edit.textChanged.connect(lambda _=None: self.changed.emit())
        val_edit.textChanged.connect(lambda _=None: self.changed.emit())

        self.rows_layout.addWidget(frame)
        self.rows.append((frame, key_edit, val_edit))
        if emit:
            self.changed.emit()

    def _remove(self, frame):
        self.rows = [(f, k, v) for (f, k, v) in self.rows if f is not frame]
        frame.setParent(None)
        frame.deleteLater()
        self.changed.emit()

    def get_value(self):
        result = []
        for (_f, k, v) in self.rows:
            key = k.text().strip()
            if key:
                result.append((key, guess_scalar(v.text())))
        return result


class YaraStringsSection(QWidget):
    """Editierbare Liste von $string-Definitionen (Text/Hex/Regex + Modifier)."""
    changed = pyqtSignal()
    MODIFIERS = ["nocase", "wide", "ascii", "fullword", "private"]

    def __init__(self, strings_list, parent=None):
        super().__init__(parent)
        self.rows = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.rows_layout = QVBoxLayout()
        outer.addLayout(self.rows_layout)

        add_btn = QToolButton()
        add_btn.setText("＋ String hinzufügen")
        add_btn.clicked.connect(lambda: self.add_row(
            {"id": "s1", "type": "text", "value": "", "modifiers": []}))
        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        for s in strings_list:
            self.add_row(s, emit=False)

    def add_row(self, s, emit=True):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        v = QVBoxLayout(frame)

        top = QHBoxLayout()
        id_edit = QLineEdit(s.get("id", ""))
        id_edit.setPlaceholderText("bezeichner")
        id_edit.setMaximumWidth(120)
        type_combo = QComboBox()
        type_combo.addItems(["text", "hex", "regex"])
        idx = type_combo.findText(s.get("type", "text"))
        if idx >= 0:
            type_combo.setCurrentIndex(idx)
        value_edit = QLineEdit(s.get("value", ""))
        value_edit.setPlaceholderText('"text" / 6A 40 68 00 / regex-muster')
        remove_btn = QToolButton()
        remove_btn.setText("✕")
        remove_btn.clicked.connect(lambda: self._remove(frame))

        top.addWidget(QLabel("$"))
        top.addWidget(id_edit)
        top.addWidget(type_combo)
        top.addWidget(value_edit, 1)
        top.addWidget(remove_btn)
        v.addLayout(top)

        mod_row = QHBoxLayout()
        mod_checks = {}
        for m in self.MODIFIERS:
            cb = QCheckBox(m)
            cb.setChecked(m in s.get("modifiers", []))
            cb.stateChanged.connect(lambda _=None: self.changed.emit())
            mod_checks[m] = cb
            mod_row.addWidget(cb)
        extra_mods = [m for m in s.get("modifiers", []) if m not in self.MODIFIERS]
        extra_edit = QLineEdit(" ".join(extra_mods))
        extra_edit.setPlaceholderText("weitere Modifier (xor, base64, …)")
        mod_row.addWidget(extra_edit)
        v.addLayout(mod_row)

        id_edit.textChanged.connect(lambda _=None: self.changed.emit())
        type_combo.currentIndexChanged.connect(lambda _=None: self.changed.emit())
        value_edit.textChanged.connect(lambda _=None: self.changed.emit())
        extra_edit.textChanged.connect(lambda _=None: self.changed.emit())

        self.rows_layout.addWidget(frame)
        self.rows.append({
            "frame": frame, "id": id_edit, "type": type_combo,
            "value": value_edit, "mods": mod_checks, "extra": extra_edit
        })
        if emit:
            self.changed.emit()

    def _remove(self, frame):
        self.rows = [r for r in self.rows if r["frame"] is not frame]
        frame.setParent(None)
        frame.deleteLater()
        self.changed.emit()

    def get_value(self):
        result = []
        for r in self.rows:
            sid = r["id"].text().strip().lstrip("$")
            if not sid:
                continue
            mods = [m for m, cb in r["mods"].items() if cb.isChecked()]
            mods += [m for m in r["extra"].text().split() if m]
            result.append({
                "id": sid, "type": r["type"].currentText(),
                "value": r["value"].text(), "modifiers": mods,
            })
        return result

    def set_invalid_ids(self, invalid_ids):
        for r in self.rows:
            bad = r["id"].text().strip().lstrip("$") in invalid_ids
            r["id"].setProperty("invalid", "true" if bad else "false")
            r["id"].style().unpolish(r["id"])
            r["id"].style().polish(r["id"])


class YaraRuleEditor(QWidget):
    """Formular für eine einzelne YARA-Regel: Kopf, Meta, Strings, Condition."""
    changed = pyqtSignal()

    def __init__(self, rule, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)

        header = QHBoxLayout()
        self.name_edit = QLineEdit(rule.get("name", ""))
        self.name_edit.setPlaceholderText("Regelname")
        self.private_cb = QCheckBox("private")
        self.private_cb.setChecked(bool(rule.get("private", False)))
        self.global_cb = QCheckBox("global")
        self.global_cb.setChecked(bool(rule.get("global", False)))
        self.tags_edit = QLineEdit(" ".join(rule.get("tags", [])))
        self.tags_edit.setPlaceholderText("tags (leerzeichengetrennt)")

        header.addWidget(QLabel("Name:"))
        header.addWidget(self.name_edit, 1)
        header.addWidget(self.private_cb)
        header.addWidget(self.global_cb)
        header.addWidget(QLabel("Tags:"))
        header.addWidget(self.tags_edit, 1)
        outer.addLayout(header)

        for w in (self.name_edit, self.tags_edit):
            w.textChanged.connect(lambda _=None: self.changed.emit())
        for cb in (self.private_cb, self.global_cb):
            cb.stateChanged.connect(lambda _=None: self.changed.emit())

        meta_box = QGroupBox("Meta")
        meta_layout = QVBoxLayout(meta_box)
        self.meta_section = YaraMetaSection(rule.get("meta", []))
        self.meta_section.changed.connect(self.changed.emit)
        meta_layout.addWidget(self.meta_section)
        outer.addWidget(meta_box)

        strings_box = QGroupBox("Strings")
        strings_layout = QVBoxLayout(strings_box)
        self.strings_section = YaraStringsSection(rule.get("strings", []))
        self.strings_section.changed.connect(self.changed.emit)
        strings_layout.addWidget(self.strings_section)
        outer.addWidget(strings_box)

        cond_box = QGroupBox("Condition")
        cond_layout = QVBoxLayout(cond_box)
        self.condition_edit = QPlainTextEdit(rule.get("condition", ""))
        self.condition_edit.setFont(QFont("Fira Code", 10))
        self.condition_edit.setMaximumHeight(120)
        self.condition_edit.textChanged.connect(lambda: self.changed.emit())
        cond_layout.addWidget(self.condition_edit)
        outer.addWidget(cond_box)

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "private": self.private_cb.isChecked(),
            "global": self.global_cb.isChecked(),
            "tags": [t for t in self.tags_edit.text().split() if t],
            "meta": self.meta_section.get_value(),
            "strings": self.strings_section.get_value(),
            "condition": self.condition_edit.toPlainText(),
        }

    def mark_condition_invalid(self, invalid):
        self.condition_edit.setProperty("invalid", "true" if invalid else "false")
        self.condition_edit.style().unpolish(self.condition_edit)
        self.condition_edit.style().polish(self.condition_edit)


class YaraFileEditor(QWidget):
    """Editor für eine komplette .yar-Datei: Imports + Liste von Regeln."""
    changed = pyqtSignal()

    def __init__(self, yara_data, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)

        imports_box = QGroupBox("Imports")
        imports_layout = QVBoxLayout(imports_box)
        self.imports_edit = QLineEdit(" ".join(yara_data.get("imports", [])))
        self.imports_edit.setPlaceholderText(
            'z.B. pe math hash  (leerzeichengetrennt, ohne "import"/Anführungszeichen)')
        self.imports_edit.textChanged.connect(lambda _=None: self.changed.emit())
        imports_layout.addWidget(self.imports_edit)
        outer.addWidget(imports_box)

        self.rules_layout = QVBoxLayout()
        outer.addLayout(self.rules_layout)

        add_rule_btn = QPushButton("＋ Neue Regel")
        add_rule_btn.clicked.connect(lambda: self.add_rule({
            "name": "NeueRegel", "private": False, "global": False,
            "tags": [], "meta": [], "strings": [], "condition": ""
        }))
        outer.addWidget(add_rule_btn)
        outer.addStretch()

        self.rule_editors = []
        for rule in yara_data.get("rules", []):
            self.add_rule(rule, emit=False)

    def add_rule(self, rule, emit=True):
        box = QGroupBox(f"Rule: {rule.get('name') or '?'}")
        box_layout = QVBoxLayout(box)
        editor = YaraRuleEditor(rule)
        editor.changed.connect(self.changed.emit)
        editor.name_edit.textChanged.connect(
            lambda t, b=box: b.setTitle(f"Rule: {t or '?'}"))

        remove_btn = QToolButton()
        remove_btn.setText("Regel entfernen ✕")
        remove_btn.clicked.connect(lambda: self._remove_rule(box))

        box_layout.addWidget(editor)
        box_layout.addWidget(remove_btn)
        self.rules_layout.addWidget(box)
        self.rule_editors.append((box, editor))
        if emit:
            self.changed.emit()

    def _remove_rule(self, box):
        self.rule_editors = [(b, e) for (b, e) in self.rule_editors if b is not box]
        box.setParent(None)
        box.deleteLater()
        self.changed.emit()

    def get_data(self):
        imports = [i for i in self.imports_edit.text().split() if i]
        rules = [e.get_data() for (_b, e) in self.rule_editors]
        return {"imports": imports, "rules": rules}

    def clear_invalid_markers(self):
        for (_b, e) in self.rule_editors:
            e.mark_condition_invalid(False)
            e.strings_section.set_invalid_ids(set())

    def apply_field_errors(self, field_errors):
        by_name = {name: (ids, cond) for (name, ids, cond) in field_errors}
        for (_b, e) in self.rule_editors:
            entry = by_name.get(e.name_edit.text().strip())
            if entry:
                ids, cond_invalid = entry
                e.strings_section.set_invalid_ids(ids)
                e.mark_condition_invalid(cond_invalid)


# ------------------------------------------------------------------------
# BACKUP-MANAGER
# ------------------------------------------------------------------------
def create_backup(filepath):
    if not os.path.isfile(filepath):
        return None
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(filepath)), ".pandora_backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.basename(filepath)
    backup_path = os.path.join(backup_dir, f"{base}.{stamp}.bak")
    shutil.copy2(filepath, backup_path)
    return backup_path


# ------------------------------------------------------------------------
# VALIDIERUNG
# ------------------------------------------------------------------------
def validate_data(data, schema):
    """
    Liefert eine Liste von (path_list, message) Fehlern.
    Nutzt jsonschema falls verfügbar & Schema geladen ist, sonst
    einen einfachen Typ-Konsistenz-Check gegen sich selbst (immer gültig,
    da Werte direkt aus typisierten Widgets stammen) -> in dem Fall leer.
    """
    errors = []
    if schema and Draft7Validator is not None:
        validator = Draft7Validator(schema)
        for err in validator.iter_errors(data):
            path = list(err.absolute_path)
            errors.append((path, err.message))
    return errors


# ------------------------------------------------------------------------
# HAUPTFENSTER
# ------------------------------------------------------------------------
class PandoraConfigEditor(QMainWindow):
    def __init__(self, initial_file=None, schema_file=None):
        super().__init__()
        self.setWindowTitle("⧉ PANDORA CONFIG EDITOR")
        self.resize(1200, 800)

        self.current_file = None
        self.file_format = "json"   # oder "yaml"
        self.mode = "data"          # "data" (JSON/YAML) oder "yara" (.yar/.yara)
        self.data = {}
        self.schema = None
        self.form_builder = None
        self.yara_data = None
        self.yara_editor = None

        self._build_ui()
        self._build_toolbar()

        if schema_file:
            self._load_schema(schema_file)
        if initial_file:
            self._load_file(initial_file)

    # -------------------- UI Aufbau --------------------
    def _build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.form_host = QWidget()
        self.form_host_layout = QVBoxLayout(self.form_host)
        placeholder = QLabel("Keine Datei geladen.\nÖffne eine JSON/YAML- oder YARA-Datei (.yar/.yara) über die Toolbar.")
        placeholder.setObjectName("SectionHint")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.form_host_layout.addWidget(placeholder)
        self.scroll_area.setWidget(self.form_host)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Fira Code", 10))
        self.highlighter = CodeHighlighter(self.preview.document())

        splitter.addWidget(self.scroll_area)
        splitter.addWidget(self.preview)
        splitter.setSizes([650, 550])

        self.setCentralWidget(splitter)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Bereit.")

    def _build_toolbar(self):
        toolbar = QToolBar("Aktionen")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_act = QAction("📂 Öffnen", self)
        open_act.triggered.connect(self.open_dialog)
        toolbar.addAction(open_act)

        schema_act = QAction("🧩 Schema laden", self)
        schema_act.triggered.connect(self.open_schema_dialog)
        toolbar.addAction(schema_act)

        reload_act = QAction("↺ Neu laden", self)
        reload_act.triggered.connect(self.reload_file)
        toolbar.addAction(reload_act)

        toolbar.addSeparator()

        self.format_toggle = QComboBox()
        self.format_toggle.addItems(["JSON", "YAML"])
        self.format_toggle.currentTextChanged.connect(self.on_format_changed)
        toolbar.addWidget(self.format_toggle)

        toolbar.addSeparator()

        validate_act = QAction("✔ Validieren", self)
        validate_act.triggered.connect(self.validate_only)
        toolbar.addAction(validate_act)

        save_act = QAction("💾 Speichern", self)
        save_act.triggered.connect(self.save_file)
        toolbar.addAction(save_act)

    # -------------------- Datei-Operationen --------------------
    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Konfigurationsdatei öffnen", "",
            "Config- & YARA-Dateien (*.json *.yaml *.yml *.yar *.yara);;"
            "JSON/YAML (*.json *.yaml *.yml);;YARA-Regeln (*.yar *.yara);;"
            "Alle Dateien (*)"
        )
        if path:
            self._load_file(path)

    def open_schema_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "JSON-Schema öffnen", "", "JSON-Schema (*.json);;Alle Dateien (*)"
        )
        if path:
            self._load_schema(path)

    def _load_schema(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.schema = json.load(f)
            self.status.showMessage(f"Schema geladen: {os.path.basename(path)}", 5000)
            if self.data:
                self._rebuild_form()
        except Exception as e:
            QMessageBox.warning(self, "Schema-Fehler", f"Schema konnte nicht geladen werden:\n{e}")

    def _load_file(self, path):
        try:
            ext = os.path.splitext(path)[1].lower()
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            if ext in (".yar", ".yara"):
                self.yara_data = parse_yara(content)
                self.mode = "yara"
                self.current_file = path
                self._rebuild_yara_form()
                self.setWindowTitle(f"⧉ PANDORA CONFIG EDITOR — {os.path.basename(path)}  [YARA]")
                n_rules = len(self.yara_data.get("rules", []))
                self.status.showMessage(f"YARA-Regeldatei geladen: {path}  ({n_rules} Regel(n))", 5000)
                return

            if ext in (".yaml", ".yml"):
                if yaml is None:
                    QMessageBox.critical(self, "Fehlende Abhängigkeit",
                                          "PyYAML ist nicht installiert:\n"
                                          "pip install PyYAML --break-system-packages")
                    return
                self.data = yaml.safe_load(content) or {}
                self.file_format = "yaml"
                self.format_toggle.setCurrentText("YAML")
            else:
                self.data = json.loads(content) if content.strip() else {}
                self.file_format = "json"
                self.format_toggle.setCurrentText("JSON")

            if not isinstance(self.data, dict):
                QMessageBox.warning(self, "Nicht unterstützt",
                                     "Nur Objekte (dict) auf oberster Ebene werden aktuell unterstützt.")
                self.data = {"root": self.data}

            self.mode = "data"
            self.current_file = path
            self._rebuild_form()
            self.setWindowTitle(f"⧉ PANDORA CONFIG EDITOR — {os.path.basename(path)}")
            self.status.showMessage(f"Geladen: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Ladefehler", f"Datei konnte nicht geparst werden:\n{e}")

    def reload_file(self):
        if self.current_file:
            self._load_file(self.current_file)
        else:
            self.status.showMessage("Keine Datei zum Neuladen vorhanden.", 4000)

    def on_format_changed(self, text):
        self.file_format = text.lower()
        self._update_preview()

    # -------------------- Formular / Vorschau --------------------
    def _clear_form_host(self):
        while self.form_host_layout.count():
            item = self.form_host_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    def _set_preview_highlighter(self, mode):
        self.highlighter.setDocument(None)
        if mode == "yara":
            self.highlighter = YaraHighlighter(self.preview.document())
        else:
            self.highlighter = CodeHighlighter(self.preview.document())

    def _rebuild_form(self):
        self._clear_form_host()
        self.format_toggle.setEnabled(True)
        self._set_preview_highlighter("data")

        self.form_builder = DynamicFormBuilder(self.data, [], self.schema, is_root=True)
        self.form_builder.changed.connect(self._update_preview)
        self.form_host_layout.addWidget(self.form_builder)
        self._update_preview()

    def _rebuild_yara_form(self):
        self._clear_form_host()
        self.format_toggle.setEnabled(False)
        self._set_preview_highlighter("yara")

        self.yara_editor = YaraFileEditor(self.yara_data)
        self.yara_editor.changed.connect(self._update_preview)
        self.form_host_layout.addWidget(self.yara_editor)
        self._update_preview()

    def _current_data(self):
        if self.mode == "yara":
            if self.yara_editor is None:
                return {}
            return self.yara_editor.get_data()
        if self.form_builder is None:
            return {}
        return self.form_builder.get_data()

    def _update_preview(self):
        data = self._current_data()
        try:
            if self.mode == "yara":
                text = serialize_yara(data)
            elif self.file_format == "yaml" and yaml is not None:
                text = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
            else:
                text = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception as e:
            text = f"# Fehler bei der Serialisierung: {e}"
        self.preview.setPlainText(text)
        self._run_validation(silent=True)

    def _run_validation(self, silent=False):
        if self.mode == "yara":
            return self._run_yara_validation(silent)

        if self.form_builder is None:
            return True
        self.form_builder.clear_invalid_markers()
        data = self._current_data()
        errors = validate_data(data, self.schema)

        if errors:
            for path, _msg in errors:
                self.form_builder.mark_invalid_path(list(path))
            summary = "; ".join(f"{'/'.join(map(str, p)) or 'root'}: {m}" for p, m in errors[:5])
            self.status.showMessage(f"⚠ {len(errors)} Validierungsfehler — {summary}", 8000)
            if not silent:
                QMessageBox.warning(self, "Validierung fehlgeschlagen",
                                     f"{len(errors)} Fehler gefunden:\n\n" +
                                     "\n".join(f"- {'/'.join(map(str, p)) or 'root'}: {m}"
                                               for p, m in errors))
            return False
        else:
            if not silent:
                self.status.showMessage("✔ Validierung erfolgreich — keine Fehler.", 5000)
            else:
                self.status.showMessage("Bereit.", 2000)
            return True

    def _run_yara_validation(self, silent=False):
        if self.yara_editor is None:
            return True
        self.yara_editor.clear_invalid_markers()
        data = self._current_data()
        errors, field_errors = validate_yara_data(data)
        self.yara_editor.apply_field_errors(field_errors)

        if errors:
            summary = "; ".join(errors[:5])
            self.status.showMessage(f"⚠ {len(errors)} YARA-Fehler — {summary}", 8000)
            if not silent:
                QMessageBox.warning(self, "Validierung fehlgeschlagen",
                                     f"{len(errors)} Fehler gefunden:\n\n" +
                                     "\n".join(f"- {m}" for m in errors))
            return False
        else:
            if not silent:
                note = "" if yara is not None else "\n(Hinweis: yara-python nicht installiert — nur Struktur-Checks, kein Compiler-Test.)"
                self.status.showMessage("✔ YARA-Validierung erfolgreich — keine Fehler." + note, 6000)
            else:
                self.status.showMessage("Bereit.", 2000)
            return True

    def validate_only(self):
        self._run_validation(silent=False)

    # -------------------- Speichern --------------------
    def save_file(self):
        if not self.current_file:
            if self.mode == "yara":
                path, _ = QFileDialog.getSaveFileName(
                    self, "YARA-Regeln speichern als", "", "YARA (*.yar)"
                )
            else:
                path, _ = QFileDialog.getSaveFileName(
                    self, "Konfiguration speichern als", "",
                    "JSON (*.json);;YAML (*.yaml)"
                )
            if not path:
                return
            self.current_file = path
            if self.mode != "yara":
                self.file_format = "yaml" if path.lower().endswith((".yaml", ".yml")) else "json"

        valid = self._run_validation(silent=True)
        if not valid:
            reply = QMessageBox.question(
                self, "Validierungsfehler vorhanden",
                "Es gibt Validierungsfehler. Trotzdem speichern?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        backup_path = None
        try:
            backup_path = create_backup(self.current_file)
        except Exception as e:
            QMessageBox.warning(self, "Backup fehlgeschlagen",
                                 f"Es konnte kein Backup erstellt werden:\n{e}\n"
                                 "Speichern wird trotzdem fortgesetzt.")

        data = self._current_data()
        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                if self.mode == "yara":
                    f.write(serialize_yara(data))
                elif self.file_format == "yaml":
                    if yaml is None:
                        raise RuntimeError("PyYAML ist nicht installiert.")
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
                else:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            msg = f"Gespeichert: {self.current_file}"
            if backup_path:
                msg += f"  (Backup: {os.path.basename(backup_path)})"
            self.status.showMessage(msg, 8000)
        except Exception as e:
            QMessageBox.critical(self, "Speicherfehler", f"Konnte Datei nicht schreiben:\n{e}")


# ------------------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Pandora Config Editor")
    parser.add_argument("file", nargs="?", help="JSON/YAML-Konfigurationsdatei oder YARA-Regeldatei (.yar/.yara)")
    parser.add_argument("--schema", help="Optionales JSON-Schema zur Validierung")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyleSheet(PANDORA_QSS)

    win = PandoraConfigEditor(initial_file=args.file, schema_file=args.schema)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
