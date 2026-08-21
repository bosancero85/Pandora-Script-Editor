# -*- coding: utf-8 -*-
"""
theme.py
Pandora® md Editor - Darkred Theme (QSS)
by AKI_SystemDown®
"""

PANDORA_DARKRED_QSS = """
* {
    outline: none;
}

QMainWindow, QWidget {
    background-color: #120707;
    color: #f0d9d9;
    font-family: "Consolas", "Cascadia Code", "Segoe UI", monospace;
    font-size: 10.5pt;
}

/* ---------- Menu Bar ---------- */
QMenuBar {
    background-color: #1a0a0a;
    color: #e8c9c9;
    border-bottom: 1px solid #4d1414;
    padding: 4px;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #5c1414;
    color: #ffffff;
}

QMenu {
    background-color: #1a0a0a;
    color: #e8c9c9;
    border: 1px solid #5c1414;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 16px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #7a1c1c;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #4d1414;
    margin: 4px 8px;
}

/* ---------- Toolbar ---------- */
QToolBar {
    background-color: #1a0a0a;
    border-bottom: 2px solid #7a1c1c;
    spacing: 6px;
    padding: 6px;
}

QToolBar QToolButton {
    background-color: #240d0d;
    color: #f0d9d9;
    border: 1px solid #4d1414;
    border-radius: 6px;
    padding: 6px 10px;
}

QToolBar QToolButton:hover {
    background-color: #7a1c1c;
    border: 1px solid #b32d2d;
    color: #ffffff;
}

QToolBar QToolButton:pressed {
    background-color: #b32d2d;
}

QToolBar::separator {
    background-color: #4d1414;
    width: 1px;
    margin: 4px 6px;
}

/* ---------- Status Bar ---------- */
QStatusBar {
    background-color: #1a0a0a;
    color: #c99;
    border-top: 1px solid #4d1414;
}

/* ---------- Splitter ---------- */
QSplitter::handle {
    background-color: #4d1414;
    width: 3px;
}

QSplitter::handle:hover {
    background-color: #b32d2d;
}

/* ---------- Text Edit (Editor) ---------- */
QTextEdit {
    background-color: #0d0505;
    color: #f2e4e4;
    border: 1px solid #4d1414;
    border-radius: 6px;
    selection-background-color: #7a1c1c;
    selection-color: #ffffff;
    padding: 8px;
}

/* ---------- Labels / Headers ---------- */
QLabel#PaneTitle {
    color: #e05c5c;
    font-weight: bold;
    font-size: 11pt;
    padding: 4px 2px;
    letter-spacing: 1px;
}

/* ---------- Web Preview Frame ---------- */
QFrame#PreviewFrame {
    border: 1px solid #4d1414;
    border-radius: 6px;
}

/* ---------- Scrollbars ---------- */
QScrollBar:vertical {
    background: #1a0a0a;
    width: 12px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #5c1414;
    min-height: 24px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #b32d2d;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #1a0a0a;
    height: 12px;
}

QScrollBar::handle:horizontal {
    background: #5c1414;
    min-width: 24px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #b32d2d;
}

/* ---------- Dialogs / Message Boxes ---------- */
QDialog {
    background-color: #120707;
    color: #f0d9d9;
}

QPushButton {
    background-color: #240d0d;
    color: #f0d9d9;
    border: 1px solid #7a1c1c;
    border-radius: 5px;
    padding: 6px 16px;
}

QPushButton:hover {
    background-color: #7a1c1c;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #b32d2d;
}

/* ---------- Tooltips ---------- */
QToolTip {
    background-color: #240d0d;
    color: #f2e4e4;
    border: 1px solid #b32d2d;
    padding: 4px 8px;
    border-radius: 4px;
}
"""

# HTML/CSS-Vorlage fuer die gerenderte Markdown-Vorschau (rechte Seite)
PREVIEW_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    body {{
        background-color: #0d0505;
        color: #f2e4e4;
        font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        font-size: 15px;
        line-height: 1.6;
        padding: 24px 32px;
        margin: 0;
    }}
    h1, h2, h3, h4, h5, h6 {{
        color: #e8574f;
        border-bottom: 1px solid #4d1414;
        padding-bottom: 6px;
        font-weight: 600;
    }}
    h1 {{ font-size: 26px; }}
    h2 {{ font-size: 21px; }}
    h3 {{ font-size: 18px; }}
    a {{
        color: #ff8b7a;
        text-decoration: none;
    }}
    a:hover {{ text-decoration: underline; }}
    code {{
        background-color: #240d0d;
        color: #ff9d8a;
        border: 1px solid #4d1414;
        border-radius: 4px;
        padding: 2px 6px;
        font-family: "Consolas", "Cascadia Code", monospace;
    }}
    pre {{
        background-color: #1a0a0a;
        border: 1px solid #4d1414;
        border-radius: 6px;
        padding: 14px;
        overflow-x: auto;
    }}
    pre code {{
        background: none;
        border: none;
        padding: 0;
    }}
    blockquote {{
        border-left: 4px solid #7a1c1c;
        margin: 8px 0;
        padding: 4px 16px;
        color: #d8b0b0;
        background-color: #1a0a0a;
    }}
    table {{
        border-collapse: collapse;
        width: 100%;
        margin: 12px 0;
    }}
    th, td {{
        border: 1px solid #4d1414;
        padding: 8px 12px;
        text-align: left;
    }}
    th {{
        background-color: #240d0d;
        color: #e8574f;
    }}
    tr:nth-child(even) {{
        background-color: #150808;
    }}
    hr {{
        border: none;
        border-top: 1px solid #4d1414;
        margin: 20px 0;
    }}
    img {{
        max-width: 100%;
        border-radius: 4px;
        border: 1px solid #4d1414;
    }}
    ul, ol {{
        padding-left: 24px;
    }}
    /* Pygments codehilite Klassen - dezente Darkred-Anpassung */
    .codehilite {{
        background-color: #1a0a0a;
        border: 1px solid #4d1414;
        border-radius: 6px;
        padding: 10px;
    }}
    .codehilite .k {{ color: #ff8b7a; font-weight: bold; }}
    .codehilite .s, .codehilite .s1, .codehilite .s2 {{ color: #d99a6c; }}
    .codehilite .c1, .codehilite .c {{ color: #7a5c5c; font-style: italic; }}
    .codehilite .n {{ color: #f2e4e4; }}
    .codehilite .nf {{ color: #ffb199; }}
    .codehilite .mi, .codehilite .mf {{ color: #e8a87c; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""
