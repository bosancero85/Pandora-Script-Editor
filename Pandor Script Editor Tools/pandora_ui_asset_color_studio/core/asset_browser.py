"""
Pandora® UI Asset & Color Studio - Icon & Asset Browser (UI-frei).

Durchsucht ein Verzeichnis nach Bild-/Icon-Dateien und erzeugt daraus
Base64-Strings sowie fertige Code-Snippets zum direkten Einbetten in
Python/PyQt6-Quellcode (z.B. als `QPixmap` aus Base64 oder als Data-URI
für Web-Tools wie den Pandora Web Editor).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".ico", ".bmp", ".gif", ".webp"}

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


class AssetError(ValueError):
    """Wird bei ungültigen Asset-Operationen geworfen."""


@dataclass(frozen=True)
class AssetEntry:
    path: Path
    size_bytes: int

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def suffix(self) -> str:
        return self.path.suffix.lower()

    @property
    def mime_type(self) -> str:
        return _MIME_BY_SUFFIX.get(self.suffix, "application/octet-stream")


def scan_directory(directory: str | Path, recursive: bool = True) -> list[AssetEntry]:
    """Listet alle unterstützten Bild-/Icon-Dateien in `directory` auf."""

    root = Path(directory)
    if not root.is_dir():
        raise AssetError(f"Kein gültiges Verzeichnis: {directory!r}")

    pattern = "**/*" if recursive else "*"
    entries = []
    for path in sorted(root.glob(pattern)):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            entries.append(AssetEntry(path=path, size_bytes=path.stat().st_size))
    return entries


def to_base64(path: str | Path) -> str:
    """Liest eine Datei ein und liefert den reinen Base64-String (ohne Prefix)."""

    file_path = Path(path)
    if not file_path.is_file():
        raise AssetError(f"Datei nicht gefunden: {path!r}")
    return base64.b64encode(file_path.read_bytes()).decode("ascii")


def to_data_uri(path: str | Path) -> str:
    """Liefert einen vollständigen `data:`-URI, z.B. für HTML/CSS/Web Editor."""

    file_path = Path(path)
    mime = _MIME_BY_SUFFIX.get(file_path.suffix.lower(), "application/octet-stream")
    encoded = to_base64(file_path)
    return f"data:{mime};base64,{encoded}"


def to_python_qpixmap_snippet(path: str | Path, variable_name: str = "ICON_DATA") -> str:
    """Erzeugt ein Code-Snippet, das ein QPixmap direkt aus Base64 lädt."""

    encoded = to_base64(path)
    file_path = Path(path)
    wrapped = _wrap_base64(encoded)
    return (
        f"# {file_path.name} als Base64 eingebettet (kein externer Datei-Zugriff nötig)\n"
        f"{variable_name} = (\n{wrapped}\n)\n\n"
        "from PyQt6.QtCore import QByteArray\n"
        "from PyQt6.QtGui import QPixmap\n\n"
        f"pixmap = QPixmap()\n"
        f"pixmap.loadFromData(QByteArray.fromBase64({variable_name}.encode('ascii')))"
    )


def _wrap_base64(encoded: str, width: int = 92) -> str:
    lines = [encoded[i : i + width] for i in range(0, len(encoded), width)]
    return "\n".join(f'    b"{chunk}"' for chunk in lines)


def human_readable_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
