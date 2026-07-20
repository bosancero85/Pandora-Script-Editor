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

## 📦 Installation

```bash
git clone https://github.com/<dein-benutzername>/pandora-script-editor.git
cd pandora-script-editor
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Nur `PyQt6` ist zwingend erforderlich. `qtawesome`, `pyflakes` und `jedi` sind optional — ohne sie läuft der Editor weiter, nur mit eingeschränkten Komfortfunktionen (siehe [requirements.txt](requirements.txt)).

## 🚀 Nutzung

```bash
python3 pandora_script_editor.py
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
