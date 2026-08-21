# Pandora® | SQL Config Editor & Validator

Vollständiger visueller Datenbankeditor für SQLite- und MariaDB-Datenbanken:
dynamisch generierte Formulare (inkl. Fremdschlüssel-Dropdowns), Live-SQL-
Vorschau, Schema-Validierung, Paginierung, Volltextsuche, Sortierung,
Tabellen-/Spaltenverwaltung, CSV-Import/-Export und automatisches Backup vor
jedem Schreibvorgang. Läuft auf Raspberry Pi 4B (8GB) unter Kali Linux, im
Pandora®-Cyberpunk-Stil.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Für MariaDB-Backups zusätzlich `mariadb-client` installieren (liefert `mysqldump`):

```bash
sudo apt install mariadb-client
```

## Start

```bash
python3 main.py
```

## Funktionsübersicht

### Verbindung & Datei
- **Backend-Erkennung**: Beim Start wird geprüft, ob lokal ein MariaDB/MySQL-Server
  läuft (Port 3306 + systemd-Status). Der Status erscheint in der Statuszeile.
- **Menüleiste „Datei“** + Toolbar: SQLite öffnen (Strg+O), Mit MariaDB
  verbinden (Strg+Umschalt+O), Speichern (Strg+S), Speichern unter…
  (Strg+Umschalt+S, Kopie bzw. Dump), Backup jetzt, Neu laden (F5).

### Daten ansehen & bearbeiten
- **Tabellenliste**: Klick lädt Schema + erste Seite der Daten.
- **Paginierung**: Seitenweise Navigation (25/50/100/250/500 Zeilen pro Seite)
  statt starrem Limit – auch bei sehr großen Tabellen performant.
- **Volltextsuche**: Suchfeld filtert über alle Spalten der aktuellen Tabelle.
- **Sortierung**: Klick auf eine Spaltenüberschrift sortiert auf-/absteigend.
- **Dynamisches Formular**: Für jede Spalte automatisch das passende Feld.
  **Fremdschlüssel werden als Dropdown mit „ID — Anzeigename“ dargestellt**
  (z. B. `posts.topic_id` → Auswahl aus `topics.name`), keine rohen IDs mehr.
- **Live-SQL-Vorschau**: Zeigt in Echtzeit das INSERT/UPDATE-Statement.
- **Sofortige Fehlermarkierung**: Ungültige Eingaben werden rot markiert,
  „Speichern“ bleibt so lange deaktiviert.
- **Neue Zeile / Zeile löschen**: Insert- bzw. Delete-Workflow.

### Schema-Verwaltung (Menü „Schema“ → Tabellen verwalten)
- **Neue Tabelle anlegen**: Spalten mit Typ, NULL-Option und Primärschlüssel
  frei zusammenstellen.
- **Spalte zu bestehender Tabelle hinzufügen**.
- **Tabelle löschen** (mit Sicherheitsabfrage).

### Daten-Import/-Export (Menü „Daten“)
- **CSV-Export** der aktuell geöffneten Tabelle.
- **CSV-Import** in die aktuell geöffnete Tabelle (Backup wird vorher automatisch angelegt).

### SQL-Dateien öffnen (`.sql`)
Neben `.db`-Dateien können auch SQL-Skripte (z. B. Schema-/Datenexporte)
geöffnet werden – sie werden in eine temporäre SQLite-Datenbank geladen.
Ist das Skript bereits SQLite-kompatibel, wird es direkt ausgeführt.
Schlägt das fehl, übersetzt `core/sql_parser.py` – ein eigenständiger,
tokenbasierter SQL-Parser (Tokenizer + struktureller Parser für
`CREATE TABLE`/`INSERT`, generischer Fallback für alles andere) – gängige
MariaDB/MySQL-Dump-Syntax (mysqldump/phpMyAdmin) automatisch nach SQLite:
Backtick-Identifier, `AUTO_INCREMENT`, `UNSIGNED`, `ENGINE=`/`CHARSET=`-
Tabellenoptionen, `ENUM(...)` (wird zu `TEXT` + `CHECK`-Constraint),
Fremdschlüssel mit `ON DELETE`/`ON UPDATE`, sowie
`INSERT ... ON DUPLICATE KEY UPDATE` (wird zu `INSERT OR REPLACE`).
Schlägt auch das fehl, wird die genaue Anweisung benannt, an der der
Import scheitert.

### Sicherheit
- **Automatisches Backup** vor jedem Speichern/Löschen/Import: Zeitstempel-Kopie
  der SQLite-Datei (`pandora_backups/`) bzw. `mysqldump` bei MariaDB
  (`~/pandora_mariadb_backups/`).
- Tabellen-/Spaltennamen für DDL-Operationen werden strikt gegen ein
  Allowlist-Muster geprüft (verhindert SQL-Injection über Schema-Operationen).

## Bekannte Grenzen / Ausbaumöglichkeiten

- MariaDB-Backup-Passwort wird aktuell nicht zwischengespeichert (Sicherheit) –
  `mysqldump` läuft daher ggf. ohne Passwort, falls die Verbindung
  passwortlos erlaubt ist; sonst Backup-Dialog erweitern.
- Spalten können aktuell nicht umbenannt oder gelöscht werden (nur hinzufügen) –
  SQLite erfordert dafür Table-Rebuild, MariaDB `ALTER TABLE ... DROP/CHANGE`;
  bei Bedarf im Schema-Manager ergänzbar.

