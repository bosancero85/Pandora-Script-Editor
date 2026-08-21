"""
Pandora® Environment & Dependency Manager - Package Installer (UI-frei).

Baut nur die Kommandozeilen-Argumente für pip- und npm-Operationen; die
tatsächliche Ausführung übernimmt die UI-Schicht über `QProcess`
(nicht-blockierend mit Live-Ausgabe, wichtig auf dem Raspberry Pi 4B, wo
`pip install` bei größeren Paketen spürbar dauern kann).

Kali Linux / Debian markieren die System-Python-Umgebung als "externally
managed" (PEP 668) - ein direkter `pip install` außerhalb einer venv
schlägt daher standardmäßig fehl. Für den bewussten Ausnahmefall (z.B.
System-Python ohne venv) gibt es die Option `allow_system_override`, die
`--break-system-packages` ergänzt.
"""

from __future__ import annotations

from dataclasses import dataclass


class PackageSpecError(ValueError):
    """Wird bei leeren oder ungültigen Paketlisten geworfen."""


@dataclass(frozen=True)
class PackageInfo:
    name: str
    version: str
    source: str  # "pip" oder "npm"
    dev: bool = False


def _clean_specs(raw: str) -> list[str]:
    """Zerlegt eine Freitext-Eingabe (Komma/Leerzeichen-getrennt) in Paketnamen."""

    tokens = raw.replace(",", " ").split()
    specs = [t.strip() for t in tokens if t.strip()]
    if not specs:
        raise PackageSpecError("Keine Paketnamen angegeben.")
    return specs


def build_pip_install_argv(
    python_executable: str,
    packages_raw: str,
    upgrade: bool = False,
    allow_system_override: bool = False,
) -> list[str]:
    specs = _clean_specs(packages_raw)
    cmd = [python_executable, "-m", "pip", "install"]
    if upgrade:
        cmd.append("--upgrade")
    if allow_system_override:
        cmd.append("--break-system-packages")
    cmd.extend(specs)
    return cmd


def build_pip_uninstall_argv(
    python_executable: str,
    packages_raw: str,
    allow_system_override: bool = False,
) -> list[str]:
    specs = _clean_specs(packages_raw)
    cmd = [python_executable, "-m", "pip", "uninstall", "-y"]
    if allow_system_override:
        cmd.append("--break-system-packages")
    cmd.extend(specs)
    return cmd


def build_pip_list_argv(python_executable: str) -> list[str]:
    return [python_executable, "-m", "pip", "list", "--format=json"]


def build_npm_install_argv(packages_raw: str, dev: bool = False) -> list[str]:
    specs = _clean_specs(packages_raw)
    cmd = ["npm", "install"]
    if dev:
        cmd.append("--save-dev")
    cmd.extend(specs)
    return cmd


def build_npm_uninstall_argv(packages_raw: str) -> list[str]:
    specs = _clean_specs(packages_raw)
    return ["npm", "uninstall", *specs]


def build_npm_list_argv(depth: int = 0) -> list[str]:
    return ["npm", "list", "--json", f"--depth={depth}"]


def parse_pip_list_json(raw_json: str) -> list[PackageInfo]:
    import json

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise PackageSpecError(f"Konnte pip-Ausgabe nicht parsen: {exc}") from exc

    return [
        PackageInfo(name=entry.get("name", "?"), version=entry.get("version", "?"), source="pip")
        for entry in data
    ]


def parse_npm_list_json(raw_json: str) -> list[PackageInfo]:
    import json

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise PackageSpecError(f"Konnte npm-Ausgabe nicht parsen: {exc}") from exc

    dependencies = data.get("dependencies", {}) or {}
    infos = []
    for name, meta in dependencies.items():
        version = meta.get("version", "?") if isinstance(meta, dict) else "?"
        infos.append(PackageInfo(name=name, version=version, source="npm"))
    return infos
