"""
Pandora® UI Asset & Color Studio - Farbkonvertierung (UI-frei).

Stellt reine Konvertierungsfunktionen zwischen den in PyQt6-Projekten
gebräuchlichen Farbdarstellungen bereit:

    HEX    "#00e5ff", "#ff2a6dcc" (mit Alpha)
    RGB    (r, g, b)
    RGBA   (r, g, b, a)          a im Bereich 0-255
    QColor-Code-Snippet          z.B. QColor(0, 229, 255)

Bewusst ohne Abhängigkeit von PyQt6, damit die Logik unabhängig von der
GUI getestet werden kann. Die UI-Schicht (ui/main_window.py) übernimmt
die Übersetzung zu/von echten QColor-Instanzen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


class ColorParseError(ValueError):
    """Wird geworfen, wenn ein Farbwert nicht geparst werden kann."""


_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


@dataclass(frozen=True)
class RGBA:
    """Farbwert als RGBA-Tupel (0-255 je Kanal)."""

    r: int
    g: int
    b: int
    a: int = 255

    def clamped(self) -> "RGBA":
        def c(v: int) -> int:
            return max(0, min(255, v))

        return RGBA(c(self.r), c(self.g), c(self.b), c(self.a))


def parse_hex(value: str) -> RGBA:
    """Parst einen HEX-String (#RGB, #RRGGBB oder #RRGGBBAA) zu RGBA."""

    match = _HEX_RE.match(value.strip())
    if not match:
        raise ColorParseError(f"Ungültiger HEX-Wert: {value!r}")

    digits = match.group(1)
    if len(digits) == 3:
        r, g, b = (int(ch * 2, 16) for ch in digits)
        return RGBA(r, g, b, 255)
    if len(digits) == 6:
        r, g, b = (int(digits[i : i + 2], 16) for i in (0, 2, 4))
        return RGBA(r, g, b, 255)
    # 8 Zeichen -> inkl. Alpha
    r, g, b, a = (int(digits[i : i + 2], 16) for i in (0, 2, 4, 6))
    return RGBA(r, g, b, a)


def to_hex(color: RGBA, include_alpha: bool = False) -> str:
    """Formatiert RGBA als HEX-String (#RRGGBB oder #RRGGBBAA)."""

    c = color.clamped()
    base = f"#{c.r:02x}{c.g:02x}{c.b:02x}"
    if include_alpha:
        return f"{base}{c.a:02x}"
    return base


def to_rgb_tuple(color: RGBA) -> tuple[int, int, int]:
    c = color.clamped()
    return (c.r, c.g, c.b)


def to_rgba_tuple(color: RGBA) -> tuple[int, int, int, int]:
    c = color.clamped()
    return (c.r, c.g, c.b, c.a)


def to_css_rgb(color: RGBA) -> str:
    c = color.clamped()
    return f"rgb({c.r}, {c.g}, {c.b})"


def to_css_rgba(color: RGBA) -> str:
    c = color.clamped()
    return f"rgba({c.r}, {c.g}, {c.b}, {round(c.a / 255, 3)})"


def to_qcolor_snippet(color: RGBA, include_alpha: bool = False) -> str:
    """Erzeugt ein einfügbares `QColor(...)`-Code-Snippet."""

    c = color.clamped()
    if include_alpha:
        return f"QColor({c.r}, {c.g}, {c.b}, {c.a})"
    return f"QColor({c.r}, {c.g}, {c.b})"


def parse_rgb_string(value: str) -> RGBA:
    """Parst 'r, g, b' oder 'r, g, b, a' (auch mit rgb()/rgba()-Hülle)."""

    cleaned = value.strip()
    cleaned = re.sub(r"^(rgba?|RGBA?)\s*\(", "", cleaned)
    cleaned = cleaned.rstrip(")")
    parts = [p.strip() for p in cleaned.split(",") if p.strip() != ""]

    if len(parts) not in (3, 4):
        raise ColorParseError(f"Ungültiger RGB(A)-Wert: {value!r}")

    try:
        nums = [float(p) for p in parts]
    except ValueError as exc:
        raise ColorParseError(f"Ungültiger RGB(A)-Wert: {value!r}") from exc

    r, g, b = (int(round(n)) for n in nums[:3])
    if len(nums) == 4:
        a_raw = nums[3]
        # Alpha kann als 0-1 (CSS rgba) oder 0-255 angegeben sein.
        a = int(round(a_raw * 255)) if 0 <= a_raw <= 1 else int(round(a_raw))
    else:
        a = 255

    return RGBA(r, g, b, a).clamped()


def relative_luminance(color: RGBA) -> float:
    """Relative Luminanz nach WCAG, nützlich für Kontrast-/Lesbarkeitschecks."""

    def channel(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    c = color.clamped()
    r, g, b = channel(c.r), channel(c.g), channel(c.b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: RGBA, b: RGBA) -> float:
    """WCAG-Kontrastverhältnis zweier Farben (1.0 - 21.0)."""

    l1 = relative_luminance(a) + 0.05
    l2 = relative_luminance(b) + 0.05
    return round(max(l1, l2) / min(l1, l2), 2)


def readable_text_color(background: RGBA) -> RGBA:
    """Liefert Schwarz oder Weiß, je nachdem was auf `background` lesbarer ist."""

    black = RGBA(0, 0, 0, 255)
    white = RGBA(255, 255, 255, 255)
    return white if contrast_ratio(background, black) < contrast_ratio(background, white) else black
