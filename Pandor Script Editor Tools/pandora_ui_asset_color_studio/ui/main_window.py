"""
Pandora® UI Asset & Color Studio - UI: MainWindow + Tabs.

Drei Reiter, jeweils dünne UI-Schicht über der Core-Logik in
`core/color_convert.py`, `core/theme_manager.py` und `core/asset_browser.py`:

  1. Farb-Picker & Konverter    - Pipette (QColorDialog) + HEX/RGB/RGBA/QColor
  2. Theming-Variablen-Manager  - Paletten pflegen & als Dict/QSS exportieren
  3. Icon & Asset Browser       - Verzeichnis durchsuchen, Vorschau, Base64
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import asset_browser, color_convert, theme_manager
from ui.style import PANDORA_QSS

APP_TITLE = "Pandora® | UI Asset & Color Studio"


def _copy_to_clipboard(text: str, status_bar: QStatusBar = None, label: str = "Wert"):
    QApplication.clipboard().setText(text)
    if status_bar is not None:
        status_bar.showMessage(f"{label} in Zwischenablage kopiert.", 2500)


def _swatch_style(hex_color: str) -> str:
    return (
        f"background-color: {hex_color}; border: 1px solid #1d2a38; "
        "border-radius: 4px;"
    )


# ------------------------------------------------------------------
# Tab 1: Farb-Picker & Konverter
# ------------------------------------------------------------------
class ColorPickerTab(QWidget):
    def __init__(self, status_bar: QStatusBar):
        super().__init__()
        self._status_bar = status_bar
        self._color = color_convert.RGBA(0, 229, 255, 255)
        self._updating = False

        header = QLabel("Farb-Picker & Konverter")
        header.setObjectName("HeaderLabel")
        sub = QLabel(
            "Pipette öffnen oder Wert eingeben - HEX, RGB, RGBA und QColor "
            "werden live synchron gehalten."
        )
        sub.setObjectName("SubHeaderLabel")

        self.preview = QLabel()
        self.preview.setMinimumHeight(90)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        pick_button = QPushButton("Pipette / Farbwähler öffnen...")
        pick_button.setObjectName("PrimaryButton")
        pick_button.clicked.connect(self._open_color_dialog)

        form = QGridLayout()
        form.setColumnStretch(1, 1)

        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#00e5ff oder #00e5ffcc")
        self.rgb_edit = QLineEdit()
        self.rgb_edit.setPlaceholderText("0, 229, 255")
        self.rgba_edit = QLineEdit()
        self.rgba_edit.setPlaceholderText("0, 229, 255, 255")
        self.qcolor_edit = QLineEdit()
        self.qcolor_edit.setReadOnly(True)

        self.hex_edit.editingFinished.connect(lambda: self._apply_from_text("hex"))
        self.rgb_edit.editingFinished.connect(lambda: self._apply_from_text("rgb"))
        self.rgba_edit.editingFinished.connect(lambda: self._apply_from_text("rgba"))

        rows = [
            ("HEX", self.hex_edit, "hex"),
            ("RGB", self.rgb_edit, "rgb"),
            ("RGBA", self.rgba_edit, "rgba"),
            ("QColor-Snippet", self.qcolor_edit, "qcolor"),
        ]
        for i, (label_text, widget, key) in enumerate(rows):
            label = QLabel(label_text)
            label.setObjectName("SectionLabel")
            copy_btn = QPushButton("Kopieren")
            copy_btn.clicked.connect(lambda _=False, k=key: self._copy_field(k))
            form.addWidget(label, i, 0)
            form.addWidget(widget, i, 1)
            form.addWidget(copy_btn, i, 2)

        self.contrast_label = QLabel("")
        self.contrast_label.setObjectName("SubHeaderLabel")

        layout = QVBoxLayout()
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addWidget(self.preview)
        layout.addWidget(pick_button)
        layout.addSpacing(8)
        layout.addLayout(form)
        layout.addWidget(self.contrast_label)
        layout.addStretch(1)
        self.setLayout(layout)

        self._refresh_fields()

    def _open_color_dialog(self):
        # QColorDialog bietet unter KDE/GNOME auf Linux eine integrierte
        # Bildschirm-Pipette ("Pick Screen Color") - keine separate
        # Implementierung nötig.
        from PyQt6.QtWidgets import QColorDialog

        initial = QColor(self._color.r, self._color.g, self._color.b, self._color.a)
        dialog = QColorDialog(initial, self)
        dialog.setOption(QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        if dialog.exec():
            qc = dialog.selectedColor()
            if qc.isValid():
                self._color = color_convert.RGBA(qc.red(), qc.green(), qc.blue(), qc.alpha())
                self._refresh_fields()
                self._status_bar.showMessage("Farbe übernommen.", 2000)

    def _apply_from_text(self, source: str):
        if self._updating:
            return
        try:
            if source == "hex":
                self._color = color_convert.parse_hex(self.hex_edit.text())
            elif source == "rgb":
                self._color = color_convert.parse_rgb_string(self.rgb_edit.text())
            elif source == "rgba":
                self._color = color_convert.parse_rgb_string(self.rgba_edit.text())
        except color_convert.ColorParseError as exc:
            self._status_bar.showMessage(str(exc), 3500)
            return
        self._refresh_fields()

    def _refresh_fields(self):
        self._updating = True
        c = self._color
        self.preview.setStyleSheet(_swatch_style(color_convert.to_hex(c, include_alpha=True)))
        self.hex_edit.setText(color_convert.to_hex(c, include_alpha=(c.a != 255)))
        self.rgb_edit.setText(", ".join(str(v) for v in color_convert.to_rgb_tuple(c)))
        self.rgba_edit.setText(", ".join(str(v) for v in color_convert.to_rgba_tuple(c)))
        self.qcolor_edit.setText(
            color_convert.to_qcolor_snippet(c, include_alpha=(c.a != 255))
        )

        text_on_bg = color_convert.readable_text_color(c)
        ratio = color_convert.contrast_ratio(c, text_on_bg)
        self.contrast_label.setText(
            f"Empfohlene Textfarbe auf diesem Hintergrund: "
            f"{color_convert.to_hex(text_on_bg)}  (Kontrastverhältnis {ratio}:1)"
        )
        self._updating = False

    def _copy_field(self, key: str):
        mapping = {
            "hex": self.hex_edit.text(),
            "rgb": self.rgb_edit.text(),
            "rgba": self.rgba_edit.text(),
            "qcolor": self.qcolor_edit.text(),
        }
        _copy_to_clipboard(mapping[key], self._status_bar, key.upper())


# ------------------------------------------------------------------
# Tab 2: Theming-Variablen-Manager
# ------------------------------------------------------------------
class ThemeManagerTab(QWidget):
    def __init__(self, status_bar: QStatusBar):
        super().__init__()
        self._status_bar = status_bar
        self._store = theme_manager.ThemeStore()

        header = QLabel("Theming-Variablen-Manager")
        header.setObjectName("HeaderLabel")
        sub = QLabel(
            "Zentrale Farbpaletten für alle Pandora-Tools pflegen und als "
            "Python-Dict oder QSS-Übersicht exportieren."
        )
        sub.setObjectName("SubHeaderLabel")

        palette_row = QHBoxLayout()
        self.palette_combo = QComboBox()
        self.palette_combo.currentTextChanged.connect(self._load_palette)
        new_btn = QPushButton("Neue Palette")
        new_btn.clicked.connect(self._new_palette)
        rename_btn = QPushButton("Umbenennen")
        rename_btn.clicked.connect(self._rename_palette)
        delete_btn = QPushButton("Löschen")
        delete_btn.clicked.connect(self._delete_palette)
        palette_row.addWidget(QLabel("Palette:"))
        palette_row.addWidget(self.palette_combo, 1)
        palette_row.addWidget(new_btn)
        palette_row.addWidget(rename_btn)
        palette_row.addWidget(delete_btn)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Variable", "HEX-Wert", "Vorschau"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 90)
        self.table.itemChanged.connect(self._on_item_changed)

        var_row = QHBoxLayout()
        add_var_btn = QPushButton("Variable hinzufügen")
        add_var_btn.clicked.connect(self._add_variable)
        remove_var_btn = QPushButton("Variable entfernen")
        remove_var_btn.clicked.connect(self._remove_variable)
        var_row.addWidget(add_var_btn)
        var_row.addWidget(remove_var_btn)
        var_row.addStretch(1)

        export_row = QHBoxLayout()
        export_dict_btn = QPushButton("Als Python-Dict exportieren")
        export_dict_btn.setObjectName("PrimaryButton")
        export_dict_btn.clicked.connect(self._export_dict)
        export_qss_btn = QPushButton("Als QSS-Übersicht exportieren")
        export_qss_btn.clicked.connect(self._export_qss)
        export_row.addWidget(export_dict_btn)
        export_row.addWidget(export_qss_btn)
        export_row.addStretch(1)

        self.export_preview = QPlainTextEdit()
        self.export_preview.setReadOnly(True)
        self.export_preview.setPlaceholderText("Export-Vorschau erscheint hier...")
        copy_export_btn = QPushButton("Export kopieren")
        copy_export_btn.clicked.connect(self._copy_export)

        layout = QVBoxLayout()
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addLayout(palette_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(var_row)
        layout.addLayout(export_row)
        layout.addWidget(self.export_preview)
        layout.addWidget(copy_export_btn)
        self.setLayout(layout)

        self._refresh_palette_list()

    # -- Paletten ---------------------------------------------------

    def _refresh_palette_list(self, select: str | None = None):
        self.palette_combo.blockSignals(True)
        self.palette_combo.clear()
        self.palette_combo.addItems(self._store.list_palette_names())
        self.palette_combo.blockSignals(False)
        if select and select in self._store.palettes:
            self.palette_combo.setCurrentText(select)
        self._load_palette(self.palette_combo.currentText())

    def _current_palette_name(self) -> str:
        return self.palette_combo.currentText()

    def _load_palette(self, name: str):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if name and name in self._store.palettes:
            palette = self._store.get(name)
            for key, value in sorted(palette.variables.items()):
                self._append_row(key, value)
        self.table.blockSignals(False)

    def _append_row(self, key: str, value: str):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(key))
        self.table.setItem(row, 1, QTableWidgetItem(value))
        swatch_item = QTableWidgetItem("")
        try:
            swatch_item.setBackground(QColor(value))
        except Exception:
            pass
        swatch_item.setFlags(swatch_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 2, swatch_item)

    def _new_palette(self):
        name, ok = QInputDialog.getText(self, "Neue Palette", "Name der neuen Palette:")
        if not ok or not name.strip():
            return
        try:
            self._store.create_palette(name.strip(), base_on=self._current_palette_name() or None)
        except theme_manager.ThemeError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        self._refresh_palette_list(select=name.strip())
        self._status_bar.showMessage(f"Palette '{name.strip()}' erstellt.", 2500)

    def _rename_palette(self):
        old_name = self._current_palette_name()
        if not old_name:
            return
        new_name, ok = QInputDialog.getText(self, "Palette umbenennen", "Neuer Name:", text=old_name)
        if not ok or not new_name.strip():
            return
        try:
            self._store.rename_palette(old_name, new_name.strip())
        except theme_manager.ThemeError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        self._refresh_palette_list(select=new_name.strip())

    def _delete_palette(self):
        name = self._current_palette_name()
        if not name:
            return
        confirm = QMessageBox.question(
            self, "Palette löschen", f"Palette '{name}' wirklich löschen?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._store.delete_palette(name)
        except theme_manager.ThemeError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        self._refresh_palette_list()
        self._status_bar.showMessage(f"Palette '{name}' gelöscht.", 2500)

    # -- Variablen --------------------------------------------------

    def _add_variable(self):
        name = self._current_palette_name()
        if not name:
            return
        key, ok = QInputDialog.getText(self, "Variable hinzufügen", "Variablenname (z.B. accent.cyan):")
        if not ok or not key.strip():
            return
        value, ok = QInputDialog.getText(self, "Variable hinzufügen", "HEX-Wert:", text="#00e5ff")
        if not ok:
            return
        try:
            self._store.set_variable(name, key.strip(), value.strip())
        except theme_manager.ThemeError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        self._load_palette(name)

    def _remove_variable(self):
        name = self._current_palette_name()
        row = self.table.currentRow()
        if not name or row < 0:
            return
        key = self.table.item(row, 0).text()
        self._store.remove_variable(name, key)
        self._load_palette(name)

    def _on_item_changed(self, item: QTableWidgetItem):
        name = self._current_palette_name()
        if not name or item.column() not in (0, 1):
            return
        row = item.row()
        key_item = self.table.item(row, 0)
        value_item = self.table.item(row, 1)
        if key_item is None or value_item is None:
            return
        try:
            self._store.set_variable(name, key_item.text(), value_item.text())
        except theme_manager.ThemeError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        self.table.blockSignals(True)
        try:
            self.table.item(row, 2).setBackground(QColor(value_item.text()))
        except Exception:
            pass
        self.table.blockSignals(False)

    # -- Export -------------------------------------------------------

    def _export_dict(self):
        name = self._current_palette_name()
        if not name:
            return
        self.export_preview.setPlainText(self._store.export_as_python_dict(name))

    def _export_qss(self):
        name = self._current_palette_name()
        if not name:
            return
        self.export_preview.setPlainText(self._store.export_as_qss_snippet(name))

    def _copy_export(self):
        text = self.export_preview.toPlainText()
        if text:
            _copy_to_clipboard(text, self._status_bar, "Export")


# ------------------------------------------------------------------
# Tab 3: Icon & Asset Browser
# ------------------------------------------------------------------
class AssetBrowserTab(QWidget):
    def __init__(self, status_bar: QStatusBar):
        super().__init__()
        self._status_bar = status_bar
        self._entries: list[asset_browser.AssetEntry] = []

        header = QLabel("Icon & Asset Browser")
        header.setObjectName("HeaderLabel")
        sub = QLabel(
            "Verzeichnis durchsuchen, Icons/Assets vorschauen und als "
            "Base64/Data-URI/Python-Snippet direkt in den Code übernehmen."
        )
        sub.setObjectName("SubHeaderLabel")

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setPlaceholderText("Kein Verzeichnis gewählt...")
        browse_btn = QPushButton("Verzeichnis wählen...")
        browse_btn.setObjectName("PrimaryButton")
        browse_btn.clicked.connect(self._choose_directory)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(browse_btn)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)

        self.preview_label = QLabel("Keine Auswahl")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(160, 160)
        self.preview_label.setStyleSheet(
            "background-color: #10161f; border: 1px solid #1d2a38; border-radius: 4px;"
        )

        self.info_label = QLabel("")
        self.info_label.setObjectName("SubHeaderLabel")
        self.info_label.setWordWrap(True)

        preview_group = QGroupBox("Vorschau")
        preview_layout = QVBoxLayout()
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.info_label)
        preview_group.setLayout(preview_layout)

        actions_row = QHBoxLayout()
        copy_b64_btn = QPushButton("Base64 kopieren")
        copy_b64_btn.clicked.connect(self._copy_base64)
        copy_uri_btn = QPushButton("Data-URI kopieren")
        copy_uri_btn.clicked.connect(self._copy_data_uri)
        copy_snippet_btn = QPushButton("Python-Snippet kopieren")
        copy_snippet_btn.clicked.connect(self._copy_python_snippet)
        actions_row.addWidget(copy_b64_btn)
        actions_row.addWidget(copy_uri_btn)
        actions_row.addWidget(copy_snippet_btn)

        right_panel = QVBoxLayout()
        right_panel.addWidget(preview_group)
        right_panel.addLayout(actions_row)
        right_panel.addStretch(1)
        right_widget = QWidget()
        right_widget.setLayout(right_panel)

        splitter = QSplitter()
        splitter.addWidget(self.list_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        layout = QVBoxLayout()
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addLayout(dir_row)
        layout.addWidget(splitter, 1)
        self.setLayout(layout)

    def _choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Verzeichnis wählen")
        if not directory:
            return
        self.dir_edit.setText(directory)
        try:
            self._entries = asset_browser.scan_directory(directory)
        except asset_browser.AssetError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return

        self.list_widget.clear()
        for entry in self._entries:
            item = QListWidgetItem(entry.name)
            icon = QIcon(str(entry.path)) if entry.suffix != ".svg" else QIcon()
            if not icon.isNull():
                item.setIcon(icon)
            item.setData(Qt.ItemDataRole.UserRole, str(entry.path))
            self.list_widget.addItem(item)

        self._status_bar.showMessage(f"{len(self._entries)} Asset(s) gefunden.", 2500)

    def _current_path(self) -> Path | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return Path(item.data(Qt.ItemDataRole.UserRole))

    def _on_selection_changed(self, current: QListWidgetItem, _previous: QListWidgetItem):
        if current is None:
            self.preview_label.setText("Keine Auswahl")
            self.preview_label.setPixmap(QPixmap())
            self.info_label.setText("")
            return

        path = Path(current.data(Qt.ItemDataRole.UserRole))
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            self.preview_label.setPixmap(
                pixmap.scaled(
                    150,
                    150,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.preview_label.setText("")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Keine Vorschau\n(z.B. SVG ohne Renderer)")

        size = asset_browser.human_readable_size(path.stat().st_size)
        self.info_label.setText(f"{path.name}\n{size}  ·  {path.suffix.lower()}")

    def _copy_base64(self):
        path = self._current_path()
        if path is None:
            return
        try:
            encoded = asset_browser.to_base64(path)
        except asset_browser.AssetError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        _copy_to_clipboard(encoded, self._status_bar, "Base64-String")

    def _copy_data_uri(self):
        path = self._current_path()
        if path is None:
            return
        try:
            uri = asset_browser.to_data_uri(path)
        except asset_browser.AssetError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        _copy_to_clipboard(uri, self._status_bar, "Data-URI")

    def _copy_python_snippet(self):
        path = self._current_path()
        if path is None:
            return
        try:
            snippet = asset_browser.to_python_qpixmap_snippet(path)
        except asset_browser.AssetError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        _copy_to_clipboard(snippet, self._status_bar, "Python-Snippet")


# ------------------------------------------------------------------
# MainWindow
# ------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1150, 760)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Bereit.", 2000)

        tabs = QTabWidget()
        tabs.addTab(ColorPickerTab(status_bar), "Farb-Picker & Konverter")
        tabs.addTab(ThemeManagerTab(status_bar), "Theming-Variablen-Manager")
        tabs.addTab(AssetBrowserTab(status_bar), "Icon & Asset Browser")
        self.setCentralWidget(tabs)


def run():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyleSheet(PANDORA_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
