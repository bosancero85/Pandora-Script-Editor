"""
Pandora® Crypto & Encoding Utility - Core: Multi-Format Encoder/Decoder.

Reine, UI-freie Konvertierungsfunktionen für Base64, Hex, URL-Encoding,
HTML-Entities und Binärdaten. Jede Funktion wirft bei ungültiger Eingabe
eine ValueError mit einer verständlichen, deutschsprachigen Meldung, damit
die UI-Schicht die Fehlermeldung direkt anzeigen kann.
"""

from __future__ import annotations

import base64
import binascii
import html
import urllib.parse

# Reihenfolge/Namen der unterstützten Formate (für Combo-Boxen in der UI).
FORMATS = ["Base64", "Hex", "URL-Encoding", "HTML-Entities", "Binär (8-Bit)"]


def _text_to_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def _bytes_to_text(data: bytes) -> str:
    # Encoder-Ausgabe soll immer darstellbar sein - Decoder-Ausgabe kann bei
    # Bedarf auch Nicht-UTF8 enthalten, dann greift der Fallback.
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


# ---------------------------------------------------------------------
# Base64
# ---------------------------------------------------------------------
def encode_base64(text: str, url_safe: bool = False) -> str:
    data = _text_to_bytes(text)
    encoded = base64.urlsafe_b64encode(data) if url_safe else base64.b64encode(data)
    return encoded.decode("ascii")


def decode_base64(text: str, url_safe: bool = False) -> str:
    cleaned = "".join(text.split())
    # Padding automatisch ergänzen, das erspart dem Nutzer Handarbeit.
    padding = (-len(cleaned)) % 4
    cleaned += "=" * padding
    try:
        data = (
            base64.urlsafe_b64decode(cleaned)
            if url_safe
            else base64.b64decode(cleaned, validate=False)
        )
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Ungültige Base64-Eingabe: {exc}") from exc
    return _bytes_to_text(data)


# ---------------------------------------------------------------------
# Hex
# ---------------------------------------------------------------------
def encode_hex(text: str, uppercase: bool = False, spaced: bool = False) -> str:
    data = _text_to_bytes(text)
    hex_str = data.hex()
    if uppercase:
        hex_str = hex_str.upper()
    if spaced:
        hex_str = " ".join(hex_str[i : i + 2] for i in range(0, len(hex_str), 2))
    return hex_str


def decode_hex(text: str) -> str:
    cleaned = "".join(text.split()).replace("0x", "").replace(",", "")
    try:
        data = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise ValueError(f"Ungültige Hex-Eingabe: {exc}") from exc
    return _bytes_to_text(data)


# ---------------------------------------------------------------------
# URL-Encoding
# ---------------------------------------------------------------------
def encode_url(text: str, encode_plus: bool = False) -> str:
    if encode_plus:
        return urllib.parse.quote_plus(text)
    return urllib.parse.quote(text, safe="")


def decode_url(text: str, encode_plus: bool = False) -> str:
    try:
        if encode_plus:
            return urllib.parse.unquote_plus(text)
        return urllib.parse.unquote(text, errors="strict")
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Ungültige URL-Kodierung: {exc}") from exc


# ---------------------------------------------------------------------
# HTML-Entities
# ---------------------------------------------------------------------
def encode_html_entities(text: str, quote: bool = True) -> str:
    return html.escape(text, quote=quote)


def decode_html_entities(text: str) -> str:
    return html.unescape(text)


# ---------------------------------------------------------------------
# Binärdaten (8-Bit je Zeichen)
# ---------------------------------------------------------------------
def encode_binary(text: str, spaced: bool = True) -> str:
    data = _text_to_bytes(text)
    parts = [format(byte, "08b") for byte in data]
    return " ".join(parts) if spaced else "".join(parts)


def decode_binary(text: str) -> str:
    cleaned = "".join(text.split())
    if len(cleaned) % 8 != 0 or not set(cleaned) <= {"0", "1"}:
        raise ValueError(
            "Ungültige Binär-Eingabe: erwartet werden nur 0/1 in 8er-Blöcken."
        )
    try:
        data = bytes(int(cleaned[i : i + 8], 2) for i in range(0, len(cleaned), 8))
    except ValueError as exc:
        raise ValueError(f"Ungültige Binär-Eingabe: {exc}") from exc
    return _bytes_to_text(data)


# ---------------------------------------------------------------------
# Dispatcher, den die UI-Schicht anhand des gewählten Formats aufruft.
# ---------------------------------------------------------------------
def encode(fmt: str, text: str, **options) -> str:
    if fmt == "Base64":
        return encode_base64(text, url_safe=options.get("url_safe", False))
    if fmt == "Hex":
        return encode_hex(
            text,
            uppercase=options.get("uppercase", False),
            spaced=options.get("spaced", False),
        )
    if fmt == "URL-Encoding":
        return encode_url(text, encode_plus=options.get("encode_plus", False))
    if fmt == "HTML-Entities":
        return encode_html_entities(text, quote=options.get("quote", True))
    if fmt == "Binär (8-Bit)":
        return encode_binary(text, spaced=options.get("spaced", True))
    raise ValueError(f"Unbekanntes Format: {fmt}")


def decode(fmt: str, text: str, **options) -> str:
    if fmt == "Base64":
        return decode_base64(text, url_safe=options.get("url_safe", False))
    if fmt == "Hex":
        return decode_hex(text)
    if fmt == "URL-Encoding":
        return decode_url(text, encode_plus=options.get("encode_plus", False))
    if fmt == "HTML-Entities":
        return decode_html_entities(text)
    if fmt == "Binär (8-Bit)":
        return decode_binary(text)
    raise ValueError(f"Unbekanntes Format: {fmt}")
