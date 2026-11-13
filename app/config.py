"""
config.py — Basic app settings.

Things that rarely change live here:
    - where the database is stored
    - app name, tagline, icon
    - the default values of the user settings

Settings that the user changes (warning thresholds etc.) are edited from the
"Settings" page inside the app and stored in the database.
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Folders & files
# ---------------------------------------------------------------------------

# Running as an .exe (PyInstaller)? Then sys.frozen is True.
IS_EXE = getattr(sys, "frozen", False)

# BASE_DIR = where the DATA lives:
#   - as .exe -> the folder NEXT TO the exe (so every copy of the exe has its own data)
#   - as .py  -> the project folder (where main.py is)
BASE_DIR = Path(sys.executable).resolve().parent if IS_EXE else Path(__file__).resolve().parent.parent

# RESOURCE_DIR = where the PROGRAM's own files are (e.g. the icon):
#   - as .exe -> inside the exe (PyInstaller unpacks them to a temp folder, sys._MEIPASS)
#   - as .py  -> the project folder
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR)) if IS_EXE else BASE_DIR

# All user data goes here. To make a manual backup, just copy this folder.
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "filament.db"          # the database (SQLite, a single file)
BACKUP_DIR = DATA_DIR / "backups"           # automatic database backups

# App icon (assets/ folder):
#   icon.png -> 1024x1024, shown at the top left of the menu
#   icon.ico -> for Windows (title bar, taskbar, the .exe)
# New icon? Replace icon.png and run:  python tools/make_icon.py
# If they are missing, the 🧵 emoji is used.
ICON_PNG = RESOURCE_DIR / "assets" / "icon.png"
ICON_ICO = RESOURCE_DIR / "assets" / "icon.ico"

# ---------------------------------------------------------------------------
# Name & server
# ---------------------------------------------------------------------------

APP_TITLE = "Spool Buddy"
APP_TAGLINE = "No spool left behind"     # shown next to the icon in the menu

# Port for --browser / --no-browser. In window (native) mode a free port is picked automatically.
PORT = 8080

# False -> reachable ONLY from this computer (safe, recommended).
# True  -> also reachable from other devices on the same network (no password!).
ALLOW_LAN_ACCESS = False

# How many automatic database backups to keep (made silently on every start, data/backups)
BACKUPS_TO_KEEP = 20

# ---------------------------------------------------------------------------
# Default settings (written to the database the first time)
# ---------------------------------------------------------------------------
# key -> (value, label). Add a new setting here and it shows up on the Settings page automatically.

DEFAULT_SETTINGS: dict[str, tuple[float, str]] = {
    "low_stock_g": (100.0, "Low stock warning below (g)"),
    "almost_empty_g": (20.0, "Suggest moving to Graveyard below (g)"),
    "default_spool_weight_g": (1000.0, "Default weight of a new spool (g)"),
}
