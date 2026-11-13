"""
make_icon.py — Builds assets/icon.ico (for Windows) from assets/icon.png.

When to run it: ONLY when you change the icon.
    1. Save the new PNG (ideally 1024x1024) as assets/icon.png
    2. .venv\\Scripts\\python.exe tools/make_icon.py

The .ico contains several sizes (16 to 256 px) so Windows can pick
the right one for the title bar, taskbar, desktop, etc.
"""

from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

if __name__ == "__main__":
    img = Image.open(ASSETS / "icon.png").convert("RGBA")
    img.save(ASSETS / "icon.ico", sizes=SIZES)
    print(f"OK -> {ASSETS / 'icon.ico'}")
