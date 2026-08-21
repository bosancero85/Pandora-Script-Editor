"""
Pandora SQL Config Editor & Validator
--------------------------------------
Tokenbasierter SQL-Parser für den Import von MariaDB/MySQL-Dumps.

Ersetzt die frühere, rein regexbasierte Übersetzung
(vormals ``db_manager._sanitize_mysql_dump`` – Text-Ersetzungen über das
komplette Skript hinweg) durch einen echten Tokenizer plus strukturelle
Parser für die beiden dump-relevanten Anweisungstypen.

Warum ein Tokenizer statt Regex:
  Regex kennt keinen Kontext. Ein Muster wie ``r",(\\s*\\))"`` trifft genauso
  auf ein Vorkommen mitten in einem String-Literal oder Kommentar wie auf
  echtes SQL. Ein Tokenizer liest Anführungszeichen, Escapes und Kommentare
  einmal korrekt ein und behandelt ihren Inhalt danach als atomare Einheit –
  Interpunktion *innerhalb* eines Strings kann Anweisungsgrenzen dann nicht
  mehr versehentlich verschieben.

Deckungsumfang:
  - Tokenizer für MySQL-/MariaDB- und SQLite-Dialekt (Backtick-, Doppel- und
    Single-Quote-Strings/Identifier, Backslash-Escapes, --/#-Zeilenkommentare,
    /* */-Blockkommentare, Zahlen, Mehrzeichen-Operatoren).
  - Anweisungstrennung anhand von Klammertiefe statt naivem ``str.split(";")``.
  - Vollständiger struktureller Parser für ``CREATE TABLE`` (Spalten, Typen,
    NOT NULL/DEFAULT/AUTO_INCREMENT, PRIMARY/UNIQUE/FOREIGN KEY, ENUM,
    Tabellenoptionen) inkl. Rückübersetzung nach SQLite-DDL.
  - Vollständiger Parser für ``INSERT INTO ... VALUES (...), (...) ...``
    inkl. ``ON DUPLICATE KEY UPDATE`` -> ``INSERT OR REPLACE``.
  - Generischer, ebenfalls tokenbasierter Fallback für alle übrigen
    Anweisungstypen (DROP, ALTER TABLE, ...): stellt Bezeichner von
    Backtick- auf SQLite-Doppelquotes um und entfernt bekannte
    MySQL-only-Klauseln (ENGINE=, CHARSET=, AUTO_INCREMENT, ...).
    Rein administrative MySQL-Anweisungen (SET, LOCK/UNLOCK TABLES, USE, ...)
    werden verworfen.

Bewusst nicht abgedeckt (für Config-/Dump-Importe nicht relevant):
  gespeicherte Prozeduren/Trigger/Views mit eigenem ``DELIMITER``,
  Unterabfragen in DEFAULT-Ausdrücken, Fensterfunktionen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional


class SqlParseError(Exception):
    """Eine einzelne Anweisung konnte nicht strukturell geparst werden."""


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_PUNCT = set("(),;")
_OP_CHARS = set("=<>!:+-*/%|&^~")
_MULTI_OPS = (":=", "<=>", "<>", "!=", ">=", "<=", "<<", ">>", "||")

_MYSQL_STRING_ESCAPES = {
    "n": "\n", "t": "\t", "r": "\r", "0": "\0", "b": "\b",
    "Z": "\x1a", "\\": "\\", "'": "'", '"': '"', "%": "%", "_": "_",
}


@dataclass
class Token:
    kind: str   # 'ident' | 'string' | 'number' | 'punct' | 'op'
    text: str   # rohes Quelltext-Fragment (inkl. evtl. Quotes)
    value: Any  # verarbeiteter Wert (entschlüsselter str / Zahl)
    pos: int


def _read_quoted(s: str, i: int, quote: str, escape: bool) -> tuple[str, int]:
    """Liest ab ``s[i] == quote`` bis zum schließenden (ggf. verdoppelten)
    Quote-Zeichen. Gibt (roher Text inkl. Quotes, Index danach) zurück."""
    n = len(s)
    j = i + 1
    buf = [quote]
    while j < n:
        c = s[j]
        if escape and c == "\\" and j + 1 < n:
            buf.append(c)
            buf.append(s[j + 1])
            j += 2
            continue
        if c == quote:
            if j + 1 < n and s[j + 1] == quote:
                buf.append(quote)
                buf.append(quote)
                j += 2
                continue
            buf.append(quote)
            j += 1
            return "".join(buf), j
        buf.append(c)
        j += 1
    # Nicht terminiert (defektes/abgeschnittenes Skript) - defensiv den Rest übernehmen
    return "".join(buf), j


def _unescape_string_literal(raw: str) -> str:
    """``raw`` enthält die äußeren Single-Quotes. Liefert den entschlüsselten str."""
    inner = raw[1:-1]
    out: list[str] = []
    i, n = 0, len(inner)
    while i < n:
        c = inner[i]
        if c == "\\" and i + 1 < n:
            out.append(_MYSQL_STRING_ESCAPES.get(inner[i + 1], inner[i + 1]))
            i += 2
            continue
        if c == "'" and i + 1 < n and inner[i + 1] == "'":
            out.append("'")
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def tokenize(sql: str) -> list[Token]:
    tokens: list[Token] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]

        if c in " \t\r\n":
            i += 1
            continue

        # -- Zeilenkommentar (MySQL verlangt nachfolgendes Leerzeichen/Ende)
        if c == "-" and i + 1 < n and sql[i + 1] == "-" and (i + 2 >= n or sql[i + 2] in " \t\r\n"):
            j = sql.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        # # Zeilenkommentar (MySQL-spezifisch)
        if c == "#":
            j = sql.find("\n", i)
            i = n if j == -1 else j + 1
            continue
        # /* ... */ Blockkommentar (deckt auch /*! ... */-Optimizer-Hints ab -
        #   deren Inhalt ist i.d.R. reine MySQL-Administration und wird bewusst verworfen)
        if c == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue

        if c == "`":
            raw, j = _read_quoted(sql, i, "`", escape=False)
            tokens.append(Token("ident", raw, raw[1:-1].replace("``", "`"), i))
            i = j
            continue
        if c == '"':
            raw, j = _read_quoted(sql, i, '"', escape=True)
            tokens.append(Token("ident", raw, raw[1:-1].replace('""', '"'), i))
            i = j
            continue
        if c == "'":
            raw, j = _read_quoted(sql, i, "'", escape=True)
            tokens.append(Token("string", raw, _unescape_string_literal(raw), i))
            i = j
            continue

        if c.isdigit() or (c == "." and i + 1 < n and sql[i + 1].isdigit()):
            j = i
            seen_dot = False
            while j < n and (sql[j].isdigit() or (sql[j] == "." and not seen_dot)):
                if sql[j] == ".":
                    seen_dot = True
                j += 1
            if j < n and sql[j] in "eE":
                k = j + 1
                if k < n and sql[k] in "+-":
                    k += 1
                if k < n and sql[k].isdigit():
                    while k < n and sql[k].isdigit():
                        k += 1
                    j = k
            raw = sql[i:j]
            try:
                value: Any = int(raw)
            except ValueError:
                value = float(raw)
            tokens.append(Token("number", raw, value, i))
            i = j
            continue

        if c.isalpha() or c in "_$":
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] in "_$"):
                j += 1
            raw = sql[i:j]
            tokens.append(Token("ident", raw, raw, i))
            i = j
            continue

        matched_op = next((op for op in _MULTI_OPS if sql.startswith(op, i)), None)
        if matched_op:
            tokens.append(Token("op", matched_op, matched_op, i))
            i += len(matched_op)
            continue

        if c in _PUNCT:
            tokens.append(Token("punct", c, c, i))
            i += 1
            continue
        if c in _OP_CHARS:
            tokens.append(Token("op", c, c, i))
            i += 1
            continue

        # Unbekanntes Zeichen: übernehmen statt hart abzubrechen (defensiv)
        tokens.append(Token("punct", c, c, i))
        i += 1

    return tokens


def split_statements(script: str) -> list[str]:
    """Zerlegt ein SQL-Skript anhand von Klammertiefe/Quote-Status in einzelne
    Anweisungen. Anders als ``str.split(";")`` wird dabei ein Semikolon
    innerhalb eines String-Literals oder Kommentars nicht als Trenner erkannt,
    weil der Tokenizer dessen Inhalt bereits als ein einzelnes Token liest."""
    tokens = tokenize(script)
    statements: list[str] = []
    depth = 0
    start = 0
    for tok in tokens:
        if tok.kind == "punct" and tok.text == "(":
            depth += 1
        elif tok.kind == "punct" and tok.text == ")":
            depth = max(0, depth - 1)
        elif tok.kind == "punct" and tok.text == ";" and depth == 0:
            end = tok.pos + 1
            stmt = script[start:end].strip()
            if stmt and stmt != ";":
                statements.append(stmt)
            start = end
    tail = script[start:].strip()
    if tail:
        statements.append(tail)
    return statements


# ---------------------------------------------------------------------------
# Token-Stream-Hilfsklasse
# ---------------------------------------------------------------------------

class TokenStream:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def peek(self, offset: int = 0) -> Optional[Token]:
        j = self.i + offset
        return self.tokens[j] if 0 <= j < len(self.tokens) else None

    def next(self) -> Optional[Token]:
        tok = self.peek()
        if tok is not None:
            self.i += 1
        return tok

    def is_kw(self, *words: str, offset: int = 0) -> bool:
        tok = self.peek(offset)
        return bool(tok) and tok.kind == "ident" and tok.value.upper() in words

    def is_punct(self, ch: str, offset: int = 0) -> bool:
        tok = self.peek(offset)
        return bool(tok) and tok.kind in ("punct", "op") and tok.text == ch

    def eat_kw(self, *words: str) -> bool:
        if self.is_kw(*words):
            self.next()
            return True
        return False

    def expect_punct(self, ch: str) -> Token:
        tok = self.next()
        if not tok or tok.text != ch:
            raise SqlParseError(f"Erwartet '{ch}', gefunden: {tok.text if tok else 'Ende der Anweisung'}")
        return tok


def _skip_parenthesized(ts: TokenStream, capture: bool = False) -> str:
    parts: list[str] = []
    ts.expect_punct("(")
    depth = 1
    while depth > 0:
        tok = ts.next()
        if tok is None:
            break
        if tok.text == "(":
            depth += 1
        elif tok.text == ")":
            depth -= 1
            if depth == 0:
                break
        if capture:
            parts.append(tok.text)
    return "(" + " ".join(parts) + ")" if capture else ""


def _parse_col_list(ts: TokenStream) -> list[str]:
    """Liest ``(col1, col2(255) DESC, ...)`` und liefert die reinen Spaltennamen
    (Index-Präfixlängen und ASC/DESC werden übersprungen)."""
    cols: list[str] = []
    ts.expect_punct("(")
    while not ts.is_punct(")"):
        tok = ts.next()
        if tok and tok.kind == "ident":
            cols.append(tok.value)
        if ts.is_punct("("):
            _skip_parenthesized(ts)  # z.B. Index-Präfixlänge: name(255)
        if ts.is_kw("ASC", "DESC"):
            ts.next()
        if ts.is_punct(","):
            ts.next()
    ts.expect_punct(")")
    return cols


# ---------------------------------------------------------------------------
# Typ-Mapping MySQL/MariaDB -> SQLite
# ---------------------------------------------------------------------------

_INT_TYPES = ("TINYINT", "SMALLINT", "MEDIUMINT", "INT", "INTEGER", "BIGINT", "BIT", "YEAR")
_TEXT_TYPES = ("VARCHAR", "CHAR", "TEXT", "TINYTEXT", "MEDIUMTEXT", "LONGTEXT", "NCHAR", "NVARCHAR", "JSON")
_REAL_TYPES = ("FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL")
_BLOB_TYPES = ("BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB", "BINARY", "VARBINARY")
_DATETIME_TYPES = ("DATETIME", "TIMESTAMP")


def map_mysql_type_to_sqlite(raw_type: str) -> str:
    m = re.match(r"[A-Za-z_]+", raw_type.strip())
    kw = m.group(0).upper() if m else raw_type.upper()
    if kw in _INT_TYPES:
        return "INTEGER"
    if kw in ("BOOL", "BOOLEAN"):
        return "INTEGER"
    if kw in _REAL_TYPES:
        return "REAL"
    if kw in _DATETIME_TYPES:
        return "DATETIME"
    if kw == "DATE":
        return "DATE"
    if kw == "TIME":
        return "TIME"
    if kw in _BLOB_TYPES:
        return "BLOB"
    if kw in _TEXT_TYPES or kw in ("ENUM", "SET"):
        return "TEXT"
    return "TEXT"


# ---------------------------------------------------------------------------
# CREATE TABLE - Datenmodell & Parser
# ---------------------------------------------------------------------------

@dataclass
class ColumnDef:
    name: str
    raw_type: str = "TEXT"
    not_null: bool = False
    default: Optional[str] = None       # bereits fertig formatiertes SQL-Literal/Ausdruck
    auto_increment: bool = False
    primary_key: bool = False
    unique: bool = False
    comment: Optional[str] = None
    enum_values: Optional[list[str]] = None


@dataclass
class TableConstraint:
    kind: str  # 'PRIMARY KEY' | 'UNIQUE' | 'FOREIGN KEY' | 'CHECK'
    columns: list[str] = field(default_factory=list)
    name: Optional[str] = None
    ref_table: Optional[str] = None
    ref_columns: list[str] = field(default_factory=list)
    on_delete: Optional[str] = None
    on_update: Optional[str] = None
    check_expr: Optional[str] = None


@dataclass
class CreateTableDef:
    name: str
    if_not_exists: bool = False
    columns: list[ColumnDef] = field(default_factory=list)
    constraints: list[TableConstraint] = field(default_factory=list)


def _parse_default_expr(ts: TokenStream) -> str:
    tok = ts.peek()
    if tok is None:
        return "NULL"
    if tok.kind == "ident" and tok.value.lower() in ("b", "x") and ts.peek(1) is not None and ts.peek(1).kind == "string":
        prefix = tok.value.lower()
        ts.next()
        s = ts.next().value
        return (str(int(s, 2)) if s else "0") if prefix == "b" else ("X'" + s.upper() + "'")
    if tok.kind == "string":
        ts.next()
        return "'" + tok.value.replace("'", "''") + "'"
    if tok.kind == "number":
        ts.next()
        return str(tok.value)
    if tok.kind == "ident" and tok.value.upper() == "NULL":
        ts.next()
        return "NULL"
    if tok.kind == "ident" and tok.value.upper() in ("CURRENT_TIMESTAMP", "NOW", "CURRENT_DATE", "CURRENT_TIME"):
        ts.next()
        if ts.is_punct("("):
            _skip_parenthesized(ts)
        return "CURRENT_TIMESTAMP"
    if ts.is_punct("("):
        return _skip_parenthesized(ts, capture=True)
    if tok.kind == "ident":
        ts.next()
        if tok.value.upper() == "TRUE":
            return "1"
        if tok.value.upper() == "FALSE":
            return "0"
        return tok.value
    ts.next()
    return str(tok.value)


def _parse_column_def(ts: TokenStream) -> ColumnDef:
    name_tok = ts.next()
    if name_tok is None or name_tok.kind != "ident":
        raise SqlParseError("Spaltenname erwartet.")
    col = ColumnDef(name=name_tok.value)

    type_tok = ts.next()
    if type_tok is None or type_tok.kind != "ident":
        raise SqlParseError(f"Datentyp für Spalte '{col.name}' erwartet.")
    type_name = type_tok.value.upper()

    if type_name in ("ENUM", "SET") and ts.is_punct("("):
        ts.next()
        values: list[str] = []
        while not ts.is_punct(")"):
            tok = ts.next()
            if tok is None:
                raise SqlParseError(f"Unerwartetes Ende in {type_name}(...) bei Spalte '{col.name}'.")
            if tok.kind == "string":
                values.append(tok.value)
            if ts.is_punct(","):
                ts.next()
        ts.expect_punct(")")
        col.raw_type = f"{type_name}({', '.join(values)})"
        if type_name == "ENUM":
            col.enum_values = values
    else:
        raw_type = type_name
        while ts.peek() and ts.peek().kind == "ident" and ts.peek().value.upper() in ("PRECISION", "VARYING"):
            raw_type += " " + ts.next().value.upper()
        if ts.is_punct("("):
            ts.next()
            digits: list[str] = []
            while not ts.is_punct(")"):
                tok = ts.next()
                if tok is None:
                    raise SqlParseError(f"Unerwartete Klammer im Typ von Spalte '{col.name}'.")
                digits.append(str(tok.value))
                if ts.is_punct(","):
                    ts.next()
                    digits[-1] += ","
            ts.expect_punct(")")
            raw_type += "(" + "".join(digits) + ")"
        col.raw_type = raw_type

    while ts.is_kw("UNSIGNED", "ZEROFILL", "SIGNED"):
        ts.next()
    while True:
        if ts.is_kw("CHARACTER") and ts.is_kw("SET", offset=1):
            ts.next(); ts.next()
            if ts.peek() and ts.peek().kind == "ident":
                ts.next()
            continue
        if ts.is_kw("CHARSET"):
            ts.next()
            if ts.peek() and ts.peek().kind == "ident":
                ts.next()
            continue
        break

    while True:
        if ts.is_kw("NOT") and ts.is_kw("NULL", offset=1):
            ts.next(); ts.next()
            col.not_null = True
        elif ts.is_kw("NULL"):
            ts.next()
            col.not_null = False
        elif ts.is_kw("DEFAULT"):
            ts.next()
            col.default = _parse_default_expr(ts)
        elif ts.is_kw("AUTO_INCREMENT"):
            ts.next()
            col.auto_increment = True
        elif ts.is_kw("PRIMARY") and ts.is_kw("KEY", offset=1):
            ts.next(); ts.next()
            col.primary_key = True
        elif ts.is_kw("UNIQUE"):
            ts.next()
            if ts.is_kw("KEY"):
                ts.next()
            col.unique = True
        elif ts.is_kw("COMMENT"):
            ts.next()
            tok = ts.next()
            col.comment = tok.value if tok and tok.kind == "string" else None
        elif ts.is_kw("ON") and ts.is_kw("UPDATE", offset=1):
            ts.next(); ts.next()
            tok = ts.next()
            if tok and ts.is_punct("("):
                _skip_parenthesized(ts)
        elif ts.is_kw("COLLATE"):
            ts.next()
            if ts.peek() and ts.peek().kind == "ident":
                ts.next()
        elif ts.is_kw("GENERATED"):
            ts.next()
            while ts.peek() and not (ts.is_punct(",") or ts.is_punct(")")):
                ts.next()
        else:
            break
    return col


def _parse_table_item(ts: TokenStream) -> Optional[TableConstraint]:
    if ts.is_kw("CONSTRAINT"):
        ts.next()
        if ts.peek() and ts.peek().kind == "ident" and not ts.is_punct("("):
            ts.next()

    if ts.is_kw("PRIMARY") and ts.is_kw("KEY", offset=1):
        ts.next(); ts.next()
        return TableConstraint(kind="PRIMARY KEY", columns=_parse_col_list(ts))

    if ts.is_kw("UNIQUE"):
        ts.next()
        if ts.is_kw("KEY", "INDEX"):
            ts.next()
        name = ts.next().value if (ts.peek() and ts.peek().kind == "ident" and not ts.is_punct("(")) else None
        return TableConstraint(kind="UNIQUE", name=name, columns=_parse_col_list(ts))

    if ts.is_kw("FOREIGN") and ts.is_kw("KEY", offset=1):
        ts.next(); ts.next()
        name = ts.next().value if (ts.peek() and ts.peek().kind == "ident" and not ts.is_punct("(")) else None
        cols = _parse_col_list(ts)
        ts.eat_kw("REFERENCES")
        ref_tok = ts.next()
        ref_table = ref_tok.value if ref_tok else ""
        ref_cols = _parse_col_list(ts) if ts.is_punct("(") else []
        on_delete = on_update = None
        while ts.is_kw("ON"):
            ts.next()
            action = ts.next().value.upper() if ts.peek() else ""
            words = []
            while ts.peek() and ts.peek().kind == "ident" and ts.peek().value.upper() in (
                "CASCADE", "RESTRICT", "SET", "NULL", "NO", "ACTION", "DEFAULT"
            ):
                words.append(ts.next().value.upper())
            clause = " ".join(words)
            if action == "DELETE":
                on_delete = clause
            elif action == "UPDATE":
                on_update = clause
        return TableConstraint(kind="FOREIGN KEY", name=name, columns=cols,
                                ref_table=ref_table, ref_columns=ref_cols,
                                on_delete=on_delete, on_update=on_update)

    if ts.is_kw("KEY", "INDEX"):
        ts.next()
        if ts.peek() and ts.peek().kind == "ident" and not ts.is_punct("("):
            ts.next()
        if ts.is_kw("USING"):
            ts.next(); ts.next()
        _parse_col_list(ts)
        # Nicht-eindeutige Sekundärindizes gehören in SQLite zu einem eigenen
        # CREATE INDEX, nicht in die CREATE-TABLE-Anweisung -> hier verworfen.
        return None

    if ts.is_kw("FULLTEXT", "SPATIAL"):
        ts.next()
        if ts.is_kw("KEY", "INDEX"):
            ts.next()
        if ts.peek() and ts.peek().kind == "ident" and not ts.is_punct("("):
            ts.next()
        _parse_col_list(ts)
        return None

    if ts.is_kw("CHECK"):
        ts.next()
        return TableConstraint(kind="CHECK", check_expr=_skip_parenthesized(ts, capture=True))

    # Unbekannte Tabellenoption defensiv bis zum nächsten Komma/Ende überspringen,
    # statt die ganze Anweisung scheitern zu lassen.
    depth = 0
    while ts.peek() and not (depth == 0 and (ts.is_punct(",") or ts.is_punct(")"))):
        if ts.is_punct("("):
            depth += 1
        elif ts.is_punct(")"):
            depth -= 1
        ts.next()
    return None


def parse_create_table(stmt: str) -> Optional[CreateTableDef]:
    ts = TokenStream(tokenize(stmt))
    if not ts.eat_kw("CREATE"):
        return None
    ts.eat_kw("TEMPORARY")
    if not ts.eat_kw("TABLE"):
        return None
    if_not_exists = False
    if ts.is_kw("IF") and ts.is_kw("NOT", offset=1) and ts.is_kw("EXISTS", offset=2):
        ts.next(); ts.next(); ts.next()
        if_not_exists = True
    name_tok = ts.next()
    if name_tok is None or name_tok.kind != "ident":
        raise SqlParseError("Tabellenname nach CREATE TABLE erwartet.")
    table = CreateTableDef(name=name_tok.value, if_not_exists=if_not_exists)

    ts.expect_punct("(")
    while not ts.is_punct(")"):
        save_i = ts.i
        if ts.is_kw("PRIMARY", "UNIQUE", "FOREIGN", "KEY", "INDEX", "FULLTEXT", "SPATIAL", "CHECK", "CONSTRAINT"):
            item = _parse_table_item(ts)
            if item is not None:
                table.constraints.append(item)
        else:
            table.columns.append(_parse_column_def(ts))
        if ts.i == save_i:
            ts.next()  # Sicherheitsnetz gegen Endlosschleife bei unbekannter Syntax
        if ts.is_punct(","):
            ts.next()
    ts.expect_punct(")")
    # Tabellenoptionen (ENGINE=..., DEFAULT CHARSET=..., ...) sind für SQLite
    # irrelevant und werden nicht weiter ausgewertet.
    return table


def create_table_to_sqlite(table: CreateTableDef) -> str:
    pk_from_constraint = next((c.columns for c in table.constraints if c.kind == "PRIMARY KEY"), [])
    pk_inline = [c.name for c in table.columns if c.primary_key]
    pk_cols = pk_from_constraint or pk_inline

    single_int_auto_pk = None
    if len(pk_cols) == 1:
        col = next((c for c in table.columns if c.name == pk_cols[0]), None)
        if col is not None and col.auto_increment and map_mysql_type_to_sqlite(col.raw_type) == "INTEGER":
            single_int_auto_pk = col.name

    lines: list[str] = []
    for col in table.columns:
        sqlite_type = map_mysql_type_to_sqlite(col.raw_type)
        parts = [f'"{col.name}"', sqlite_type]
        if col.name == single_int_auto_pk:
            parts.append("PRIMARY KEY AUTOINCREMENT")
        elif col.primary_key and not pk_from_constraint:
            parts.append("PRIMARY KEY")
        if col.not_null and col.name != single_int_auto_pk:
            parts.append("NOT NULL")
        if col.unique and not col.primary_key:
            parts.append("UNIQUE")
        if col.default is not None:
            parts.append(f"DEFAULT {col.default}")
        if col.enum_values:
            values_sql = ", ".join("'" + v.replace("'", "''") + "'" for v in col.enum_values)
            parts.append(f'CHECK("{col.name}" IN ({values_sql}))')
        lines.append("  " + " ".join(parts))

    for c in table.constraints:
        if c.kind == "PRIMARY KEY" and c.columns != ([single_int_auto_pk] if single_int_auto_pk else []):
            lines.append("  PRIMARY KEY (" + ", ".join(f'"{n}"' for n in c.columns) + ")")
        elif c.kind == "UNIQUE":
            lines.append("  UNIQUE (" + ", ".join(f'"{n}"' for n in c.columns) + ")")
        elif c.kind == "FOREIGN KEY":
            fk_cols_sql = ", ".join(f'"{n}"' for n in c.columns)
            fk_ref_cols_sql = ", ".join(f'"{n}"' for n in c.ref_columns)
            fk = f'  FOREIGN KEY ({fk_cols_sql}) REFERENCES "{c.ref_table}" ({fk_ref_cols_sql})'
            if c.on_delete:
                fk += f" ON DELETE {c.on_delete}"
            if c.on_update:
                fk += f" ON UPDATE {c.on_update}"
            lines.append(fk)
        elif c.kind == "CHECK" and c.check_expr:
            lines.append(f"  CHECK {c.check_expr}")

    exists_clause = "IF NOT EXISTS " if table.if_not_exists else ""
    return f'CREATE TABLE {exists_clause}"{table.name}" (\n' + ",\n".join(lines) + "\n);"


# ---------------------------------------------------------------------------
# INSERT - Datenmodell & Parser
# ---------------------------------------------------------------------------

@dataclass
class InsertStatement:
    table: str
    columns: list[str]
    rows: list[list[str]]   # bereits fertig formatierte SQL-Literale je Wert
    or_replace: bool = False


def _format_value_token(ts: TokenStream) -> str:
    tok = ts.peek()
    if tok is None:
        return "NULL"
    if tok.kind == "ident" and tok.value.lower() in ("b", "x") and ts.peek(1) is not None and ts.peek(1).kind == "string":
        prefix = tok.value.lower()
        ts.next()
        s = ts.next().value
        return (str(int(s, 2)) if s else "0") if prefix == "b" else ("X'" + s.upper() + "'")
    if tok.kind == "string":
        ts.next()
        return "'" + tok.value.replace("'", "''") + "'"
    if tok.kind == "number":
        ts.next()
        return str(tok.value)
    if tok.kind == "op" and tok.text == "-" and ts.peek(1) is not None and ts.peek(1).kind == "number":
        ts.next()
        return "-" + _format_value_token(ts)
    if tok.kind == "ident" and tok.value.upper() == "NULL":
        ts.next()
        return "NULL"
    if tok.kind == "ident" and tok.value.upper() == "TRUE":
        ts.next()
        return "1"
    if tok.kind == "ident" and tok.value.upper() == "FALSE":
        ts.next()
        return "0"
    if tok.kind == "ident" and tok.value.upper() in ("CURRENT_TIMESTAMP", "NOW"):
        ts.next()
        if ts.is_punct("("):
            _skip_parenthesized(ts)
        return "CURRENT_TIMESTAMP"
    # Unbekannter Ausdruck (z.B. Funktionsaufruf) - roh bis zum nächsten
    # Komma/Klammerende auf Tiefe 0 übernehmen statt abzubrechen.
    parts: list[str] = []
    depth = 0
    while ts.peek() and not (depth == 0 and (ts.is_punct(",") or ts.is_punct(")"))):
        t = ts.next()
        if t.text == "(":
            depth += 1
        elif t.text == ")":
            depth -= 1
        parts.append(t.text)
    return " ".join(parts) if parts else "NULL"


def parse_insert(stmt: str) -> Optional[InsertStatement]:
    ts = TokenStream(tokenize(stmt))
    if not ts.eat_kw("INSERT"):
        return None
    ts.eat_kw("IGNORE")
    ts.eat_kw("INTO")
    name_tok = ts.next()
    if name_tok is None or name_tok.kind != "ident":
        return None
    table = name_tok.value

    columns: list[str] = []
    if ts.is_punct("("):
        columns = _parse_col_list(ts)

    if not ts.eat_kw("VALUES", "VALUE"):
        return None

    rows: list[list[str]] = []
    while True:
        ts.expect_punct("(")
        row: list[str] = []
        while not ts.is_punct(")"):
            row.append(_format_value_token(ts))
            if ts.is_punct(","):
                ts.next()
        ts.expect_punct(")")
        rows.append(row)
        if ts.is_punct(","):
            ts.next()
            continue
        break

    or_replace = ts.is_kw("ON") and ts.is_kw("DUPLICATE", offset=1)
    return InsertStatement(table=table, columns=columns, rows=rows, or_replace=or_replace)


def insert_to_sqlite(ins: InsertStatement) -> str:
    verb = "INSERT OR REPLACE INTO" if ins.or_replace else "INSERT INTO"
    cols_sql = " (" + ", ".join(f'"{c}"' for c in ins.columns) + ")" if ins.columns else ""
    values_sql = ", ".join("(" + ", ".join(row) + ")" for row in ins.rows)
    return f'{verb} "{ins.table}"{cols_sql} VALUES {values_sql};'


# ---------------------------------------------------------------------------
# Generischer Fallback für alle übrigen Anweisungstypen
# ---------------------------------------------------------------------------

_NO_SPACE_BEFORE = {",", ")", ";"}
_NO_SPACE_AFTER = {"("}
_DROP_STATEMENT_FIRST_WORDS = {
    "SET", "LOCK", "UNLOCK", "USE", "START", "COMMIT", "BEGIN", "SAVEPOINT",
    "DELIMITER", "GRANT", "REVOKE", "FLUSH", "ANALYZE", "OPTIMIZE",
}


def _render_token_text(tok: Token) -> str:
    if tok.kind == "ident":
        if tok.text[:1] in ("`", '"'):
            return '"' + tok.value.replace('"', '""') + '"'
        return tok.value
    if tok.kind == "string":
        return "'" + tok.value.replace("'", "''") + "'"
    if tok.kind == "number":
        return str(tok.value)
    return tok.text


def render_tokens(tokens: list[Token]) -> str:
    out: list[str] = []
    prev_text = ""
    for tok in tokens:
        piece = _render_token_text(tok)
        if out:
            need_space = piece[:1] not in _NO_SPACE_BEFORE and prev_text[-1:] not in _NO_SPACE_AFTER
            out.append((" " if need_space else "") + piece)
        else:
            out.append(piece)
        prev_text = piece
    return "".join(out)


def _filter_mysql_only_tokens(tokens: list[Token]) -> list[Token]:
    skip_words = {"AUTO_INCREMENT", "UNSIGNED", "ZEROFILL"}
    out: list[Token] = []
    i, n = 0, len(tokens)
    while i < n:
        tok = tokens[i]
        up = tok.value.upper() if tok.kind == "ident" else ""
        if up in skip_words:
            i += 1
            continue
        if up == "CHARACTER" and i + 1 < n and tokens[i + 1].kind == "ident" and tokens[i + 1].value.upper() == "SET":
            i += 2
            if i < n and tokens[i].kind == "ident":
                i += 1
            continue
        if up in ("CHARSET", "COLLATE", "ENGINE"):
            i += 1
            if i < n and tokens[i].text == "=":
                i += 1
            if i < n and tokens[i].kind == "ident":
                i += 1
            continue
        if up == "COMMENT" and i + 1 < n and tokens[i + 1].kind == "string":
            i += 2
            continue
        if (up == "ON" and i + 2 < n and tokens[i + 1].kind == "ident"
                and tokens[i + 1].value.upper() == "UPDATE"
                and tokens[i + 2].kind == "ident"
                and tokens[i + 2].value.upper() in ("CURRENT_TIMESTAMP", "NOW")):
            i += 3
            if i < n and tokens[i].text == "(":
                depth = 1
                i += 1
                while i < n and depth > 0:
                    if tokens[i].text == "(":
                        depth += 1
                    elif tokens[i].text == ")":
                        depth -= 1
                    i += 1
            continue
        out.append(tok)
        i += 1
    return out


def convert_generic_statement(stmt: str) -> Optional[str]:
    """Fallback für Anweisungstypen ohne eigenen strukturellen Parser (DROP,
    ALTER TABLE, CREATE INDEX, ...): stellt Bezeichner-Quoting um und entfernt
    bekannte MySQL-only-Klauseln, ohne die übrige Struktur zu verändern.
    Rein administrative MySQL-Anweisungen werden verworfen (None)."""
    tokens = tokenize(stmt)
    if not tokens:
        return None
    first = tokens[0].value.upper() if tokens[0].kind == "ident" else ""
    second = tokens[1].value.upper() if len(tokens) > 1 and tokens[1].kind == "ident" else ""

    if first in _DROP_STATEMENT_FIRST_WORDS:
        return None
    if first in ("CREATE", "ALTER", "DROP") and second == "DATABASE":
        return None

    filtered = _filter_mysql_only_tokens(tokens)
    if not filtered or all(t.kind == "punct" for t in filtered):
        return None
    rendered = render_tokens(filtered).rstrip()
    if not rendered.endswith(";"):
        rendered += ";"
    return rendered


# ---------------------------------------------------------------------------
# Öffentliche Einstiegsfunktion
# ---------------------------------------------------------------------------

def convert_mysql_script_to_sqlite(script: str) -> str:
    """Übersetzt ein MariaDB/MySQL-Dump-Skript (mysqldump, phpMyAdmin-Export, ...)
    in ein SQLite-ausführbares Skript. Siehe Moduldokumentation oben für den
    genauen Deckungsumfang."""
    out_statements: list[str] = []
    for stmt in split_statements(script):
        stripped = stmt.strip()
        if not stripped or stripped == ";":
            continue
        try:
            if re.match(r"(?is)^CREATE\s+TABLE\b", stripped):
                table = parse_create_table(stripped)
                if table is not None:
                    out_statements.append(create_table_to_sqlite(table))
                    continue
            if re.match(r"(?is)^INSERT\s+(IGNORE\s+)?INTO\b", stripped):
                ins = parse_insert(stripped)
                if ins is not None:
                    out_statements.append(insert_to_sqlite(ins))
                    continue
        except SqlParseError:
            # Diese eine Anweisung konnte strukturell nicht ausgewertet werden -
            # auf die generische Tokenbereinigung ausweichen, statt das gesamte
            # Skript abzubrechen.
            pass
        converted = convert_generic_statement(stripped)
        if converted:
            out_statements.append(converted)
    return "\n".join(out_statements)
