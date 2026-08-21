# ⧉ Pandora Config Editor

Visueller JSON/YAML-Konfigurations-Editor & Validator mit dunklem Neon-("Pandora")-Theme,
gebaut mit PyQt6. Läuft flüssig auf einem Raspberry Pi 4B (8GB) unter Kali Linux.

## Features

- **Dynamisches Formular**: Aus jeder beliebig verschachtelten JSON/YAML-Datei werden
  automatisch passende Eingabefelder erzeugt — Textfelder, Zahlenfelder, Checkboxen,
  Dropdowns (bei Enum-Werten im Schema) sowie Listen-Editoren mit +/- Buttons.
- **Live-Vorschau**: Split-Screen rechts zeigt den aktuellen Stand als formatierten
  JSON- oder YAML-Code mit einfachem Syntax-Highlighting, in Echtzeit synchronisiert.
- **Schema-Validierung**: Wird ein JSON-Schema geladen, wird jede Änderung sofort
  gegen das Schema geprüft (`jsonschema`-Bibliothek). Ungültige Felder werden rot markiert.
- **Automatisches Backup**: Vor jedem Speichern wird eine Zeitstempel-Kopie der
  Originaldatei in einem versteckten Ordner `.pandora_backups/` neben der Datei abgelegt.
- **JSON ⇄ YAML**: Umschalten des Ausgabeformats über die Toolbar, unabhängig vom
  ursprünglichen Dateiformat.

## Installation auf dem Raspberry Pi 4B (Kali Linux)

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv

# (empfohlen) virtuelle Umgebung anlegen
python3 -m venv ~/pandora-env
source ~/pandora-env/bin/activate

pip install --break-system-packages PyQt6 PyYAML jsonschema
```

> Hinweis: PyQt6 muss ggf. als vorkompiliertes Wheel für ARM64 vorliegen.
> Falls die Installation über pip auf dem Pi sehr lange dauert oder fehlschlägt,
> alternativ über die Paketquellen installieren:
> ```bash
> sudo apt install -y python3-pyqt6
> ```

## Start

```bash
python3 pandora_config_editor.py                          # leer starten
python3 pandora_config_editor.py beispiel_config.json      # Datei direkt öffnen
python3 pandora_config_editor.py beispiel_config.json --schema beispiel_schema.json
```

## Bedienung

| Aktion              | Beschreibung                                                       |
|---------------------|---------------------------------------------------------------------|
| 📂 Öffnen           | JSON/YAML-Datei laden, Formular wird automatisch generiert          |
| 🧩 Schema laden     | Optionales JSON-Schema für Live-Validierung laden                   |
| ↺ Neu laden         | Aktuell geladene Datei erneut von der Platte einlesen (verwirft Änderungen) |
| JSON / YAML         | Ausgabeformat der Vorschau & beim Speichern umschalten               |
| ✔ Validieren        | Manuelle Vollvalidierung mit Detail-Fehlerliste                      |
| 💾 Speichern        | Erstellt zuerst ein Backup, validiert, schreibt dann die Datei       |

## Mitgelieferte Beispieldateien

- `beispiel_config.json` — Beispiel-Serverkonfiguration mit verschachtelten Objekten,
  einer einfachen Liste (`allowed_ips`) und einer Liste von Objekten (`users`).
- `beispiel_schema.json` — passendes JSON-Schema mit Typ-, Bereichs- und Enum-Regeln
  (z. B. `log_level` wird dadurch automatisch als Dropdown angezeigt).

## Hinweise zur Architektur

- `DynamicFormBuilder` baut rekursiv verschachtelte `QGroupBox`-Strukturen für jedes
  `dict`-Objekt auf.
- `ListEditor` verwaltet Arrays: Skalare Listen (Strings/Zahlen) und Listen aus Objekten
  werden beide unterstützt, inkl. Hinzufügen/Entfernen einzelner Einträge.
- `ScalarField` wählt automatisch das passende Widget (`QCheckBox` für bool,
  `QSpinBox`/`QDoubleSpinBox` für Zahlen, `QComboBox` bei `enum` im Schema, sonst `QLineEdit`).
- Validierung läuft bei jeder Änderung im Hintergrund (`Draft7Validator`), Fehler werden
  per Pfad auf das jeweilige Feld zurückgeführt und rot markiert.
- Performance: Für den Pi 4B wurde bewusst auf schwergewichtige Web-Views o.ä. verzichtet —
  reines natives Qt-Widget-Tree hält den RAM- und CPU-Verbrauch niedrig.
