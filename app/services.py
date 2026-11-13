"""
services.py — All the app "logic" (calculations + storage).

Rule: pages (the ui/ folder) NEVER write SQL. They call functions from here,
so if a calculation changes, it changes in ONE place.

Core formulas:
    print cost     = weight (g) × price (€/kg) / 1000
    filament left  = spool's initial weight − sum of the weights of its prints
"""

from __future__ import annotations

import re
from datetime import datetime

from .config import DEFAULT_SETTINGS
from .db import connect

DATE_FMT = "%Y-%m-%d %H:%M:%S"   # how dates are stored in the database


# ===========================================================================
# Date helpers
# ===========================================================================

def now_str() -> str:
    return datetime.now().strftime(DATE_FMT)


def parse_dt(value: str | None) -> datetime | None:
    """Accepts 'YYYY-MM-DD[ HH:MM[:SS]]' (also with 'T') or 'DD/MM/YYYY' (as typed in the UI)."""
    if not value:
        return None
    value = value.strip().replace("T", " ")
    for fmt in (DATE_FMT, "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")


def normalize_dt(value: str | None) -> str | None:
    """Converts any accepted format to the database format."""
    dt = parse_dt(value)
    return dt.strftime(DATE_FMT) if dt else None


# ===========================================================================
# Settings
# ===========================================================================

def get_settings() -> dict[str, float]:
    with connect() as con:
        rows = con.execute("SELECT key, value FROM settings").fetchall()
    values = {key: default for key, (default, _label) in DEFAULT_SETTINGS.items()}
    for r in rows:
        try:
            values[r["key"]] = float(r["value"])
        except ValueError:
            pass
    return values


def save_settings(values: dict[str, float]) -> None:
    with connect() as con:
        for key, value in values.items():
            con.execute(
                "INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(float(value))),
            )


def print_cost(weight_g: float | None, price_per_kg: float | None) -> float:
    """Filament cost of one print in €."""
    return (weight_g or 0) * (price_per_kg or 0) / 1000


# ===========================================================================
# Spools
# ===========================================================================

_SPOOL_STATS_SQL = """
SELECT s.*,
       COUNT(p.id)                                             AS prints_count,
       COALESCE(SUM(p.weight_g), 0)                            AS used_g,
       COALESCE(SUM(p.weight_g * p.price_per_kg / 1000.0), 0)  AS filament_cost,
       COALESCE(SUM(CASE WHEN p.failed = 1 THEN p.weight_g END), 0) AS failed_g,
       MIN(p.printed_at)                                       AS first_print,
       MAX(p.printed_at)                                       AS last_print
FROM spools s
LEFT JOIN prints p ON p.spool_id = s.id
{where}
GROUP BY s.id
"""


# ---------------------------------------------------------------------------
# Spool IDs (F1, F2, F3...)
# ---------------------------------------------------------------------------
# Every spool has a name (its color, e.g. "Black") + a unique ID (e.g. "F8").
# Everywhere in the app it is shown as "Black (F8)" -> spool_label().
# The counter "next_spool_number" is stored in the database (settings table),
# so an ID that was handed out is NEVER reused (not even when the spool goes to the Graveyard).
# Exception: if the LAST spool created is deleted (it has no prints), the counter steps back.
SPOOL_PREFIX = "F"
_COUNTER_KEY = "next_spool_number"
_LABEL_RE = re.compile(r"^(.*?)\s*\(([^()]+)\)\s*$")


def spool_label(name: str, code: str) -> str:
    return f"{name} ({code})" if code else name


