@echo off
setlocal enabledelayedexpansion

:: ================================================================
::  Pandora Script Editor - Build-Skript
::  Nutzt das System-Python (z.B. 3.14.3) direkt ueber
::  "python -m PyInstaller" - keine virtuelle Umgebung.
::  Erstellt fuer den Haupteditor und alle Werkzeuge unter
::  "Pandor Script Editor Tools\" jeweils eine eigenstaendige
::  --onedir PyInstaller-Ausgabe (EXE + Ordner mit Abhaengigkeiten),
::  wobei die Ordnerstruktur des Repos unter dist\ 1:1 gespiegelt
::  wird, z.B.:
::
::    dist\pandora_script_editor\PandoraScriptEditor\PandoraScriptEditor.exe
::    dist\Pandor Script Editor Tools\pandora_crypto_tool\PandoraCryptoTool\PandoraCryptoTool.exe
::    dist\Pandor Script Editor Tools\pandora_md_editor\PandoraMdEditor\...exe
:: ================================================================

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "TOOLS=%ROOT%\Pandor Script Editor Tools"
set "DIST=%ROOT%\dist"
set "BUILDDIR=%ROOT%\build"
set "SPECDIR=%ROOT%\build\specs"

echo.
echo ================================================================
echo   Pandora Script Editor - Build-Setup
echo ================================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python wurde nicht im PATH gefunden.
    echo          Bitte Python 3.x installieren und erneut versuchen.
    pause
    exit /b 1
)

echo [Info] Verwende folgendes Python:
python --version

echo.
echo [1/4] Aktualisiere pip und installiere PyInstaller ...
python -m pip install --upgrade pip
python -m pip install pyinstaller
if errorlevel 1 (
    echo [FEHLER] Installation von PyInstaller fehlgeschlagen.
    pause
    exit /b 1
)

echo.
echo [2/4] Installiere Kern- und optionale Abhaengigkeiten ...
python -m pip install "PyQt6>=6.6"
if errorlevel 1 (
    echo [FEHLER] PyQt6-Installation fehlgeschlagen - Build wird abgebrochen.
    pause
    exit /b 1
)
:: Pflicht fuer den Pandora MD Editor (Live-Vorschau/PDF-Export)
python -m pip install "PyQt6-WebEngine>=6.6.0"
if errorlevel 1 (
    echo [FEHLER] PyQt6-WebEngine-Installation fehlgeschlagen - Build wird abgebrochen.
    pause
    exit /b 1
)
call :install_optional qtawesome
call :install_optional jedi
call :install_optional pyflakes
call :install_optional jsonschema
call :install_optional PyYAML
call :install_optional yara-python
call :install_optional PyMySQL
call :install_optional markdown
call :install_optional Pygments
call :install_optional matplotlib

echo.
echo [3/4] Baue ausfuehrbare Dateien (--onedir) ...

call :has_module qtawesome QTA
call :has_module jedi JEDI
call :has_module parso PARSO
call :has_module jsonschema JSONSCHEMA
call :has_module yara YARA

set "MAIN_OPTS="
if defined QTA set "MAIN_OPTS=!MAIN_OPTS! --collect-all qtawesome"
if defined JEDI set "MAIN_OPTS=!MAIN_OPTS! --collect-all jedi"
if defined PARSO set "MAIN_OPTS=!MAIN_OPTS! --collect-all parso"

set "YAML_OPTS="
if defined JSONSCHEMA set "YAML_OPTS=!YAML_OPTS! --collect-all jsonschema"
if defined YARA set "YAML_OPTS=!YAML_OPTS! --collect-all yara"

:: Assets (Icons/Logos), die per os.path/Path relativ zur Quelldatei
:: geladen werden und daher explizit mit ins onedir-Bundle muessen.
set "MD_OPTS=--collect-all markdown --collect-all pygments --add-data "%TOOLS%\pandora_md_editor\assets;assets""
set "PCB_OPTS=--collect-all matplotlib --add-data "%TOOLS%\pandora_pcb_editor\assets;assets""

:: :build Parameter:
::   %1 = Name der EXE / des Ausgabeordners
::   %2 = Pfad zum Einstiegsskript
::   %3 = Arbeitsverzeichnis (fuer lokale ui\/core\ Imports der Werkzeuge)
::   %4 = relativer Zielordner unter dist\, spiegelt die Repo-Struktur
::   %5 = zusaetzliche PyInstaller-Optionen (z.B. --collect-all)

