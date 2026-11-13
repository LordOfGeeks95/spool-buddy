"""
ui/ — the app's screens. One file = one page.

    layout.py      -> the shared frame (menu) + small reusable pieces
    print_form.py  -> the shared print form (New Print + Edit in History)
    spool_list.py  -> shared spool row card + sorting toolbar (Storage + Graveyard)
    new_print.py   -> /           New Print (opens first)
    storage.py     -> /storage    Storage (spools)
    dashboard.py   -> /dashboard  Dashboard
    history.py     -> /history    History
    graveyard.py   -> /graveyard  Graveyard (finished spools)
    settings.py    -> /settings   Settings (preferences + export/import)

To add a NEW page: create a file here with @ui.page('/route'), add it to
NAV in layout.py and import it in main.py.
"""
