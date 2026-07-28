"""
Pandora® Environment & Dependency Manager - Virtualenv-Verwaltung (UI-frei).

Zielplattform primär Raspberry Pi 4B (8GB RAM) unter Kali Linux, daher:
  - venv-Erstellung läuft synchron über `subprocess.run` (dauert i.d.R. nur
    wenige Sekunden, auch auf dem Pi) statt asynchron über QProcess.
  - Pfade werden POSIX-typisch behandelt (bin/ statt Scripts/), Windows
    bleibt als Fallback unterstützt, da Aki gelegentlich auch dorthin baut.

Enthält keine Qt-Importe, damit die Logik unabhängig testbar bleibt. Die
UI-Schicht (ui/main_window.py) ruft diese Funktionen auf und stellt die
Ergebnisse dar.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_VENV_ROOT = Path.home() / "pandora_venvs"


class VenvError(RuntimeError):
    """Wird bei ungültigen oder fehlgeschlagenen venv-Operationen geworfen."""


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass(frozen=True)
class VenvInfo:
    path: Path
    python_version: str
    size_bytes: int

    @property
    def name(self) -> str:
        return self.path.name


def is_valid_venv(path: str | Path) -> bool:
    """Prüft, ob `path` eine gültige venv ist (anhand von pyvenv.cfg)."""

    return (Path(path) / "pyvenv.cfg").is_file()


def venv_python_executable(venv_path: str | Path) -> Path:
    """Liefert den Pfad zum Python-Interpreter innerhalb der venv."""

    root = Path(venv_path)
    if sys.platform.startswith("win"):
        candidate = root / "Scripts" / "python.exe"
    else:
        candidate = root / "bin" / "python"
    return candidate


def venv_pip_executable(venv_path: str | Path) -> Path:
    root = Path(venv_path)
    if sys.platform.startswith("win"):
        return root / "Scripts" / "pip.exe"
    return root / "bin" / "pip"


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                continue
    return total


def read_venv_info(venv_path: str | Path) -> VenvInfo:
    root = Path(venv_path)
    if not is_valid_venv(root):
        raise VenvError(f"Kein gültiges venv-Verzeichnis: {venv_path!r}")

    version = "unbekannt"
    cfg_file = root / "pyvenv.cfg"
    for line in cfg_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip().lower().startswith("version"):
            version = line.split("=", 1)[1].strip()
            break

    return VenvInfo(path=root, python_version=version, size_bytes=_dir_size_bytes(root))


def discover_venvs(root: str | Path) -> list[VenvInfo]:
    """Sucht direkte Unterverzeichnisse von `root`, die gültige venvs sind."""

    base = Path(root)
    if not base.is_dir():
        return []

    infos = []
    for entry in sorted(base.iterdir()):
        if entry.is_dir() and is_valid_venv(entry):
            try:
                infos.append(read_venv_info(entry))
            except VenvError:
                continue
    return infos


def create_venv(
    path: str | Path,
    python_executable: str = "python3",
    system_site_packages: bool = False,
) -> CommandResult:
    """Erstellt eine neue venv unter `path` via `python3 -m venv`."""

    target = Path(path)
    if target.exists() and any(target.iterdir()):
        raise VenvError(f"Zielverzeichnis existiert bereits und ist nicht leer: {path!r}")

    target.parent.mkdir(parents=True, exist_ok=True)

    cmd = [python_executable, "-m", "venv", str(target)]
    if system_site_packages:
        cmd.append("--system-site-packages")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    return CommandResult(proc.returncode, proc.stdout, proc.stderr)


def delete_venv(path: str | Path) -> None:
    root = Path(path)
    if not is_valid_venv(root):
        raise VenvError(f"Kein gültiges venv-Verzeichnis, Löschen abgebrochen: {path!r}")
    shutil.rmtree(root)


def human_readable_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
