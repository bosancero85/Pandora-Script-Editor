# Pandora® - PCB Editor | by AKI_SystemDown® ©2026

![Pandora PCB Editor Icon](assets/icon.png)

## Installation (Raspberry Pi 4B / Kali Linux)
```bash
pip install -r requirements.txt --break-system-packages
python3 pandora_pcb_editor.py
```

## Enthalten (MVP)
- Pandora-Cyberpunk-Dark-Theme (Cyan/Magenta/Purple auf Schwarz)
- Layerverwaltung: Top/Bottom Copper, Top/Bottom Silkscreen, Drill, Board Outline
  (Sichtbarkeit + aktiver Layer per Dock links)
- QGraphicsScene/View-Canvas mit Raster (einstellbar, Standard 1.27mm), Snap-to-Grid, Zoom via Mausrad
- Werkzeuge: Auswählen, Leiterbahn (Mehrsegment, Doppelklick beendet), Pad, Via,
  Footprint-Platzhalter (Körper + Pins + Referenz), Board-Umriss (Polygon)
- Undo/Redo über QUndoStack (Hinzufügen, Löschen, Verschieben)
- Eigenschaften-Dock: Position (X/Y in mm), Layer, Netz – live editierbar
- Netzliste: einfache Netzverwaltung (Name, Farbe)
- Projekt speichern/laden als JSON (`.pandora`)
- Vollständiger Gerber-X2- + Excellon-Export (siehe eigener Abschnitt unten)

## Neu hinzugefügt
- **Ratsnest**: automatische Luftlinien (gestrichelt) je Netz, berechnet per
  Minimal-Spannbaum (MST) über alle Pads/Vias eines Netzes. Bereits durch Traces
  verbundene Punkte werden erkannt und nicht erneut verbunden. Live-Update nach
  Verschieben (Auswahl-Modus), Hinzufügen/Löschen (Undo/Redo) und Projekt-Laden.
  Ein/Aus-Schalter in der Toolbar, manuelles Neuberechnen über Menü „Werkzeuge“.
- **Netz-Zuweisung**: im Eigenschaften-Dock kann für Pads/Vias/Traces per Dropdown
  ein Netz zugewiesen werden (inkl. „kein Netz“).
- **Design Rule Check (DRC)**: neues Dock rechts mit einstellbaren Regeln
  (Mindest-Clearance, Mindest-Leiterbahnbreite, Mindest-Bohrdurchmesser).
  Prüft Kupfer-Elemente unterschiedlicher Netze auf demselben Layer auf
  Abstandsverletzungen (Näherung über Bounding-Box-Distanz) sowie zu dünne Traces
  und zu kleine Bohrungen. Verstöße sind anklickbar → Element(e) werden selektiert
  und die Ansicht zoomt darauf.

## Neu hinzugefügt: Footprint-Bibliothek
- **Echte Footprints statt Platzhalter**: neues Dock „Footprint-Bibliothek“ (links,
  tabbed mit dem Layer-Dock) mit 36 vordefinierten Footprints in vier Kategorien
  (SMD Passiv, SMD Diode/Transistor, SMD IC, THT, Stiftleisten, Mechanik) —
  u. a. R/C/LED 0402–1206, SOD-123, SOT-23/-23-5/-223, SOIC-8/14/16,
  TSSOP-8/16, DIP-8/14/16, TO-220-3, Stiftleisten 1x02–1x10 & 2x05/2x10,
  Bohrungen M2.5/M3. Suchfeld zum Filtern nach Name.
- Pads jedes Footprints sind **echte, netzfähige PadItem-Elemente** (kein reiner
  Platzhalter mehr) — Ratsnest, DRC und Gerber-Lite-Export berücksichtigen sie
  wie frei platzierte Pads. Netzzuweisung je Pin erfolgt im Eigenschaften-Dock
  über eine „Pins“-Liste, sobald ein Footprint ausgewählt ist.
