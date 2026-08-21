"""Pandora®-Cyberpunk-Stylesheet für den SQL Config Editor & Validator."""

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

QListWidget, QTableView, QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #10161f;
    border: 1px solid #1d2a38;
    border-radius: 4px;
}

QListWidget {
    padding: 4px;
}

QListWidget::item {
    padding: 6px 8px;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #ff2a6d;
    color: #0a0e14;
}

QListWidget::item:hover:!selected {
    background-color: #16202c;
}

QTableView {
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

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    padding: 5px 8px;
    color: #d8f7ff;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #00e5ff;
}

QLineEdit[invalid="true"] {
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

QPushButton#DangerButton {
    border-color: #ff2a6d;
    color: #ff2a6d;
}

QPushButton#DangerButton:hover {
    background-color: #ff2a6d;
    color: #0a0e14;
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
