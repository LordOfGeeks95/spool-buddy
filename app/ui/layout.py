"""
layout.py — The shared page frame + small reusable UI building blocks.

    page_frame(...)   -> side menu + page title
    kpi_card(...)     -> card with an icon and a number (Dashboard)
    spool_dot(...)    -> colored spool dot
    date_input(...)   -> DD/MM/YYYY date field with a calendar
    combo_input(...)  -> text field with suggestions
    money/grams/...   -> number & date formatting

Icons are Material Icons: https://fonts.google.com/icons
(just use the name, e.g. "add_circle").
"""

import inspect
from contextlib import contextmanager
from datetime import datetime

from nicegui import ui

from .. import services
from ..config import APP_TAGLINE, ICON_PNG
from ..theme import PALETTE, apply_quasar_colors

# ---------------------------------------------------------------------------
# The menu: (route, title, icon, palette color)
# Change order / icons / colors here and it changes everywhere.
# The FIRST entry is the page that opens when the app starts ("/").
# ---------------------------------------------------------------------------
NAV = [
    ("/", "New Print", "add_circle", "sage"),
    ("/storage", "Storage", "inventory_2", "peach"),
    ("/dashboard", "Dashboard", "space_dashboard", "lavender"),
    ("/history", "History", "history", "sky"),
    ("/graveyard", "Graveyard", "heart_broken", "rose"),
    ("/settings", "Settings", "tune", "butter"),
]


# ===========================================================================
# Formatting
# ===========================================================================

def money(value: float | None) -> str:
    return f"€{(value or 0):,.2f}"


# The weight unit shown everywhere in the app.
GRAM_UNIT = "g"


def grams(value: float | None, decimals: int = 0) -> str:
    """ALWAYS in grams (never kg): 532 -> '532 g', 6028.7 -> '6,029 g'."""
    return f"{(value or 0):,.{decimals}f} {GRAM_UNIT}"


def fmt_date(value: str | None) -> str:
    """Date for display, WITHOUT time: '28 Sep 2026'."""
    dt = services.parse_dt(value) if isinstance(value, str) else value
    if not dt:
        return "—"
    return dt.strftime("%d %b %Y")


# Date format in input fields: DD/MM/YYYY
DATE_INPUT_FMT = "%d/%m/%Y"


def to_input_date(value: str | None = None) -> str:
    """'2026-09-28 14:03:00' -> '28/09/2026'. No value -> today."""
    dt = services.parse_dt(value) if value else datetime.now()
    return dt.strftime(DATE_INPUT_FMT)


def date_input(label: str, value: str | None = "", on_change=None, clearable: bool = False) -> ui.input:
    """
    Date field 28/09/2026 with a calendar (click the icon). No time.
    value: a date in any database format, '' for empty (None = today).
    The field's .value is the text 'DD/MM/YYYY' — services.parse_dt understands it.
    """
    initial = to_input_date(value) if value is None or value else ""
    field = ui.input(label, value=initial, on_change=on_change) \
        .props("outlined mask='##/##/####' placeholder='DD/MM/YYYY' stack-label" + (" clearable" if clearable else ""))
    with field.add_slot("append"):
        icon = ui.icon("event").classes("cursor-pointer")
        with ui.menu().props("no-parent-event") as menu:
            # The calendar writes straight into the field (same DD/MM/YYYY format) and closes once you pick a day
            ui.date(mask="DD/MM/YYYY", on_change=lambda: menu.close()).props("first-day-of-week=1") \
                .bind_value(field)
        icon.on("click", menu.open)
    return field


def combo_input(label: str, options: list[str], value: str | None = None):
    """
    Text field with suggestions: type "Bam" -> "Bambu Lab" shows up below, click it.
    You can also type something NEW (no Enter needed — whatever you typed is kept).
    Returns (element, get) — get() returns the final value.
    """
    typed = {"text": value or ""}
    element = ui.select(sorted(set(o for o in options if o)), label=label, value=value or None,
                        with_input=True, new_value_mode="add-unique").props("outlined")
    # ALWAYS keep the latest: what was typed OR what was picked from the list
    # (otherwise: type "Bam", click "Bambu Lab", and "Bam" would be saved)
    element.on("input-value", lambda e: typed.update(text=e.args or ""))
    element.on_value_change(lambda e: typed.update(text=e.value or ""))

    def get() -> str:
        return (typed["text"] or element.value or "").strip()

    return element, get


# ===========================================================================
# Small components
# ===========================================================================

def spool_dot(color: str, size: int = 14) -> ui.element:
    return ui.element("span").classes("spool-dot").style(
        f"background:{color}; width:{size}px; height:{size}px; min-width:{size}px"
    )