- Auswahl eines Footprints in der Bibliothek aktiviert automatisch das
  Footprint-Werkzeug; jeder Klick auf dem Board platziert eine Instanz mit
  automatisch hochgezähltem Referenzbezeichner (R1, R2, U1, …) auf Basis des
  Footprint-Präfixes. Ein optionales „Wert“-Feld (z. B. „10k“, „100nF“) wird
  bei der Platzierung übernommen.
- Eigenschaften-Dock für Footprints: Referenz und Wert live editierbar,
  Rotation (0/90/180/270°), Anzeige des zugrunde liegenden Bibliotheksschlüssels.
- **Rotation**: „Bauteil drehen“ (Strg+R) dreht die aktuelle Auswahl um 90°,
  mit Undo/Redo-Unterstützung.
- Alt-Projekte (vor der Footprint-Bibliothek, ohne `footprint_key`) werden
  beim Laden automatisch mit einem generischen, aber ebenfalls netzfähigen
  Footprint rekonstruiert.
- Hinweis: Pad-Maße sind praxistaugliche Näherungswerte, keine datenblatt-
  geprüften Fertigungs-Footprints.

## Neu hinzugefügt: Autorouter
- **Grid-/Maze-Router (A*)**: neues Dock „Autorouter“ mit einstellbarer
  Raster-Zellgröße, Mindest-Clearance, Trace-Breite und Ziel-Layer (Top/Bottom Copper).
- Nimmt alle offenen Ratsnest-Verbindungen, rasterisiert Kupfer-Elemente fremder Netze
  (inkl. Clearance-Puffer) als Hindernisse und sucht je Verbindung per A*
  (8-Wege-Bewegung) den kürzesten freien Pfad.
- Gefundene Pfade werden kollinear vereinfacht und als echte Traces eingefügt
  (ein Undo-Schritt für den gesamten Lauf über `beginMacro`/`endMacro`).
- Log-Liste zeigt pro Netz ✓ (geroutet) oder ✗ (kein Pfad / Raster zu groß).

## Neu hinzugefügt: Vollständiger Gerber X2 + Excellon-Export
- **Menü „Projekt → Gerber X2 / Excellon-Export…“** exportiert in ein gewähltes
  Verzeichnis sechs Dateien: `pandora_top_copper.gbr`, `pandora_bottom_copper.gbr`,
  `pandora_top_silk.gbr`, `pandora_bottom_silk.gbr`, `pandora_outline.gbr` und
  `pandora_drill_pth.drl`.
- **Gerber X2 (RS-274X + Attribute)**: jede `.gbr`-Datei enthält Datei-Attribute
  (`%TF.GenerationSoftware*%`, `%TF.CreationDate*%`, `%TF.Part*%`,
  `%TF.FileFunction*%`, bei Copper zusätzlich `%TF.FilePolarity*%`) sowie
  Apertur-Attribute (`%TA.AperFunction*%`/`%TD*%`) für SMD-Pads (`SMDPad,CuDef`),
  THT-Pads (`ComponentPad`), Vias (`Via`), Leiterbahnen (`Conductor`) und
  Silkscreen-Konturen (`Legend`). Koordinatenformat `%FSLAX46Y46*%` (4.6, mm,
  Leading-Zero-Suppression), Aperturen werden dedupliziert (gleiche
  Form/Größe/Funktion → gleicher D-Code).
- **Kupfer-Layer**: Pads (rect/round/oval → R-/C-/O-Apertur) als Flash (D03),
  Vias als Flash mit eigener Via-Apertur, Leiterbahnen als D01/D02-Interpolation
  mit einer Rundapertur passend zur Trace-Breite. Footprint-Kind-Pads werden
  über `scenePos()` in absolute Board-Koordinaten aufgelöst (korrekt auch bei
  gedrehten Footprints).
