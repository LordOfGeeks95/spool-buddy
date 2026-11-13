"""
dashboard.py — Statistics (/dashboard).

Contains:
    - 6 KPI cards in 2 rows of 3 (their order is defined in _kpis)
    - The loaded spool with a remaining-filament ring + how many prints still fit
    - Monthly usage chart for ONE year, with ‹ › arrows for other years
    - "Donut" chart of usage per spool (in each spool's own color)
    - Recent prints & warnings for spools that are running low
"""

from datetime import datetime

from nicegui import ui

from .. import services
from ..config import APP_TITLE
from ..theme import FONT_STACK, PALETTE, level_color
from .layout import empty_state, fmt_date, grams, kpi_card, money, page_frame, pill, spool_dot


@ui.page("/dashboard", title=f"Dashboard · {APP_TITLE}")
def dashboard_page():
    stats = services.dashboard_stats()
    settings = services.get_settings()
    loaded = services.loaded_spool()

    with page_frame("/dashboard", "Dashboard", "Everything about your printing at a glance"):

        # ---------------- KPI cards (3 + 3) ----------------
        with ui.grid().classes("w-full grid-cols-3 gap-4"):
            _kpis(stats)

        # ---------------- Loaded spool + yearly chart ----------------
        with ui.grid().classes("w-full grid-cols-3 gap-4"):
            _loaded_card(loaded, stats["avg_recent_g"])
            with ui.element("div").classes("cozy-card col-span-2"):
                _yearly_chart()

        # ---------------- Donut per spool + recent prints ----------------
        with ui.grid().classes("w-full grid-cols-3 gap-4"):
            with ui.element("div").classes("cozy-card"):
                ui.label("Usage per spool").classes("section-title")
                _spool_donut()
            with ui.element("div").classes("cozy-card col-span-2"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Recent prints").classes("section-title")
                    ui.button("See all", icon="arrow_forward",
                              on_click=lambda: ui.navigate.to("/history")).props("flat dense")
                _recent_prints()

        # ---------------- Warnings ----------------
        low = [s for s in services.list_spools("active") if s["remaining_g"] < settings["low_stock_g"]]
        if low:
            with ui.element("div").classes("cozy-card w-full"):
                with ui.row().classes("items-center gap-2"):
                    ui.icon("warning_amber").style(f"color:{PALETTE['butter_dark']}").classes("text-xl")
                    ui.label("Running low").classes("section-title")
                with ui.row().classes("gap-3 mt-2 flex-wrap"):
                    for s in low:
                        with ui.row().classes("items-center gap-2 px-3 py-2 rounded-xl").style(
                            f"background:{PALETTE['rose']}22"
                        ):
                            spool_dot(s["color_hex"])
                            ui.label(s["label"]).classes("font-medium")
                            ui.label(f"{grams(max(0, s['remaining_g']))} left").classes("muted text-sm")
                ui.label("Tip: finished spools can be moved to the Graveyard from Storage.") \
                    .classes("muted text-xs mt-2")


def _kpis(stats: dict) -> None:
    """The 6 cards. Reorder these lines to reorder them on screen."""
    kpi_card("inventory_2", "Filament in storage", grams(stats["remaining_g"]), "peach",
             f"{stats['active_spools']} spools · worth {money(stats['remaining_value'])}")
    kpi_card("print", "Prints", f"{stats['prints']}", "sky",
             f"{stats['success_rate']:.0f}% success rate")
    kpi_card("sentiment_dissatisfied", "Failed prints", f"{stats['failed']}", "rose",
             f"{money(stats['failed_cost'])} wasted · {grams(stats['failed_g'])}")
    kpi_card("scale", "Filament printed", grams(stats["grams"]), "sage",
             f"avg {grams(stats['avg_g'])} per print · heaviest {grams(stats['heaviest'])}")
    kpi_card("payments", "Spent on filament", money(stats["cost"]), "lavender",
             f"{money(stats['invested'])} invested in spools")
    kpi_card("heart_broken", "Spools in the Graveyard", f"{stats['graveyard_spools']}", "mint",
             f"{grams(stats['graveyard_used_g'])} printed with them")


def _loaded_card(loaded: dict | None, avg_g: float) -> None:
    with ui.element("div").classes("cozy-card"):
        ui.label("Loaded in the printer").classes("section-title")
        if not loaded:
            empty_state("help_outline", "No spool loaded", "Go to Storage and press “Load” on a spool.")
            return
        with ui.row().classes("items-center gap-3 mt-2 no-wrap"):
            spool_dot(loaded["color_hex"], 26)
            with ui.column().classes("gap-0"):
                ui.label(loaded["label"]).classes("text-lg font-semibold")
                ui.label(f"{loaded['brand']} · {loaded['material']} · {loaded['finish']}").classes("muted text-sm")

        with ui.row().classes("w-full items-center justify-center gap-6 mt-4 no-wrap"):
            with ui.element("div").classes("relative"):
                ui.circular_progress(loaded["percent_left"], max=100, show_value=False, size="130px",
                                     color=None).props("thickness=0.16 track-color=grey-3 rounded") \
                    .style(f"color:{level_color(loaded['percent_left'])}")
                with ui.column().classes("absolute inset-0 items-center justify-center gap-0"):
                    ui.label(f"{loaded['percent_left']:.0f}%").classes("text-2xl font-semibold")
                    ui.label("left").classes("muted text-xs")
            with ui.column().classes("gap-1"):
                ui.label(grams(max(0, loaded["remaining_g"]))).classes("text-xl font-semibold")
                ui.label(f"of {grams(loaded['initial_weight_g'])}").classes("muted text-sm")
                left = services.estimate_prints_left(loaded, avg_g)
                if left is not None:
                    pill(f"≈ {left} more prints", "sage")
                ui.label(f"avg print {grams(avg_g)}").classes("muted text-xs")

        ui.button("New print", icon="add", on_click=lambda: ui.navigate.to("/")) \
            .props("unelevated").classes("w-full mt-4")


def _chart_base() -> dict:
    """Shared settings for all charts (font, text colors)."""
    return {
        "textStyle": {"fontFamily": FONT_STACK, "color": PALETTE["text"]},
        "tooltip": {"trigger": "axis", "backgroundColor": "#fff", "borderColor": PALETTE["border"],
                    "textStyle": {"color": PALETTE["text"]}},
    }


def _yearly_chart() -> None:
    """Jan–Dec chart for one year. The arrows switch year (only years with data + the current one)."""
    years = services.years_with_prints()
    state = {"year": datetime.now().year}

    @ui.refreshable
    def chart():
        year = state["year"]
        data = services.monthly_usage(year)
        total_g = sum(d["grams"] for d in data)
        total_cost = sum(d["cost"] for d in data)
        total_prints = sum(d["prints"] for d in data)

        with ui.row().classes("w-full items-center justify-between no-wrap"):
            with ui.column().classes("gap-0"):
                ui.label("Monthly usage").classes("section-title")
                ui.label(f"{year}: {grams(total_g)} · {money(total_cost)} · {total_prints} prints") \
                    .classes("muted text-sm")
            with ui.row().classes("items-center gap-1 no-wrap"):
                i = years.index(year)
                ui.button(icon="chevron_left", on_click=lambda: go(-1)) \
                    .props(f"flat round dense {'disable' if i == 0 else ''}")
                ui.label(str(year)).classes("text-lg font-semibold px-2")
                ui.button(icon="chevron_right", on_click=lambda: go(+1)) \
                    .props(f"flat round dense {'disable' if i == len(years) - 1 else ''}")

        ui.echart({
            **_chart_base(),
            "grid": {"left": 55, "right": 50, "top": 45, "bottom": 30},
            "legend": {"data": ["Grams", "Cost (€)"], "top": 0, "left": "center",
                       "textStyle": {"color": PALETTE["muted"]}},
            "xAxis": {"type": "category",
                      "data": [datetime(year, m, 1).strftime("%b") for m in range(1, 13)],
                      "axisLine": {"lineStyle": {"color": PALETTE["border"]}},
                      "axisLabel": {"color": PALETTE["muted"]}},
            "yAxis": [
                {"type": "value", "name": "g", "axisLabel": {"color": PALETTE["muted"]},
                 "splitLine": {"lineStyle": {"color": PALETTE["border"], "type": "dashed"}}},
                {"type": "value", "name": "€", "axisLabel": {"color": PALETTE["muted"]},
                 "splitLine": {"show": False}},
            ],
            "series": [
                {"name": "Grams", "type": "bar", "data": [round(d["grams"], 1) for d in data],
                 "barMaxWidth": 34,
                 "itemStyle": {"color": PALETTE["lavender"], "borderRadius": [10, 10, 0, 0]}},
                {"name": "Cost (€)", "type": "line", "yAxisIndex": 1, "smooth": True, "symbolSize": 7,
                 "data": [round(d["cost"], 2) for d in data],
                 "itemStyle": {"color": PALETTE["peach_dark"]}, "lineStyle": {"width": 3}},
            ],
        }).classes("w-full h-72 mt-2")

    def go(step: int) -> None:
        i = years.index(state["year"]) + step
        if 0 <= i < len(years):
            state["year"] = years[i]
            chart.refresh()

    chart()


def _spool_donut() -> None:
    spools = [s for s in services.list_spools("all") if s["used_g"] > 0]
    if not spools:
        empty_state("donut_large", "No data yet", "Add a print to see this chart.")
        return
    ui.echart({
        **_chart_base(),
        "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c} g ({d}%)"},
        "series": [{
            "type": "pie", "radius": ["48%", "75%"], "center": ["50%", "50%"],
            "itemStyle": {"borderColor": "#fff", "borderWidth": 3, "borderRadius": 8},
            "label": {"show": False},
            "data": [{"name": s["label"], "value": round(s["used_g"], 1),
                      # thin border so even white filament stays visible
                      "itemStyle": {"color": s["color_hex"], "borderColor": "#E0D8CE", "borderWidth": 1}}
                     for s in spools],
        }],
    }).classes("w-full h-64")
    with ui.column().classes("gap-1 mt-1"):
        for s in sorted(spools, key=lambda x: -x["used_g"]):
            with ui.row().classes("items-center gap-2 no-wrap"):
                spool_dot(s["color_hex"], 10)
                ui.label(s["label"]).classes("text-sm")
                ui.label(grams(s["used_g"])).classes("muted text-xs")


def _recent_prints() -> None:
    prints = services.list_prints(limit=7)
    if not prints:
        empty_state("print", "No prints yet", "Your latest prints will show up here.")
        return
    with ui.column().classes("w-full gap-1 mt-2"):
        for p in prints:
            with ui.row().classes("w-full items-center gap-3 py-2 px-2 rounded-xl no-wrap hover:bg-[#F7F1EA]"):
                spool_dot(p["spool_color"], 16)
                with ui.column().classes("gap-0 grow min-w-0"):
                    with ui.row().classes("items-center gap-2 no-wrap"):
                        ui.label(p["name"]).classes("font-medium ellipsis")
                        if p["failed"]:
                            pill("failed", "rose")
                    ui.label(f"{p['spool_name']} · {fmt_date(p['printed_at'])}").classes("muted text-xs")
                with ui.column().classes("gap-0 items-end"):
                    ui.label(grams(p["weight_g"], 2)).classes("text-sm font-medium")
                    ui.label(money(p["cost"])).classes("muted text-xs")
