"""Pandora®-Cyberpunk-Stylesheet für den UI Asset & Color Studio.

Identische Farb-/Struktursprache wie bei den anderen Pandora-Werkzeugen
(Crypto Utility, SQL Config Editor: dunkler Hintergrund, Cyan-Akzent
#00e5ff, Pink-Akzent #ff2a6d), damit sich das Tool nahtlos in die
bestehende Pandora-Werkzeugleiste einfügt.
"""

PANDORA_QSS = """
QWidget {
    background-color: #0a0e14;
    color: #d8f7ff;
    font-family: "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 13px;
}

QMainWindow {
    background-color: #0a0e14;
}

QLabel#HeaderLabel {
    color: #00e5ff;
    font-size: 18px;
    font-weight: bold;
    padding: 6px 0px;
}

QLabel#SubHeaderLabel {
    color: #6b7a8f;
    font-size: 11px;
    padding-bottom: 8px;
}

QLabel#SectionLabel {
    color: #00e5ff;
    font-weight: bold;
    padding-top: 4px;
}

QLabel#WarningLabel {
    color: #ff2a6d;
    font-weight: bold;
}

QLabel#SuccessLabel {
    color: #37ffb0;
    font-weight: bold;
}

QTabWidget::pane {
    border: 1px solid #1d2a38;
    border-radius: 4px;
    top: -1px;
}

QTabBar::tab {
    background-color: #10161f;
    color: #6b7a8f;
    border: 1px solid #1d2a38;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #16202c;
    color: #00e5ff;
    border-bottom: 2px solid #ff2a6d;
}

QTabBar::tab:hover:!selected {
    color: #d8f7ff;
}

QListWidget, QTableWidget, QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox {
    background-color: #10161f;
    border: 1px solid #1d2a38;
    border-radius: 4px;
}

QTextEdit, QPlainTextEdit {
    padding: 6px;
    selection-background-color: #00e5ff;
    selection-color: #0a0e14;
}

QListWidget::item, QTableWidget::item {
    padding: 5px 8px;
}

QListWidget::item:selected, QTableWidget::item:selected {
    background-color: #ff2a6d;
    color: #0a0e14;
}

QTableWidget {
    gridline-color: #1d2a38;
    selection-background-color: #00e5ff;
    selection-color: #0a0e14;
}

QHeaderView::section {
    background-color: #10161f;
    color: #00e5ff;
    padding: 6px;
    border: none;
    border-bottom: 2px solid #ff2a6d;
    font-weight: bold;
}

QLineEdit, QComboBox, QSpinBox {
    padding: 5px 8px;
    color: #d8f7ff;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #00e5ff;
}

QLineEdit[invalid="true"], QPlainTextEdit[invalid="true"] {
    border: 1px solid #ff2a6d;
    background-color: #1f0f18;
}

QPushButton {
    background-color: #16202c;
    color: #00e5ff;
    border: 1px solid #00e5ff;
    border-radius: 4px;
    padding: 7px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #00e5ff;
    color: #0a0e14;
}

QPushButton:disabled {
    color: #445;
    border-color: #2a3644;
}

QPushButton#PrimaryButton {
    background-color: #ff2a6d;
    color: #0a0e14;
    border-color: #ff2a6d;
}

QPushButton#PrimaryButton:hover {
    background-color: #ff5c8d;
}

QSplitter::handle {
    background-color: #1d2a38;
}

QStatusBar {
    background-color: #10161f;
    color: #6b7a8f;
    border-top: 1px solid #1d2a38;
}

QScrollBar:vertical {
    background: #10161f;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #1d2a38;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #00e5ff;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #00e5ff;
    border-radius: 3px;
    background-color: #10161f;
}
QCheckBox::indicator:checked {
    background-color: #00e5ff;
}

QToolBar {
    background-color: #10161f;
    border-bottom: 1px solid #1d2a38;
    spacing: 6px;
    padding: 4px;
}

QGroupBox {
    border: 1px solid #1d2a38;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 12px;
    color: #00e5ff;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
"""