- **Silkscreen-Layer** (`Legend,Top`/`Legend,Bot`): Körperumriss jedes
  Footprints als geschlossener Linienzug, mit Referenzbezeichner als
  Klartext-Kommentar (`G04 Bauteil ...*`) davor.
- **Board-Outline** als `Profile,NP`-Layer: geschlossener Linienzug aus dem
  Board-Umriss-Polygon.
- **Excellon-Bohrdatei** (`METRIC,LZ`, `M48`/`%`/`G90`/`G05`/`M30`): alle Vias
  und Pads mit `drill_mm > 0` werden nach Durchmesser zu Werkzeugen (`T01`, `T02`, …)
  gruppiert und als PTH (durchkontaktiert) exportiert.
- **Einschränkungen**: Footprint-Pads liegen intern immer auf Top-Copper (siehe
  bekannte Limitierung bei Multi-Layer-THT-Pads), es gibt keine automatische
  NPTH-Trennung (z. B. reine Befestigungsbohrungen werden ebenfalls als PTH
  exportiert), und es wird kein separates `.gbrjob`-Jobfile erzeugt.

## Neu hinzugefügt: 3D-Vorschau
- **Menü „Werkzeuge → 3D-Vorschau…“** (`Strg+3`) bzw. Toolbar-Button „3D-Vorschau“
  öffnet ein eigenes Fenster mit einer 3D-Darstellung des aktuellen Boards,
  gerendert per `matplotlib` (mplot3d).
- **Dargestellte Geometrie**: Board-Substrat als extrudiertes Prisma aus dem
  Board-Umriss (FR4-grün, Standardstärke 1,6 mm; ohne gezeichneten Umriss wird
  automatisch die Bounding-Box aller Elemente + Rand verwendet), Kupfer-Elemente
  (Pads, Vias, Leiterbahnen) auf Top-/Bottom-Copper in den jeweiligen
  Layerfarben, Bohrungen als ausgesparte Zylinder durch das gesamte Board,
  sowie Footprint-Silkscreen-Umrisse als dünne Bänder auf der Bauteilseite.
- **Ansichten**: Buttons für „Isometrisch“, „Oben (Bestückungsseite)“, „Unten“
  und „Neu berechnen“; frei drehbar/zoombar per Maus (Standard-mplot3d-Steuerung).
- **Einschränkung**: kein vollwertiger 3D-Renderer (kein STEP-/Bauteilkörper-Import,
  keine Textur-/Glanz-Darstellung) — dient als schneller visueller Eindruck von
  Lagenlage, Bestückungsseite und grober Bohrungslage, nicht als Fertigungs-Review.
- **Abhängigkeit**: benötigt `matplotlib` (siehe `requirements.txt`). Ist
  `matplotlib` nicht installiert, zeigt der Dialog einen Installationshinweis
  statt der 3D-Ansicht an.

## Roadmap / noch offen (bewusst nicht im MVP, da Enterprise-Umfang sehr groß ist)
- Exaktes Polygon-Clearance-Modell (aktuell Bounding-Box-Näherung, keine Rotationen)
- Autorouter: kein Layer-Wechsel per Via während des Routings, kein Push-and-Shove,
  kein Rip-up/Re-Route bei Sackgassen; Raster wird pro Segment neu aufgebaut
  (nicht performance-optimal bei sehr vielen Netzen/großen Boards)
- Footprint-Bibliothek: KiCad-Import, benutzerdefinierte/editierbare Footprints,
  echte THT-Pads über mehrere Layer (aktuell nur als Top-Copper-Pad realisiert),
  Courtyard/Fab-Layer, maßstabsgetreue Referenzbeschriftung (aktuell fixe
  Bildschirmgröße statt mm-Skalierung)
- Mehrschicht-PCBs (>2 Layer, interne Layer)
- Undo/Redo auch für Trace-Punkt-Bearbeitung, Layer-Sichtbarkeit und
  Eigenschaften-Dock-Bearbeitungen (Position/Ref/Wert/Rotation direkt im Dock)
