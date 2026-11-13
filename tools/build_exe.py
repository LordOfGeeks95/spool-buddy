"""
build_exe.py — Builds "Spool Buddy.exe" (a single file, no console window).

Run (from the project folder):
    build.bat
or
    .venv\\Scripts\\python.exe tools\\build_exe.py

Result:
    release\\Spool Buddy.exe   <- ONLY the program, NO data.

What does NOT go into the exe:
    - the data\\ folder (your database) — never
    - any export files
When someone opens the exe, a NEW data\\ folder with an empty database is created next to it.

Needs PyInstaller in the .venv — it is installed automatically if missing.
Temporary build files go to the build\\ folder (safe to delete).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "Spool Buddy"
RELEASE_DIR = ROOT / "release"
BUILD_DIR = ROOT / "build"


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print(">>> Installing PyInstaller (only the first time)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def main() -> None:
    if ".venv" not in sys.executable:
        print("!!! Run this with the project's Python: .venv\\Scripts\\python.exe tools\\build_exe.py")
        sys.exit(1)

    ensure_pyinstaller()
    import nicegui
    import PyInstaller.__main__

    sep = ";"  # on Windows --add-data expects "source;destination"
    args = [
        str(ROOT / "main.py"),
        "--name", APP_NAME,
        "--onefile",            # ONE .exe file (starts a bit slower — it unpacks itself every time)
        "--windowed",           # no console window
        "--noconfirm",
        "--clean",
        "--icon", str(ROOT / "assets" / "icon.ico"),
        # NiceGUI's files (css/js/fonts) and our icon are bundled INSIDE the exe
        "--add-data", f"{Path(nicegui.__file__).parent}{sep}nicegui",
        "--add-data", f"{ROOT / 'assets'}{sep}assets",
        "--distpath", str(RELEASE_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(BUILD_DIR),
    ]
    print(">>> Building... (takes 1-3 minutes)")
    PyInstaller.__main__.run(args)

    exe = RELEASE_DIR / f"{APP_NAME}.exe"
    if exe.exists():
        print()
        print("=" * 60)
        print(f"  DONE!  {exe}")
        print(f"  Size: {exe.stat().st_size / 1024 / 1024:.0f} MB")
        print("  This exe has NO data inside - it is clean.")
        print("=" * 60)
    else:
        print("!!! Something went wrong - no exe was created. See the messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
