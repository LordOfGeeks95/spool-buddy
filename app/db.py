"""
db.py — The database (SQLite).

SQLite is just ONE file (data/filament.db). Nothing to install, no server —
it ships with Python.

Tables:
    spools   -> filament spools (active + finished ones = Graveyard)
    prints   -> every print
    settings -> values from the Settings page (key/value)

To change the schema (e.g. add a column):
    1. Append a new step to the MIGRATIONS list (NEVER edit the old ones!)
    2. It is applied automatically on the next start.
    The database remembers which step it is at via `PRAGMA user_version`.
"""

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import DATA_DIR, DB_PATH, DEFAULT_SETTINGS

# ---------------------------------------------------------------------------
# Migrations: each item is one step of schema changes.
# Step 1 creates the tables from scratch.
# ---------------------------------------------------------------------------
MIGRATIONS: list[str] = [
    # --- v1: initial schema ---
    """
    CREATE TABLE spools (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        name             TEXT    NOT NULL,             -- e.g. "Grey"
        color_hex        TEXT    NOT NULL DEFAULT '#B8A9DE',
        material         TEXT    NOT NULL DEFAULT 'PLA',
        finish           TEXT    NOT NULL DEFAULT 'Basic',
        brand            TEXT    NOT NULL DEFAULT '',
        price            REAL    NOT NULL DEFAULT 0,   -- what the WHOLE spool cost
        initial_weight_g REAL    NOT NULL DEFAULT 1000,-- net filament weight
        opened_at        TEXT,                         -- "date of birth" (ISO)
        finished_at      TEXT,                         -- "date of death" (NULL = active)
        is_loaded        INTEGER NOT NULL DEFAULT 0,   -- 1 = currently in the printer
        notes            TEXT    NOT NULL DEFAULT '',
        created_at       TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
    );

    CREATE TABLE prints (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        number        INTEGER NOT NULL,               -- running print number (#)
        printed_at    TEXT    NOT NULL,               -- ISO date/time
        name          TEXT    NOT NULL,
        weight_g      REAL    NOT NULL,
        spool_id      INTEGER NOT NULL REFERENCES spools(id),
        -- The price per kg AT THE TIME of the print. Stored separately so that changing
        -- the spool's price later does not change old print costs.
        price_per_kg  REAL    NOT NULL,
        print_minutes INTEGER,                        -- (removed in v2)
        energy_cost   REAL    NOT NULL DEFAULT 0,     -- (removed in v2)
        failed        INTEGER NOT NULL DEFAULT 0,     -- 1 = failed print
        sale_price    REAL,                           -- (removed in v2)
        notes         TEXT    NOT NULL DEFAULT ''
    );
    CREATE INDEX idx_prints_spool ON prints(spool_id);
    CREATE INDEX idx_prints_date  ON prints(printed_at);

    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # --- v2: removed electricity cost, print time and sale price ---
    """
    ALTER TABLE prints DROP COLUMN print_minutes;
    ALTER TABLE prints DROP COLUMN energy_cost;
    ALTER TABLE prints DROP COLUMN sale_price;
    DELETE FROM settings WHERE key IN
        ('electricity_price', 'printer_power_w', 'profit_margin_pct', 'backups_to_keep');
    """,
    # --- v3: unique spool ID (F1, F2, ...) separate from the name/color ---
    # "Grey (F7)" -> name = "Grey", code = "F7". The counter (next_spool_number) lives in
    # the settings table so the numbering is NEVER lost (not even when a spool goes to the Graveyard).
    """
    ALTER TABLE spools ADD COLUMN code TEXT NOT NULL DEFAULT '';
    UPDATE spools
       SET code = substr(name, instr(name, '(') + 1, length(name) - instr(name, '(') - 1),
           name = rtrim(substr(name, 1, instr(name, '(') - 1))
     WHERE name LIKE '%(%)';
    CREATE UNIQUE INDEX idx_spools_code ON spools(code) WHERE code != '';
    INSERT OR REPLACE INTO settings(key, value)
        SELECT 'next_spool_number', COALESCE(MAX(CAST(substr(code, 2) AS INTEGER)), 0) + 1
        FROM spools WHERE code LIKE 'F%';
    """,
    # --- v4: (example for the future) ---
    # "ALTER TABLE prints ADD COLUMN printer TEXT NOT NULL DEFAULT '';",
]


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """
    Opens a connection, commits at the end (or rolls back on error).

    Usage:
        with connect() as con:
            con.execute("SELECT ...")
    """
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row          # rows behave like dicts: row["name"]
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """Creates the database if missing and applies any pending migrations."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        version = con.execute("PRAGMA user_version").fetchone()[0]
        for i, script in enumerate(MIGRATIONS[version:], start=version + 1):
            con.executescript(script)
            con.execute(f"PRAGMA user_version = {i}")

        # Insert default settings (only the ones that don't exist yet)
        for key, (value, _label) in DEFAULT_SETTINGS.items():
            con.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, str(value))
            )