- 3D-Vorschau: echter OpenGL-Renderer mit Beleuchtung/Texturen statt
  matplotlib-Extrusion, STEP-Export/Import von Bauteilkörpern

## Projekt-Icon
Das Anwendungsicon liegt unter [`assets/icon.png`](assets/icon.png) (PNG, für
Fenster-/Taskleisten-Icon unter Linux/macOS) und [`assets/icon.ico`](assets/icon.ico)
(Mehrfachauflösung 16–256 px, für Windows-Fenstericon und `.exe`-Icon beim
PyInstaller-Build, siehe unten). Beide werden automatisch beim Programmstart
geladen (`app.setWindowIcon(...)` in `main()` sowie `MainWindow.__init__`).

## Windows-Build: eigenständiges Programm mit PyInstaller (`--onedir`)
Um aus dem Python-Quellcode ein eigenständiges Windows-Programm zu bauen (ohne
dass auf dem Zielrechner Python installiert sein muss), wird
[PyInstaller](https://pyinstaller.org/) im `--onedir`-Modus verwendet. Dabei
entsteht ein Ordner mit der `.exe` und allen Abhängigkeiten (im Gegensatz zu
`--onefile`, was eine einzelne, aber langsamer startende `.exe` erzeugt).

### 1. Voraussetzungen installieren
In einer **PowerShell** oder **Eingabeaufforderung (cmd)** unter Windows, im
Projektordner (dort, wo `pandora_pcb_editor.py` liegt):

```powershell
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller
```

> Falls `py` nicht gefunden wird: Python von [python.org](https://www.python.org/downloads/windows/)
> installieren und beim Setup **„Add python.exe to PATH“** aktivieren.

### 2. `--onedir`-Build erstellen
Mit aktivierter virtueller Umgebung (`venv`) den Build starten:

```powershell
pyinstaller --onedir --windowed --name "Pandora_PCB_Editor" --icon assets\icon.ico pandora_pcb_editor.py
```

Bedeutung der Optionen:
- `--onedir` – erzeugt **einen Ordner** (nicht eine einzelne Datei) mit der
  `.exe` und allen DLLs/Abhängigkeiten. Startet spürbar schneller als
  `--onefile`, da beim Start nichts erst in ein Temp-Verzeichnis entpackt
  werden muss.
- `--windowed` – unterdrückt das schwarze Konsolenfenster im Hintergrund
  (passend für eine GUI-Anwendung wie diese).
- `--name` – legt den Namen des Ausgabeordners/der `.exe` fest.
- `--icon` – setzt das `.ico`-Icon der erzeugten `.exe`.

### 3. Ergebnis
Nach erfolgreichem Build liegt das fertige Programm unter:

```
dist\Pandora_PCB_Editor\Pandora_PCB_Editor.exe
```

Der komplette Ordner `dist\Pandora_PCB_Editor\` muss zusammenbleiben (die
`.exe` benötigt die danebenliegenden DLLs/Ressourcen) — er kann als Ganzes
kopiert, gezippt oder z. B. per Inno Setup/NSIS zu einem Installer verpackt
werden.

### Hinweise
- `build\` und `dist\` sowie die von PyInstaller erzeugte `.spec`-Datei sind
  generierte Build-Artefakte und daher in `.gitignore` ausgeschlossen.
- Bei Antivirus-/SmartScreen-Warnungen bei frisch erzeugten, unsignierten
  `.exe`-Dateien handelt es sich um ein bekanntes PyInstaller-Verhalten
  (fehlende Code-Signatur) und keinen Hinweis auf Schadsoftware im Quellcode.
- Für eine einzelne portable Datei statt eines Ordners kann alternativ
  `--onefile` statt `--onedir` verwendet werden (Start dauert dann etwas
  länger, da bei jedem Programmstart in einen Temp-Ordner entpackt wird).
