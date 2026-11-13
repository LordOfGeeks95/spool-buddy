"""
spool_list.py — Shared pieces for the spool lists (Storage + Graveyard).

    list_toolbar(...) -> bar with "Sort by" and a brand filter
    spool_row(...)    -> one row card: number, ring, title (color, name,
                         brand · type · finish) and the stats laid out HORIZONTALLY below

Sort options are defined in services.SPOOL_SORTS.
The sort/filter is written to the URL (?sort=...&brand=...) so it isn't lost
when the page reloads (e.g. after pressing Load).
"""

from urllib.parse import urlencode

from nicegui import ui

from .. import services
from ..theme import PALETTE, level_color
from .layout import spool_dot


def list_toolbar(sort_keys: list[str], state: dict, brands: list[str], on_change) -> None:
    """
    state = {"sort": ..., "brand": ..., "custom": bool}. Calls on_change() whenever something changes.
    custom: becomes True as soon as the user picks a "Sort by" option -> the sort then applies to the
    loaded spool too (it no longer sticks to the top). Leaving the page resets everything.
    """

    def _set(key, value):
        state[key] = value or ""
        if key == "sort":
            state["custom"] = True
        # Keep the choice in the URL without reloading the page (so it survives Load etc.).
        # The sort only goes into the URL if the user picked it.
        params = {"sort": state["sort"] if state.get("custom") else "", "brand": state["brand"]}
        query = urlencode({k: v for k, v in params.items() if v})
        ui.run_javascript(f"history.replaceState(null, '', '?{query}')")
        on_change()

    with ui.row().classes("items-center gap-3"):
        ui.select({k: services.SPOOL_SORTS[k][0] for k in sort_keys}, value=state["sort"], label="Sort by",
                  on_change=lambda e: _set("sort", e.value)).props("outlined dense").classes("w-56")
        ui.select({"": "All brands", **{b: b for b in brands}}, value=state["brand"], label="Brand",
                  on_change=lambda e: _set("brand", e.value)).props("outlined dense").classes("w-44")


def spool_row(index: int, s: dict, stats: list[tuple[str, str, bool]], pills=(), buttons=None,
              background: str | None = None, highlight: bool = False) -> None:
    """
    index   -> the number on the left (1, 2, 3...)
    stats   -> [(label, value, bold?), ...] — shown side by side
    pills   -> [(text, palette color), ...] next to the title
    buttons -> function that builds the buttons on the right
    """
    style = f"background:{background};" if background else ""
    if highlight:
        style += f"border: 2px solid {PALETTE['lavender']};"
    with ui.element("div").classes("cozy-card w-full").style(style + "padding:16px 20px"):
        with ui.row().classes("w-full items-center gap-5 no-wrap"):
            # --- Number ---
            ui.label(str(index)).classes("text-lg font-semibold text-center").style(
                f"min-width:34px; color:{PALETTE['muted']}"
            )

            # --- Remaining-filament ring ---
            with ui.element("div").classes("relative"):
                ui.circular_progress(s["percent_left"], max=100, show_value=False, size="72px", color=None) \
                    .props("thickness=0.16 track-color=grey-3 rounded").style(f"color:{level_color(s['percent_left'])}")
                with ui.column().classes("absolute inset-0 items-center justify-center"):
                    ui.label(f"{s['percent_left']:.0f}%").classes("text-sm font-semibold")

            # --- Title + stats ---
            with ui.column().classes("grow gap-2 min-w-0"):
                with ui.row().classes("items-center gap-3 no-wrap"):
                    spool_dot(s["color_hex"], 22)
                    ui.label(s["label"]).classes("text-lg font-semibold")
                    ui.label(" · ".join(x for x in (s["brand"], s["material"], s["finish"]) if x)) \
                        .classes("muted text-sm")
                    for text, tone in pills:
                        ui.label(text).classes("pill").style(
                            f"background:{PALETTE[tone]}55; color:{PALETTE[tone + '_dark']}"
                        )
                with ui.row().classes("gap-x-8 gap-y-1 items-start"):
                    for label, value, bold in stats:
                        with ui.column().classes("gap-0"):
                            ui.label(label).classes("muted text-xs")
                            ui.label(value).classes(
                                "text-no-wrap " + ("text-base font-bold" if bold else "text-sm font-medium")
                            )
                if s["notes"]:
                    ui.label(s["notes"]).classes("muted text-xs")

            # --- Buttons ---
            if buttons:
                with ui.row().classes("items-center gap-1 no-wrap"):
                    buttons()
