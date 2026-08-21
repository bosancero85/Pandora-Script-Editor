"""
Pandora® Crypto & Encoding Utility - Core: JWT & Token Inspector.

Zerlegt JSON Web Tokens (Header/Payload/Signature) und kann - sofern der
Nutzer den Secret-Key kennt - HS256/HS384/HS512-Signaturen validieren.
Bewusst ohne PyJWT-Abhängigkeit implementiert (nur `base64`/`json`/`hmac`),
damit der Editor keine zusätzlichen Pakete benötigt.

Es werden ausschließlich HMAC-basierte Algorithmen (HS256/384/512)
unterstützt. RS/ES/PS-Algorithmen (asymmetrisch) werden erkannt und im
Header angezeigt, eine Signaturprüfung dafür wird aber bewusst NICHT
angeboten, da dafür öffentliche/private Schlüssel benötigt würden, die
hier den Rahmen sprengen.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac as hmac_lib
import json
from dataclasses import dataclass, field
from typing import Optional

_HMAC_ALGOS = {
    "HS256": "sha256",
    "HS384": "sha384",
    "HS512": "sha512",
}


@dataclass
class JwtParts:
    header: dict
    payload: dict
    signature: bytes
    header_b64: str
    payload_b64: str
    signature_b64: str
    is_hmac_algo: bool
    algorithm: Optional[str] = None
    warnings: list = field(default_factory=list)


def _b64url_decode(segment: str) -> bytes:
    padding = (-len(segment)) % 4
    try:
        return base64.urlsafe_b64decode(segment + "=" * padding)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"Ungültiges Base64URL-Segment: {exc}") from exc


def parse_jwt(token: str) -> JwtParts:
    """Zerlegt einen JWT-String in Header, Payload und Signatur, ohne die
    Signatur zu prüfen (reines Parsing/Debugging - wie z.B. jwt.io)."""
    token = token.strip()
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError(
            "Kein gültiges JWT-Format: es werden genau 3 Punkt-getrennte "
            "Segmente (Header.Payload.Signatur) erwartet."
        )
    header_b64, payload_b64, signature_b64 = parts

    header_raw = _b64url_decode(header_b64)
    payload_raw = _b64url_decode(payload_b64)
    try:
        signature = _b64url_decode(signature_b64) if signature_b64 else b""
    except ValueError:
        signature = b""

    try:
        header = json.loads(header_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Header ist kein gültiges JSON: {exc}") from exc
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Payload ist kein gültiges JSON: {exc}") from exc

    algorithm = header.get("alg")
    is_hmac = algorithm in _HMAC_ALGOS
    warnings = []
    if algorithm == "none":
        warnings.append(
            "Algorithmus 'none' - dieses Token ist unsigniert und sollte "
            "niemals als vertrauenswürdig behandelt werden."
        )
    elif algorithm and not is_hmac:
        warnings.append(
            f"Algorithmus '{algorithm}' ist asymmetrisch - eine lokale "
            "Signaturprüfung ohne Public Key ist hier nicht möglich."
        )
    elif not algorithm:
        warnings.append("Header enthält kein 'alg'-Feld.")

    return JwtParts(
        header=header,
        payload=payload,
        signature=signature,
        header_b64=header_b64,
        payload_b64=payload_b64,
        signature_b64=signature_b64,
        is_hmac_algo=is_hmac,
        algorithm=algorithm,
        warnings=warnings,
    )


def verify_hmac_signature(token: str, secret: str) -> bool:
    """Prüft die Signatur eines HS256/384/512-Tokens gegen den angegebenen
    Secret-Key. Wirft ValueError, wenn der Algorithmus nicht HMAC-basiert ist."""
    parts = parse_jwt(token)
    if not parts.is_hmac_algo:
        raise ValueError(
            f"Algorithmus '{parts.algorithm}' ist kein unterstützter "
            "HMAC-Algorithmus (erlaubt: HS256, HS384, HS512)."
        )
    digestmod = _HMAC_ALGOS[parts.algorithm]
    signing_input = f"{parts.header_b64}.{parts.payload_b64}".encode("ascii")
    expected_sig = hmac_lib.new(secret.encode("utf-8"), signing_input, digestmod).digest()
    return hmac_lib.compare_digest(expected_sig, parts.signature)


def pretty(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False)
