"""
Pandora® Crypto & Encoding Utility - Core: Hash & Checksum Generator.

Berechnet gängige Hash-/Checksummen-Werte (MD5, SHA-1, SHA-256, SHA-512)
sowie HMAC-Signaturen. Bewusst nur auf der Standardbibliothek `hashlib`/
`hmac` aufgebaut, damit das Tool ohne zusätzliche Abhängigkeiten läuft.

Hinweis: MD5/SHA-1 werden ausschließlich zu Kompatibilitäts- und
Prüfsummenzwecken (z.B. Datei-Integrität) angeboten, nicht als
kryptographisch sichere Wahl für neue Anwendungen - siehe Tooltip in der UI.
"""

from __future__ import annotations

import hashlib
import hmac as hmac_lib

# Reihenfolge/Namen der unterstützten Algorithmen (für Checkbox-Liste in UI).
ALGORITHMS = ["MD5", "SHA-1", "SHA-256", "SHA-512"]

_ALGO_MAP = {
    "MD5": "md5",
    "SHA-1": "sha1",
    "SHA-256": "sha256",
    "SHA-512": "sha512",
}


def compute_hash(algo: str, text: str, encoding: str = "utf-8") -> str:
    """Berechnet den Hexdigest von `text` für den angegebenen Algorithmus."""
    key = _ALGO_MAP.get(algo)
    if key is None:
        raise ValueError(f"Unbekannter Hash-Algorithmus: {algo}")
    digest = hashlib.new(key, text.encode(encoding))
    return digest.hexdigest()


def compute_all_hashes(text: str, algorithms=None, encoding: str = "utf-8") -> dict:
    """Berechnet mehrere Hashes auf einmal, z.B. für die Ergebnisliste in der UI."""
    algorithms = algorithms or ALGORITHMS
    return {algo: compute_hash(algo, text, encoding=encoding) for algo in algorithms}


def compute_hmac(algo: str, key: str, message: str, encoding: str = "utf-8") -> str:
    """Berechnet eine HMAC-Signatur (Hexdigest) für `message` mit `key`."""
    algo_key = _ALGO_MAP.get(algo)
    if algo_key is None:
        raise ValueError(f"Unbekannter HMAC-Algorithmus: {algo}")
    if not key:
        raise ValueError("HMAC benötigt einen Schlüssel (Key).")
    mac = hmac_lib.new(key.encode(encoding), message.encode(encoding), algo_key)
    return mac.hexdigest()


def verify_hmac(algo: str, key: str, message: str, expected_hex: str) -> bool:
    """Vergleicht eine erwartete HMAC-Hexsignatur zeitkonstant mit der
    tatsächlich berechneten - nützlich zur Validierung von Webhook-
    Signaturen o.ä."""
    actual_hex = compute_hmac(algo, key, message)
    return hmac_lib.compare_digest(actual_hex.lower(), expected_hex.strip().lower())
