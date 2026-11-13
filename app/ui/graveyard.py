"""
graveyard.py — Finished spools (/graveyard) 🪦.

Same idea as Storage: numbered list, sorting and a brand filter.
Default: the most recently "deceased" spool comes first.

For each spool: when it was "born" (opened), when it "died" (finished),
how many days it lasted, how many prints it made, leftover filament and cost.
Buttons: Edit (e.g. fix dates) and Restore (back to Storage).
"""

from nicegui import ui

from .. import services
from ..config import APP_TITLE
from ..theme import PALETTE
from .layout import empty_state, fmt_date, grams, kpi_card, money, page_frame
from .spool_list import list_toolbar, spool_row
from .storage import spool_dialog

# Sort options shown in the Graveyard (in this order)
GRAVEYARD_SORTS = ["died_new", "died_old", "life_desc", "life_asc", "prints_desc",
                   "code", "name", "brand", "material", "price_desc"]


@ui.page("/graveyard", title=f"Graveyard · {APP_TITLE}")
def graveyard_page(sort: str = "", brand: str = ""):
    custom = sort in GRAVEYARD_SORTS
    state = {"sort": sort if custom else "died_new", "brand": brand, "custom": custom}
    all_spools = services.list_spools("finished")

    with page_frame("/graveyard", "Graveyard", "Rest in peace, dear spools"):
        if not all_spools:
            with ui.element("div").classes("cozy-card w-full"):
                empty_state("local_florist", "Nobody here yet 🌱",
                            "When a spool runs out, send it here from Storage.")
            return

        lifetimes = [s["days_of_use"] for s in all_spools if s["days_of_use"] is not None]
        with ui.grid().classes("w-full grid-cols-4 gap-4"):
            kpi_card("heart_broken", "Finished spools", f"{len(all_spools)}", "rose")
            kpi_card("hourglass_bottom", "Average lifetime",
                     f"{sum(lifetimes) / len(lifetimes):.0f} days" if lifetimes else "—", "lavender")
            kpi_card("scale", "Printed with them", grams(sum(s["used_g"] for s in all_spools)), "sage")
            kpi_card("delete_sweep", "Leftover filament",
                     grams(sum(max(0, s["remaining_g"]) for s in all_spools)), "peach",
                     "what was left on the spools when they died")

        @ui.refreshable
        def content():
            spools = services.list_spools("finished", sort=state["sort"], brand=state["brand"] or None)
            list_toolbar(GRAVEYARD_SORTS, state, services.known_values("brand", finished=True), content.refresh)
            if not spools:
                with ui.element("div").classes("cozy-card w-full"):
                    empty_state("filter_alt_off", "No spools match this filter", "")
                return
            with ui.column().classes("w-full gap-3"):
                for i, s in enumerate(spools, start=1):
                    _row(i, s)

        content()


def _row(i: int, s: dict) -> None:
    per_day = s["used_g"] / s["days_of_use"] if s["days_of_use"] else 0
    stats = [
        ("Lifetime", f"{fmt_date(s['born'])}  →  {fmt_date(s['finished_at'])}", True),
        ("Days of use", f"{s['days_of_use']}" if s["days_of_use"] is not None else "—", False),
        ("Prints", f"{s['prints_count']}", False),
        ("Used", f"{grams(s['used_g'])} of {grams(s['initial_weight_g'])} · {money(s['filament_cost'])}", False),
        ("Leftover", grams(max(0, s["remaining_g"])), False),
        ("Price", money(s["price"]), False),
        ("Per day", grams(per_day, 1), False),
    ]

    def buttons():
        ui.button(icon="edit", on_click=lambda: spool_dialog(s)).props("flat dense round").tooltip("Edit")
        ui.button("Restore", icon="undo", on_click=lambda: _restore(s)).props("flat dense no-caps")

    spool_row(i, s, stats, pills=[("🪦", "rose")], buttons=buttons, background=PALETTE["bg"])


def _restore(s: dict) -> None:
    services.restore_spool(s["id"])
    ui.notify(f"{s['label']} is back in Storage ✨", position="top")
    ui.navigate.reload()
