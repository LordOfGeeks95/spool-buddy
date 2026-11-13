"""
print_form.py — The fields of a print form.

Used in TWO places so the same thing isn't written twice:
    - New Print
    - History -> Edit

PrintForm provides:
    .values()  -> dict ready for services.add_print / update_print
    .reset()   -> clears the fields (keeps the selected spool)
"""

from datetime import datetime

from nicegui import ui

from .. import services
from .layout import date_input, grams, to_input_date


def spool_options(include_finished: bool = False) -> dict[int, str]:
    """Dropdown options: {id: 'Grey (F7) · 396 g left'}."""
    spools = services.list_spools("all" if include_finished else "active", sort="name")
    opts = {}
    for s in spools:
        tag = "  🪦" if s["is_finished"] else f" · {grams(max(0, s['remaining_g']))} left"
        opts[s["id"]] = f"{s['label']}{tag}"
    return opts


class PrintForm:
    def __init__(self, initial: dict | None = None, include_finished: bool = False, on_change=None):
        initial = initial or {}
        change = on_change or (lambda *_: None)
        past_names = sorted({p["name"] for p in services.list_prints(limit=300)})
        # The time is NEVER shown. The database still stores one so prints of the same day stay
        # in the right order: when editing we keep the original time, new prints get the current time.
        old = services.parse_dt(initial.get("printed_at"))
        self._time = old.strftime("%H:%M:%S") if old else None

        with ui.column().classes("w-full gap-3"):
            self.name = ui.input("Print name", value=initial.get("name", ""),
                                 autocomplete=past_names, on_change=change) \
                .props("outlined clearable").classes("w-full")

            with ui.row().classes("w-full gap-3 no-wrap"):
                self.weight = ui.number("Weight (g)", value=initial.get("weight_g"), min=0, step=0.01,
                                        on_change=change).props("outlined").classes("grow")
                self.spool = ui.select(spool_options(include_finished), label="Filament",
                                       value=initial.get("spool_id"), on_change=change) \
                    .props("outlined").classes("grow").style("min-width: 220px")

            with ui.row().classes("w-full gap-3 items-center no-wrap"):
                self.date = date_input("Date", initial.get("printed_at")).classes("grow")
                self.failed = ui.switch("Failed print", value=bool(initial.get("failed")), on_change=change) \
                    .props("color=negative")

            self.notes = ui.textarea("Notes — optional", value=initial.get("notes", "")) \
                .props("outlined autogrow").classes("w-full")

    # -----------------------------------------------------------------
    def _printed_at(self) -> str:
        """'28/09/2026' + (hidden) time -> '2026-09-28 14:03:00'. Invalid date -> ValueError."""
        day = services.parse_dt(self.date.value)
        if not day:
            raise ValueError("Choose a date")
        return f"{day:%Y-%m-%d} {self._time or datetime.now().strftime('%H:%M:%S')}"

    def values(self) -> dict:
        return {
            "name": self.name.value,
            "weight_g": self.weight.value,
            "spool_id": self.spool.value,
            "printed_at": self._printed_at(),
            "failed": self.failed.value,
            "notes": self.notes.value,
        }

    def reset(self) -> None:
        self.name.value = None
        self.weight.value = None
        self.notes.value = ""
        self.failed.value = False
        self.date.value = to_input_date()
        self.spool.options = spool_options()
        self.spool.update()
