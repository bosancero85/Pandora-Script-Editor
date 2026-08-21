#!/usr/bin/env python3
"""
Pandora® | Environment & Dependency Manager
Einstiegspunkt der Anwendung.

Läuft - analog zu den anderen Pandora-Werkzeugen (Crypto Utility, SQL
Config Editor, UI Asset & Color Studio) - als eigenständiger Prozess und
wird vom Pandora Script Editor über Werkzeuge > Environment & Dependency
Manager gestartet.
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
