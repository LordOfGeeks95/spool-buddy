"""
backup.py — Automatic database backups.

On every app start (and before every import) a copy of the database is saved
to data/backups/. Only the latest N are kept (config.BACKUPS_TO_KEEP).

To restore: close the app, copy the backup you want over data/filament.db
and open the app again.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

from .config import BACKUP_DIR, DB_PATH


def backup_now(keep: int = 20) -> Path | None:
    if not DB_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"filament_{datetime.now():%Y-%m-%d_%H-%M-%S}.db"

    # SQLite's backup API makes a consistent copy even while the database is open
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(target)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    _prune(max(1, int(keep)))
    return target


def list_backups() -> list[Path]:
    """All backups, newest first."""
    if not BACKUP_DIR.exists():
        return []
    return sorted(BACKUP_DIR.glob("filament_*.db"), reverse=True)


def _prune(keep: int) -> None:
    for old in list_backups()[keep:]:
        old.unlink(missing_ok=True)
