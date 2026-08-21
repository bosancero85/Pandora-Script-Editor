"""
Pandora® SQL Config Editor & Validator
Hauptfenster: Split-Screen aus dynamischem Formular (links/mitte) und
Live-SQL-Vorschau (rechts), Tabellen-/Datenübersicht, automatische
Backend-Erkennung (MariaDB/SQLite) und automatisches Backup vor dem Speichern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
    QListWidgetItem, QLabel, QTableView, QPushButton, QTextEdit, QFileDialog,
    QMessageBox, QFormLayout, QLineEdit, QScrollArea, QGroupBox, QStatusBar,
    QInputDialog, QToolBar, QDialog, QDialogButtonBox, QComboBox, QSpinBox,
    QHeaderView, QTabWidget, QCheckBox
)
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from core.db_manager import DatabaseManager, DBBackendError, TableInfo, ColumnInfo, validate_identifier
from core.validator import validate_row
from core.backup import backup_sqlite, backup_mariadb, backup_sql_source
from ui.style import PANDORA_QSS


class SchemaManagerDialog(QDialog):
    """
    Dialog zur Tabellen-/Spaltenverwaltung: neue Tabelle anlegen,
    bestehende Tabelle löschen, Spalte zu bestehender Tabelle hinzufügen.
    """

    GENERIC_TYPES = ["TEXT", "INTEGER", "REAL", "BOOLEAN", "DATE", "DATETIME", "BLOB"]

    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Tabellen verwalten")
        self.resize(560, 480)
        self.new_columns: list[dict] = []

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # --- Tab 1: Neue Tabelle ---
        create_tab = QWidget()
        create_layout = QVBoxLayout(create_tab)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Tabellenname:"))
        self.new_table_name = QLineEdit()
        name_row.addWidget(self.new_table_name)
        create_layout.addLayout(name_row)

        self.columns_list = QListWidget()
        create_layout.addWidget(self.columns_list, stretch=1)

        add_col_row = QHBoxLayout()
        self.col_name_edit = QLineEdit()
        self.col_name_edit.setPlaceholderText("Spaltenname")
        self.col_type_combo = QComboBox()
        self.col_type_combo.addItems(self.GENERIC_TYPES)
        self.col_nullable_check = QCheckBox("NULL erlaubt")
        self.col_nullable_check.setChecked(True)
        self.col_pk_check = QCheckBox("Primärschlüssel")
        btn_add_col = QPushButton("+ Spalte hinzufügen")
        btn_add_col.clicked.connect(self._on_add_column_to_list)
        add_col_row.addWidget(self.col_name_edit)
        add_col_row.addWidget(self.col_type_combo)
        add_col_row.addWidget(self.col_nullable_check)
        add_col_row.addWidget(self.col_pk_check)
        add_col_row.addWidget(btn_add_col)
        create_layout.addLayout(add_col_row)

        btn_create_table = QPushButton("Tabelle erstellen")
        btn_create_table.setObjectName("PrimaryButton")
        btn_create_table.clicked.connect(self._on_create_table)
        create_layout.addWidget(btn_create_table)

        tabs.addTab(create_tab, "Neue Tabelle")

        # --- Tab 2: Spalte hinzufügen ---
        alter_tab = QWidget()
        alter_layout = QVBoxLayout(alter_tab)
        alter_layout.addWidget(QLabel("Zieltabelle:"))
        self.alter_table_combo = QComboBox()
        self.alter_table_combo.addItems(self.db.list_tables())
        alter_layout.addWidget(self.alter_table_combo)

        alter_row = QHBoxLayout()
        self.alter_col_name = QLineEdit()
        self.alter_col_name.setPlaceholderText("Neue Spalte")
        self.alter_col_type = QComboBox()
        self.alter_col_type.addItems(self.GENERIC_TYPES)
        self.alter_col_nullable = QCheckBox("NULL erlaubt")
        self.alter_col_nullable.setChecked(True)
        alter_row.addWidget(self.alter_col_name)
        alter_row.addWidget(self.alter_col_type)
        alter_row.addWidget(self.alter_col_nullable)
        alter_layout.addLayout(alter_row)

        btn_add_column = QPushButton("Spalte hinzufügen")
        btn_add_column.setObjectName("PrimaryButton")
        btn_add_column.clicked.connect(self._on_add_column_to_table)
        alter_layout.addWidget(btn_add_column)
        alter_layout.addStretch(1)

        tabs.addTab(alter_tab, "Spalte hinzufügen")

        # --- Tab 3: Tabelle löschen ---
        drop_tab = QWidget()
        drop_layout = QVBoxLayout(drop_tab)
        drop_layout.addWidget(QLabel("Tabelle zum Löschen auswählen:"))
        self.drop_table_combo = QComboBox()
        self.drop_table_combo.addItems(self.db.list_tables())
        drop_layout.addWidget(self.drop_table_combo)
        btn_drop = QPushButton("🗑 Tabelle unwiderruflich löschen")
        btn_drop.setObjectName("DangerButton")
        btn_drop.clicked.connect(self._on_drop_table)
        drop_layout.addWidget(btn_drop)
        drop_layout.addStretch(1)

        tabs.addTab(drop_tab, "Tabelle löschen")

        close_btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btns.rejected.connect(self.reject)
        close_btns.accepted.connect(self.accept)
        layout.addWidget(close_btns)

    def _on_add_column_to_list(self):
        name = self.col_name_edit.text().strip()
        if not validate_identifier(name):
            QMessageBox.warning(self, "Ungültig", "Bitte einen gültigen Spaltennamen angeben (Buchstaben/Zahlen/_).")
            return
        col = {
            "name": name,
            "type": self.col_type_combo.currentText(),
            "nullable": self.col_nullable_check.isChecked(),
            "primary_key": self.col_pk_check.isChecked(),
        }
        self.new_columns.append(col)
        pk_marker = " · PK" if col["primary_key"] else ""
        null_marker = "" if col["nullable"] else " · Pflichtfeld"
        self.columns_list.addItem(f"{col['name']} ({col['type']}){pk_marker}{null_marker}")
        self.col_name_edit.clear()
        self.col_pk_check.setChecked(False)

    def _on_create_table(self):
        name = self.new_table_name.text().strip()
        if not validate_identifier(name):
            QMessageBox.warning(self, "Ungültig", "Bitte einen gültigen Tabellennamen angeben.")
            return
        if not self.new_columns:
            QMessageBox.warning(self, "Ungültig", "Bitte mindestens eine Spalte hinzufügen.")
            return
        try:
            self.db.create_table(name, self.new_columns)
            QMessageBox.information(self, "Erstellt", f"Tabelle „{name}“ wurde angelegt.")
            self.new_table_name.clear()
            self.columns_list.clear()
            self.new_columns.clear()
            self.alter_table_combo.addItem(name)
            self.drop_table_combo.addItem(name)
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def _on_add_column_to_table(self):
        table = self.alter_table_combo.currentText()
        name = self.alter_col_name.text().strip()
        if not table:
            QMessageBox.warning(self, "Hinweis", "Keine Tabelle vorhanden.")
            return
        if not validate_identifier(name):
            QMessageBox.warning(self, "Ungültig", "Bitte einen gültigen Spaltennamen angeben.")
            return
        try:
            self.db.add_column(table, name, self.alter_col_type.currentText(),
                                nullable=self.alter_col_nullable.isChecked())
            QMessageBox.information(self, "Hinzugefügt", f"Spalte „{name}“ wurde zu „{table}“ hinzugefügt.")
            self.alter_col_name.clear()
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def _on_drop_table(self):
        table = self.drop_table_combo.currentText()
        if not table:
            return
        confirm = QMessageBox.question(
            self, "Tabelle löschen",
            f"Tabelle „{table}“ inkl. aller Daten unwiderruflich löschen?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.drop_table(table)
            QMessageBox.information(self, "Gelöscht", f"Tabelle „{table}“ wurde gelöscht.")
            idx = self.drop_table_combo.currentIndex()
            self.drop_table_combo.removeItem(idx)
            alter_idx = self.alter_table_combo.findText(table)
            if alter_idx >= 0:
                self.alter_table_combo.removeItem(alter_idx)
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))


class MariaDBConnectDialog(QDialog):
    """Kleiner Dialog zur Eingabe der MariaDB-Verbindungsdaten."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mit MariaDB verbinden")
        layout = QFormLayout(self)

        self.host_edit = QLineEdit("127.0.0.1")
        self.port_edit = QLineEdit("3306")
        self.user_edit = QLineEdit("root")
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.db_edit = QLineEdit()

        layout.addRow("Host:", self.host_edit)
        layout.addRow("Port:", self.port_edit)
        layout.addRow("Benutzer:", self.user_edit)
        layout.addRow("Passwort:", self.pass_edit)
        layout.addRow("Datenbank:", self.db_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> dict:
        return dict(
            host=self.host_edit.text().strip() or "127.0.0.1",
            port=int(self.port_edit.text().strip() or "3306"),
            user=self.user_edit.text().strip(),
            password=self.pass_edit.text(),
            database=self.db_edit.text().strip(),
        )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pandora® | SQL Config Editor & Validator")
        self.resize(1280, 800)

        self.db = DatabaseManager()
        self.current_table: Optional[TableInfo] = None
        self.current_pk_col: Optional[str] = None
        self.current_pk_value = None
        self.field_widgets: dict[str, QWidget] = {}
        self.field_errors: dict[str, QLabel] = {}
        self.pending_is_insert = False

        # Pagination / Suche / Sortierung
        self.page_size = 100
        self.current_page = 0
        self.total_rows = 0
        self.search_text = ""
        self.sort_col: Optional[str] = None
        self.sort_dir = "ASC"

        self._build_ui()
        self._build_actions()
        self._build_menu_bar()
        self._build_toolbar()
        self._refresh_backend_status()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)

        header = QLabel("PANDORA® | SQL CONFIG EDITOR & VALIDATOR")
        header.setObjectName("HeaderLabel")
        sub = QLabel("Visuelle Bearbeitung, Live-Schema-Validierung, automatisches Backup")
        sub.setObjectName("SubHeaderLabel")
        root.addWidget(header)
        root.addWidget(sub)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- linke Spalte: Tabellenliste + Datenraster ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QLabel("Tabellen"))
        self.table_list = QListWidget()
        self.table_list.currentItemChanged.connect(self._on_table_selected)
        left_layout.addWidget(self.table_list, stretch=1)

        left_layout.addWidget(QLabel("Datensätze"))

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Suche über alle Spalten…")
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self.search_edit)
        left_layout.addLayout(search_row)

        self.data_view = QTableView()
        self.data_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.data_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.data_view.horizontalHeader().setSectionsClickable(True)
        self.data_view.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        left_layout.addWidget(self.data_view, stretch=2)

        page_row = QHBoxLayout()
        self.btn_prev_page = QPushButton("◀ Zurück")
        self.btn_prev_page.clicked.connect(self._on_prev_page)
        self.page_label = QLabel("Seite 1")
        self.btn_next_page = QPushButton("Weiter ▶")
        self.btn_next_page.clicked.connect(self._on_next_page)
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["25", "50", "100", "250", "500"])
        self.page_size_combo.setCurrentText("100")
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        page_row.addWidget(self.btn_prev_page)
        page_row.addWidget(self.page_label)
        page_row.addWidget(self.btn_next_page)
        page_row.addWidget(QLabel("pro Seite:"))
        page_row.addWidget(self.page_size_combo)
        left_layout.addLayout(page_row)

        row_btns = QHBoxLayout()
        self.btn_new_row = QPushButton("+ Neue Zeile")
        self.btn_delete_row = QPushButton("Zeile löschen")
        self.btn_delete_row.setObjectName("DangerButton")
        self.btn_new_row.clicked.connect(self._on_new_row)
        self.btn_delete_row.clicked.connect(self._on_delete_row)
        row_btns.addWidget(self.btn_new_row)
        row_btns.addWidget(self.btn_delete_row)
        left_layout.addLayout(row_btns)

        # --- mittlere Spalte: dynamisches Formular ---
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)
        self.form_group = QGroupBox("Formular (wähle eine Tabelle / Zeile)")
        self.form_scroll = QScrollArea()
        self.form_scroll.setWidgetResizable(True)
        self.form_container = QWidget()
        self.form_layout = QFormLayout(self.form_container)
        self.form_scroll.setWidget(self.form_container)
        group_layout = QVBoxLayout(self.form_group)
        group_layout.addWidget(self.form_scroll)
        mid_layout.addWidget(self.form_group, stretch=1)

        save_row = QHBoxLayout()
        self.btn_save = QPushButton("💾  Speichern (mit Backup)")
        self.btn_save.setObjectName("PrimaryButton")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save.setEnabled(False)
        save_row.addWidget(self.btn_save)
        mid_layout.addLayout(save_row)

        # --- rechte Spalte: Live-SQL-Vorschau ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("Live-SQL-Vorschau"))
        self.sql_preview = QTextEdit()
        self.sql_preview.setReadOnly(True)
        self.sql_preview.setFont(QFont("Consolas", 11))
        right_layout.addWidget(self.sql_preview, stretch=1)

        splitter.addWidget(left_widget)
        splitter.addWidget(mid_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([380, 460, 440])

        root.addWidget(splitter, stretch=1)
        self.setCentralWidget(central)

        self.setStatusBar(QStatusBar())
        self.setStyleSheet(PANDORA_QSS)

    def _build_actions(self):
        """Legt alle QActions einmal zentral an, damit Menü und Toolbar
        dieselben Objekte (inkl. Enabled-Status) teilen."""

        self.act_open_sqlite = QAction("📂 Datei öffnen (SQLite/SQL)…", self)
        self.act_open_sqlite.setShortcut("Ctrl+O")
        self.act_open_sqlite.triggered.connect(self._on_open_sqlite)

        self.act_connect_mariadb = QAction("🔌 Mit MariaDB verbinden…", self)
        self.act_connect_mariadb.setShortcut("Ctrl+Shift+O")
        self.act_connect_mariadb.triggered.connect(self._on_connect_mariadb)

        self.act_save = QAction("💾 Speichern", self)
        self.act_save.setShortcut("Ctrl+S")
        self.act_save.triggered.connect(self._on_save)
        self.act_save.setEnabled(False)

        self.act_save_as = QAction("💾 Speichern unter…", self)
        self.act_save_as.setShortcut("Ctrl+Shift+S")
        self.act_save_as.triggered.connect(self._on_save_as)

        self.act_backup_now = QAction("🛡 Backup jetzt", self)
        self.act_backup_now.triggered.connect(self._on_manual_backup)

        self.act_refresh = QAction("🔄 Neu laden", self)
        self.act_refresh.setShortcut("F5")
        self.act_refresh.triggered.connect(self._on_refresh)

        self.act_quit = QAction("Beenden", self)
        self.act_quit.setShortcut("Ctrl+Q")
        self.act_quit.triggered.connect(self.close)

        self.act_manage_schema = QAction("🧩 Tabellen verwalten…", self)
        self.act_manage_schema.triggered.connect(self._on_manage_schema)

        self.act_export_csv = QAction("⬇ Als CSV exportieren…", self)
        self.act_export_csv.triggered.connect(self._on_export_csv)

        self.act_import_csv = QAction("⬆ CSV importieren…", self)
        self.act_import_csv.triggered.connect(self._on_import_csv)

    def _build_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&Datei")
        file_menu.addAction(self.act_open_sqlite)
        file_menu.addAction(self.act_connect_mariadb)
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_backup_now)
        file_menu.addAction(self.act_refresh)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        schema_menu = menu_bar.addMenu("&Schema")
        schema_menu.addAction(self.act_manage_schema)

        data_menu = menu_bar.addMenu("&Daten")
        data_menu.addAction(self.act_export_csv)
        data_menu.addAction(self.act_import_csv)

    def _build_toolbar(self):
        toolbar = QToolBar("Hauptwerkzeuge")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(self.act_open_sqlite)
        toolbar.addAction(self.act_connect_mariadb)
        toolbar.addSeparator()
        toolbar.addAction(self.act_save)
        toolbar.addAction(self.act_save_as)
        toolbar.addSeparator()
        toolbar.addAction(self.act_backup_now)
        toolbar.addAction(self.act_refresh)
        toolbar.addSeparator()
        toolbar.addAction(self.act_manage_schema)
        toolbar.addAction(self.act_export_csv)
        toolbar.addAction(self.act_import_csv)

    # ------------------------------------------------------------------
    # Backend-Erkennung
    # ------------------------------------------------------------------

    def _refresh_backend_status(self):
        info = DatabaseManager.autodetect()
        parts = []
        if info["mariadb_socket_open"] or info["mariadb_service_active"]:
            parts.append("MariaDB erkannt (läuft lokal)")
        else:
            parts.append("Kein lokaler MariaDB-Server erkannt")
        if not info["pymysql_installed"]:
            parts.append("pymysql fehlt – MariaDB-Verbindung eingeschränkt")
        self.statusBar().showMessage(" | ".join(parts))

    # ------------------------------------------------------------------
    # Verbindungen öffnen
    # ------------------------------------------------------------------

    def _on_manage_schema(self):
        if self.db.backend is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Datenbank öffnen/verbinden.")
            return
        dialog = SchemaManagerDialog(self.db, self)
        dialog.exec()
        self._load_tables()
        if self.current_table is not None:
            try:
                self.current_table = self.db.get_schema(self.current_table.name)
                self._reload_data_page()
            except DBBackendError:
                self.current_table = None

    def _on_export_csv(self):
        if self.current_table is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Tabelle auswählen.")
            return
        target, _ = QFileDialog.getSaveFileName(
            self, "Tabelle als CSV exportieren", f"{self.current_table.name}.csv", "CSV (*.csv)"
        )
        if not target:
            return
        try:
            n = self.db.export_table_to_csv(self.current_table.name, Path(target))
            self.statusBar().showMessage(f"{n} Zeilen exportiert nach {target}")
            QMessageBox.information(self, "Exportiert", f"{n} Zeilen wurden nach\n{target}\nexportiert.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Export", str(e))

    def _on_import_csv(self):
        if self.current_table is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Tabelle auswählen.")
            return
        source, _ = QFileDialog.getOpenFileName(self, "CSV importieren", "", "CSV (*.csv)")
        if not source:
            return
        try:
            self._run_backup()
            n = self.db.import_csv_into_table(self.current_table.name, Path(source))
            self.statusBar().showMessage(f"{n} Zeilen importiert (Backup wurde angelegt).")
            QMessageBox.information(self, "Importiert", f"{n} Zeilen wurden importiert.")
            self._reload_data_page()
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Import", str(e))

    def _on_open_sqlite(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Datenbank öffnen", "",
            "SQLite/SQL (*.db *.sqlite *.sqlite3 *.sql);;"
            "SQLite DB (*.db *.sqlite *.sqlite3);;"
            "SQL-Skript (*.sql);;"
            "Alle Dateien (*)"
        )
        if not path:
            return
        try:
            self.db.close()
            if Path(path).suffix.lower() == ".sql":
                self.db.open_sql_file(path)
                if self.db.sql_was_converted:
                    self.statusBar().showMessage(
                        f"Verbunden: SQL-Skript – {Path(path).name} "
                        "(MariaDB/MySQL-Dialekt erkannt und automatisch nach SQLite konvertiert)"
                    )
                    QMessageBox.information(
                        self, "Automatisch konvertiert",
                        "Die Datei war im MariaDB/MySQL-Format (z.B. ENGINE=, AUTO_INCREMENT, "
                        "ON DUPLICATE KEY UPDATE). Sie wurde automatisch in SQLite-kompatibles "
                        "SQL übersetzt. Bitte das Ergebnis kurz prüfen."
                    )
                else:
                    self.statusBar().showMessage(
                        f"Verbunden: SQL-Skript – {Path(path).name} "
                        f"(Änderungen werden beim Speichern in die .sql-Datei zurückgeschrieben)"
                    )
            else:
                self.db.open_sqlite(path)
                self.statusBar().showMessage(f"Verbunden: SQLite – {Path(path).name}")
            self.current_table = None
            self._load_tables()
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))

    def _on_connect_mariadb(self):
        dialog = MariaDBConnectDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dialog.values()
        try:
            self.db.close()
            self.db.connect_mariadb(**vals)
            self.current_table = None
            self._load_tables()
            self.statusBar().showMessage(f"Verbunden: MariaDB – {vals['database']}@{vals['host']}")
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Verbindungsfehler", str(e))

    def _on_refresh(self):
        if self.db.backend is None:
            return
        self._load_tables()
        if self.current_table is not None:
            self._reload_data_page()

    def _load_tables(self):
        self.table_list.clear()
        try:
            tables = self.db.list_tables()
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))
            return
        for t in tables:
            self.table_list.addItem(QListWidgetItem(t))

    # ------------------------------------------------------------------
    # Tabelle & Zeilen
    # ------------------------------------------------------------------

    def _on_table_selected(self, current: QListWidgetItem, _previous):
        if current is None:
            return
        table_name = current.text()
        try:
            self.current_table = self.db.get_schema(table_name)
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))
            return

        self.current_page = 0
        self.sort_col = None
        self.sort_dir = "ASC"
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self.search_text = ""

        self.form_group.setTitle(f"Formular – Tabelle „{table_name}“")
        self._reload_data_page()
        self._build_form_for_table(self.current_table, values=None)

    def _reload_data_page(self):
        if self.current_table is None:
            return
        table_name = self.current_table.name
        colnames_all = [c.name for c in self.current_table.columns]
        try:
            self.total_rows = self.db.count_rows(table_name, colnames_all, self.search_text)
            offset = self.current_page * self.page_size
            colnames, rows = self.db.get_rows_paginated(
                table_name, colnames_all, self.page_size, offset,
                self.search_text, self.sort_col, self.sort_dir,
            )
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))
            return

        model = QStandardItemModel(len(rows), len(colnames))
        model.setHorizontalHeaderLabels(colnames)
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                model.setItem(r, c, QStandardItem("" if val is None else str(val)))
        self.data_view.setModel(model)
        self.data_view.selectionModel().selectionChanged.connect(self._on_row_selected)

        total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
        self.page_label.setText(f"Seite {self.current_page + 1} / {total_pages} ({self.total_rows} Zeilen)")
        self.btn_prev_page.setEnabled(self.current_page > 0)
        self.btn_next_page.setEnabled(self.current_page + 1 < total_pages)

    def _on_search_changed(self, text: str):
        self.search_text = text
        self.current_page = 0
        self._reload_data_page()

    def _on_header_clicked(self, section_index: int):
        model = self.data_view.model()
        if model is None:
            return
        col_name = model.headerData(section_index, Qt.Orientation.Horizontal)
        if self.sort_col == col_name:
            self.sort_dir = "DESC" if self.sort_dir == "ASC" else "ASC"
        else:
            self.sort_col = col_name
            self.sort_dir = "ASC"
        self._reload_data_page()

    def _on_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._reload_data_page()

    def _on_next_page(self):
        total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
        if self.current_page + 1 < total_pages:
            self.current_page += 1
            self._reload_data_page()

    def _on_page_size_changed(self, text: str):
        try:
            self.page_size = int(text)
        except ValueError:
            self.page_size = 100
        self.current_page = 0
        self._reload_data_page()

    def _on_row_selected(self, *_args):
        if self.current_table is None:
            return
        sel = self.data_view.selectionModel().selectedRows()
        if not sel:
            return
        row_idx = sel[0].row()
        model = self.data_view.model()
        colnames = [model.headerData(c, Qt.Orientation.Horizontal) for c in range(model.columnCount())]
        values = {colnames[c]: model.item(row_idx, c).text() for c in range(model.columnCount())}

        pk_col = next((c.name for c in self.current_table.columns if c.primary_key), None)
        self.current_pk_col = pk_col
        self.current_pk_value = values.get(pk_col) if pk_col else None
        self.pending_is_insert = False

        self._build_form_for_table(self.current_table, values=values)

    def _on_new_row(self):
        if self.current_table is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Tabelle auswählen.")
            return
        self.pending_is_insert = True
        self.current_pk_value = None
        self._build_form_for_table(self.current_table, values=None)

    def _on_delete_row(self):
        if self.current_table is None or self.current_pk_col is None or self.current_pk_value is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Zeile in der Tabelle auswählen.")
            return
        confirm = QMessageBox.question(
            self, "Zeile löschen",
            f"Zeile mit {self.current_pk_col} = {self.current_pk_value} wirklich löschen?"
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self._run_backup()
            sql = self.db.build_delete_sql(self.current_table.name, self.current_pk_col, self.current_pk_value)
            self.db.execute(sql)
            self.statusBar().showMessage("Zeile gelöscht (Backup wurde angelegt).")
            self._reload_data_page()
            self._build_form_for_table(self.current_table, values=None)
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler", str(e))

    # ------------------------------------------------------------------
    # Dynamisches Formular
    # ------------------------------------------------------------------

    def _clear_form(self):
        while self.form_layout.rowCount():
            self.form_layout.removeRow(0)
        self.field_widgets.clear()
        self.field_errors.clear()

    def _build_form_for_table(self, table: TableInfo, values: Optional[dict]):
        self._clear_form()
        for col in table.columns:
            field_box = QVBoxLayout()

            if col.foreign_key is not None:
                ref_table, ref_col = col.foreign_key
                combo = QComboBox()
                combo.setEditable(False)
                try:
                    label_map = self.db.get_label_map(ref_table, ref_col)
                except DBBackendError:
                    label_map = {}
                if col.nullable:
                    combo.addItem("(leer)", None)
                current_value = values.get(col.name, "") if values is not None else ""
                selected_index = 0
                for i, (pk_val, label) in enumerate(label_map.items(), start=(1 if col.nullable else 0)):
                    combo.addItem(label, pk_val)
                    if values is not None and str(current_value) == str(pk_val):
                        selected_index = i
                combo.setCurrentIndex(selected_index)
                if col.primary_key and values is not None:
                    combo.setEnabled(False)
                combo.currentIndexChanged.connect(self._on_field_changed)
                widget = combo
            else:
                edit = QLineEdit()
                if values is not None:
                    edit.setText(values.get(col.name, "") or "")
                if col.primary_key and values is not None:
                    edit.setReadOnly(True)  # Primärschlüssel bei bestehender Zeile nicht änderbar
                edit.textChanged.connect(self._on_field_changed)
                widget = edit

            placeholder_hint = f"{col.raw_type}" + (" · PK" if col.primary_key else "") + \
                                (" · FK" if col.foreign_key else "") + \
                                ("" if col.nullable else " · Pflichtfeld")
            if isinstance(widget, QLineEdit):
                widget.setPlaceholderText(placeholder_hint)

            error_label = QLabel("" if col.foreign_key is None else "")
            error_label.setStyleSheet("color: #ff2a6d; font-size: 10px;")

            field_box.addWidget(widget)
            hint_label = QLabel(placeholder_hint)
            hint_label.setStyleSheet("color: #445; font-size: 10px;")
            field_box.addWidget(hint_label)
            field_box.addWidget(error_label)
            wrapper = QWidget()
            wrapper.setLayout(field_box)

            label_text = f"{col.name} ({col.data_type})"
            self.form_layout.addRow(label_text, wrapper)

            self.field_widgets[col.name] = widget
            self.field_errors[col.name] = error_label

        self._validate_form()

    def _field_text(self, widget: QWidget) -> str:
        """Liest den aktuellen Rohwert eines Formularfeldes, unabhängig vom Widget-Typ."""
        if isinstance(widget, QComboBox):
            data = widget.currentData()
            return "" if data is None else str(data)
        return widget.text()

    def _on_field_changed(self, *_args):
        self._validate_form()

    def _validate_form(self):
        if self.current_table is None:
            return
        raw_values = {name: self._field_text(widget) for name, widget in self.field_widgets.items()}
        results = validate_row(raw_values, self.current_table.columns)

        all_valid = True
        converted = {}
        for col in self.current_table.columns:
            valid, error_msg, value = results[col.name]
            widget = self.field_widgets[col.name]
            error_label = self.field_errors[col.name]
            if isinstance(widget, QLineEdit):
                widget.setProperty("invalid", not valid)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
            error_label.setText(error_msg or "")
            if not valid:
                all_valid = False
            converted[col.name] = value

        self.btn_save.setEnabled(all_valid)
        if hasattr(self, "act_save"):
            self.act_save.setEnabled(all_valid)
        self._update_sql_preview(converted, all_valid)

    def _update_sql_preview(self, converted: dict, all_valid: bool):
        if self.current_table is None or not all_valid:
            if not all_valid:
                self.sql_preview.setPlainText("-- Formular enthält ungültige Werte --")
            return

        table_name = self.current_table.name
        pk_col = next((c.name for c in self.current_table.columns if c.primary_key), None)

        if self.pending_is_insert or self.current_pk_value is None:
            sql = self.db.build_insert_sql(table_name, converted)
        else:
            changes = {k: v for k, v in converted.items() if k != pk_col}
            sql = self.db.build_update_sql(table_name, pk_col, self.current_pk_value, changes)

        self.sql_preview.setPlainText(sql)

    # ------------------------------------------------------------------
    # Speichern & Backup
    # ------------------------------------------------------------------

    def _run_backup(self):
        if self.db.backend == "sqlite" and self.db.sql_source_path:
            path = backup_sql_source(self.db.sql_source_path)
            self.statusBar().showMessage(f"Backup angelegt: {path}")
        elif self.db.backend == "sqlite" and self.db.sqlite_path:
            path = backup_sqlite(self.db.sqlite_path)
            self.statusBar().showMessage(f"Backup angelegt: {path}")
        elif self.db.backend == "mariadb" and self.db.mariadb_params:
            out_dir = Path.home() / "pandora_mariadb_backups"
            path = backup_mariadb(
                self.db.mariadb_params["host"], self.db.mariadb_params["user"],
                "", self.db.mariadb_params["database"],
                self.db.mariadb_params["port"], out_dir,
            )
            if path:
                self.statusBar().showMessage(f"Backup angelegt: {path}")
            else:
                self.statusBar().showMessage(
                    "Warnung: mysqldump nicht verfügbar – kein MariaDB-Backup erstellt."
                )

    def _on_manual_backup(self):
        if self.db.backend is None:
            QMessageBox.information(self, "Hinweis", "Keine aktive Verbindung.")
            return
        self._run_backup()

    def _on_save_as(self):
        """Speichert den aktuellen Datenbankstand als Kopie unter neuem Pfad,
        ohne die laufende Sitzung zu wechseln."""
        if self.db.backend is None:
            QMessageBox.information(self, "Hinweis", "Keine aktive Verbindung.")
            return

        if self.db.backend == "sqlite":
            target, _ = QFileDialog.getSaveFileName(
                self, "Speichern unter", "",
                "SQL-Dump (*.sql);;SQLite DB (*.db *.sqlite *.sqlite3);;Alle Dateien (*)"
            )
            if not target:
                return
            try:
                self.db.conn.commit()
                if target.lower().endswith(".sql"):
                    self.db.dump_to_sql_file(target)
                else:
                    import shutil
                    shutil.copy2(self.db.sqlite_path, Path(target))
                self.statusBar().showMessage(f"Kopie gespeichert unter: {target}")
                QMessageBox.information(self, "Gespeichert", f"Kopie gespeichert unter:\n{target}")
            except (OSError, DBBackendError) as e:
                QMessageBox.critical(self, "Fehler", f"Konnte Kopie nicht speichern: {e}")

        elif self.db.backend == "mariadb":
            target, _ = QFileDialog.getSaveFileName(
                self, "MariaDB-Dump speichern unter", "", "SQL-Dump (*.sql);;Alle Dateien (*)"
            )
            if not target:
                return
            out_dir = Path(target).parent
            result = backup_mariadb(
                self.db.mariadb_params["host"], self.db.mariadb_params["user"],
                "", self.db.mariadb_params["database"],
                self.db.mariadb_params["port"], out_dir,
            )
            if result:
                result.rename(target)
                self.statusBar().showMessage(f"Dump gespeichert unter: {target}")
                QMessageBox.information(self, "Gespeichert", f"Dump gespeichert unter:\n{target}")
            else:
                QMessageBox.warning(
                    self, "Nicht möglich",
                    "mysqldump ist nicht verfügbar. Bitte 'mariadb-client' installieren."
                )

    def _on_save(self):
        if self.current_table is None:
            return
        sql = self.sql_preview.toPlainText()
        if not sql or sql.startswith("--"):
            QMessageBox.warning(self, "Nicht speicherbar", "Bitte zuerst Formular gültig ausfüllen.")
            return
        try:
            self._run_backup()
            self.db.execute(sql)
            if self.db.sql_source_path is not None:
                self.db.save_to_sql_source()
                QMessageBox.information(
                    self, "Gespeichert",
                    f"Änderungen wurden gespeichert und in\n{self.db.sql_source_path.name}\n"
                    "zurückgeschrieben."
                )
            else:
                QMessageBox.information(self, "Gespeichert", "Änderungen wurden gespeichert.")
            self.pending_is_insert = False
            self._reload_data_page()
            self._build_form_for_table(self.current_table, values=None)
        except DBBackendError as e:
            QMessageBox.critical(self, "Fehler beim Speichern", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Speichern", str(e))
