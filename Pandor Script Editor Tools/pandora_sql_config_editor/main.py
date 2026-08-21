#!/usr/bin/env python3
"""
Pandora® | SQL Config Editor & Validator
Einstiegspunkt der Anwendung.
"""

import sys
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Pandora SQL Config Editor & Validator")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