call :build "PandoraScriptEditor"         "%ROOT%\pandora_script_editor.py"                                 "%ROOT%"                                          "pandora_script_editor"                                "!MAIN_OPTS!"
call :build "PandoraJsonYamlEditor"       "%TOOLS%\json yaml editor\jy_editor.py"                           "%TOOLS%\json yaml editor"                        "Pandor Script Editor Tools\json yaml editor"          "!YAML_OPTS!"
call :build "PandoraSqlConfigEditor"      "%TOOLS%\pandora_sql_config_editor\main.py"                       "%TOOLS%\pandora_sql_config_editor"               "Pandor Script Editor Tools\pandora_sql_config_editor" ""
call :build "PandoraEnvDependencyManager" "%TOOLS%\pandora_env_dependency_manager\pandora_env_dependency_manager.py" "%TOOLS%\pandora_env_dependency_manager"   "Pandor Script Editor Tools\pandora_env_dependency_manager" ""
call :build "PandoraWebEditor"            "%TOOLS%\pandora_web_editor\pandora_web_editor.py"                "%TOOLS%\pandora_web_editor"                      "Pandor Script Editor Tools\pandora_web_editor"        ""
call :build "PandoraCryptoTool"           "%TOOLS%\pandora_crypto_tool\pandora_crypto_tool.py"              "%TOOLS%\pandora_crypto_tool"                     "Pandor Script Editor Tools\pandora_crypto_tool"       ""
call :build "PandoraUiAssetColorStudio"   "%TOOLS%\pandora_ui_asset_color_studio\pandora_ui_asset_color_studio.py" "%TOOLS%\pandora_ui_asset_color_studio"    "Pandor Script Editor Tools\pandora_ui_asset_color_studio" ""
call :build "PandoraUiForge"              "%TOOLS%\pandora_ui_forge\pandora_ui_forge.py"                    "%TOOLS%\pandora_ui_forge"                        "Pandor Script Editor Tools\pandora_ui_forge"          ""
call :build "PandoraMdEditor"             "%TOOLS%\pandora_md_editor\main.py"                               "%TOOLS%\pandora_md_editor"                       "Pandor Script Editor Tools\pandora_md_editor"         "!MD_OPTS!"
call :build "PandoraStructureCreator"     "%TOOLS%\pandora_structure_creator\main.py"                       "%TOOLS%\pandora_structure_creator"               "Pandor Script Editor Tools\pandora_structure_creator" ""
call :build "PandoraPcbEditor"            "%TOOLS%\pandora_pcb_editor\pandora_pcb_editor.py"                "%TOOLS%\pandora_pcb_editor"                      "Pandor Script Editor Tools\pandora_pcb_editor"        "!PCB_OPTS!"
call :build "PandoraSnippetVault"         "%TOOLS%\pandora_snippet_vault\pandora_snippet_vault.py"          "%TOOLS%\pandora_snippet_vault"                   "Pandor Script Editor Tools\pandora_snippet_vault"     ""

echo.
echo [4/4] Fertig.
echo.
echo Alle Programmordner (onedir, jeweils mit eigener .exe) liegen unter
echo   %DIST%
echo in der gleichen Ordnerstruktur wie das Repo, z.B.:
echo   dist\pandora_script_editor\PandoraScriptEditor\PandoraScriptEditor.exe
echo   dist\Pandor Script Editor Tools\pandora_md_editor\PandoraMdEditor\PandoraMdEditor.exe
echo   dist\Pandor Script Editor Tools\pandora_pcb_editor\PandoraPcbEditor\PandoraPcbEditor.exe
echo.
pause
exit /b 0

:: ================================================================
:: Subroutinen
:: ================================================================

:install_optional
python -m pip install %~1
if errorlevel 1 (
    echo   [Hinweis] Optionales Paket "%~1" konnte nicht installiert werden - wird uebersprungen.
) else (
    echo   [OK] %~1
)
exit /b 0

:has_module
:: %1 = zu pruefendes Modul, %2 = Name der Ergebnisvariable
python -c "import %~1" >nul 2>&1
if not errorlevel 1 set "%~2=1"
exit /b 0

:build
:: %1 = Name der EXE / des Ausgabeordners
:: %2 = Pfad zum Einstiegsskript
:: %3 = Arbeitsverzeichnis (fuer lokale ui\/core\ Imports der Werkzeuge)
:: %4 = relativer Zielordner unter dist\ (spiegelt Repo-Struktur)
:: %5 = zusaetzliche PyInstaller-Optionen
set "TARGETDIST=%DIST%\%~4"
echo.
echo   --------------------------------------------------------------
echo   Baue: %~1   -^>   dist\%~4\%~1\%~1.exe
echo   --------------------------------------------------------------
if not exist "%TARGETDIST%" mkdir "%TARGETDIST%"
pushd "%~3"
python -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --name "%~1" ^
    --distpath "%TARGETDIST%" ^
    --workpath "%BUILDDIR%\%~4\%~1" ^
    --specpath "%SPECDIR%\%~4" ^
    --paths "%~3" ^
    %~5 "%~2"
if errorlevel 1 (
    echo   [FEHLER] Build von %~1 fehlgeschlagen - siehe Ausgabe oben.
) else (
    echo   [OK] %TARGETDIST%\%~1\%~1.exe
)
popd
exit /b 0
