"""
Pandora® Environment & Dependency Manager - Abhängigkeits-Übersicht (UI-frei).

Nimmt die von `package_installer.parse_pip_list_json` /
`parse_npm_list_json` gelieferten `PackageInfo`-Listen entgegen und bietet
Filter-, Sortier- und Export-Hilfsfunktionen (z.B. für `requirements.txt`).
"""

from __future__ import annotations

from core.package_installer import PackageInfo


def filter_packages(packages: list[PackageInfo], query: str) -> list[PackageInfo]:
    """Filtert Pakete anhand eines Namens-Teilstrings (case-insensitive)."""

    q = query.strip().lower()
    if not q:
        return list(packages)
    return [p for p in packages if q in p.name.lower()]


def sort_packages(packages: list[PackageInfo], by: str = "name") -> list[PackageInfo]:
    key = (lambda p: p.name.lower()) if by == "name" else (lambda p: p.version.lower())
    return sorted(packages, key=key)


def find_duplicates_across(
    pip_packages: list[PackageInfo], npm_packages: list[PackageInfo]
) -> list[tuple[str, str, str]]:
    """Findet Paketnamen, die (zufällig) sowohl bei pip als auch npm auftauchen.

    Nützlich als grober Hinweis auf Namensüberschneidungen zwischen
    Python- und Node-Abhängigkeiten in einem gemischten Projekt.
    """

    npm_by_name = {p.name.lower(): p.version for p in npm_packages}
    result = []
    for p in pip_packages:
        key = p.name.lower()
        if key in npm_by_name:
            result.append((p.name, p.version, npm_by_name[key]))
    return result


def to_requirements_txt(packages: list[PackageInfo]) -> str:
    """Formatiert pip-Pakete als `requirements.txt`-Inhalt (name==version)."""

    lines = [f"{p.name}=={p.version}" for p in sort_packages(packages, by="name")]
    return "\n".join(lines) + ("\n" if lines else "")


def to_package_json_dependencies_snippet(packages: list[PackageInfo]) -> str:
    """Formatiert npm-Pakete als einfügbaren `dependencies`-Block für package.json."""

    entries = sort_packages(packages, by="name")
    lines = ['"dependencies": {']
    for i, p in enumerate(entries):
        comma = "," if i < len(entries) - 1 else ""
        lines.append(f'  "{p.name}": "^{p.version}"{comma}')
    lines.append("}")
    return "\n".join(lines)
