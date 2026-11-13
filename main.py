"""
main.py — Entry point of Spool Buddy.

    python main.py              -> opens in its OWN WINDOW (like a normal desktop app)
    python main.py --browser    -> opens in your web browser instead
    python main.py --no-browser -> only starts the server on :8080 (useful for testing)

What happens on startup:
    1. A silent backup of the database is made (data/backups)
    2. The database is created / upgraded if needed (data/filament.db)
    3. The app window opens

Everything runs LOCALLY on your computer. Closing the window closes the app.
"""

import multiprocessing
import os
import sys

# When running as a windowed .exe there is no console, so sys.stdout / sys.stderr are None
# and any print/log would crash the app. Send them to data/log.txt next to the exe instead
# (also handy for figuring out what went wrong).
if getattr(sys, "frozen", False) and (sys.stdout is None or sys.stderr is None):
    _log_dir = os.path.join(os.path.dirname(sys.executable), "data")
    os.makedirs(_log_dir, exist_ok=True)
    _log = open(os.path.join(_log_dir, "log.txt"), "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log

from nicegui import app as nicegui_app  # (renamed so it doesn't clash with our app/ package)
from nicegui import ui

from app import backup, config, db
from app.theme import apply_theme

# Importing the pages registers them (each file uses @ui.page)
from app.ui import dashboard, graveyard, history, new_print, settings, storage  # noqa: F401

# Window size when it is not maximized (width, height in pixels)
WINDOW_SIZE = (1440, 920)

# Tell Windows this is its OWN app (not "Python"), so the taskbar shows our icon.
# This also runs in the window's process.
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SpoolBuddy.App")


def _favicon() -> str:
    """The .ico is also used as the window icon on Windows. Falls back to the PNG, then to an emoji."""
    if config.ICON_ICO.exists():
        return str(config.ICON_ICO)
    if config.ICON_PNG.exists():
        return str(config.ICON_PNG)
    return "🧵"


def startup() -> None:
    backup.backup_now(keep=config.BACKUPS_TO_KEEP)  # backup FIRST, before any change / migration
    db.init_db()
    apply_theme()


if __name__ in {"__main__", "__mp_main__"}:
    # For the .exe: the window runs in a second process that starts the same exe.
    # This line must come FIRST so that process only runs the window, not the whole app again.
    multiprocessing.freeze_support()

    # The window (pywebview) runs in a second process that re-imports this file.
    # Backups / migrations must only run once, in the main process.
    if multiprocessing.current_process().name == "MainProcess":
        startup()

    use_browser = "--browser" in sys.argv or "--no-browser" in sys.argv
    # The window opens MAXIMIZED. WINDOW_SIZE is used when you restore it.
    nicegui_app.native.window_args["maximized"] = True
    ui.run(
        title=config.APP_TITLE,
        host="0.0.0.0" if config.ALLOW_LAN_ACCESS else "127.0.0.1",
        # In window mode a free port is picked automatically (no clash if 8080 is taken)
        port=config.PORT if use_browser else None,
        favicon=_favicon(),
        reload=False,               # set True while developing to auto-restart on every code change
        native=not use_browser,     # own window instead of a browser tab
        window_size=None if use_browser else WINDOW_SIZE,
        show="--browser" in sys.argv,
        language="en-US",
    )
