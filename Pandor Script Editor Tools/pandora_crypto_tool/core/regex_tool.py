"""
Pandora® Crypto & Encoding Utility - Core: RegEx & Pattern Tester.

Kompiliert einen regulären Ausdruck (Python-`re`-Dialekt) und wendet ihn
auf einen Test-String an - inkl. Gruppen, Spans und optionalem
Ersetzungs-Modus. Gedacht als Unterstützung bei der YARA-/Skript-
Entwicklung (YARA-Regex-Strings folgen weitgehend PCRE-artiger Syntax,
die sich mit Pythons `re` meist gut genug voranalysieren lässt).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# Auswahl der in der UI als Checkboxen angebotenen Flags.
FLAG_OPTIONS = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
    "VERBOSE": re.VERBOSE,
}


@dataclass
class MatchResult:
    index: int
    start: int
    end: int
    text: str
    groups: tuple
    named_groups: dict


@dataclass
class RegexTestResult:
    matches: list = field(default_factory=list)
    match_count: int = 0
    error: Optional[str] = None


def build_flags(selected: list) -> int:
    flags = 0
    for name in selected:
        flags |= FLAG_OPTIONS.get(name, 0)
    return flags


def test_pattern(pattern: str, test_string: str, flag_names=None) -> RegexTestResult:
    """Wendet `pattern` auf `test_string` an und liefert alle Treffer inkl.
    Gruppen. Fehler (z.B. ungültige Regex-Syntax) werden im Ergebnis-Objekt
    zurückgegeben statt eine Exception zu werfen, damit die UI sie einfach
    inline anzeigen kann."""
    if not pattern:
        return RegexTestResult(error="Kein Muster (Pattern) angegeben.")

    flags = build_flags(flag_names or [])
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        return RegexTestResult(error=f"Ungültiger regulärer Ausdruck: {exc}")

    results = []
    try:
        for i, m in enumerate(compiled.finditer(test_string)):
            results.append(
                MatchResult(
                    index=i,
                    start=m.start(),
                    end=m.end(),
                    text=m.group(0),
                    groups=m.groups(),
                    named_groups=m.groupdict(),
                )
            )
    except re.error as exc:  # pragma: no cover - defensive (z.B. catastrophic backtracking Guards)
        return RegexTestResult(error=f"Fehler bei der Auswertung: {exc}")

    return RegexTestResult(matches=results, match_count=len(results))


def substitute(pattern: str, replacement: str, test_string: str, flag_names=None, count: int = 0):
    """Führt re.sub aus und gibt (ergebnis, anzahl_ersetzungen, fehler) zurück."""
    if not pattern:
        return None, 0, "Kein Muster (Pattern) angegeben."
    flags = build_flags(flag_names or [])
    try:
        compiled = re.compile(pattern, flags)
        result, n = compiled.subn(replacement, test_string, count=count)
        return result, n, None
    except re.error as exc:
        return None, 0, f"Ungültiger regulärer Ausdruck: {exc}"
