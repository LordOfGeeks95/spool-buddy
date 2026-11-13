"""
settings.py — Preferences & data (/settings).

Two cards:
    1. Alerts & defaults -> warning thresholds, default spool weight
       (generated AUTOMATICALLY from DEFAULT_SETTINGS in config.py)
    2. Your data -> Export EVERYTHING to one .json file / Import from such a file
       (to move to a new app version or another computer — see transfer.py)

In window (native) mode the regular Windows file dialog opens.
In the browser (--browser) the export is downloaded and the import is an upload.
"""

from datetime import datetime

from nicegui import app, ui

from .. import transfer
from .. import services
from ..config import APP_TITLE, DEFAULT_SETTINGS
from .layout import confirm, icon_badge, page_frame

try:
    import webview  # pywebview — only needed in window mode
except ImportError:  # pragma: no cover
    webview = None

FILE_TYPES = ("Spool Buddy data (*.json)", "All files (*.*)")


def _card_title(icon: str, tone: str, title: str, subtitle: str = "") -> None:
    with ui.row().classes("items-center gap-3 no-wrap mb-3"):
        icon_badge(icon, tone, 40)
        with ui.column().classes("gap-0"):
            ui.label(title).classes("section-title")
            if subtitle:
                ui.label(subtitle).classes("muted text-xs")


def _native_window():
    """The app window, or None when running in the browser."""
    return getattr(app.native, "main_window", None) if webview else None


def _first(result):
    """pywebview returns either a str or a tuple — always get a single path."""
    if not result:
        return None
    return result[0] if isinstance(result, (list, tuple)) else result


@ui.page("/settings", title=f"Settings · {APP_TITLE}")
def settings_page():
    values = services.get_settings()

    with page_frame("/settings", "Settings", "A few preferences and your data"):
        with ui.grid().classes("w-full grid-cols-2 gap-4"):

            # ---------------- Thresholds & defaults ----------------
            with ui.element("div").classes("cozy-card"):
                _card_title("tune", "butter", "Alerts & defaults", "Used for warnings and new spools")
                inputs = {}
                with ui.column().classes("w-full gap-3"):
                    for key, (_default, label) in DEFAULT_SETTINGS.items():
                        inputs[key] = ui.number(label, value=values[key], min=0).props("outlined dense") \
                            .classes("w-full")

                def _save():
                    services.save_settings({k: (i.value or 0) for k, i in inputs.items()})
                    ui.notify("Settings saved ✓", type="positive", position="top")

                ui.button("Save settings", icon="check", on_click=_save).props("unelevated").classes("mt-3")

            # ---------------- Export / Import ----------------
            with ui.element("div").classes("cozy-card"):
                _card_title("swap_vert", "lavender", "Your data",
                            "Move everything to a new version of the app or another PC")
                ui.label("Export saves ALL your spools, prints, graveyard and settings in ONE file (.json). "
                         "Import loads such a file and replaces everything that is here now.") \
                    .classes("text-sm muted")
                with ui.row().classes("gap-3 mt-4"):
                    ui.button("Export everything", icon="upload", on_click=_export).props("unelevated")
                    ui.button("Import", icon="download", on_click=_ask_import).props("outline")
                ui.label("Before every import, a safety copy of the current data is kept automatically.") \
                    .classes("muted text-xs mt-3")


# ===========================================================================
# Export
# ===========================================================================

async def _export():
    filename = f"SpoolBuddy_{datetime.now():%Y-%m-%d}.json"
    window = _native_window()
    if window is None:  # browser mode -> plain download
        ui.download.content(transfer.export_bytes(), filename)
        return
    path = _first(await window.create_file_dialog(webview.FileDialog.SAVE, save_filename=filename,
                                                  file_types=FILE_TYPES))
    if not path:
        return  # the user pressed Cancel
    try:
        counts = transfer.export_to_file(path)
    except OSError as e:
        ui.notify(f"Could not save the file: {e}", type="negative", position="top", multi_line=True)
        return
    ui.notify(f"Exported {counts['spools']} spools and {counts['prints']} prints ✓",
              type="positive", position="top")


# ===========================================================================
# Import
# ===========================================================================

def _ask_import():
    confirm("Import data?",
            "Everything currently in the app will be REPLACED by the data in the file. "
            "A safety copy of the current data is kept first.",
            _choose_file, "Choose file", danger=True)


async def _choose_file():
    window = _native_window()
    if window is None:
        _upload_dialog()
        return
    path = _first(await window.create_file_dialog(webview.FileDialog.OPEN, file_types=FILE_TYPES))
    if not path:
        return
    try:
        with open(path, encoding="utf-8") as f:
            _do_import(f.read())
    except OSError as e:
        ui.notify(f"Could not read the file: {e}", type="negative", position="top", multi_line=True)


def _upload_dialog():
    """Browser mode only."""
    with ui.dialog() as dialog, ui.card().classes("p-6 rounded-3xl").style("min-width: 420px"):
        ui.label("Choose your .json file").classes("section-title")

        async def _on_upload(e):
            dialog.close()
            _do_import(await e.file.text())

        ui.upload(auto_upload=True, on_upload=_on_upload).props("accept=.json flat bordered").classes("w-full")
    dialog.open()


def _do_import(text: str):
    try:
        r = transfer.import_from_text(text)
    except ValueError as e:
        ui.notify(f"Import failed: {e}", type="negative", position="top", multi_line=True)
        return
    ui.notify(f"Imported {r['spools']} spools and {r['prints']} prints ✓", type="positive", position="top")
    ui.timer(1.2, lambda: ui.navigate.to("/storage"), once=True)
