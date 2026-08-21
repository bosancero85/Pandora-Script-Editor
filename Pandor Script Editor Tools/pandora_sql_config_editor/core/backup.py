"""
Automatische Backups vor jedem Schreibvorgang.
SQLite: Datei-Kopie mit Zeitstempel.
MariaDB: mysqldump, falls verfügbar, sonst Warnung an die UI.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional


BACKUP_DIRNAME = "pandora_backups"


def backup_sqlite(db_path: Path) -> Path:
    backup_dir = db_path.parent / BACKUP_DIRNAME
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"{db_path.stem}_{stamp}{db_path.suffix}.bak"
    shutil.copy2(db_path, target)
    return target


def backup_sql_source(sql_path: Path) -> Path:
    """Sichert die ursprüngliche .sql-Datei per Zeitstempel-Kopie, bevor sie
    beim Speichern überschrieben wird."""
    backup_dir = sql_path.parent / BACKUP_DIRNAME
    backup_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"{sql_path.stem}_{stamp}{sql_path.suffix}.bak"
    if sql_path.exists():
        shutil.copy2(sql_path, target)
    return target


def backup_mariadb(host: str, user: str, password: str, database: str,
                    port: int, out_dir: Path) -> Optional[Path]:
    out_dir.mkdir(exist_ok=True, parents=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = out_dir / f"{database}_{stamp}.sql"
    if shutil.which("mysqldump") is None:
        return None
    cmd = [
        "mysqldump", f"-h{host}", f"-P{port}", f"-u{user}",
        f"-p{password}", database,
    ]
    try:
        with open(target, "w") as f:
            subprocess.run(cmd, stdout=f, check=True, timeout=30)
        return target
    except (subprocess.SubprocessError, OSError):
        return None
