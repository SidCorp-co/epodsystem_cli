"""Store menus. Nav is a runtime `linklists['<handle>']` lookup in Liquid, so a
menu item is how a page joins a nav — no per-page template edit anywhere.
"""
import json
import re


def find(e, handle):
    """(menu_id, [items]) for a handle, or (None, []).

    list_menus reports items as empty, so the items come from storeMenu(id).
    """
    r = e.tool("list_menus", {})
    menus = r.get("storeMenus", r) if isinstance(r, dict) else r
    for m in menus or []:
        if m.get("handle") == handle:
            mid = str(m.get("id"))
            q = e.query(f"query {{ storeMenu(id: {mid}) "
                        f"{{ items {{ id label page_id url link_type }} }} }}")
            sm = q.get("storeMenu", q) if isinstance(q, dict) else {}
            items = (sm or {}).get("items", []) if isinstance(sm, dict) else []
            return mid, items
    return None, []


def ensure(e, handle, name, location):
    mid, items = find(e, handle)
    if mid:
        return mid, items
    r = e.tool("create_menu", {"name": name, "handle": handle, "location": location})
    m = re.search(r'"id":\s*(\d+)', r if isinstance(r, str) else json.dumps(r))
    return (m.group(1) if m else None), []


def add_page_item(e, menu_id, label, page_id, position):
    return e.tool("create_menu_item", {
        "menu_id": str(menu_id), "label": label,
        "link_type": "page", "page_id": str(page_id), "position": position})


def relabel(e, item_id, label):
    return e.tool("update_menu_item", {"item_id": str(item_id), "label": label})


def delete_item(e, item_id):
    return e.tool("delete_menu_item", {"item_id": str(item_id)})
