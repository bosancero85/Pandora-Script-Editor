"""
Pandora® UI Asset & Color Studio - Theming-Variablen-Manager (UI-frei).

Verwaltet benannte Farb-Variablen (z.B. "bg.base", "accent.cyan",
"accent.pink") in Paletten, die als JSON persistiert werden. Damit lassen
sich Farbpaletten zentral pflegen und als QSS-Variablen-Dict in andere
Pandora-Tools exportieren.

Standardpalette entspricht der bereits in den anderen Pandora-Werkzeugen
(Crypto Utility, SQL Config Editor) verwendeten Cyberpunk-Dark-Palette.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PALETTE_NAME = "Pandora Cyberpunk (Standard)"

DEFAULT_VARIABLES: dict[str, str] = {
    "bg.base": "#0a0e14",
    "bg.panel": "#10161f",
    "bg.panel_alt": "#16202c",
    "border.default": "#1d2a38",
    "text.default": "#d8f7ff",
    "text.muted": "#6b7a8f",
    "accent.cyan": "#00e5ff",
    "accent.pink": "#ff2a6d",
    "accent.success": "#37ffb0",
    "accent.warning": "#ff2a6d",
}

_DEFAULT_STORE_PATH = Path.home() / ".pandora_ui_asset_color_studio_themes.json"


class ThemeError(ValueError):
    """Wird bei ungültigen Palettenoperationen geworfen."""


@dataclass
class Palette:
    name: str
    variables: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"name": self.name, "variables": dict(self.variables)}

    @staticmethod
    def from_dict(data: dict) -> "Palette":
        return Palette(name=data.get("name", "Unbenannt"), variables=dict(data.get("variables", {})))


class ThemeStore:
    """Verwaltet mehrere benannte Paletten in einer JSON-Datei."""

    def __init__(self, store_path: Path | None = None):
        self.store_path = store_path or _DEFAULT_STORE_PATH
        self.palettes: dict[str, Palette] = {}
        self._load_or_seed()

    # -- Persistenz ---------------------------------------------------

    def _load_or_seed(self) -> None:
        if self.store_path.exists():
            try:
                raw = json.loads(self.store_path.read_text(encoding="utf-8"))
                self.palettes = {
                    p["name"]: Palette.from_dict(p) for p in raw.get("palettes", [])
                }
            except (json.JSONDecodeError, OSError):
                self.palettes = {}

        if not self.palettes:
            self.palettes[DEFAULT_PALETTE_NAME] = Palette(
                name=DEFAULT_PALETTE_NAME, variables=dict(DEFAULT_VARIABLES)
            )
            self.save()

    def save(self) -> None:
        payload = {"palettes": [p.to_dict() for p in self.palettes.values()]}
        self.store_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # -- Palettenverwaltung --------------------------------------------

    def list_palette_names(self) -> list[str]:
        return sorted(self.palettes.keys())

    def get(self, name: str) -> Palette:
        if name not in self.palettes:
            raise ThemeError(f"Palette nicht gefunden: {name!r}")
        return self.palettes[name]

    def create_palette(self, name: str, base_on: str | None = None) -> Palette:
        if not name.strip():
            raise ThemeError("Palettenname darf nicht leer sein.")
        if name in self.palettes:
            raise ThemeError(f"Palette existiert bereits: {name!r}")

        variables = dict(self.palettes[base_on].variables) if base_on else dict(DEFAULT_VARIABLES)
        palette = Palette(name=name, variables=variables)
        self.palettes[name] = palette
        self.save()
        return palette

    def delete_palette(self, name: str) -> None:
        if name not in self.palettes:
            raise ThemeError(f"Palette nicht gefunden: {name!r}")
        if len(self.palettes) == 1:
            raise ThemeError("Die letzte verbleibende Palette kann nicht gelöscht werden.")
        del self.palettes[name]
        self.save()

    def rename_palette(self, old_name: str, new_name: str) -> None:
        if old_name not in self.palettes:
            raise ThemeError(f"Palette nicht gefunden: {old_name!r}")
        if not new_name.strip():
            raise ThemeError("Neuer Palettenname darf nicht leer sein.")
        if new_name in self.palettes:
            raise ThemeError(f"Palette existiert bereits: {new_name!r}")

        palette = self.palettes.pop(old_name)
        palette.name = new_name
        self.palettes[new_name] = palette
        self.save()

    def set_variable(self, palette_name: str, key: str, hex_value: str) -> None:
        palette = self.get(palette_name)
        if not key.strip():
            raise ThemeError("Variablenname darf nicht leer sein.")
        palette.variables[key.strip()] = hex_value
        self.save()

    def remove_variable(self, palette_name: str, key: str) -> None:
        palette = self.get(palette_name)
        palette.variables.pop(key, None)
        self.save()

    # -- Export ----------------------------------------------------------

    def export_as_python_dict(self, palette_name: str) -> str:
        """Exportiert die Palette als einfügbares Python-Dict-Literal."""

        palette = self.get(palette_name)
        lines = ["PANDORA_THEME = {"]
        for key, value in sorted(palette.variables.items()):
            lines.append(f'    "{key}": "{value}",')
        lines.append("}")
        return "\n".join(lines)

    def export_as_qss_snippet(self, palette_name: str) -> str:
        """Exportiert die Palette als kommentierte QSS-Variablenübersicht.

        Qt-QSS kennt keine echten Variablen; das Snippet dient als
        Kopiervorlage, die die Werte direkt an den passenden Stellen im
        bestehenden PANDORA_QSS-Stylesheet der anderen Tools einsetzt.
        """

        palette = self.get(palette_name)
        lines = [f"/* Pandora-Theme-Variablen: {palette.name} */"]
        for key, value in sorted(palette.variables.items()):
            lines.append(f"/* {key} */ {value}")
        return "\n".join(lines)
