#!/usr/bin/env python3
"""Automatisch generiert mit Pandora® UI Forge | by AKI_SystemDown® ©2026"""

import sys
import json
import hashlib
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QDialogButtonBox, QFrame, QLabel, QLineEdit, QGraphicsDropShadowEffect, QMessageBox
from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt, pyqtSignal


# --- Zugangsdaten -----------------------------------------------------------
# Werden in login_config.json (im selben Ordner) abgelegt. Beim allerersten
# Start existiert die Datei noch nicht - dann werden die Werte unten als
# Vorgabe verwendet und die Datei automatisch angelegt. Das Passwort wird
# NICHT im Klartext gespeichert, sondern nur als SHA-256-Hash - trotzdem ist
# das kein Ersatz fuer echtes Sicherheitskonzept (kein Salt, kein Rate-
# Limiting), sondern weiterhin nur fuer lokale/private Tools gedacht.
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin123"

CONFIG_PATH = Path(__file__).resolve().parent / "login_config.json"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def load_credentials() -> tuple[str, str]:
    """Liest (username, password_hash) aus login_config.json.
    Existiert die Datei nicht, wird sie mit den Standard-Zugangsdaten
    angelegt."""
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return data["username"], data["password_hash"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass  # Fallback: Datei neu anlegen

    save_credentials(DEFAULT_USERNAME, DEFAULT_PASSWORD)
    return DEFAULT_USERNAME, _hash_password(DEFAULT_PASSWORD)


def save_credentials(username: str, password: str) -> None:
    """Speichert Benutzername + gehashtes Passwort in login_config.json."""
    data = {"username": username, "password_hash": _hash_password(password)}
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


class GeneratedWindow(QMainWindow):
    """Mit Pandora® UI Forge entworfenes Fenster."""

    # Wird nach erfolgreicher Anmeldung ausgeloest, damit z.B. der
    # Script Editor darauf reagieren und sein Hauptfenster oeffnen kann.
    login_success = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pandora® | Login Page | by AKI_SystemDown® ©2026")
        self.resize(800, 600)
        self.init_ui()

    def init_ui(self) -> None:
        central_widget = QWidget()
        central_widget.setObjectName("central_widget")
        self.setCentralWidget(central_widget)
        self.setStyleSheet("""
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
""")

        self.frame_login = QFrame(central_widget)
        self.frame_login.setGeometry(145, 135, 400, 204)
        self.frame_login.setStyleSheet("border: 2px solid #3a2a55; border-radius: 16px;")
        self.frame_login_effect = QGraphicsDropShadowEffect()
        _color = QColor("#ff0000")
        _color.setAlpha(210)
        self.frame_login_effect.setColor(_color)
        self.frame_login_effect.setBlurRadius(60)
        self.frame_login_effect.setOffset(0, 0)
        self.frame_login.setGraphicsEffect(self.frame_login_effect)

        self.dialogbuttonbox_1 = QDialogButtonBox(central_widget)
        self.dialogbuttonbox_1.setStandardButtons(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.dialogbuttonbox_1.setGeometry(265, 275, 180, 35)
        self.dialogbuttonbox_1.setStyleSheet("border: 2px solid #3a2a55; border-radius: 16px; color: #ff0000;")
        self.dialogbuttonbox_1_effect = QGraphicsDropShadowEffect()
        _color = QColor("#ff0000")
        _color.setAlpha(210)
        self.dialogbuttonbox_1_effect.setColor(_color)
        self.dialogbuttonbox_1_effect.setBlurRadius(60)
        self.dialogbuttonbox_1_effect.setOffset(0, 0)
        self.dialogbuttonbox_1.setGraphicsEffect(self.dialogbuttonbox_1_effect)

        # OK prueft die Eingabe gegen die fest hinterlegten Zugangsdaten,
        # Cancel schliesst das Fenster ohne Pruefung.
        self.dialogbuttonbox_1.accepted.connect(self.handle_login)
        self.dialogbuttonbox_1.rejected.connect(self.close)

        self.lineedit_password_1 = QLineEdit(central_widget)
        self.lineedit_password_1.setGeometry(350, 225, 150, 35)
        self.lineedit_password_1.setEchoMode(QLineEdit.EchoMode.Password) 		# <-- Text maskieren
        self.lineedit_password_1.setStyleSheet("border: 2px solid #3a2a55; border-radius: 16px; color: #00e5ff;")
        self.lineedit_password_1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineedit_password_1_effect = QGraphicsDropShadowEffect()
        _color = QColor("#ff0000")
        _color.setAlpha(210)
        self.lineedit_password_1_effect.setColor(_color)
        self.lineedit_password_1_effect.setBlurRadius(60)
        self.lineedit_password_1_effect.setOffset(0, 0)
        self.lineedit_password_1.setGraphicsEffect(self.lineedit_password_1_effect)

        self.lineedit_1 = QLineEdit(central_widget)
        self.lineedit_1.setGeometry(350, 175, 150, 35)
        self.lineedit_1.setStyleSheet("border: 2px solid #3a2a55; border-radius: 16px; color: #00e5ff;")
        self.lineedit_1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lineedit_1_effect = QGraphicsDropShadowEffect()
        _color = QColor("#ff0000")
        _color.setAlpha(210)
        self.lineedit_1_effect.setColor(_color)
        self.lineedit_1_effect.setBlurRadius(60)
        self.lineedit_1_effect.setOffset(0, 0)
        self.lineedit_1.setGraphicsEffect(self.lineedit_1_effect)

        self.label_user = QLabel(central_widget)
        self.label_user.setText("Username")
        self.label_user.setGeometry(200, 175, 110, 35)
        self.label_user.setStyleSheet("border: 2px solid #3a2a55; border-radius: 16px; color: #ff0000; font-style: italic; text-decoration: underline;")
        self.label_user.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_user_effect = QGraphicsDropShadowEffect()
        _color = QColor("#ff0000")
        _color.setAlpha(210)
        self.label_user_effect.setColor(_color)
        self.label_user_effect.setBlurRadius(60)
        self.label_user_effect.setOffset(0, 0)
        self.label_user.setGraphicsEffect(self.label_user_effect)

        self.label_login = QLabel(central_widget)
        self.label_login.setText("Login")
        self.label_login.setGeometry(200, 110, 45, 35)
        self.label_login.setStyleSheet("border: 2px solid #3a2a55; border-radius: 16px; color: #ff0000; font-weight: bold;")
        self.label_login.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_login_effect = QGraphicsDropShadowEffect()
        _color = QColor("#ff0000")
        _color.setAlpha(210)
        self.label_login_effect.setColor(_color)
        self.label_login_effect.setBlurRadius(60)
        self.label_login_effect.setOffset(0, 0)
        self.label_login.setGraphicsEffect(self.label_login_effect)

        self.label_password = QLabel(central_widget)
        self.label_password.setText("Password")
        self.label_password.setGeometry(200, 225, 110, 35)
        self.label_password.setStyleSheet("border: 2px solid #3a2a55; border-radius: 16px; color: #ff0000; font-style: italic; text-decoration: underline;")
        self.label_password.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_password_effect = QGraphicsDropShadowEffect()
        _color = QColor("#ff0000")
        _color.setAlpha(210)
        self.label_password_effect.setColor(_color)
        self.label_password_effect.setBlurRadius(60)
        self.label_password_effect.setOffset(0, 0)
        self.label_password.setGraphicsEffect(self.label_password_effect)

        self.label_4 = QLabel(central_widget)
        self.label_4.setText("Pandora® | by AKI_SystemDown® ©2026")
        self.label_4.setGeometry(145, 340, 400, 20)
        self.label_4.setStyleSheet("border: 2px solid #3a2a55; border-radius: 8px; color: #ff0000; font-size: 10px; font-weight: bold; font-style: italic; text-decoration: underline;")
        self.label_4.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.label_4_effect = QGraphicsDropShadowEffect()
        _color = QColor("#ff0000")
        _color.setAlpha(210)
        self.label_4_effect.setColor(_color)
        self.label_4_effect.setBlurRadius(60)
        self.label_4_effect.setOffset(0, 0)
        self.label_4.setGraphicsEffect(self.label_4_effect)

    def handle_login(self) -> None:
        """Prueft die Eingaben gegen die in login_config.json hinterlegten
        Zugangsdaten (per load_credentials()). Bei Erfolg wird das Fenster
        geschlossen (Einstiegspunkt fuer den weiteren Programmablauf),
        bei Fehlschlag erscheint eine Fehlermeldung und die Felder
        werden geleert.

        Erweiterung: Statt sys.exit()/close() hier z.B. ein zweites
        Fenster oeffnen (self.next_window = MainApp(); self.next_window.show()),
        falls nach dem Login eine weitere Ansicht folgen soll.
        """
        username = self.lineedit_1.text()
        password = self.lineedit_password_1.text()

        valid_username, valid_password_hash = load_credentials()

        if username == valid_username and _hash_password(password) == valid_password_hash:
            QMessageBox.information(self, "Login erfolgreich", "<b><font color='#ff0000'>ACCESS GRANTED!</font></b>")
            self.login_success.emit()
            self.close()
        else:
            QMessageBox.critical(self, "Login fehlgeschlagen", "Username oder Passwort falsch.")
            self.lineedit_password_1.clear()
            self.lineedit_password_1.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratedWindow()
    window.show()
    sys.exit(app.exec())
