"""
Schema-Validierung für den Pandora SQL Config Editor.
Prüft Eingabewerte gegen den normalisierten Spaltentyp und liefert
sofortige, feldbezogene Fehlermeldungen für die UI.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def validate_value(raw_text: str, data_type: str, nullable: bool) -> tuple[bool, Optional[str], Any]:
    """
    Validiert einen rohen (String-)Eingabewert gegen den Spaltentyp.
    Gibt zurück: (ist_gueltig, fehlermeldung_oder_None, konvertierter_wert)
    """
    text = raw_text.strip() if raw_text is not None else ""

    if text == "":
        if nullable:
            return True, None, None
        return False, "Pflichtfeld darf nicht leer sein.", None

    if data_type == "INTEGER":
        try:
            return True, None, int(text)
        except ValueError:
            return False, "Erwartet eine Ganzzahl.", None

    if data_type == "REAL":
        try:
            return True, None, float(text.replace(",", "."))
        except ValueError:
            return False, "Erwartet eine Kommazahl.", None

    if data_type == "BOOLEAN":
        if text.lower() in ("1", "0", "true", "false", "ja", "nein"):
            val = text.lower() in ("1", "true", "ja")
            return True, None, val
        return False, "Erwartet einen Wahrheitswert (true/false, 1/0).", None

    if data_type == "DATE":
        if DATE_RE.match(text):
            try:
                datetime.strptime(text, "%Y-%m-%d")
                return True, None, text
            except ValueError:
                return False, "Ungültiges Datum.", None
        return False, "Format muss JJJJ-MM-TT sein.", None

    if data_type == "DATETIME":
        if DATETIME_RE.match(text.replace("T", " ")):
            return True, None, text
        return False, "Format muss JJJJ-MM-TT HH:MM[:SS] sein.", None

    if data_type == "BLOB":
        return True, None, text

    # TEXT / Fallback
    return True, None, text


def validate_row(values: dict[str, str], columns: list) -> dict[str, tuple[bool, Optional[str], Any]]:
    """
    Validiert alle Felder einer Zeile.
    columns: Liste von ColumnInfo-Objekten (aus db_manager).
    Rückgabe: dict spaltenname -> (gueltig, fehlermeldung, konvertierter_wert)
    """
    results = {}
    for col in columns:
        raw = values.get(col.name, "")
        results[col.name] = validate_value(raw, col.data_type, col.nullable)
    return results