def split_label(text: str) -> tuple[str, str]:
    """'Grey (F7)' -> ('Grey', 'F7'). No parentheses -> (text, '')."""
    m = _LABEL_RE.match(text or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else ((text or "").strip(), "")


def code_number(code: str) -> int | None:
    """'F12' -> 12. Anything else -> None."""
    m = re.fullmatch(rf"{SPOOL_PREFIX}(\d+)", (code or "").strip(), re.IGNORECASE)
    return int(m.group(1)) if m else None


def _get_counter(con) -> int:
    row = con.execute("SELECT value FROM settings WHERE key = ?", (_COUNTER_KEY,)).fetchone()
    stored = int(float(row[0])) if row else 1
    # Safety: never below the highest existing ID + 1
    codes = [code_number(r[0]) for r in con.execute("SELECT code FROM spools")]
    return max([stored] + [n + 1 for n in codes if n is not None])


def _set_counter(con, value: int) -> None:
    con.execute("INSERT INTO settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (_COUNTER_KEY, str(int(value))))


def restore_counter(value: float | None = None) -> None:
    """After an import: counter = max(value from the file, highest ID + 1).
    (The database's old counter is ignored — an import replaces everything.)"""
    with connect() as con:
        _set_counter(con, int(value) if value else 1)
        _set_counter(con, _get_counter(con))   # _get_counter makes sure it isn't below existing IDs


def peek_next_code() -> str:
    """Which ID the next new spool will get (preview in the dialog)."""
    with connect() as con:
        return f"{SPOOL_PREFIX}{_get_counter(con)}"


def _enrich_spool(row) -> dict:
    """Adds computed fields (remaining, %, days of use, ...)."""
    s = dict(row)
    s["label"] = spool_label(s["name"], s["code"])   # e.g. "Grey (F7)" — this is shown everywhere
    initial = s["initial_weight_g"] or 1
    s["remaining_g"] = initial - s["used_g"]
    s["percent_left"] = max(0.0, min(100.0, s["remaining_g"] / initial * 100))
    s["price_per_kg"] = s["price"] / initial * 1000
    # Value of the remaining filament (e.g. 300 g at 13 €/kg = 3.90 €)
    s["remaining_value"] = max(0.0, s["remaining_g"]) * s["price_per_kg"] / 1000

    # "Birth" = when Load was first pressed (or, for older data, the first print)
    born = parse_dt(s["opened_at"]) or parse_dt(s["first_print"])
    died = parse_dt(s["finished_at"]) or datetime.now()
    s["born"] = born
    s["days_of_use"] = (died - born).days if born else None
    s["is_finished"] = s["finished_at"] is not None
    s["is_sealed"] = born is None and not s["is_finished"]   # not opened yet
    return s


# Sort options: key -> (label in the UI, key function, reverse?)
# To add a new sort, add a line here — it appears in the dropdown automatically.
_NEVER = datetime.min
SPOOL_SORTS: dict[str, tuple[str, object, bool]] = {
    "left_desc":   ("Most filament left",  lambda s: s["remaining_g"], True),
    "left_asc":    ("Least filament left", lambda s: s["remaining_g"], False),
    "code":        ("Spool ID (F1, F2…)",  lambda s: (code_number(s["code"]) or 0, s["code"]), False),
    "name":        ("Name (A–Z)",          lambda s: (s["name"].lower(), code_number(s["code"]) or 0), False),
    "brand":       ("Brand (A–Z)",         lambda s: (s["brand"].lower(), s["name"].lower()), False),
    "material":    ("Type (A–Z)",          lambda s: (s["material"].lower(), s["name"].lower()), False),
    "price_desc":  ("Most expensive",      lambda s: s["price_per_kg"], True),
    "prints_desc": ("Most prints",         lambda s: s["prints_count"], True),
    "opened_new":  ("Recently opened",     lambda s: s["born"] or _NEVER, True),
    "opened_old":  ("Oldest opened",       lambda s: s["born"] or datetime.max, False),
    "died_new":    ("Recently finished",   lambda s: parse_dt(s["finished_at"]) or _NEVER, True),
    "died_old":    ("First finished",      lambda s: parse_dt(s["finished_at"]) or datetime.max, False),
    "life_desc":   ("Longest life",        lambda s: s["days_of_use"] or 0, True),
    "life_asc":    ("Shortest life",       lambda s: s["days_of_use"] or 0, False),
}


def list_spools(status: str = "active", sort: str | None = None, brand: str | None = None,
                loaded_first: bool = True) -> list[dict]:
    """
    status: 'active' (Storage), 'finished' (Graveyard) or 'all'.
    sort:   a key from SPOOL_SORTS. brand: brand filter (None = all).
    loaded_first: True  -> the loaded spool comes first (default view).
                  False -> plain sorting (when the user picked "Sort by").
    """
    where = {
        "active": "WHERE s.finished_at IS NULL",
        "finished": "WHERE s.finished_at IS NOT NULL",
        "all": "",
    }[status]
    with connect() as con:
        rows = con.execute(_SPOOL_STATS_SQL.format(where=where)).fetchall()
    spools = [_enrich_spool(r) for r in rows]
    if brand:
        spools = [s for s in spools if s["brand"] == brand]

    sort = sort or ("died_new" if status == "finished" else "left_desc")
    _label, key, reverse = SPOOL_SORTS[sort]
    spools.sort(key=key, reverse=reverse)
    if loaded_first:
        spools.sort(key=lambda s: not s["is_loaded"])  # stable sort: loaded on top, the rest keep their order
    return spools


def get_spool(spool_id: int) -> dict | None:
    with connect() as con:
        row = con.execute(_SPOOL_STATS_SQL.format(where="WHERE s.id = ?"), (spool_id,)).fetchone()
    return _enrich_spool(row) if row else None


def loaded_spool() -> dict | None:
    """The spool that is currently in the printer."""
    return next((s for s in list_spools("active") if s["is_loaded"]), None)


_SPOOL_FIELDS = ("name", "code", "color_hex", "material", "finish", "brand", "price",
                 "initial_weight_g", "opened_at", "finished_at", "notes")


def _validate_spool(data: dict) -> dict:
    clean = {k: data.get(k) for k in _SPOOL_FIELDS if k in data}
    if "name" in clean:
        # If "Black (F9)" is typed as the name, keep only "Black" — the ID is a separate field
        clean["name"] = split_label(clean["name"] or "")[0]
        if not clean["name"]:
            raise ValueError("Spool name is required")
    if "code" in clean:
        clean["code"] = (clean["code"] or "").strip().upper()
        if not clean["code"]:
            raise ValueError("Spool ID is required (e.g. F8)")
    if "price" in clean and (clean["price"] is None or float(clean["price"]) < 0):
        raise ValueError("Price must be 0 or more")
    if "initial_weight_g" in clean and (not clean["initial_weight_g"] or float(clean["initial_weight_g"]) <= 0):
        raise ValueError("Spool weight must be more than 0")
    for key in ("opened_at", "finished_at"):
        if key in clean:
            clean[key] = normalize_dt(clean[key])
    return clean


def _check_code_free(con, code: str, exclude_id: int | None = None) -> None:
    row = con.execute("SELECT name FROM spools WHERE code = ? AND id != ?", (code, exclude_id or -1)).fetchone()
    if row:
        raise ValueError(f"The ID {code} is already used by {spool_label(row[0], code)}")


def create_spool(data: dict) -> int:
    """
    New spool. Gets the next ID (F8, F9, ...) from the counter AUTOMATICALLY.
    It has NO opened date — that is set when Load is pressed.
    """
    clean = _validate_spool({k: v for k, v in data.items() if k not in ("opened_at", "finished_at", "code")})
    with connect() as con:  # one transaction: ID + insert + counter
        number = _get_counter(con)
        clean["code"] = f"{SPOOL_PREFIX}{number}"
        cols = ", ".join(clean)
        marks = ", ".join("?" for _ in clean)
        cur = con.execute(f"INSERT INTO spools ({cols}) VALUES ({marks})", tuple(clean.values()))
        new_id = cur.lastrowid
        _set_counter(con, number + 1)
    if data.get("is_loaded"):
        load_spool(new_id)
    return new_id


def update_spool(spool_id: int, data: dict) -> None:
    clean = _validate_spool(data)
    if not clean:
        return
    with connect() as con:
        if "code" in clean:
            _check_code_free(con, clean["code"], spool_id)
            # If a higher number was typed by hand (e.g. F20), the counter continues from there
            n = code_number(clean["code"])
            if n is not None and n + 1 > _get_counter(con):
                _set_counter(con, n + 1)
        sets = ", ".join(f"{k} = ?" for k in clean)
        con.execute(f"UPDATE spools SET {sets} WHERE id = ?", (*clean.values(), spool_id))


def load_spool(spool_id: int) -> None:
    """
    Puts this spool in the printer (and "unloads" all the others).
    The FIRST time a spool is loaded becomes its opened date.
    """
    with connect() as con:
        con.execute("UPDATE spools SET is_loaded = 0")
        con.execute("UPDATE spools SET is_loaded = 1 WHERE id = ? AND finished_at IS NULL", (spool_id,))
        con.execute("UPDATE spools SET opened_at = ? WHERE id = ? AND opened_at IS NULL", (now_str(), spool_id))


def finish_spool(spool_id: int) -> None:
    """Sends the spool to the Graveyard 🪦."""
    with connect() as con:
        con.execute(
            "UPDATE spools SET finished_at = ?, is_loaded = 0 WHERE id = ?", (now_str(), spool_id)
        )


def restore_spool(spool_id: int) -> None:
    """Brings a spool back from the Graveyard (e.g. if it was sent there by mistake)."""
    with connect() as con:
        con.execute("UPDATE spools SET finished_at = NULL WHERE id = ?", (spool_id,))


def delete_spool(spool_id: int) -> None:
    """
    Deleting is ONLY allowed if the spool has no prints (so no history is lost).
    If it had the last ID handed out (e.g. F8 while the counter is at 9),
    the counter steps back so the next new spool gets F8 again.
    """
    with connect() as con:
        n = con.execute("SELECT COUNT(*) FROM prints WHERE spool_id = ?", (spool_id,)).fetchone()[0]
        if n:
            raise ValueError(f"This spool has {n} prints — move it to the Graveyard instead")
        row = con.execute("SELECT code FROM spools WHERE id = ?", (spool_id,)).fetchone()
        con.execute("DELETE FROM spools WHERE id = ?", (spool_id,))
        number = code_number(row[0]) if row else None
        stored = con.execute("SELECT value FROM settings WHERE key = ?", (_COUNTER_KEY,)).fetchone()
        if number is not None and stored and int(float(stored[0])) == number + 1:
            _set_counter(con, number)


def known_values(column: str, finished: bool | None = None) -> list[str]:
    """
    Values already used (for suggestions and filters).
    finished: None = all spools, False = active only, True = Graveyard only.
    """
    assert column in ("brand", "material", "finish")
    where = f"{column} != ''"
    if finished is not None:
        where += " AND finished_at IS " + ("NOT NULL" if finished else "NULL")
    with connect() as con:
        rows = con.execute(f"SELECT DISTINCT {column} FROM spools WHERE {where} ORDER BY {column}").fetchall()
    return [r[0] for r in rows]


# ===========================================================================
# Prints
# ===========================================================================

_PRINT_SQL = """
SELECT p.*,
       -- "Grey (F7)": name + ID, so spool changes show up in the History right away
       CASE WHEN s.code != '' THEN s.name || ' (' || s.code || ')' ELSE s.name END AS spool_name,
       s.color_hex AS spool_color,
       p.weight_g * p.price_per_kg / 1000.0 AS cost
FROM prints p
JOIN spools s ON s.id = p.spool_id
"""


def list_prints(search: str = "", spool_id: int | None = None, status: str = "all",
                date_from: str | None = None, date_to: str | None = None,
                limit: int | None = None) -> list[dict]:
    """Returns prints (newest first) with optional filters."""
    where, args = [], []
    if search:
        where.append("(p.name LIKE ? OR p.notes LIKE ?)")
        args += [f"%{search}%", f"%{search}%"]
    if spool_id:
        where.append("p.spool_id = ?")
        args.append(spool_id)
    if status == "success":
        where.append("p.failed = 0")
    elif status == "failed":
        where.append("p.failed = 1")
    if date_from:
        where.append("p.printed_at >= ?")
        args.append(date_from[:10] + " 00:00:00")
    if date_to:
        where.append("p.printed_at <= ?")
        args.append(date_to[:10] + " 23:59:59")

    sql = _PRINT_SQL + (" WHERE " + " AND ".join(where) if where else "")
    sql += " ORDER BY p.printed_at DESC, p.number DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    with connect() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def get_print(print_id: int) -> dict | None:
    with connect() as con:
        row = con.execute(_PRINT_SQL + " WHERE p.id = ?", (print_id,)).fetchone()
    return dict(row) if row else None


def next_print_number() -> int:
    with connect() as con:
        return (con.execute("SELECT MAX(number) FROM prints").fetchone()[0] or 0) + 1


def _validate_print(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Print name is required")
    try:
        weight = float(data.get("weight_g") or 0)
    except (TypeError, ValueError):
        raise ValueError("Weight must be a number")
    if weight <= 0:
        raise ValueError("Weight must be more than 0 g")
    if not data.get("spool_id"):
        raise ValueError("Choose a filament spool")
    return {
        "name": name,
        "weight_g": weight,
        "spool_id": int(data["spool_id"]),
        "printed_at": normalize_dt(data.get("printed_at")) or now_str(),
        "failed": 1 if data.get("failed") else 0,
        "notes": (data.get("notes") or "").strip(),
    }


def add_print(data: dict) -> int:
    """New print. The €/kg price is "frozen" from the spool at this moment."""
    clean = _validate_print(data)
    spool = get_spool(clean["spool_id"])
    if not spool:
        raise ValueError("Spool not found")
    clean["price_per_kg"] = spool["price_per_kg"]
    clean["number"] = data.get("number") or next_print_number()
    cols = ", ".join(clean)
    marks = ", ".join("?" for _ in clean)
    with connect() as con:
        cur = con.execute(f"INSERT INTO prints ({cols}) VALUES ({marks})", tuple(clean.values()))
        return cur.lastrowid


def update_print(print_id: int, data: dict) -> None:
    old = get_print(print_id)
    if not old:
        raise ValueError("Print not found")
    clean = _validate_print(data)
    # If the spool changed, take the new spool's price. Otherwise keep the original one.
    if clean["spool_id"] != old["spool_id"]:
        clean["price_per_kg"] = get_spool(clean["spool_id"])["price_per_kg"]
    sets = ", ".join(f"{k} = ?" for k in clean)
    with connect() as con:
        con.execute(f"UPDATE prints SET {sets} WHERE id = ?", (*clean.values(), print_id))


def delete_print(print_id: int) -> None:
    with connect() as con:
        con.execute("DELETE FROM prints WHERE id = ?", (print_id,))


# ===========================================================================
# Statistics (Dashboard)
# ===========================================================================

def dashboard_stats() -> dict:
    """All the numbers for the Dashboard cards."""
    with connect() as con:
        t = con.execute("""
            SELECT COUNT(*)                                                   AS prints,
                   COALESCE(SUM(weight_g), 0)                                 AS grams,
                   COALESCE(SUM(weight_g * price_per_kg / 1000.0), 0)         AS cost,
                   COALESCE(SUM(failed), 0)                                   AS failed,
                   COALESCE(SUM(CASE WHEN failed = 1 THEN weight_g END), 0)   AS failed_g,
                   COALESCE(SUM(CASE WHEN failed = 1
                        THEN weight_g * price_per_kg / 1000.0 END), 0)        AS failed_cost,
                   MAX(weight_g)                                              AS heaviest
            FROM prints
        """).fetchone()
        invested = con.execute("SELECT COALESCE(SUM(price), 0) FROM spools").fetchone()[0]
        # Average weight of the last 30 successful prints (for estimates)
        avg_recent = con.execute("""
            SELECT AVG(weight_g) FROM (
                SELECT weight_g FROM prints WHERE failed = 0
                ORDER BY printed_at DESC LIMIT 30)
        """).fetchone()[0] or 0

    stats = dict(t)
    stats["invested"] = invested
    stats["avg_recent_g"] = avg_recent
    stats["avg_g"] = stats["grams"] / stats["prints"] if stats["prints"] else 0
    stats["success_rate"] = (1 - stats["failed"] / stats["prints"]) * 100 if stats["prints"] else 100

    active = list_spools("active")
    stats["active_spools"] = len(active)
    stats["remaining_g"] = sum(max(0, s["remaining_g"]) for s in active)
    stats["remaining_value"] = sum(s["remaining_value"] for s in active)

    finished = list_spools("finished")
    stats["graveyard_spools"] = len(finished)
    stats["graveyard_used_g"] = sum(s["used_g"] for s in finished)
    return stats


def estimate_prints_left(spool: dict, avg_g: float) -> int | None:
    """How many "average" prints still fit on the spool."""
    if not avg_g or spool["remaining_g"] <= 0:
        return 0 if spool["remaining_g"] <= 0 else None
    return int(spool["remaining_g"] // avg_g)


def years_with_prints() -> list[int]:
    """Years that have prints (for the chart arrows). Always includes the current year."""
    with connect() as con:
        rows = con.execute("SELECT DISTINCT substr(printed_at, 1, 4) FROM prints").fetchall()
    years = {int(r[0]) for r in rows if r[0]}
    years.add(datetime.now().year)
    return sorted(years)


def monthly_usage(year: int) -> list[dict]:
    """Grams / cost / count for every month (Jan–Dec) of a year."""
    with connect() as con:
        rows = con.execute("""
            SELECT substr(printed_at, 1, 7) AS month,
                   SUM(weight_g) AS grams,
                   SUM(weight_g * price_per_kg / 1000.0) AS cost,
                   COUNT(*) AS prints
            FROM prints
            WHERE substr(printed_at, 1, 4) = ?
            GROUP BY month
        """, (f"{year:04d}",)).fetchall()
    by_month = {r["month"]: dict(r) for r in rows}
    return [by_month.get(f"{year:04d}-{m:02d}", {"month": f"{year:04d}-{m:02d}", "grams": 0, "cost": 0, "prints": 0})
            for m in range(1, 13)]
