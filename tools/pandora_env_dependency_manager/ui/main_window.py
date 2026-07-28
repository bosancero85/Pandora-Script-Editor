"""
Pandora® Environment & Dependency Manager - UI: MainWindow + Tabs.

Drei Reiter, jeweils dünne UI-Schicht über der Core-Logik in
`core/venv_manager.py`, `core/package_installer.py` und
`core/dependency_overview.py`:

  1. Virtualenv Control     - venvs erstellen, auflisten, aktivieren, löschen
  2. Package Installer      - pip/npm install & uninstall mit Live-Ausgabe
  3. Abhängigkeits-Übersicht - installierte Pakete filtern & exportieren

Installationen/Deinstallationen laufen über `QProcess` (nicht-blockierend),
damit die Oberfläche auf dem Raspberry Pi 4B während längerer pip/npm-
Operationen responsiv bleibt.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core import dependency_overview as do
from core import package_installer as pi
from core import venv_manager as vm
from ui.style import PANDORA_QSS

APP_TITLE = "Pandora® | Environment & Dependency Manager"


def _copy_to_clipboard(text: str, status_bar: QStatusBar = None, label: str = "Wert"):
    QApplication.clipboard().setText(text)
    if status_bar is not None:
        status_bar.showMessage(f"{label} in Zwischenablage kopiert.", 2500)


class SharedState:
    """Hält die aktuell 'aktivierte' venv, damit Tab 2/3 sie gemeinsam nutzen."""

    def __init__(self):
        self.active_venv: Path | None = None
        self.active_npm_project: Path | None = None


# ------------------------------------------------------------------
# Tab 1: Virtualenv Control
# ------------------------------------------------------------------
class VirtualenvControlTab(QWidget):
    def __init__(self, status_bar: QStatusBar, state: SharedState):
        super().__init__()
        self._status_bar = status_bar
        self._state = state
        self._root = vm.DEFAULT_VENV_ROOT
        self._root.mkdir(parents=True, exist_ok=True)

        header = QLabel("Virtualenv Control")
        header.setObjectName("HeaderLabel")
        sub = QLabel(
            "Python-venvs erstellen, auflisten und als 'aktiv' markieren - "
            "der Package Installer und die Abhängigkeits-Übersicht nutzen "
            "dann automatisch diese Umgebung."
        )
        sub.setObjectName("SubHeaderLabel")

        root_row = QHBoxLayout()
        self.root_edit = QLineEdit(str(self._root))
        self.root_edit.setReadOnly(True)
        change_root_btn = QPushButton("Anderes Verzeichnis...")
        change_root_btn.clicked.connect(self._choose_root)
        root_row.addWidget(QLabel("venv-Wurzelverzeichnis:"))
        root_row.addWidget(self.root_edit, 1)
        root_row.addWidget(change_root_btn)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Python-Version", "Größe", "Aktiv"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        actions_row = QHBoxLayout()
        create_btn = QPushButton("Neue venv erstellen...")
        create_btn.setObjectName("PrimaryButton")
        create_btn.clicked.connect(self._create_venv)
        activate_btn = QPushButton("Als aktiv setzen")
        activate_btn.clicked.connect(self._activate_selected)
        delete_btn = QPushButton("Löschen")
        delete_btn.clicked.connect(self._delete_selected)
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.clicked.connect(self._refresh)
        actions_row.addWidget(create_btn)
        actions_row.addWidget(activate_btn)
        actions_row.addWidget(delete_btn)
        actions_row.addWidget(refresh_btn)
        actions_row.addStretch(1)

        self.active_label = QLabel("Keine venv aktiv.")
        self.active_label.setObjectName("SuccessLabel")

        layout = QVBoxLayout()
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addLayout(root_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions_row)
        layout.addWidget(self.active_label)
        self.setLayout(layout)

        self._refresh()

    def _choose_root(self):
        directory = QFileDialog.getExistingDirectory(self, "venv-Wurzelverzeichnis wählen", str(self._root))
        if directory:
            self._root = Path(directory)
            self.root_edit.setText(str(self._root))
            self._refresh()

    def _refresh(self):
        infos = vm.discover_venvs(self._root)
        self.table.setRowCount(0)
        for info in infos:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(info.name))
            self.table.setItem(row, 1, QTableWidgetItem(info.python_version))
            self.table.setItem(row, 2, QTableWidgetItem(vm.human_readable_size(info.size_bytes)))
            is_active = self._state.active_venv == info.path
            active_item = QTableWidgetItem("✓" if is_active else "")
            self.table.setItem(row, 3, active_item)
        self._status_bar.showMessage(f"{len(infos)} venv(s) gefunden.", 2000)

    def _selected_path(self) -> Path | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        name = self.table.item(row, 0).text()
        return self._root / name

    def _create_venv(self):
        name, ok = QInputDialog.getText(self, "Neue venv", "Name der neuen venv:")
        if not ok or not name.strip():
            return
        target = self._root / name.strip()
        try:
            result = vm.create_venv(target, python_executable=sys.executable)
        except vm.VenvError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        if not result.ok:
            QMessageBox.critical(self, "venv-Erstellung fehlgeschlagen", result.stderr or "Unbekannter Fehler")
            return
        self._refresh()
        self._status_bar.showMessage(f"venv '{name.strip()}' erstellt.", 3000)

    def _activate_selected(self):
        path = self._selected_path()
        if path is None:
            return
        self._state.active_venv = path
        self.active_label.setText(f"Aktive venv: {path}")
        self._refresh()

    def _delete_selected(self):
        path = self._selected_path()
        if path is None:
            return
        confirm = QMessageBox.question(self, "venv löschen", f"venv '{path.name}' wirklich löschen?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            vm.delete_venv(path)
        except vm.VenvError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return
        if self._state.active_venv == path:
            self._state.active_venv = None
            self.active_label.setText("Keine venv aktiv.")
        self._refresh()


# ------------------------------------------------------------------
# Tab 2: Package Installer
# ------------------------------------------------------------------
class PackageInstallerTab(QWidget):
    def __init__(self, status_bar: QStatusBar, state: SharedState):
        super().__init__()
        self._status_bar = status_bar
        self._state = state
        self._process: QProcess | None = None

        header = QLabel("Package Installer")
        header.setObjectName("HeaderLabel")
        sub = QLabel(
            "Pakete für die aktive venv (pip) oder ein Node-Projekt (npm) "
            "nachladen - Ausgabe läuft live, ohne das Terminal zu öffnen."
        )
        sub.setObjectName("SubHeaderLabel")

        mode_row = QHBoxLayout()
        self.pip_radio = QRadioButton("Python (pip)")
        self.pip_radio.setChecked(True)
        self.npm_radio = QRadioButton("Node (npm)")
        self.pip_radio.toggled.connect(self._update_mode_visibility)
        mode_row.addWidget(self.pip_radio)
        mode_row.addWidget(self.npm_radio)
        mode_row.addStretch(1)

        self.venv_label = QLabel("Keine aktive venv (siehe Tab 'Virtualenv Control').")
        self.venv_label.setObjectName("SubHeaderLabel")

        npm_row = QHBoxLayout()
        self.npm_project_edit = QLineEdit()
        self.npm_project_edit.setPlaceholderText("Node-Projektverzeichnis (mit package.json)...")
        npm_browse_btn = QPushButton("Wählen...")
        npm_browse_btn.clicked.connect(self._choose_npm_project)
        npm_row.addWidget(self.npm_project_edit, 1)
        npm_row.addWidget(npm_browse_btn)

        self.package_edit = QLineEdit()
        self.package_edit.setPlaceholderText("Paketnamen, Komma- oder leerzeichengetrennt (z.B. requests flask==2.3.0)")

        options_row = QHBoxLayout()
        self.upgrade_check = QCheckBox("Upgrade (pip: --upgrade)")
        self.dev_check = QCheckBox("Dev-Abhängigkeit (npm: --save-dev)")
        self.dev_check.setVisible(False)
        self.system_override_check = QCheckBox("PEP-668-Schutz umgehen (--break-system-packages)")
        options_row.addWidget(self.upgrade_check)
        options_row.addWidget(self.dev_check)
        options_row.addWidget(self.system_override_check)
        options_row.addStretch(1)

        buttons_row = QHBoxLayout()
        install_btn = QPushButton("Installieren")
        install_btn.setObjectName("PrimaryButton")
        install_btn.clicked.connect(self._install)
        uninstall_btn = QPushButton("Deinstallieren")
        uninstall_btn.clicked.connect(self._uninstall)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self._cancel)
        buttons_row.addWidget(install_btn)
        buttons_row.addWidget(uninstall_btn)
        buttons_row.addWidget(cancel_btn)
        buttons_row.addStretch(1)

        self.output_edit = QPlainTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Ausgabe erscheint hier...")

        layout = QVBoxLayout()
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addLayout(mode_row)
        layout.addWidget(self.venv_label)
        layout.addLayout(npm_row)
        layout.addWidget(self.package_edit)
        layout.addLayout(options_row)
        layout.addLayout(buttons_row)
        layout.addWidget(self.output_edit, 1)
        self.setLayout(layout)

        self._update_mode_visibility()

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_venv_label()

    def _refresh_venv_label(self):
        if self._state.active_venv is not None:
            self.venv_label.setText(f"Aktive venv: {self._state.active_venv}")
        else:
            self.venv_label.setText("Keine aktive venv (siehe Tab 'Virtualenv Control').")

    def _update_mode_visibility(self):
        is_pip = self.pip_radio.isChecked()
        self.venv_label.setVisible(is_pip)
        self.npm_project_edit.setVisible(not is_pip)
        self.upgrade_check.setVisible(is_pip)
        self.system_override_check.setVisible(is_pip)
        self.dev_check.setVisible(not is_pip)
        if is_pip:
            self._refresh_venv_label()

    def _choose_npm_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Node-Projektverzeichnis wählen")
        if directory:
            self.npm_project_edit.setText(directory)
            self._state.active_npm_project = Path(directory)

    def _python_executable_for_pip(self) -> str | None:
        if self._state.active_venv is None:
            QMessageBox.warning(
                self, "Keine venv aktiv", "Bitte zuerst im Tab 'Virtualenv Control' eine venv aktivieren."
            )
            return None
        python_exe = vm.venv_python_executable(self._state.active_venv)
        if not python_exe.exists():
            QMessageBox.warning(self, "Fehler", f"Python-Interpreter nicht gefunden: {python_exe}")
            return None
        return str(python_exe)

    def _run_command(self, argv: list[str], cwd: str | None = None):
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            QMessageBox.information(self, "Läuft bereits", "Es läuft bereits ein Vorgang. Bitte warten oder abbrechen.")
            return

        self.output_edit.appendPlainText(f"$ {' '.join(argv)}\n")
        process = QProcess(self)
        if cwd:
            process.setWorkingDirectory(cwd)
        process.readyReadStandardOutput.connect(lambda: self._on_output(process))
        process.readyReadStandardError.connect(lambda: self._on_output(process))
        process.finished.connect(lambda code, _status: self._on_finished(code))
        self._process = process
        process.start(argv[0], argv[1:])
        self._status_bar.showMessage("Vorgang gestartet...", 2000)

    def _on_output(self, process: QProcess):
        stdout = bytes(process.readAllStandardOutput()).decode(errors="replace")
        stderr = bytes(process.readAllStandardError()).decode(errors="replace")
        if stdout:
            self.output_edit.appendPlainText(stdout)
        if stderr:
            self.output_edit.appendPlainText(stderr)

    def _on_finished(self, code: int):
        self.output_edit.appendPlainText(f"\n[Beendet mit Exit-Code {code}]\n")
        self._status_bar.showMessage(
            "Vorgang abgeschlossen." if code == 0 else "Vorgang mit Fehler beendet.", 3000
        )

    def _install(self):
        try:
            if self.pip_radio.isChecked():
                python_exe = self._python_executable_for_pip()
                if python_exe is None:
                    return
                argv = pi.build_pip_install_argv(
                    python_exe,
                    self.package_edit.text(),
                    upgrade=self.upgrade_check.isChecked(),
                    allow_system_override=self.system_override_check.isChecked(),
                )
                self._run_command(argv)
            else:
                project = self.npm_project_edit.text().strip()
                if not project:
                    QMessageBox.warning(self, "Fehler", "Bitte ein Node-Projektverzeichnis wählen.")
                    return
                argv = pi.build_npm_install_argv(self.package_edit.text(), dev=self.dev_check.isChecked())
                self._run_command(argv, cwd=project)
        except pi.PackageSpecError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))

    def _uninstall(self):
        try:
            if self.pip_radio.isChecked():
                python_exe = self._python_executable_for_pip()
                if python_exe is None:
                    return
                argv = pi.build_pip_uninstall_argv(
                    python_exe,
                    self.package_edit.text(),
                    allow_system_override=self.system_override_check.isChecked(),
                )
                self._run_command(argv)
            else:
                project = self.npm_project_edit.text().strip()
                if not project:
                    QMessageBox.warning(self, "Fehler", "Bitte ein Node-Projektverzeichnis wählen.")
                    return
                argv = pi.build_npm_uninstall_argv(self.package_edit.text())
                self._run_command(argv, cwd=project)
        except pi.PackageSpecError as exc:
            QMessageBox.warning(self, "Fehler", str(exc))

    def _cancel(self):
        if self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self.output_edit.appendPlainText("\n[Vom Nutzer abgebrochen]\n")


# ------------------------------------------------------------------
# Tab 3: Abhängigkeits-Übersicht
# ------------------------------------------------------------------
class DependencyOverviewTab(QWidget):
    def __init__(self, status_bar: QStatusBar, state: SharedState):
        super().__init__()
        self._status_bar = status_bar
        self._state = state
        self._process: QProcess | None = None
        self._packages: list[pi.PackageInfo] = []

        header = QLabel("Abhängigkeits-Übersicht")
        header.setObjectName("HeaderLabel")
        sub = QLabel(
            "Installierte Bibliotheken der aktiven venv (pip) oder des "
            "Node-Projekts (npm) auflisten, filtern und exportieren."
        )
        sub.setObjectName("SubHeaderLabel")

        mode_row = QHBoxLayout()
        self.pip_radio = QRadioButton("Python (pip)")
        self.pip_radio.setChecked(True)
        self.npm_radio = QRadioButton("Node (npm)")
        mode_row.addWidget(self.pip_radio)
        mode_row.addWidget(self.npm_radio)
        mode_row.addStretch(1)

        filter_row = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Nach Paketname filtern...")
        self.filter_edit.textChanged.connect(self._apply_filter)
        refresh_btn = QPushButton("Aktualisieren")
        refresh_btn.setObjectName("PrimaryButton")
        refresh_btn.clicked.connect(self._refresh)
        filter_row.addWidget(self.filter_edit, 1)
        filter_row.addWidget(refresh_btn)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Paket", "Version", "Quelle"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)

        export_row = QHBoxLayout()
        export_req_btn = QPushButton("Als requirements.txt exportieren")
        export_req_btn.clicked.connect(self._export_requirements)
        export_pkg_btn = QPushButton("Als package.json-Snippet exportieren")
        export_pkg_btn.clicked.connect(self._export_package_json)
        export_row.addWidget(export_req_btn)
        export_row.addWidget(export_pkg_btn)
        export_row.addStretch(1)

        self.export_preview = QPlainTextEdit()
        self.export_preview.setReadOnly(True)
        self.export_preview.setPlaceholderText("Export-Vorschau erscheint hier...")
        copy_export_btn = QPushButton("Export kopieren")
        copy_export_btn.clicked.connect(self._copy_export)

        layout = QVBoxLayout()
        layout.addWidget(header)
        layout.addWidget(sub)
        layout.addLayout(mode_row)
        layout.addLayout(filter_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(export_row)
        layout.addWidget(self.export_preview)
        layout.addWidget(copy_export_btn)
        self.setLayout(layout)

    def _refresh(self):
        try:
            if self.pip_radio.isChecked():
                if self._state.active_venv is None:
                    QMessageBox.warning(
                        self, "Keine venv aktiv", "Bitte zuerst im Tab 'Virtualenv Control' eine venv aktivieren."
                    )
                    return
                python_exe = str(vm.venv_python_executable(self._state.active_venv))
                argv = pi.build_pip_list_argv(python_exe)
                cwd = None
            else:
                if self._state.active_npm_project is None:
                    QMessageBox.warning(
                        self, "Kein Projekt", "Bitte zuerst im Tab 'Package Installer' ein Node-Projekt wählen."
                    )
                    return
                argv = pi.build_npm_list_argv()
                cwd = str(self._state.active_npm_project)

            import subprocess

            proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
            raw = proc.stdout or "[]"
            self._packages = (
                pi.parse_pip_list_json(raw) if self.pip_radio.isChecked() else pi.parse_npm_list_json(raw)
            )
        except (pi.PackageSpecError, OSError) as exc:
            QMessageBox.warning(self, "Fehler", str(exc))
            return

        self._apply_filter()
        self._status_bar.showMessage(f"{len(self._packages)} Paket(e) geladen.", 2500)

    def _apply_filter(self):
        filtered = do.filter_packages(self._packages, self.filter_edit.text())
        filtered = do.sort_packages(filtered, by="name")
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        for pkg in filtered:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(pkg.name))
            self.table.setItem(row, 1, QTableWidgetItem(pkg.version))
            self.table.setItem(row, 2, QTableWidgetItem(pkg.source))
        self.table.setSortingEnabled(True)

    def _export_requirements(self):
        pip_only = [p for p in self._packages if p.source == "pip"]
        self.export_preview.setPlainText(do.to_requirements_txt(pip_only))

    def _export_package_json(self):
        npm_only = [p for p in self._packages if p.source == "npm"]
        self.export_preview.setPlainText(do.to_package_json_dependencies_snippet(npm_only))

    def _copy_export(self):
        text = self.export_preview.toPlainText()
        if text:
            _copy_to_clipboard(text, self._status_bar, "Export")


# ------------------------------------------------------------------
# MainWindow
# ------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1150, 780)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Bereit.", 2000)

        state = SharedState()

        tabs = QTabWidget()
        tabs.addTab(VirtualenvControlTab(status_bar, state), "Virtualenv Control")
        tabs.addTab(PackageInstallerTab(status_bar, state), "Package Installer")
        tabs.addTab(DependencyOverviewTab(status_bar, state), "Abhängigkeits-Übersicht")
        self.setCentralWidget(tabs)


def run():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyleSheet(PANDORA_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
