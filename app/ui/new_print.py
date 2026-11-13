"""
new_print.py — Log a new print ("/", the first page of the app).

Left: the form. Right: a card that updates LIVE with
    the cost of the print and how much filament will be left on the spool.

After saving, if the spool dropped below "almost_empty_g" (Settings),
the app suggests moving it to the Graveyard.
"""

from nicegui import ui

from .. import services
from ..config import APP_TITLE
from ..theme import PALETTE, level_color
from .layout import grams, money, page_frame, spool_dot
from .print_form import PrintForm


@ui.page("/", title=f"New Print · {APP_TITLE}")
def new_print_page():
    loaded = services.loaded_spool()

    with page_frame("/", "New Print", "Log a finished (or failed) print"):
        with ui.grid().classes("w-full grid-cols-5 gap-5"):

            # ---------------- Form ----------------
            with ui.element("div").classes("cozy-card col-span-3"):
                form = PrintForm(initial={"spool_id": loaded["id"] if loaded else None},
                                 on_change=lambda *_: summary.refresh())
                with ui.row().classes("w-full justify-end gap-2 mt-4"):
                    ui.button("Clear", icon="restart_alt", on_click=lambda: (form.reset(), summary.refresh())) \
                        .props("flat")
                    ui.button("Add print", icon="add_circle", on_click=lambda: save()) \
                        .props("unelevated size=md").classes("px-6")

            # ---------------- Live summary ----------------
            with ui.element("div").classes("cozy-card col-span-2"):
                @ui.refreshable
                def summary():
                    _summary(form)
                summary()

    form.name.on("keydown.enter", lambda: save())
    form.weight.on("keydown.enter", lambda: save())

    def save():
        try:
            services.add_print(form.values())
        except ValueError as e:
            ui.notify(str(e), type="negative", position="top")
            return
        name, spool_id = form.name.value, form.spool.value
        ui.notify(f"“{name}” added to history 🎉", type="positive", position="top")
        form.reset()
        summary.refresh()
        _maybe_suggest_graveyard(spool_id)


def _summary(form: PrintForm) -> None:
    settings = services.get_settings()
    spool = services.get_spool(form.spool.value) if form.spool.value else None
    weight = float(form.weight.value or 0)
    cost = services.print_cost(weight, spool["price_per_kg"] if spool else 0)

    ui.label("Cost of this print").classes("section-title")
    with ui.row().classes("w-full items-end justify-between mt-2"):
        ui.label(money(cost)).classes("text-4xl font-semibold").style(f"color:{PALETTE['lavender_dark']}")
        ui.label(grams(weight, 2)).classes("muted text-lg")

    if not spool:
        ui.label("Choose a filament to see how much will be left.").classes("muted text-sm mt-4")
        return

    after = spool["remaining_g"] - weight
    pct_after = max(0.0, after / spool["initial_weight_g"] * 100)
    with ui.column().classes("w-full gap-2 mt-5 p-4 rounded-2xl").style(f"background:{PALETTE['bg']}"):
        with ui.row().classes("items-center gap-2 no-wrap"):
            spool_dot(spool["color_hex"], 18)
            ui.label(spool["label"]).classes("font-medium")
            ui.label(f"{money(spool['price_per_kg'])}/kg").classes("muted text-xs")
        with ui.row().classes("w-full justify-between"):
            ui.label(f"Now: {grams(max(0, spool['remaining_g']))}").classes("text-sm")
            ui.label(f"After: {grams(after)}").classes("text-sm font-semibold")
        ui.linear_progress(pct_after / 100, show_value=False, size="10px", color=None) \
            .props("rounded track-color=grey-3").style(f"color:{level_color(pct_after)}")
        if after < 0:
            ui.label(f"⚠️ Not enough filament — you are {grams(-after)} short!") \
                .classes("text-sm font-medium").style(f"color:{PALETTE['rose_dark']}")
        elif after < settings["low_stock_g"]:
            ui.label("Heads up: this spool is running low.") \
                .classes("text-sm").style(f"color:{PALETTE['butter_dark']}")


def _maybe_suggest_graveyard(spool_id: int) -> None:
    spool = services.get_spool(spool_id)
    if not spool or spool["remaining_g"] >= services.get_settings()["almost_empty_g"]:
        return
    with ui.dialog() as dialog, ui.card().classes("p-6 rounded-3xl").style("min-width: 360px"):
        with ui.row().classes("items-center gap-3 no-wrap"):
            spool_dot(spool["color_hex"], 28)
            ui.label(f"{spool['label']} is almost empty").classes("section-title")
        ui.label(f"Only {grams(max(0, spool['remaining_g']))} left. Move it to the Graveyard? 🪦").classes("muted")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Not yet", on_click=dialog.close).props("flat")

            def _finish():
                services.finish_spool(spool_id)
                dialog.close()
                ui.notify(f"{spool['label']} rests in peace 🪦 — load a new spool in Storage.", position="top")

            ui.button("Move to Graveyard", icon="heart_broken", on_click=_finish).props("unelevated color=negative")
    dialog.open()
