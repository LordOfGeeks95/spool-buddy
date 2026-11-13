"""
storage.py — Your active spools (/storage).

Numbered list (one below the other). The loaded spool comes first by default.
On top: sorting ("Sort by") and a brand filter.

Each row: number, ring, title (color, name, brand · type · finish)
and below it, side by side: Left (bold), Used, Price, Prints, Opened, Days.
Buttons: Load (put it in the printer), Edit, Graveyard, Delete.

spool_dialog() is used for a NEW spool and for editing
(also from the Graveyard).
"""

from nicegui import ui

from .. import services
from ..config import APP_TITLE
from ..theme import PALETTE
from .layout import (combo_input, confirm, date_input, empty_state, fmt_date, grams, money, page_frame, pill,
                     to_input_date)
from .spool_list import list_toolbar, spool_row

# Suggestions for the dropdowns (you can also type your own values in the app)
MATERIALS = ["PLA", "PLA+", "PETG", "ABS", "ASA", "TPU", "Silk PLA", "PLA-CF", "PETG-CF", "Nylon"]
FINISHES = ["Basic", "Matte", "Silk", "Glossy", "Glow", "Marble", "Sparkle", "Wood", "Translucent"]

# Sort options shown in Storage (in this order)
STORAGE_SORTS = ["left_desc", "left_asc", "code", "name", "brand", "material", "price_desc",
                 "prints_desc", "opened_new", "opened_old"]


@ui.page("/storage", title=f"Storage · {APP_TITLE}")
def storage_page(sort: str = "", brand: str = ""):
    # custom = True when the user picked "Sort by" themselves -> plain sorting.
    # When opening the page from the menu (no ?sort=), the loaded spool comes first.
    custom = sort in STORAGE_SORTS
    state = {"sort": sort if custom else "left_desc", "brand": brand, "custom": custom}

    with page_frame("/storage", "Storage", "Your active spools"):

        @ui.refreshable
        def content():
            settings = services.get_settings()
            all_spools = services.list_spools("active")
            spools = services.list_spools("active", sort=state["sort"], brand=state["brand"] or None,
                                          loaded_first=not state["custom"])

            with ui.row().classes("w-full items-center justify-between"):
                list_toolbar(STORAGE_SORTS, state, services.known_values("brand", finished=False), content.refresh)
                with ui.row().classes("items-center gap-2"):
                    pill(f"{len(all_spools)} spools", "peach")
                    pill(f"{grams(sum(max(0, s['remaining_g']) for s in all_spools))} left", "sage")
                    pill(f"worth {money(sum(s['remaining_value'] for s in all_spools))}", "lavender")
                    ui.button("Add spool", icon="add", on_click=lambda: spool_dialog(None)).props("unelevated")

            if not spools:
                with ui.element("div").classes("cozy-card w-full"):
                    empty_state("inventory_2", "No spools here",
                                "Press “Add spool” to add one." if not all_spools else "No spools match this filter.")
                return

            with ui.column().classes("w-full gap-3"):
                for i, s in enumerate(spools, start=1):
                    _row(i, s, settings)

        content()


def _row(i: int, s: dict, settings: dict) -> None:
    price = money(s["price"])
    if abs(s["initial_weight_g"] - 1000) > 1:  # show €/kg only if it isn't a 1000 g spool
        price += f" · {money(s['price_per_kg'])}/kg"
    stats = [
        # Left: JUST the remaining amount (bold) — that's what the eye looks for first
        ("Left", grams(max(0, s["remaining_g"])), True),
        ("Used", f"{grams(s['used_g'])} of {grams(s['initial_weight_g'])} · {money(s['filament_cost'])}", False),
        ("Price", price, False),
        ("Prints", f"{s['prints_count']}", False),
        ("Opened", fmt_date(s["born"]) if s["born"] else "—", False),
        ("Days", f"{s['days_of_use']}" if s["days_of_use"] is not None else "—", False),
    ]

    almost_empty = s["remaining_g"] < settings["almost_empty_g"]
    pills = []
    if s["is_loaded"]:
        pills.append(("● loaded", "lavender"))
    if s["is_sealed"]:
        pills.append(("● Sealed", "sage"))   # new, unopened spool (never loaded)
    if almost_empty:
        pills.append(("almost empty", "rose"))
    elif s["remaining_g"] < settings["low_stock_g"]:
        pills.append(("running low", "butter"))

    def buttons():
        if not s["is_loaded"]:
            ui.button("Load", icon="play_circle", on_click=lambda: _load(s)).props("flat dense no-caps")
        ui.button(icon="edit", on_click=lambda: spool_dialog(s)).props("flat dense round").tooltip("Edit")
        ui.button(icon="heart_broken", on_click=lambda: _finish(s)) \
            .props(f"{'unelevated' if almost_empty else 'flat'} dense round color=negative") \
            .tooltip("Move to Graveyard")
        if s["prints_count"] == 0:
            ui.button(icon="delete_outline", on_click=lambda: _delete(s)) \
                .props("flat dense round color=grey").tooltip("Delete (only spools without prints)")

    spool_row(i, s, stats, pills, buttons, highlight=bool(s["is_loaded"]))


