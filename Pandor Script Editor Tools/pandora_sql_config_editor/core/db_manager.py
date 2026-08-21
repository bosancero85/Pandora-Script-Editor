"""
Pandora SQL Config Editor & Validator
--------------------------------------
DB-Abstraktionsschicht. Erkennt automatisch, ob eine SQLite-Datei oder ein
laufender MariaDB/MySQL-Server als Ziel benutzt wird, liest das Schema aus
und baut die SQL-Statements für Insert/Update/Delete.
"""

from __future__ import annotations

import sqlite3
import socket
import shutil
import subprocess
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

try:
    import pymysql  # MariaDB / MySQL Treiber
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

from core.sql_parser import convert_mysql_script_to_sqlite, split_statements


@dataclass
class ColumnInfo:
    name: str
    data_type: str          # normalisierter Typ: TEXT, INTEGER, REAL, BOOLEAN, DATE, DATETIME, BLOB
    raw_type: str            # Originaltyp aus dem Schema
    nullable: bool
    primary_key: bool
    default: Any = None
    foreign_key: Optional[tuple[str, str]] = None   # (referenzierte_tabelle, referenzierte_spalte)


@dataclass
class TableInfo:
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)


class DBBackendError(Exception):
    pass


IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_identifier(name: str) -> bool:
    """Erlaubt nur sichere Tabellen-/Spaltennamen (verhindert SQL-Injection über DDL)."""
    return bool(IDENTIFIER_RE.match(name or ""))


def normalize_type(raw_type: str) -> str:
    """Bildet SQLite/MariaDB-Typnamen auf eine kleine, einheitliche Menge ab."""
    t = (raw_type or "").upper()
    if any(x in t for x in ("INT",)):
        return "INTEGER"
    if any(x in t for x in ("BOOL",)):
        return "BOOLEAN"
    if any(x in t for x in ("REAL", "FLOA", "DOUB", "DEC", "NUMERIC")):
        return "REAL"
    if "DATETIME" in t or "TIMESTAMP" in t:
        return "DATETIME"
    if t == "DATE":
        return "DATE"
    if "BLOB" in t or "BINARY" in t:
        return "BLOB"
    return "TEXT"


