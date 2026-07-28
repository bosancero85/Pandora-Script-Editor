#!/usr/bin/env python3
"""
Pandora® | Crypto & Encoding Utility
Einstiegspunkt der Anwendung.

Läuft - analog zum SQL Config Editor & Web Editor - als eigenständiger
Prozess und wird vom Pandora Script Editor über Werkzeuge > Crypto & Encoding
Utility gestartet (siehe launch_crypto_tool() in pandora_script_editor.py).
"""

import os
import sys

# Sicherstellen, dass das eigene Verzeichnis auf dem Pfad liegt, damit
# `from core...` / `from ui...` unabhängig vom Aufrufkontext funktionieren
# (wichtig, wenn das Skript per subprocess mit anderem cwd gestartet wird).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from ui.main_window import run  # noqa: E402


if __name__ == "__main__":
    run()
