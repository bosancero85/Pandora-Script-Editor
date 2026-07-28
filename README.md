# Pandora® Script Editor

Eine PyQt6-basierte Python-IDE mit integrierter Gemini-KI-Unterstützung, Live-Linting, Git-Integration und Split-Screen-Editing — entwickelt für den täglichen Gebrauch auf einem Raspberry Pi 4B (Kali Linux), läuft aber auf jedem System mit Python 3.10+ und PyQt6.

> Teil des **Pandora®**-Projekt-Universums von **AKI_SystemDown®**.

---
<p align="center">
  <img src="screenshot.png" alt="Pandora® Script Editor" width="600">
</p>
## ✨ Features

- **Code-Editor**
  Zeilennummern, Syntax-Highlighting für Python, Klammer-Matching, automatische Einrückung, Autovervollständigung (mit [jedi](https://github.com/davidhalter/jedi) für kontextbezogene Vorschläge, sonst Wortlisten-Fallback).
- **Live-Linting**
  Fehler und Warnungen in Echtzeit über [pyflakes](https://github.com/PyCQA/pyflakes) im Probleme-Panel.
- **Suchen & Ersetzen**
  Mit Groß-/Kleinschreibungs-Option, Umbruchsuche und automatischem Springen zum passenden Tab.
- **Split-Screen**
  Zwei Editor-Bereiche horizontal oder vertikal nebeneinander.
- **Projekt-Panel**
  Datei-Explorer mit Kontextmenü (neue Datei/Ordner, umbenennen, löschen).
- **Git-Integration**
  Status, Staging, Commit, Push, Pull direkt aus dem Editor — inklusive:
  - **Von URL klonen** — beliebiges Repository per HTTPS/SSH-URL klonen
  - **GitHub-Repos-Browser** — eigene GitHub-Repositories (auch private) über die GitHub-API auflisten und klonen (Personal Access Token erforderlich)
- **Gemini-KI-Integration**
  Chat- und Code-Modus mit Mehrdatei-Kontext (mehrere offene Dateien und/oder ein ganzer Ordner als Kontext auswählbar).
- **Interaktive Python-Konsole** zum direkten Ausführen von Code.
- **Ein-/ausklappbare Seitenleisten**
  `Strg+B` (links: Projekt/Git) und `Strg+Alt+B` (rechts: Gemini), wie in VS Code.
- **QtAwesome-Icon-Theme** mit Emoji-/Text-Fallback, falls `qtawesome` nicht installiert ist.

## Enthaltene Werkzeuge

| Werkzeug | Pfad | Kurzbeschreibung |
|---|---|---|
| **Haupteditor** | `pandora_script_editor.py` | Code-Editor mit Projekt-Sidebar, Git-Integration, AI-Panel, Vervollständigung (jedi/pyflakes) |
| JSON/YAML/YARA-Editor | `tools/pandora_json_yaml_yara_editor/` | Bearbeiten & Validieren von JSON-, YAML- und YARA-Dateien |
| SQL Config Editor & Validator | `tools/pandora_sql_config_editor/` | SQLite/MySQL-Konfigurationsverwaltung mit Validierung & Backup |
| Web Editor | `tools/pandora_web_editor/` | HTML/CSS/JS-Editor mit Live-Vorschau |
| Code Snippet Vault | `tools/pandora_snippet_vault/` | Snippet-Bibliothek mit Schnell-Einfügen (läuft in-process) |
| **Crypto & Encoding Utility** | `tools/pandora_crypto_tool/` | Encoder/Decoder, Hash/HMAC, JWT-Inspector, RegEx-Tester (siehe unten) |
| **UI Asset & Color Studio** | `tools/pandora_ui_asset_color_studio/` | Farb-Picker & Konverter (HEX/RGB/RGBA/QColor), Theming-Variablen-Manager, Icon & Asset Browser (siehe unten) |
| **Environment & Dependency Manager** | `tools/pandora_env_dependency_manager/` | Virtualenv Control, Package Installer (pip/npm), Abhängigkeits-Übersicht (siehe unten) |

Alle externen Werkzeuge werden aus dem Haupteditor über das Menü
**Werkzeuge** bzw. die Toolbar gestartet und laufen als eigenständiger
Prozess (Ausnahme: Snippet Vault, siehe Kommentar im Code).

## 📦 Installation

```bash
git clone <repo-url>
cd pandora-script-editor
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` unterscheidet zwischen Kern-Abhängigkeit (`PyQt6`) und
optionalen Paketen, die nur für einzelne Werkzeuge gebraucht werden
(`qtawesome`, `jedi`, `pyflakes`, `jsonschema`, `PyYAML`, `yara-python`,
`PyMySQL`).

## Start

```bash
python3 pandora_script_editor.py
```

Beim ersten Aufruf eines externen Werkzeugs (Menü **Werkzeuge**) fragt der
Editor einmalig nach dem Pfad zum jeweiligen Einstiegs-Skript (z.B.
`tools/pandora_crypto_tool/pandora_crypto_tool.py`) und merkt sich diesen
in `~/.pandora_script_editor.json`.

Jedes Tool lässt sich auch direkt und unabhängig vom Haupteditor starten,
z.B.:

```bash
python3 tools/pandora_crypto_tool/pandora_crypto_tool.py
```

## Projektstruktur

```
.
├── pandora_script_editor.py
├── requirements.txt
├── LICENSE
└── tools/
    ├── pandora_json_yaml_yara_editor/
    ├── pandora_snippet_vault/
    ├── pandora_sql_config_editor/
    │   ├── core/
    │   └── ui/
    ├── pandora_web_editor/
    ├── pandora_crypto_tool/
    │   ├── core/
    │   └── ui/
    ├── pandora_ui_asset_color_studio/
    │   ├── core/
    │   └── ui/
    └── pandora_env_dependency_manager/
        ├── core/
        └── ui/
```

### Wichtige Tastenkürzel

| Aktion                          | Kürzel         |
|----------------------------------|----------------|
| Linke Seitenleiste ein-/ausblenden | `Strg+B`     |
| Rechte Seitenleiste ein-/ausblenden | `Strg+Alt+B` |
| Suchen & Ersetzen                | `Strg+F`       |

### Gemini-KI einrichten

1. Rechte Seitenleiste öffnen (Gemini-Panel)
2. API-Key eintragen (kostenlos erhältlich über [Google AI Studio](https://aistudio.google.com/))
3. Kontext auswählen (optional): offene Dateien und/oder ein Ordner

### GitHub-Repositories einbinden

1. Git-Panel öffnen (linke Seitenleiste)
2. **„GitHub-Repos…“** klicken
3. [Personal Access Token](https://github.com/settings/tokens) eintragen (Scope `repo` genügt)
4. Repository auswählen → klonen

Sowohl der Gemini-API-Key als auch der GitHub-Token werden ausschließlich lokal in `~/.pandora_script_editor.json` gespeichert (siehe `.gitignore` — diese Datei wird nie versioniert).

## 🛠 Entwicklung

Das Projekt besteht bewusst aus einer einzigen Datei (`pandora_script_editor.py`), um es einfach auf einem Raspberry Pi zu deployen. Beiträge (Pull Requests) sind willkommen — bitte vorab ein Issue eröffnen, um größere Änderungen abzustimmen.

## 📄 Lizenz

Veröffentlicht unter der [MIT-Lizenz](LICENSE).

## 🏷 Branding

**Pandora®** und **AKI_SystemDown® ©2026** sind Teil der persönlichen Projekt-Markenidentität des Autors und erscheinen konsistent über alle zugehörigen Repositories hinweg.