def detect_mariadb_running(host: str = "127.0.0.1", port: int = 3306, timeout: float = 0.6) -> bool:
    """Prüft, ob auf dem System ein MariaDB/MySQL-Server lauscht."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def detect_mariadb_service() -> bool:
    """Zusätzliche Erkennung über systemd, nützlich auf Kali/Raspberry Pi OS."""
    for svc in ("mariadb", "mysql"):
        try:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=2,
            )
            if result.stdout.strip() == "active":
                return True
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
    return False


class DatabaseManager:
    """
    Einheitliche Schnittstelle für SQLite-Dateien und MariaDB-Verbindungen.
    backend ist entweder "sqlite" oder "mariadb".
    """

    def __init__(self) -> None:
        self.backend: Optional[str] = None
        self.conn = None
        self.sqlite_path: Optional[Path] = None
        self.mariadb_params: Optional[dict] = None
        # Gesetzt, wenn die aktuelle Sitzung aus einer .sql-Skriptdatei geladen wurde.
        # In diesem Fall arbeitet der Editor auf einer temporären SQLite-Kopie und
        # schreibt Änderungen bei Bedarf als SQL-Dump in diese Originaldatei zurück.
        self.sql_source_path: Optional[Path] = None
        # True, wenn die zuletzt geöffnete .sql-Datei automatisch von
        # MariaDB/MySQL-Dialekt nach SQLite konvertiert werden musste.
        self.sql_was_converted: bool = False

    # ---------- Verbindungsaufbau ----------

    def open_sqlite(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            raise DBBackendError(f"Datei nicht gefunden: {path}")
        self.conn = sqlite3.connect(str(p))
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.backend = "sqlite"
        self.sqlite_path = p
        self.sql_source_path = None

    def open_sql_file(self, path: str) -> None:
        """
        Lädt ein SQL-Skript (.sql, z.B. ein Dump oder Schema-Export) in eine
        temporäre SQLite-Datenbank, damit es mit derselben Oberfläche wie
        .db-Dateien durchsucht und bearbeitet werden kann.

        Beim Speichern (siehe save_to_sql_source / dump_to_sql_file) wird der
        aktuelle Inhalt wieder als SQL-Dump in die Originaldatei geschrieben.
        Hinweis: Das Skript muss SQLite-kompatibles SQL enthalten (Dumps aus
        MariaDB/MySQL mit z.B. Backtick-Syntax oder AUTO_INCREMENT müssen ggf.
        vorher angepasst werden).
        """
        p = Path(path)
        if not p.exists():
            raise DBBackendError(f"Datei nicht gefunden: {path}")
        try:
            script = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            raise DBBackendError(f"Konnte SQL-Datei nicht lesen: {e}")

        tmp_dir = Path(tempfile.gettempdir()) / "pandora_sql_editor"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"{p.stem}_{uuid.uuid4().hex[:8]}.tmp.sqlite"

        conn = sqlite3.connect(str(tmp_path))
        converted = False
        try:
            conn.executescript(script)
        except sqlite3.Error as first_err:
            # Vermutlich MariaDB/MySQL-Dialekt (mysqldump/phpMyAdmin-Export) –
            # mit dem tokenbasierten SQL-Parser (core/sql_parser.py) in
            # SQLite-kompatibles SQL übersetzen und erneut versuchen.
            conn.close()
            conn = sqlite3.connect(str(tmp_path))
            try:
                sanitized = convert_mysql_script_to_sqlite(script)
                conn.executescript(sanitized)
                converted = True
            except sqlite3.Error as second_err:
                # Genaue Fehlerstelle ermitteln: statementweise auf einer
                # FRISCHEN In-Memory-DB ausführen (nicht auf tmp_path, das aus
                # dem vorigen executescript-Versuch bereits teilweise befüllt
                # sein kann und sonst die falsche Anweisung als Ursache melden würde).
                conn.close()
                diag_conn = sqlite3.connect(":memory:")
                failing_stmt = None
                try:
                    for stmt in split_statements(sanitized):
                        try:
                            diag_conn.execute(stmt)
                        except sqlite3.Error as stmt_err:
                            failing_stmt = (stmt, stmt_err)
                            break
                except Exception:
                    pass
                diag_conn.close()
                tmp_path.unlink(missing_ok=True)
                detail = ""
                if failing_stmt is not None:
                    stmt_text, stmt_err = failing_stmt
                    preview = stmt_text if len(stmt_text) <= 300 else stmt_text[:300] + " …"
                    detail = f"\n\nBetroffene Anweisung:\n{preview}\n\nFehler: {stmt_err}"
                raise DBBackendError(
                    "Konnte SQL-Datei nicht einlesen – vermutlich enthält sie SQL-Syntax, "
                    "die weder von SQLite noch nach automatischer MariaDB/MySQL-Umwandlung "
                    f"unterstützt wird.\n\nErster Versuch: {first_err}\n"
                    f"Nach Umwandlung: {second_err}{detail}"
                )
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

        self.conn = conn
        self.backend = "sqlite"
        self.sqlite_path = tmp_path
        self.sql_source_path = p
        self.sql_was_converted = converted

    def dump_to_sql_file(self, path: str) -> None:
        """Schreibt den kompletten aktuellen SQLite-Inhalt als SQL-Dump (.sql)."""
        if self.backend != "sqlite" or self.conn is None:
            raise DBBackendError("SQL-Export ist nur für SQLite-Sitzungen möglich.")
        self.conn.commit()
        p = Path(path)
        try:
            with open(p, "w", encoding="utf-8") as f:
                for line in self.conn.iterdump():
                    f.write(f"{line}\n")
        except OSError as e:
            raise DBBackendError(f"Konnte SQL-Datei nicht schreiben: {e}")

    def save_to_sql_source(self) -> None:
        """Schreibt Änderungen zurück in die ursprüngliche .sql-Datei, falls
        die aktuelle Sitzung aus einer solchen geöffnet wurde (no-op sonst)."""
        if self.sql_source_path is not None:
            self.dump_to_sql_file(str(self.sql_source_path))

    def connect_mariadb(self, host: str, user: str, password: str,
                         database: str, port: int = 3306) -> None:
        if not HAS_PYMYSQL:
            raise DBBackendError(
                "pymysql ist nicht installiert. Bitte 'pip install pymysql' ausführen."
            )
        self.conn = pymysql.connect(
            host=host, user=user, password=password,
            database=database, port=port, autocommit=False,
        )
        self.backend = "mariadb"
        self.mariadb_params = dict(host=host, user=user, database=database, port=port)

    @staticmethod
    def autodetect() -> dict:
        """Liefert Infos, welches Backend auf dem System vorhanden ist."""
        return {
            "mariadb_socket_open": detect_mariadb_running(),
            "mariadb_service_active": detect_mariadb_service(),
            "pymysql_installed": HAS_PYMYSQL,
        }

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
        if self.sql_source_path is not None and self.sqlite_path is not None:
            try:
                self.sqlite_path.unlink(missing_ok=True)
            except Exception:
                pass
        self.conn = None
        self.backend = None
        self.sql_source_path = None

    # ---------- Schema-Introspektion ----------

    def list_tables(self) -> list[str]:
        if self.backend == "sqlite":
            cur = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name;"
            )
            return [row[0] for row in cur.fetchall()]
        elif self.backend == "mariadb":
            with self.conn.cursor() as cur:
                cur.execute("SHOW TABLES;")
                return [row[0] for row in cur.fetchall()]
        raise DBBackendError("Keine aktive Verbindung.")

    def get_schema(self, table: str) -> TableInfo:
        if self.backend == "sqlite":
            cur = self.conn.execute(f"PRAGMA table_info('{table}');")
            fk_map = {}
            for _id, _seq, ref_table, from_col, to_col, *_rest in self.conn.execute(
                f"PRAGMA foreign_key_list('{table}');"
            ).fetchall():
                fk_map[from_col] = (ref_table, to_col)

            cols = []
            for cid, name, ctype, notnull, dflt, pk in cur.fetchall():
                cols.append(ColumnInfo(
                    name=name,
                    data_type=normalize_type(ctype),
                    raw_type=ctype or "TEXT",
                    nullable=(notnull == 0),
                    primary_key=bool(pk),
                    default=dflt,
                    foreign_key=fk_map.get(name),
                ))
            return TableInfo(name=table, columns=cols)

        elif self.backend == "mariadb":
            with self.conn.cursor() as cur:
                cur.execute(f"SHOW COLUMNS FROM `{table}`;")
                rows = cur.fetchall()
                cur.execute(
                    "SELECT COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME "
                    "FROM information_schema.KEY_COLUMN_USAGE "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                    "AND REFERENCED_TABLE_NAME IS NOT NULL;",
                    (table,),
                )
                fk_map = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

                cols = []
                for field_name, ctype, nullable, key, default, extra in rows:
                    cols.append(ColumnInfo(
                        name=field_name,
                        data_type=normalize_type(ctype),
                        raw_type=ctype,
                        nullable=(nullable == "YES"),
                        primary_key=(key == "PRI"),
                        default=default,
                        foreign_key=fk_map.get(field_name),
                    ))
                return TableInfo(name=table, columns=cols)
        raise DBBackendError("Keine aktive Verbindung.")

    def get_rows(self, table: str, limit: int = 500) -> tuple[list[str], list[tuple]]:
        quote = '"' if self.backend == "sqlite" else "`"
        sql = f"SELECT * FROM {quote}{table}{quote} LIMIT {int(limit)};"
        if self.backend == "sqlite":
            cur = self.conn.execute(sql)
            colnames = [d[0] for d in cur.description]
            return colnames, cur.fetchall()
        elif self.backend == "mariadb":
            with self.conn.cursor() as cur:
                cur.execute(sql)
                colnames = [d[0] for d in cur.description]
                return colnames, cur.fetchall()
        raise DBBackendError("Keine aktive Verbindung.")

    def count_rows(self, table: str, columns: list[str], search: str = "") -> int:
        quote = '"' if self.backend == "sqlite" else "`"
        t = f"{quote}{table}{quote}"
        where, params = self._build_search_where(columns, search)
        sql = f"SELECT COUNT(*) FROM {t} {where};"
        if self.backend == "sqlite":
            return self.conn.execute(sql, params).fetchone()[0]
        elif self.backend == "mariadb":
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()[0]
        raise DBBackendError("Keine aktive Verbindung.")

    def _build_search_where(self, columns: list[str], search: str) -> tuple[str, list]:
        if not search:
            return "", []
        quote = '"' if self.backend == "sqlite" else "`"
        ph = "?" if self.backend == "sqlite" else "%s"
        like_val = f"%{search}%"
        clauses = " OR ".join(f"CAST({quote}{c}{quote} AS CHAR) LIKE {ph}" for c in columns) \
            if self.backend == "mariadb" else \
            " OR ".join(f"CAST({quote}{c}{quote} AS TEXT) LIKE {ph}" for c in columns)
        return f"WHERE {clauses}", [like_val] * len(columns)

    def get_rows_paginated(self, table: str, columns: list[str], limit: int, offset: int,
                            search: str = "", sort_col: Optional[str] = None,
                            sort_dir: str = "ASC") -> tuple[list[str], list[tuple]]:
        quote = '"' if self.backend == "sqlite" else "`"
        t = f"{quote}{table}{quote}"
        where, params = self._build_search_where(columns, search)
        order = ""
        if sort_col and sort_col in columns:
            direction = "DESC" if sort_dir.upper() == "DESC" else "ASC"
            order = f"ORDER BY {quote}{sort_col}{quote} {direction}"
        sql = f"SELECT * FROM {t} {where} {order} LIMIT {int(limit)} OFFSET {int(offset)};"
        if self.backend == "sqlite":
            cur = self.conn.execute(sql, params)
            colnames = [d[0] for d in cur.description]
            return colnames, cur.fetchall()
        elif self.backend == "mariadb":
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                colnames = [d[0] for d in cur.description]
                return colnames, cur.fetchall()
        raise DBBackendError("Keine aktive Verbindung.")

    def get_label_map(self, ref_table: str, ref_col: str, limit: int = 1000) -> dict:
        """
        Liefert {pk_wert: anzeige_label} für ein Fremdschlüssel-Dropdown.
        Sucht heuristisch eine sprechende Anzeigespalte (name/title/username/label),
        fällt sonst auf die erste Nicht-PK-Spalte zurück.
        """
        schema = self.get_schema(ref_table)
        display_col = None
        for candidate in ("name", "username", "title", "label"):
            if any(c.name == candidate for c in schema.columns):
                display_col = candidate
                break
        if display_col is None:
            non_pk = [c.name for c in schema.columns if not c.primary_key]
            display_col = non_pk[0] if non_pk else ref_col

        quote = '"' if self.backend == "sqlite" else "`"
        sql = (f"SELECT {quote}{ref_col}{quote}, {quote}{display_col}{quote} "
               f"FROM {quote}{ref_table}{quote} LIMIT {int(limit)};")
        if self.backend == "sqlite":
            rows = self.conn.execute(sql).fetchall()
        else:
            with self.conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
        return {str(pk): f"{pk} — {label}" for pk, label in rows}

    # ---------- Tabellen-/Spaltenverwaltung (Schema-Editor) ----------

    def create_table(self, name: str, columns: list[dict]) -> None:
        """columns: Liste von dicts mit keys name, type, nullable, primary_key."""
        if not validate_identifier(name):
            raise DBBackendError(f"Ungültiger Tabellenname: {name}")
        col_defs = []
        pk_cols = []
        for c in columns:
            if not validate_identifier(c["name"]):
                raise DBBackendError(f"Ungültiger Spaltenname: {c['name']}")
            sql_type = self._map_create_type(c["type"])
            null_clause = "" if c.get("nullable", True) else " NOT NULL"
            col_defs.append(f"{self._quote_ident(c['name'])} {sql_type}{null_clause}")
            if c.get("primary_key"):
                pk_cols.append(c["name"])

        pk_clause = ""
        if pk_cols:
            quoted_pks = ", ".join(self._quote_ident(p) for p in pk_cols)
            pk_clause = f", PRIMARY KEY ({quoted_pks})"

        t = self._quote_ident(name)
        sql = f"CREATE TABLE {t} ({', '.join(col_defs)}{pk_clause});"
        self.execute(sql)

    def drop_table(self, name: str) -> None:
        if not validate_identifier(name):
            raise DBBackendError(f"Ungültiger Tabellenname: {name}")
        self.execute(f"DROP TABLE {self._quote_ident(name)};")

    def add_column(self, table: str, name: str, col_type: str,
                   nullable: bool = True, default: Optional[str] = None) -> None:
        if not validate_identifier(table) or not validate_identifier(name):
            raise DBBackendError("Ungültiger Tabellen- oder Spaltenname.")
        sql_type = self._map_create_type(col_type)
        null_clause = "" if nullable else " NOT NULL"
        default_clause = f" DEFAULT {self._quote_value(default)}" if default is not None else ""
        sql = (f"ALTER TABLE {self._quote_ident(table)} "
               f"ADD COLUMN {self._quote_ident(name)} {sql_type}{null_clause}{default_clause};")
        self.execute(sql)

    def _map_create_type(self, generic_type: str) -> str:
        """Bildet die generischen Editor-Typen auf backend-spezifisches SQL ab."""
        t = generic_type.upper()
        if self.backend == "mariadb":
            return {
                "TEXT": "TEXT", "INTEGER": "INT", "REAL": "DOUBLE",
                "BOOLEAN": "TINYINT(1)", "DATE": "DATE",
                "DATETIME": "DATETIME", "BLOB": "BLOB",
            }.get(t, "TEXT")
        # SQLite: Type-Affinity reicht mit den generischen Namen
        return {
            "TEXT": "TEXT", "INTEGER": "INTEGER", "REAL": "REAL",
            "BOOLEAN": "INTEGER", "DATE": "DATE",
            "DATETIME": "DATETIME", "BLOB": "BLOB",
        }.get(t, "TEXT")

    # ---------- SQL-Erzeugung ----------

    def _quote_ident(self, name: str) -> str:
        return f'"{name}"' if self.backend == "sqlite" else f"`{name}`"

    def _quote_value(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"

    def build_update_sql(self, table: str, pk_col: str, pk_value: Any,
                          changes: dict[str, Any]) -> str:
        t = self._quote_ident(table)
        set_clause = ", ".join(
            f"{self._quote_ident(c)} = {self._quote_value(v)}" for c, v in changes.items()
        )
        return f"UPDATE {t} SET {set_clause} WHERE {self._quote_ident(pk_col)} = {self._quote_value(pk_value)};"

    def build_insert_sql(self, table: str, values: dict[str, Any]) -> str:
        t = self._quote_ident(table)
        cols = ", ".join(self._quote_ident(c) for c in values.keys())
        vals = ", ".join(self._quote_value(v) for v in values.values())
        return f"INSERT INTO {t} ({cols}) VALUES ({vals});"

    def build_delete_sql(self, table: str, pk_col: str, pk_value: Any) -> str:
        t = self._quote_ident(table)
        return f"DELETE FROM {t} WHERE {self._quote_ident(pk_col)} = {self._quote_value(pk_value)};"

    def execute(self, sql: str) -> None:
        if self.backend == "sqlite":
            self.conn.execute(sql)
            self.conn.commit()
        elif self.backend == "mariadb":
            with self.conn.cursor() as cur:
                cur.execute(sql)
            self.conn.commit()
        else:
            raise DBBackendError("Keine aktive Verbindung.")

    # ---------- CSV Import/Export ----------

    def export_table_to_csv(self, table: str, path: Path) -> int:
        import csv
        colnames, rows = self.get_rows(table, limit=1_000_000)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(colnames)
            writer.writerows(rows)
        return len(rows)

    def import_csv_into_table(self, table: str, path: Path) -> int:
        import csv
        schema_cols = {c.name for c in self.get_schema(table).columns}
        inserted = 0
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                values = {k: v for k, v in row.items() if k in schema_cols and v != ""}
                if not values:
                    continue
                sql = self.build_insert_sql(table, values)
                self.execute(sql)
                inserted += 1
        return inserted