def _load(s):
    services.load_spool(s["id"])
    ui.notify(f"{s['label']} is now in the printer 🖨️", position="top")
    ui.navigate.reload()  # so the side menu refreshes too


def _finish(s):
    def _do():
        services.finish_spool(s["id"])
        ui.notify(f"{s['label']} moved to the Graveyard 🪦", position="top")
        ui.navigate.reload()

    confirm("Move to Graveyard?",
            f"{s['label']} still has {grams(max(0, s['remaining_g']))}. You can restore it later if needed.",
            _do, "Move", danger=True)


def _delete(s):
    def _do():
        try:
            services.delete_spool(s["id"])
        except ValueError as e:
            ui.notify(str(e), type="negative")
            return
        ui.navigate.reload()

    confirm("Delete spool?", f"{s['label']} will be deleted for good.", _do, "Delete", danger=True)


def spool_dialog(spool: dict | None) -> None:
    """
    New spool (spool=None) or edit an existing one.
    - New: NO opened date (it is set automatically on the first Load).
    - Edit: you can fix the opened date (and the finished date, if it's in the Graveyard).
    """
    settings = services.get_settings()
    s = spool or {}
    with ui.dialog() as dialog, ui.card().classes("p-6 rounded-3xl").style("width: 560px; max-width: 95vw"):
        ui.label("Edit spool" if spool else "New spool").classes("section-title")
        with ui.column().classes("w-full gap-3"):
            with ui.row().classes("w-full gap-3 no-wrap"):
                name = ui.input("Name", value=s.get("name", ""), placeholder="e.g. Black") \
                    .props("outlined").classes("grow")
                # ID: for a NEW spool it's assigned automatically (read-only, shows which one it will get).
                #     In Edit you can change it (it must be unique).
                if spool:
                    code = ui.input("ID", value=s.get("code", "")).props("outlined").classes("w-28")
                else:
                    code = ui.input("ID", value=services.peek_next_code()) \
                        .props("outlined readonly hint=automatic").classes("w-28")
                color = ui.color_input("Color", value=s.get("color_hex", "#B8A9DE")) \
                    .props("outlined").classes("w-40")
            # Fields with suggestions: type "Bam" -> "Bambu Lab" shows up below (or type something new)
            with ui.row().classes("w-full gap-3 no-wrap"):
                material_el, material = combo_input("Type", MATERIALS + services.known_values("material"),
                                                    s.get("material", "PLA"))
                material_el.classes("grow")
                finish_el, finish = combo_input("Finish", FINISHES + services.known_values("finish"),
                                                s.get("finish", "Basic"))
                finish_el.classes("grow")
            brand_el, brand = combo_input("Brand", services.known_values("brand"), s.get("brand", ""))
            brand_el.classes("w-full")
            with ui.row().classes("w-full gap-3 no-wrap"):
                price = ui.number("Price of the spool (€)", value=s.get("price"), min=0, step=0.1) \
                    .props("outlined").classes("grow")
                weight = ui.number("Filament weight (g)",
                                   value=s.get("initial_weight_g", settings["default_spool_weight_g"]),
                                   min=1, step=50).props("outlined").classes("grow")

            opened = finished = load_now = None
            if spool:
                with ui.row().classes("w-full gap-3 no-wrap"):
                    opened = date_input("Opened on", s.get("opened_at") or "", clearable=True).classes("grow")
                    if s.get("finished_at"):
                        finished = date_input("Finished on", s["finished_at"]).classes("grow")
            notes = ui.textarea("Notes", value=s.get("notes", "")).props("outlined autogrow").classes("w-full")
            if not spool:
                load_now = ui.checkbox("Load it in the printer now", value=False)

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def _save():
                data = {"name": name.value, "color_hex": color.value or "#B8A9DE",
                        "material": material() or "PLA", "finish": finish() or "Basic",
                        "brand": brand(), "price": price.value or 0,
                        "initial_weight_g": weight.value, "notes": notes.value or ""}
                # Dates only change if you edited them (otherwise the hidden time would be lost)
                if opened is not None and (opened.value or "") != (to_input_date(s["opened_at"]) if s.get("opened_at") else ""):
                    data["opened_at"] = opened.value or None
                if finished is not None and finished.value and finished.value != to_input_date(s["finished_at"]):
                    data["finished_at"] = finished.value
                try:
                    if spool:
                        services.update_spool(spool["id"], {**data, "code": code.value})
                        saved = services.get_spool(spool["id"])
                    else:
                        saved = services.get_spool(services.create_spool({**data, "is_loaded": load_now.value}))
                except ValueError as e:
                    ui.notify(str(e), type="negative", position="top")
                    return
                dialog.close()
                ui.notify(f"Saved as {saved['label']} ✓", type="positive", position="top")
                ui.navigate.reload()

            ui.button("Save", icon="check", on_click=_save).props("unelevated")
    dialog.open()
