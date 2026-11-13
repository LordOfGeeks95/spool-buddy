"""
history.py — The full print history (/history).

    - Search (name or notes), filament filter, success/failed, date range
    - Totals for whatever is shown (count, grams, cost)
    - Edit / Delete on every row
    (Exporting all data is done from Settings.)

Table columns are defined in COLUMNS. The "slots" below are small
Vue/HTML snippets for custom rendering (color dot, buttons).
"""

from nicegui import ui

from .. import services
from ..config import APP_TITLE
from .layout import confirm, date_input, fmt_date, grams, money, page_frame
from .print_form import PrintForm, spool_options

COLUMNS = [
    {"name": "number", "label": "#", "field": "number", "sortable": True, "align": "left"},
    {"name": "printed_at", "label": "Date", "field": "printed_at", "sortable": True, "align": "left"},
    {"name": "name", "label": "Print", "field": "name", "sortable": True, "align": "left"},
    {"name": "spool", "label": "Filament", "field": "spool_name", "sortable": True, "align": "left"},
    {"name": "weight_g", "label": "Weight", "field": "weight_g", "sortable": True, "align": "right"},
    {"name": "cost", "label": "Cost", "field": "cost", "sortable": True, "align": "right"},
    {"name": "status", "label": "Status", "field": "failed", "sortable": True, "align": "center"},
    {"name": "actions", "label": "", "field": "id", "align": "right"},
]


@ui.page("/history", title=f"History · {APP_TITLE}")
def history_page():
    # Current filter state
    f = {"search": "", "spool_id": None, "status": "all", "date_from": "", "date_to": ""}

    def current_prints() -> list[dict]:
        return services.list_prints(f["search"], f["spool_id"], f["status"], f["date_from"], f["date_to"])

    with page_frame("/history", "History", "Every print you have ever made"):

        # ---------------- Filters ----------------
        with ui.element("div").classes("cozy-card w-full"):
            with ui.row().classes("w-full items-center gap-3"):
                ui.input(placeholder="Search prints or notes…", on_change=lambda e: set_filter("search", e.value)) \
                    .props("outlined dense clearable debounce=300").classes("grow").style("min-width:220px") \
                    .add_slot("prepend", '<q-icon name="search" />')
                ui.select({0: "All filaments", **spool_options(include_finished=True)}, value=0,
                          on_change=lambda e: set_filter("spool_id", e.value)) \
                    .props("outlined dense").style("min-width:220px")
                ui.toggle({"all": "All", "success": "✓ Success", "failed": "✗ Failed"}, value="all",
                          on_change=lambda e: set_filter("status", e.value)).props("unelevated rounded no-caps")
                date_input("From", "", on_change=lambda e: set_date("date_from", e.value), clearable=True) \
                    .props("dense").classes("w-44")
                date_input("To", "", on_change=lambda e: set_date("date_to", e.value), clearable=True) \
                    .props("dense").classes("w-44")

        # ---------------- Totals (of what is shown) ----------------
        totals = ui.label().classes("muted")

        # ---------------- Table ----------------
        table = ui.table(columns=COLUMNS, rows=[], row_key="id",
                         pagination={"rowsPerPage": 20, "sortBy": "printed_at", "descending": True}) \
            .classes("w-full").props("flat")

        table.add_slot("body-cell-printed_at", """
            <q-td :props="props"><span class="text-no-wrap">{{ props.row.date_label }}</span></q-td>""")
        table.add_slot("body-cell-name", """
            <q-td :props="props">
              <div style="font-weight:500">{{ props.row.name }}</div>
              <div v-if="props.row.notes" class="muted text-xs ellipsis" style="max-width:260px">{{ props.row.notes }}</div>
            </q-td>""")
        table.add_slot("body-cell-spool", """
            <q-td :props="props">
              <span class="spool-dot" :style="{background: props.row.spool_color}"></span>{{ props.row.spool_name }}
            </q-td>""")
        table.add_slot("body-cell-weight_g", """
            <q-td :props="props">{{ props.row.weight_g.toFixed(2) }} g</q-td>""")
        table.add_slot("body-cell-cost", """
            <q-td :props="props">€{{ props.row.cost.toFixed(2) }}</q-td>""")
        table.add_slot("body-cell-status", """
            <q-td :props="props">
              <span v-if="props.row.failed" class="pill" style="background:#EFA7B855;color:#C2627A">failed</span>
              <span v-else class="pill" style="background:#A8C9A155;color:#5E8F57">ok</span>
            </q-td>""")
        table.add_slot("body-cell-actions", """
            <q-td :props="props" class="text-no-wrap">
              <q-btn flat round dense size="sm" icon="edit" color="primary" @click="() => $parent.$emit('edit', props.row.id)" />
              <q-btn flat round dense size="sm" icon="delete_outline" color="negative" @click="() => $parent.$emit('delete', props.row.id)" />
            </q-td>""")

    # ---------------- Logic ----------------
    def reload() -> None:
        rows = current_prints()
        for r in rows:
            r["date_label"] = fmt_date(r["printed_at"])
        table.rows = rows
        table.update()
        totals.text = (f"{len(rows)} prints · {grams(sum(r['weight_g'] for r in rows))} · "
                       f"{money(sum(r['cost'] for r in rows))}")

    def set_filter(key, value) -> None:
        f[key] = value or ("all" if key == "status" else None if key == "spool_id" else "")
        reload()

    def set_date(key, value) -> None:
        """The filter only applies once the date is complete (e.g. 28/09/2026) or empty."""
        try:
            day = services.parse_dt(value) if value else None
        except ValueError:
            return  # still being typed
        set_filter(key, day.strftime("%Y-%m-%d") if day else "")

    def on_delete(e) -> None:
        p = services.get_print(e.args)
        if not p:
            return

        def _do():
            services.delete_print(p["id"])
            ui.notify(f"Deleted “{p['name']}”", position="top")
            reload()

        confirm("Delete print?", f"“{p['name']}” ({grams(p['weight_g'])}) will be removed for good.",
                _do, "Delete", danger=True)

    def on_edit(e) -> None:
        p = services.get_print(e.args)
        if p:
            edit_dialog(p, reload)

    table.on("edit", on_edit)
    table.on("delete", on_delete)
    reload()


def edit_dialog(p: dict, on_saved) -> None:
    with ui.dialog() as dialog, ui.card().classes("p-6 rounded-3xl").style("width: 640px; max-width: 95vw"):
        ui.label(f"Edit print #{p['number']}").classes("section-title")
        form = PrintForm(initial=p, include_finished=True)
        ui.label("Tip: the €/kg price stays as it was when printed, unless you change the filament.") \
            .classes("muted text-xs")
        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Cancel", on_click=dialog.close).props("flat")

            def _save():
                try:
                    services.update_print(p["id"], form.values())
                except ValueError as e:
                    ui.notify(str(e), type="negative", position="top")
                    return
                dialog.close()
                ui.notify("Saved ✓", type="positive", position="top")
                on_saved()

            ui.button("Save", icon="check", on_click=_save).props("unelevated")
    dialog.open()
