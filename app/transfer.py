"""
transfer.py — Export / Import of ALL data in ONE file (.json).

Purpose: move your data from one version of the app to another
(e.g. v1 -> v2) or from one computer to another.

Why JSON:
    - ONE file, plain text — you can open and read it in Notepad
    - non-English text is stored as-is (ensure_ascii=False)
    - any future version can read it easily

File format (format_version 1):
    {
      "app": "Spool Buddy",
      "format_version": 1,
      "exported_at": "2026-09-28 18:00:00",
      "counts":   {"spools": 7, "prints": 117},
      "settings": {"low_stock_g": 100.0, ...},
      "spools":   [ {"id": 1, "name": "Grey", "code": "F7", "color_hex": "#8E9196", ...}, ... ],
      "prints":   [ {"id": 1, "number": 1, "printed_at": "...", "spool_id": 1, ...}, ... ]
    }
    Prints point to their spool via "spool_id" = the spool's "id".

IF THE SCHEMA CHANGES IN THE FUTURE:
    - New field: just add it to SPOOL_FIELDS / PRINT_FIELDS with a default value.
      Old files without it get the default — nothing breaks.
    - Big change: bump FORMAT_VERSION and write the conversion in _upgrade().
    NEVER break importing older files — that's how users move their data to a new version.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import backup, services
from .config import APP_TITLE, BACKUPS_TO_KEEP
from .db import connect

FORMAT_VERSION = 1

# field -> default value if missing from the file
SPOOL_FIELDS = {
    "id": None, "name": "", "code": "", "color_hex": "#B8A9DE", "material": "PLA", "finish": "Basic",
    "brand": "", "price": 0.0, "initial_weight_g": 1000.0, "opened_at": None,
    "finished_at": None, "is_loaded": 0, "notes": "", "created_at": None,
}
PRINT_FIELDS = {
    "id": None, "number": 0, "printed_at": None, "name": "", "weight_g": 0.0,
    "spool_id": None, "price_per_kg": 0.0, "failed": 0, "notes": "",
}


# ===========================================================================
# Export
# ===========================================================================

def export_data() -> dict:
    with connect() as con:
        spools = [dict(r) for r in con.execute("SELECT * FROM spools ORDER BY id")]
        prints = [dict(r) for r in con.execute("SELECT * FROM prints ORDER BY number, id")]
    return {
        "app": APP_TITLE,
        "format_version": FORMAT_VERSION,
        "exported_at": services.now_str(),
        "counts": {"spools": len(spools), "prints": len(prints)},
        "settings": services.get_settings(),
        # Only known fields, in a fixed order (easier to read)
        "spools": [{k: s.get(k, d) for k, d in SPOOL_FIELDS.items()} for s in spools],
        "prints": [{k: p.get(k, d) for k, d in PRINT_FIELDS.items()} for p in prints],
    }


def export_to_file(path: str | Path) -> dict:
    """Writes the file. Returns the counts for the success message."""
    data = export_data()
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data["counts"]


def export_bytes() -> bytes:
    """For browser mode (file download instead of a save dialog)."""
    return json.dumps(export_data(), ensure_ascii=False, indent=2).encode("utf-8")


# ===========================================================================
# Import
# ===========================================================================

def _upgrade(data: dict) -> dict:
    """Converts older file formats to the current one. (Only v1 exists today.)"""
    version = data.get("format_version")
    if version is None or "spools" not in data or "prints" not in data:
        raise ValueError("This is not a Spool Buddy export file")
    if version > FORMAT_VERSION:
        raise ValueError(f"This file is from a newer version of the app (format {version}). Update the app first.")
    # if version == 1: data = ... convert to v2 ... (when needed)
    return data


def import_from_text(text: str) -> dict:
    """
    Replaces ALL data with the data from the file.
    An automatic backup of the current database is made first.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("The file is not valid JSON")
    data = _upgrade(data)

    spools = [{k: s.get(k, d) for k, d in SPOOL_FIELDS.items()} for s in data["spools"]]
    prints = [{k: p.get(k, d) for k, d in PRINT_FIELDS.items()} for p in data["prints"]]

    # Older files have no "code": the ID was part of the name, e.g. "Grey (F7)"
    for s in spools:
        if not s["code"]:
            s["name"], s["code"] = services.split_label(s["name"])
    codes = [s["code"] for s in spools if s["code"]]
    duplicates = sorted({c for c in codes if codes.count(c) > 1})
    if duplicates:
        raise ValueError(f"The file has the same spool ID more than once: {', '.join(duplicates)}")

    # Make sure every print points to an existing spool
    spool_ids = {s["id"] for s in spools}
    orphans = [p for p in prints if p["spool_id"] not in spool_ids]
    if orphans:
        raise ValueError(f"{len(orphans)} prints point to a spool that is not in the file")

    backup.backup_now(keep=BACKUPS_TO_KEEP)   # safety net

    with connect() as con:  # all or nothing: if anything fails, everything is rolled back
        con.execute("DELETE FROM prints")
        con.execute("DELETE FROM spools")
        for s in spools:
            if s["created_at"] is None:
                s.pop("created_at")         # let the database fill in the current time
            cols = ", ".join(s)
            con.execute(f"INSERT INTO spools ({cols}) VALUES ({', '.join('?' for _ in s)})", tuple(s.values()))
        for p in prints:
            p["printed_at"] = p["printed_at"] or services.now_str()
            cols = ", ".join(p)
            con.execute(f"INSERT INTO prints ({cols}) VALUES ({', '.join('?' for _ in p)})", tuple(p.values()))

    settings = data.get("settings") if isinstance(data.get("settings"), dict) else {}
    services.save_settings({k: v for k, v in settings.items()
                            if k in services.DEFAULT_SETTINGS and isinstance(v, (int, float))})
    # The ID counter continues where it was (or from the highest ID in the file + 1)
    services.restore_counter(settings.get("next_spool_number"))

    return {"spools": len(spools), "prints": len(prints)}


def import_from_file(path: str | Path) -> dict:
    return import_from_text(Path(path).read_text(encoding="utf-8"))
