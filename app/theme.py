"""
theme.py — Colors, fonts and CSS of the app.

Want to change the look & feel? It's all here:
    - PALETTE: the pastel colors (change a hex here and it changes everywhere)
    - FONT_STACK: Poppins, with Arimo as fallback for characters Poppins lacks (e.g. Greek)
    - CSS: rounded corners, shadows, menu styling, etc.
"""

from nicegui import ui

# ---------------------------------------------------------------------------
# Palette — warm, cozy pastels
# ---------------------------------------------------------------------------
PALETTE = {
    # Base
    "bg": "#FBF7F2",          # page background (cream)
    "surface": "#FFFFFF",     # cards
    "sidebar": "#F4EDE4",     # side menu (warm beige)
    "border": "#EDE4D9",      # thin borders
    "text": "#4A4453",        # main text (soft dark plum-grey)
    "muted": "#9A91A3",       # secondary text

    # Pastel tones (cards, badges, charts)
    "lavender": "#B8A9DE",
    "sage": "#A8C9A1",
    "peach": "#F5BFA3",
    "rose": "#EFA7B8",
    "butter": "#F3D98B",
    "sky": "#A9CBE8",
    "mint": "#A6DDD0",

    # Darker versions for text/icons on top of pastel backgrounds
    "lavender_dark": "#7E6BB8",
    "sage_dark": "#5E8F57",
    "peach_dark": "#C97A55",
    "rose_dark": "#C2627A",
    "butter_dark": "#B08F2A",
    "sky_dark": "#4F86B5",
    "mint_dark": "#3F9483",
}

# Chart color order when there is no spool color
CHART_COLORS = [PALETTE[c] for c in ("lavender", "sage", "peach", "sky", "rose", "butter", "mint")]

# Poppins has no Greek glyphs -> the browser automatically falls back to Arimo ONLY for
# those characters. Fonts are loaded from Google Fonts (needs internet the first time);
# offline, the system font is used.
FONT_STACK = "'Poppins', 'Arimo', 'Segoe UI', sans-serif"

FONTS_HTML = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Arimo:wght@400;500;600;700&family=Poppins:wght@300;400;500;600;700&display=swap&subset=greek" rel="stylesheet">
"""


def _css() -> str:
    p = PALETTE
    return f"""
<style>
  :root {{
    --bg: {p['bg']}; --surface: {p['surface']}; --sidebar: {p['sidebar']};
    --border: {p['border']}; --text: {p['text']}; --muted: {p['muted']};
  }}
  body, .q-field, .q-btn, .q-table, .q-item, .q-menu, .q-dialog, .q-notification {{
    font-family: {FONT_STACK} !important;
  }}
  body {{ background: var(--bg); color: var(--text); }}

  /* Cards: rounded, with a soft shadow */
  .cozy-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 20px; box-shadow: 0 4px 18px rgba(120, 100, 90, 0.07);
    padding: 20px;
  }}
  .page-title {{ font-size: 1.6rem; font-weight: 600; color: var(--text); }}
  .page-subtitle {{ color: var(--muted); font-size: 0.95rem; margin-top: -4px; }}
  .section-title {{ font-weight: 600; font-size: 1.05rem; color: var(--text); }}
  .muted {{ color: var(--muted); }}

  /* App icon at the top left: off-white rounded square with a soft shadow */
  .app-icon-frame {{
    width: 64px; height: 64px; min-width: 64px; padding: 7px;
    background: #FFFDF8; border: 1px solid {p['border']}; border-radius: 18px;
    box-shadow: 0 4px 14px rgba(120, 100, 90, 0.12);
    display: flex; align-items: center; justify-content: center;
  }}

  /* Side menu */
  .nav-item {{
    border-radius: 14px; margin: 3px 10px; padding: 10px 14px; color: var(--text);
    display: flex; align-items: center; gap: 12px; text-decoration: none; font-weight: 500;
    transition: background .15s ease;
  }}
  .nav-item:hover {{ background: rgba(184, 169, 222, 0.20); }}
  .nav-item.active {{ background: {p['lavender']}; color: #fff; box-shadow: 0 4px 12px rgba(126,107,184,.25); }}
  .nav-icon {{
    width: 34px; height: 34px; border-radius: 11px; display: flex;
    align-items: center; justify-content: center; font-size: 20px;
  }}
  .nav-item.active .nav-icon {{ background: rgba(255,255,255,.25) !important; color: #fff !important; }}

  /* KPI cards */
  .kpi-icon {{
    width: 46px; height: 46px; border-radius: 14px; display: flex;
    align-items: center; justify-content: center; font-size: 24px;
  }}
  .kpi-value {{ font-size: 1.45rem; font-weight: 600; line-height: 1.2; }}
  .kpi-label {{ color: var(--muted); font-size: .85rem; }}

  /* Colored spool "dot" */
  .spool-dot {{
    display: inline-block; width: 14px; height: 14px; border-radius: 50%;
    border: 1px solid rgba(0,0,0,.15); vertical-align: middle; margin-right: 6px;
  }}

  /* Badges */
  .pill {{ border-radius: 999px; padding: 2px 10px; font-size: .78rem; font-weight: 500; display: inline-block; }}

  /* Tables */
  .q-table__container {{ border-radius: 20px !important; box-shadow: none !important; border: 1px solid var(--border); }}
  .q-table thead th {{ font-weight: 600; color: var(--muted); }}

  /* Slightly rounder inputs */
  .q-field--outlined .q-field__control {{ border-radius: 12px; }}
  .q-btn {{ border-radius: 12px; text-transform: none; font-weight: 500; }}
</style>
"""


def apply_theme() -> None:
    """Called once on startup: adds fonts + CSS to ALL pages."""
    ui.add_head_html(FONTS_HTML + _css(), shared=True)
    # In number fields keep the label ALWAYS above the value,
    # otherwise it sometimes overlapped the number.
    ui.number.default_props("stack-label")


def apply_quasar_colors() -> None:
    """Colors of the built-in components (buttons, toggles, ...). Called on every page."""
    ui.colors(
        primary=PALETTE["lavender_dark"],
        secondary=PALETTE["sage_dark"],
        accent=PALETTE["peach_dark"],
        positive=PALETTE["sage_dark"],
        negative=PALETTE["rose_dark"],
        warning=PALETTE["butter_dark"],
        info=PALETTE["sky_dark"],
    )


def level_color(percent_left: float) -> str:
    """Color based on how much filament is left (green -> yellow -> pink)."""
    if percent_left >= 50:
        return PALETTE["sage_dark"]
    if percent_left >= 20:
        return PALETTE["butter_dark"]
    return PALETTE["rose_dark"]
