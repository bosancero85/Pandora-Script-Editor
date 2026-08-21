# Pandora® Structure Creator

Ein PyQt6-Tool, das aus einer textuellen Baum-Darstellung automatisch
Ordner und Dateien an einem frei wählbaren Zielort anlegt.

## Voraussetzungen

```bash
pip install PyQt6
```

## Start

```bash
python3 main.py
```

## Benutzung

1. **Zielort wählen** – oben auf "Verzeichnis wählen …" klicken.
2. **Struktur eingeben** – links die gewünschte Ordner-/Dateistruktur
   eintippen oder einfügen. Zwei Formate werden unterstützt:

   **a) Baum-Zeichen-Format** (z.B. aus GitHub-READMEs kopiert):
   ```
   MeinProjekt/
   ├── main.py
   ├── core/
   │   ├── __init__.py
   │   └── config.py
   └── gui/
       ├── __init__.py
       └── main_window.py
   ```

   **b) Einrückungs-Format** (4 Leerzeichen oder ein Tab pro Ebene):
   ```
   MeinProjekt/
       main.py
       core/
           __init__.py
           config.py
   ```

   Ordner werden durch ein abschließendes `/` gekennzeichnet.
   Kommentare hinter Dateinamen (z.B. `main.py  ← Einstiegspunkt`)
   werden beim Anlegen automatisch ignoriert.

3. **Vorschau prüfen** – rechts wird live angezeigt, was erstellt wird.
4. **"Struktur erstellen"** klicken – Ordner und Dateien werden im
   gewählten Zielverzeichnis angelegt. Bereits vorhandene Dateien
   werden dabei **nicht überschrieben**.

## Vorlagen

Über "Vorlage speichern …" / "Vorlage laden …" lassen sich häufig
genutzte Strukturen als `.txt`-Datei sichern und wiederverwenden.

## Erweiterbarkeit

- Der Parser (`parse_tree_structure`) ist von der GUI entkoppelt und
  kann eigenständig getestet oder um weitere Formate erweitert werden.
- Neue Optionen (z.B. Datei-Vorlagen pro Endung, Git-Init, virtuelle
  Umgebung anlegen) lassen sich einfach als weitere Checkboxen bzw.
  Schritte in `create_structure()` ergänzen.