def pill(text: str, tone: str = "lavender") -> ui.label:
    """Small rounded badge. tone = a color name from PALETTE."""
    return ui.label(text).classes("pill").style(
        f"background:{PALETTE[tone]}55; color:{PALETTE[tone + '_dark']}"
    )


def icon_badge(icon: str, tone: str, size: int = 46) -> None:
    """Rounded square with a pastel background and an icon."""
    with ui.element("div").classes("kpi-icon").style(
        f"background:{PALETTE[tone]}40; color:{PALETTE[tone + '_dark']};"
        f"width:{size}px; height:{size}px; min-width:{size}px"
    ):
        ui.icon(icon)


def kpi_card(icon: str, label: str, value: str, tone: str, sub: str | None = None) -> None:
    with ui.element("div").classes("cozy-card"):
        with ui.row().classes("items-center gap-4 no-wrap"):
            icon_badge(icon, tone)
            with ui.column().classes("gap-0"):
                ui.label(label).classes("kpi-label")
                ui.label(value).classes("kpi-value")
        if sub:
            ui.label(sub).classes("muted text-xs mt-2")


def empty_state(icon: str, title: str, text: str) -> None:
    with ui.column().classes("w-full items-center py-10 gap-2"):
        ui.icon(icon).classes("text-6xl").style(f"color:{PALETTE['lavender']}")
        ui.label(title).classes("section-title")
        ui.label(text).classes("muted text-center")


def confirm(title: str, text: str, on_yes, yes_label: str = "Yes", danger: bool = False) -> None:
    """Confirmation dialog (e.g. before deleting something)."""
    with ui.dialog() as dialog, ui.card().classes("p-6 rounded-3xl").style("min-width: 340px"):
        ui.label(title).classes("section-title")
        ui.label(text).classes("muted")
        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            async def _yes():
                dialog.close()
                result = on_yes()
                if inspect.isawaitable(result):  # also works with async functions
                    await result

            ui.button(yes_label, on_click=_yes).props(f"unelevated color={'negative' if danger else 'primary'}")
    dialog.open()


# ===========================================================================
# The page frame
# ===========================================================================

@contextmanager
def page_frame(active: str, title: str, subtitle: str = ""):
    """
    Used by every page:
        with page_frame("/storage", "Storage", "Your spools"):
            ... content ...
    """
    apply_quasar_colors()
    current = next((n for n in NAV if n[0] == active), NAV[0])

    # --- Side menu (always open — this is a desktop app) ---
    with ui.left_drawer(value=True, bordered=False).style(
        f"background:{PALETTE['sidebar']}"
    ).props("width=250 breakpoint=0").classes("p-0"):
        # Top left: icon in an off-white rounded frame + tagline next to it
        # (the app name is already in the window title bar). Frame style: .app-icon-frame in theme.py
        with ui.row().classes("items-center gap-3 px-4 pt-6 pb-5 no-wrap w-full"):
            with ui.element("div").classes("app-icon-frame"):
                if ICON_PNG.exists():
                    # Path (not str) -> NiceGUI serves the local file to the window
                    ui.image(ICON_PNG).style("width:50px; height:50px").props("no-spinner fit=contain")
                else:
                    ui.label("🧵").classes("text-3xl")
            ui.label(APP_TAGLINE).classes("text-sm font-medium italic leading-snug").style(
                f"color:{PALETTE['text']}"
            )

        for path, label, icon, tone in NAV:
            is_active = path == active
            with ui.element("a").props(f"href={path}").classes(
                "nav-item" + (" active" if is_active else "")
            ):
                with ui.element("div").classes("nav-icon").style(
                    f"background:{PALETTE[tone]}45; color:{PALETTE[tone + '_dark']}"
                ):
                    ui.icon(icon)
                ui.label(label)

        # Bottom of the menu: the loaded spool
        loaded = services.loaded_spool()
        with ui.element("a").props("href=/storage").classes("nav-item mt-6 mb-4").style(
            "background: rgba(255,255,255,.6)"
        ):
            if loaded:
                spool_dot(loaded["color_hex"], 22)
                with ui.column().classes("gap-0"):
                    ui.label("Now loaded").classes("muted text-xs")
                    ui.label(loaded["label"]).classes("text-sm font-medium")
                    ui.label(f"{grams(loaded['remaining_g'])} left").classes("muted text-xs")
            else:
                ui.icon("help_outline").classes("text-xl muted")
                ui.label("No spool loaded").classes("text-sm muted")

    # --- Content ---
    with ui.column().classes("w-full max-w-7xl mx-auto px-4 md:px-8 py-6 gap-5"):
        with ui.row().classes("items-center gap-4 no-wrap"):
            icon_badge(current[2], current[3], 52)
            with ui.column().classes("gap-1"):
                ui.label(title).classes("page-title")
                if subtitle:
                    ui.label(subtitle).classes("page-subtitle")
        yield
