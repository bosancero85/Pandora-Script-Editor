"""
Pandora® Crypto & Encoding Utility - UI: MainWindow + Tabs.

Vier Reiter, jeweils dünne UI-Schicht über der Core-Logik in
`core/encoding.py`, `core/hashing.py`, `core/jwt_tool.py` und
`core/regex_tool.py`:

  1. Encoder/Decoder   - Base64, Hex, URL, HTML-Entities, Binär
  2. Hash & Checksum    - MD5/SHA-1/SHA-256/SHA-512 + HMAC
  3. JWT & Token        - Header/Payload-Parsing + HMAC-Signaturprüfung
  4. RegEx Tester       - Treffer/Gruppen + optionale Ersetzung
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QClipboard
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import encoding, hashing, jwt_tool, regex_tool
from ui.style import PANDORA_QSS

APP_TITLE = "Pandora® Crypto & Encoding Utility"


def _copy_to_clipboard(text: str, status_bar: QStatusBar = None, label: str = "Wert"):
    QApplication.clipboard().setText(text, QClipboard.Mode.Clipboard)
    if status_bar is not None:
        status_bar.showMessage(f"{label} in Zwischenablage kopiert.", 2500)


# ------------------------------------------------------------------
# Tab 1: Multi-Format Encoder/Decoder
# ------------------------------------------------------------------
class EncoderDecoderTab(QWidget):
    def __init__(self, status_bar: QStatusBar, parent=None):
        super().__init__(parent)
        self._status_bar = status_bar
        self._updating = False
        self._build_ui()
        self._on_format_changed()

    def _build_ui(self):
        root = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(encoding.FORMATS)
        self.format_combo.currentTextChanged.connect(self._on_format_changed)
        top_row.addWidget(self.format_combo)

        self.rb_encode = QRadioButton("Encode")
        self.rb_decode = QRadioButton("Decode")
        self.rb_encode.setChecked(True)
        self.rb_encode.toggled.connect(self._convert)
        top_row.addWidget(self.rb_encode)
        top_row.addWidget(self.rb_decode)
        top_row.addStretch(1)

        self.swap_btn = QPushButton("⇄ Ein-/Ausgabe tauschen")
        self.swap_btn.clicked.connect(self._swap)
        top_row.addWidget(self.swap_btn)
        root.addLayout(top_row)

        # Format-spezifische Optionen (werden je nach Format ein-/ausgeblendet)
        self.opt_row = QHBoxLayout()
        self.cb_url_safe = QCheckBox("URL-sicheres Base64 (-_ statt +/)")
        self.cb_hex_upper = QCheckBox("Hex Großbuchstaben")
        self.cb_hex_spaced = QCheckBox("Hex mit Leerzeichen gruppieren")
        self.cb_url_plus = QCheckBox("Leerzeichen als '+' (application/x-www-form-urlencoded)")
        self.cb_html_quote = QCheckBox("Anführungszeichen mit escapen")
        self.cb_bin_spaced = QCheckBox("Binär mit Leerzeichen gruppieren")
        for cb in (
            self.cb_url_safe,
            self.cb_hex_upper,
            self.cb_hex_spaced,
            self.cb_url_plus,
            self.cb_html_quote,
            self.cb_bin_spaced,
        ):
            cb.toggled.connect(self._convert)
            self.opt_row.addWidget(cb)
        self.opt_row.addStretch(1)
        root.addLayout(self.opt_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.addWidget(QLabel("Eingabe"))
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("Text hier eingeben oder einfügen …")
        self.input_edit.textChanged.connect(self._convert)
        left_layout.addWidget(self.input_edit)
        splitter.addWidget(left_box)

        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)
        out_header = QHBoxLayout()
        out_header.addWidget(QLabel("Ergebnis"))
        out_header.addStretch(1)
        copy_btn = QPushButton("Kopieren")
        copy_btn.clicked.connect(
            lambda: _copy_to_clipboard(self.output_edit.toPlainText(), self._status_bar, "Ergebnis")
        )
        out_header.addWidget(copy_btn)
        right_layout.addLayout(out_header)
        self.output_edit = QPlainTextEdit()
        self.output_edit.setReadOnly(True)
        right_layout.addWidget(self.output_edit)
        splitter.addWidget(right_box)

        root.addWidget(splitter, stretch=1)

        self.error_label = QLabel("")
        self.error_label.setObjectName("WarningLabel")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

    def _on_format_changed(self):
        fmt = self.format_combo.currentText()
        self.cb_url_safe.setVisible(fmt == "Base64")
        self.cb_hex_upper.setVisible(fmt == "Hex")
        self.cb_hex_spaced.setVisible(fmt == "Hex")
        self.cb_url_plus.setVisible(fmt == "URL-Encoding")
        self.cb_html_quote.setVisible(fmt == "HTML-Entities")
        self.cb_bin_spaced.setVisible(fmt == "Binär (8-Bit)")
        self._convert()

    def _current_options(self) -> dict:
        return dict(
            url_safe=self.cb_url_safe.isChecked(),
            uppercase=self.cb_hex_upper.isChecked(),
            spaced=self.cb_hex_spaced.isChecked() if self.format_combo.currentText() == "Hex" else self.cb_bin_spaced.isChecked(),
            encode_plus=self.cb_url_plus.isChecked(),
            quote=self.cb_html_quote.isChecked(),
        )

    def _swap(self):
        # Richtung umkehren UND Inhalte tauschen, damit z.B. eine erhaltene
        # Base64-Zeichenkette direkt weiterverarbeitet werden kann.
        output_text = self.output_edit.toPlainText()
        was_encode = self.rb_encode.isChecked()
        self.input_edit.setPlainText(output_text)
        if was_encode:
            self.rb_decode.setChecked(True)
        else:
            self.rb_encode.setChecked(True)

    def _convert(self):
        if self._updating:
            return
        fmt = self.format_combo.currentText()
        text = self.input_edit.toPlainText()
        self.error_label.setText("")
        if not text:
            self.output_edit.setPlainText("")
            return
        options = self._current_options()
        try:
            if self.rb_encode.isChecked():
                result = encoding.encode(fmt, text, **options)
            else:
                result = encoding.decode(fmt, text, **options)
        except ValueError as exc:
            self.output_edit.setPlainText("")
            self.error_label.setText(str(exc))
            return
        self.output_edit.setPlainText(result)


# ------------------------------------------------------------------
# Tab 2: Hash & Checksum Generator (inkl. HMAC)
# ------------------------------------------------------------------
class HashTab(QWidget):
    def __init__(self, status_bar: QStatusBar, parent=None):
        super().__init__(parent)
        self._status_bar = status_bar
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(QLabel("Eingabetext"))
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("Text, dessen Hash berechnet werden soll …")
        self.input_edit.textChanged.connect(self._recompute)
        self.input_edit.setMaximumHeight(120)
        root.addWidget(self.input_edit)

        algo_row = QHBoxLayout()
        algo_row.addWidget(QLabel("Algorithmen:"))
        self.algo_checks = {}
        for algo in hashing.ALGORITHMS:
            cb = QCheckBox(algo)
            cb.setChecked(True)
            cb.toggled.connect(self._recompute)
            self.algo_checks[algo] = cb
            algo_row.addWidget(cb)
        algo_row.addStretch(1)
        root.addLayout(algo_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Algorithmus", "Hexdigest"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._copy_row)
        root.addWidget(self.table, stretch=1)
        root.addWidget(QLabel("Tipp: Zeile doppelklicken, um den Hash zu kopieren."))

        # HMAC-Bereich
        hmac_box = QGroupBox("HMAC-Signatur")
        hmac_layout = QGridLayout(hmac_box)
        hmac_layout.addWidget(QLabel("Algorithmus:"), 0, 0)
        self.hmac_algo_combo = QComboBox()
        self.hmac_algo_combo.addItems(hashing.ALGORITHMS)
        self.hmac_algo_combo.setCurrentText("SHA-256")
        hmac_layout.addWidget(self.hmac_algo_combo, 0, 1)

        hmac_layout.addWidget(QLabel("Key:"), 0, 2)
        self.hmac_key_edit = QLineEdit()
        self.hmac_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        hmac_layout.addWidget(self.hmac_key_edit, 0, 3)
        self.show_key_cb = QCheckBox("Key anzeigen")
        self.show_key_cb.toggled.connect(
            lambda checked: self.hmac_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        hmac_layout.addWidget(self.show_key_cb, 0, 4)

        compute_btn = QPushButton("HMAC berechnen")
        compute_btn.setObjectName("PrimaryButton")
        compute_btn.clicked.connect(self._compute_hmac)
        hmac_layout.addWidget(compute_btn, 1, 0)

        self.hmac_result_edit = QLineEdit()
        self.hmac_result_edit.setReadOnly(True)
        hmac_layout.addWidget(self.hmac_result_edit, 1, 1, 1, 3)

        copy_hmac_btn = QPushButton("Kopieren")
        copy_hmac_btn.clicked.connect(
            lambda: _copy_to_clipboard(self.hmac_result_edit.text(), self._status_bar, "HMAC")
        )
        hmac_layout.addWidget(copy_hmac_btn, 1, 4)

        hmac_layout.addWidget(QLabel("Erwarteter Wert (optional, zum Vergleich):"), 2, 0, 1, 2)
        self.hmac_expected_edit = QLineEdit()
        hmac_layout.addWidget(self.hmac_expected_edit, 2, 2, 1, 2)
        verify_btn = QPushButton("Vergleichen")
        verify_btn.clicked.connect(self._verify_hmac)
        hmac_layout.addWidget(verify_btn, 2, 4)

        self.hmac_status_label = QLabel("")
        hmac_layout.addWidget(self.hmac_status_label, 3, 0, 1, 5)

        root.addWidget(hmac_box)

    def _recompute(self):
        text = self.input_edit.toPlainText()
        selected = [algo for algo, cb in self.algo_checks.items() if cb.isChecked()]
        self.table.setRowCount(0)
        if not text or not selected:
            return
        results = hashing.compute_all_hashes(text, algorithms=selected)
        for algo in selected:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(algo))
            self.table.setItem(row, 1, QTableWidgetItem(results[algo]))

    def _copy_row(self, row, _column):
        item = self.table.item(row, 1)
        if item:
            _copy_to_clipboard(item.text(), self._status_bar, "Hash")

    def _compute_hmac(self):
        algo = self.hmac_algo_combo.currentText()
        key = self.hmac_key_edit.text()
        message = self.input_edit.toPlainText()
        try:
            result = hashing.compute_hmac(algo, key, message)
        except ValueError as exc:
            self.hmac_result_edit.setText("")
            self.hmac_status_label.setObjectName("WarningLabel")
            self.hmac_status_label.setText(str(exc))
            self.hmac_status_label.style().unpolish(self.hmac_status_label)
            self.hmac_status_label.style().polish(self.hmac_status_label)
            return
        self.hmac_result_edit.setText(result)
        self.hmac_status_label.setText("")

    def _verify_hmac(self):
        expected = self.hmac_expected_edit.text().strip()
        if not expected:
            self.hmac_status_label.setObjectName("WarningLabel")
            self.hmac_status_label.setText("Bitte einen erwarteten Wert zum Vergleich eingeben.")
            self._repolish_status()
            return
        algo = self.hmac_algo_combo.currentText()
        key = self.hmac_key_edit.text()
        message = self.input_edit.toPlainText()
        try:
            match = hashing.verify_hmac(algo, key, message, expected)
        except ValueError as exc:
            self.hmac_status_label.setObjectName("WarningLabel")
            self.hmac_status_label.setText(str(exc))
            self._repolish_status()
            return
        if match:
            self.hmac_status_label.setObjectName("SuccessLabel")
            self.hmac_status_label.setText("✓ Signatur stimmt überein.")
        else:
            self.hmac_status_label.setObjectName("WarningLabel")
            self.hmac_status_label.setText("✗ Signatur stimmt NICHT überein.")
        self._repolish_status()

    def _repolish_status(self):
        self.hmac_status_label.style().unpolish(self.hmac_status_label)
        self.hmac_status_label.style().polish(self.hmac_status_label)


# ------------------------------------------------------------------
# Tab 3: JWT & Token Inspector
# ------------------------------------------------------------------
class JwtTab(QWidget):
    def __init__(self, status_bar: QStatusBar, parent=None):
        super().__init__(parent)
        self._status_bar = status_bar
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(QLabel("JWT / Token"))
        self.token_edit = QPlainTextEdit()
        self.token_edit.setPlaceholderText("eyJhbGciOi... . eyJzdWIiOi... . SflKxwRJ...")
        self.token_edit.setMaximumHeight(90)
        self.token_edit.textChanged.connect(self._decode)
        root.addWidget(self.token_edit)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("WarningLabel")
        self.warning_label.setWordWrap(True)
        root.addWidget(self.warning_label)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        header_box = QWidget()
        header_layout = QVBoxLayout(header_box)
        header_layout.addWidget(QLabel("Header"))
        self.header_edit = QPlainTextEdit()
        self.header_edit.setReadOnly(True)
        header_layout.addWidget(self.header_edit)
        splitter.addWidget(header_box)

        payload_box = QWidget()
        payload_layout = QVBoxLayout(payload_box)
        payload_layout.addWidget(QLabel("Payload"))
        self.payload_edit = QPlainTextEdit()
        self.payload_edit.setReadOnly(True)
        payload_layout.addWidget(self.payload_edit)
        splitter.addWidget(payload_box)

        root.addWidget(splitter, stretch=1)

        verify_box = QGroupBox("Signaturprüfung (nur HS256 / HS384 / HS512)")
        verify_layout = QHBoxLayout(verify_box)
        verify_layout.addWidget(QLabel("Secret:"))
        self.secret_edit = QLineEdit()
        self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        verify_layout.addWidget(self.secret_edit)
        self.show_secret_cb = QCheckBox("anzeigen")
        self.show_secret_cb.toggled.connect(
            lambda checked: self.secret_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        verify_layout.addWidget(self.show_secret_cb)
        verify_btn = QPushButton("Signatur prüfen")
        verify_btn.setObjectName("PrimaryButton")
        verify_btn.clicked.connect(self._verify_signature)
        verify_layout.addWidget(verify_btn)
        self.verify_result_label = QLabel("")
        verify_layout.addWidget(self.verify_result_label, stretch=1)
        root.addWidget(verify_box)

    def _decode(self):
        token = self.token_edit.toPlainText().strip()
        self.warning_label.setText("")
        self.verify_result_label.setText("")
        if not token:
            self.header_edit.setPlainText("")
            self.payload_edit.setPlainText("")
            return
        try:
            parts = jwt_tool.parse_jwt(token)
        except ValueError as exc:
            self.header_edit.setPlainText("")
            self.payload_edit.setPlainText("")
            self.warning_label.setText(str(exc))
            return
        self.header_edit.setPlainText(jwt_tool.pretty(parts.header))
        self.payload_edit.setPlainText(jwt_tool.pretty(parts.payload))
        if parts.warnings:
            self.warning_label.setText(" | ".join(parts.warnings))
        self._parts = parts

    def _verify_signature(self):
        token = self.token_edit.toPlainText().strip()
        secret = self.secret_edit.text()
        if not token:
            return
        try:
            ok = jwt_tool.verify_hmac_signature(token, secret)
        except ValueError as exc:
            self.verify_result_label.setObjectName("WarningLabel")
            self.verify_result_label.setText(str(exc))
            self._repolish()
            return
        if ok:
            self.verify_result_label.setObjectName("SuccessLabel")
            self.verify_result_label.setText("✓ Signatur gültig für dieses Secret.")
        else:
            self.verify_result_label.setObjectName("WarningLabel")
            self.verify_result_label.setText("✗ Signatur ungültig für dieses Secret.")
        self._repolish()

    def _repolish(self):
        self.verify_result_label.style().unpolish(self.verify_result_label)
        self.verify_result_label.style().polish(self.verify_result_label)


# ------------------------------------------------------------------
# Tab 4: RegEx & Pattern Tester
# ------------------------------------------------------------------
class RegexTab(QWidget):
    def __init__(self, status_bar: QStatusBar, parent=None):
        super().__init__(parent)
        self._status_bar = status_bar
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        pattern_row = QHBoxLayout()
        pattern_row.addWidget(QLabel("Pattern:"))
        self.pattern_edit = QLineEdit()
        self.pattern_edit.setPlaceholderText(r"z.B. [a-fA-F0-9]{32}  oder  \\bhttps?://\\S+")
        self.pattern_edit.textChanged.connect(self._run_test)
        pattern_row.addWidget(self.pattern_edit, stretch=1)
        root.addLayout(pattern_row)

        flag_row = QHBoxLayout()
        flag_row.addWidget(QLabel("Flags:"))
        self.flag_checks = {}
        for name in regex_tool.FLAG_OPTIONS:
            cb = QCheckBox(name)
            cb.toggled.connect(self._run_test)
            self.flag_checks[name] = cb
            flag_row.addWidget(cb)
        flag_row.addStretch(1)
        root.addLayout(flag_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        test_box = QWidget()
        test_layout = QVBoxLayout(test_box)
        test_layout.addWidget(QLabel("Test-String"))
        self.test_edit = QPlainTextEdit()
        self.test_edit.setPlaceholderText("Text, gegen den das Pattern getestet wird …")
        self.test_edit.textChanged.connect(self._run_test)
        test_layout.addWidget(self.test_edit)
        splitter.addWidget(test_box)

        result_box = QWidget()
        result_layout = QVBoxLayout(result_box)
        header_row = QHBoxLayout()
        self.match_count_label = QLabel("0 Treffer")
        header_row.addWidget(self.match_count_label)
        header_row.addStretch(1)
        result_layout.addLayout(header_row)

        self.result_table = QTableWidget(0, 4)
        self.result_table.setHorizontalHeaderLabels(["#", "Start–Ende", "Treffer", "Gruppen"])
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        result_layout.addWidget(self.result_table)
        splitter.addWidget(result_box)

        root.addWidget(splitter, stretch=1)

        self.error_label = QLabel("")
        self.error_label.setObjectName("WarningLabel")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        # Ersetzungs-Bereich
        sub_box = QGroupBox("Ersetzen (re.sub)")
        sub_layout = QHBoxLayout(sub_box)
        sub_layout.addWidget(QLabel("Ersetzung:"))
        self.replacement_edit = QLineEdit()
        self.replacement_edit.setPlaceholderText(r"z.B. [REDACTED]  oder  \\1-\\2")
        sub_layout.addWidget(self.replacement_edit, stretch=1)
        sub_btn = QPushButton("Anwenden")
        sub_btn.clicked.connect(self._apply_substitution)
        sub_layout.addWidget(sub_btn)
        root.addWidget(sub_box)

        self.sub_result_edit = QPlainTextEdit()
        self.sub_result_edit.setReadOnly(True)
        self.sub_result_edit.setMaximumHeight(90)
        self.sub_result_edit.setPlaceholderText("Ergebnis der Ersetzung erscheint hier …")
        root.addWidget(self.sub_result_edit)

    def _selected_flags(self):
        return [name for name, cb in self.flag_checks.items() if cb.isChecked()]

    def _run_test(self):
        pattern = self.pattern_edit.text()
        text = self.test_edit.toPlainText()
        self.result_table.setRowCount(0)
        self.error_label.setText("")
        if not pattern:
            self.match_count_label.setText("0 Treffer")
            return
        result = regex_tool.test_pattern(pattern, text, self._selected_flags())
        if result.error:
            self.error_label.setText(result.error)
            self.match_count_label.setText("0 Treffer")
            return
        self.match_count_label.setText(f"{result.match_count} Treffer")
        for m in result.matches:
            row = self.result_table.rowCount()
            self.result_table.insertRow(row)
            self.result_table.setItem(row, 0, QTableWidgetItem(str(m.index + 1)))
            self.result_table.setItem(row, 1, QTableWidgetItem(f"{m.start}–{m.end}"))
            self.result_table.setItem(row, 2, QTableWidgetItem(m.text))
            groups_display = ", ".join(str(g) for g in m.groups) if m.groups else "–"
            self.result_table.setItem(row, 3, QTableWidgetItem(groups_display))

    def _apply_substitution(self):
        pattern = self.pattern_edit.text()
        replacement = self.replacement_edit.text()
        text = self.test_edit.toPlainText()
        result, count, error = regex_tool.substitute(pattern, replacement, text, self._selected_flags())
        if error:
            self.error_label.setText(error)
            return
        self.error_label.setText("")
        self.sub_result_edit.setPlainText(result)
        self._status_bar.showMessage(f"{count} Ersetzung(en) durchgeführt.", 3000)


# ------------------------------------------------------------------
# MainWindow
# ------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1100, 720)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Bereit.", 2000)

        tabs = QTabWidget()
        tabs.addTab(EncoderDecoderTab(status_bar), "Encoder / Decoder")
        tabs.addTab(HashTab(status_bar), "Hash & Checksum")
        tabs.addTab(JwtTab(status_bar), "JWT & Token")
        tabs.addTab(RegexTab(status_bar), "RegEx Tester")
        self.setCentralWidget(tabs)


def run():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyleSheet(PANDORA_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
