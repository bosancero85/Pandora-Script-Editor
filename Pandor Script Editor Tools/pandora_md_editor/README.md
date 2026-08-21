# Pandora® md Editor

Ein schlanker Split-Screen-Markdown-Editor im **Darkred**-Design – geschrieben mit
Python 3 und PyQt6. Links Eingabe (mit Syntax-Highlighting), rechts Live-Vorschau
als gerendertes HTML, inklusive PDF-Export.

by **AKI_SystemDown®** — Teil der Pandora-Projektreihe

## Features

- Zwei-Fenster-Ansicht (Splitter): `QTextEdit`-Editor links, `QWebEngineView`-Vorschau rechts
- Live-Rendering während des Tippens (entprellt, 150 ms)
- Markdown-Syntax-Highlighting im Editor (Überschriften, Fett/Kursiv, Code, Links, Listen, Zitate, `---`)
- Menüleiste & Toolbar: Neu, Öffnen, Speichern, Speichern unter, PDF-Export, HTML-Export, Beenden
- Markdown-Parsing über die `markdown`-Bibliothek (Extras: Tabellen, Fenced Code Blocks, `codehilite` für Code-Syntax-Highlighting im HTML, TOC, sane_lists, nl2br)
- PDF-Export direkt aus der gerenderten Vorschau (`QWebEnginePage.printToPdf`, A4)
- Zusätzlicher HTML-Export der gerenderten Ansicht
- Modernes Darkred-QSS-Theme, Logo im Fenster-Icon & Kopfzeile

## Projektstruktur

```
pandora_md_editor/
├── main.py            # Einstiegspunkt
├── editor.py           # Hauptfenster (Split-Screen, Datei-/PDF-Logik)
├── highlighter.py       # QSyntaxHighlighter für Markdown im Editor
├── theme.py             # Darkred-QSS + HTML/CSS-Vorlage für die Vorschau
├── requirements.txt
└── assets/
    ├── logo.png          # Fenster-Icon / Kopfzeilen-Logo
    └── aki_logo.gif       # Original-Logo-Datei
```

## Installation

```bash
pip install -r requirements.txt
```

oder einzeln:

```bash
pip install PyQt6 PyQt6-WebEngine markdown Pygments
```

> **Hinweis (Linux/Raspberry Pi):** `PyQt6-WebEngine` benötigt ggf. zusätzliche
> Systembibliotheken (Qt WebEngine/Chromium-Abhängigkeiten). Falls der Import
> fehlschlägt: `sudo apt install libnss3 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxkbcommon0`

## Ausführen

```bash
cd pandora_md_editor
python main.py
```

## Bedienung

| Aktion              | Shortcut     |
|---------------------|--------------|
| Neu                 | Strg+N       |
| Öffnen              | Strg+O       |
| Speichern           | Strg+S       |
| Speichern unter     | Strg+Umschalt+S |
| Als PDF exportieren | Strg+P       |

Die Vorschau rendert automatisch, sobald der Text im linken Editor geändert wird
(mit kurzer Verzögerung von 150 ms, um bei langen Dokumenten flüssig zu bleiben).
