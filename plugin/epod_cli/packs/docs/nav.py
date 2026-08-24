"""The sidebar menu.

The sidebar reads the `docs-nav` menu at runtime, so adding a page is one menu
item and every existing page's sidebar updates with it — no edit to an old page.
`sync` is idempotent: it adds what is missing, relabels what drifted, and removes
duplicates and orphans (deleting a page does not remove its item, which would
otherwise keep pointing at a 404).
"""
import re

from ...resources import menus, pages
from . import NAV_HANDLE, labels


def doc_code(page):
    """Uppercase document code from the slug ('01-brd' → BRD) or a title prefix."""
    table = labels()
    slug = page.get("slug") or ""
    s = re.sub(r"^\d+[-_.]*", "", slug)
    # Try the whole compressed slug first ('tech-design' → TECHDESIGN); several
    # slugs share a first token, so the token alone would collide.
    full = re.sub(r"[^a-z0-9]", "", s.lower())
    if full.upper() in table:
        return full.upper()
    code = re.split(r"[-_./]", s)[0] if s else slug
    code = re.sub(r"[^a-z0-9]", "", code.lower())
    if code.upper() in table:
        return code.upper()
    m = re.match(r"^\s*([A-Z0-9]{2,8})\s*[—:\-]", (page.get("title") or ""))
    if m and m.group(1) in table:
        return m.group(1)
    return code.upper() if code else "DOC"


def label_for(page):
    """Short generic label by document type; else the title minus its prefix."""
    table = labels()
    code = doc_code(page)
    if code in table:
        return table[code]
    t = (page.get("title") or "").strip()
    if t:
        t = re.sub(r"^\s*\d+\s*[—.\-:]\s*", "", t)
        t = re.sub(r"^\s*[A-Z0-9]{2,8}\s*[—:\-]\s*", "", t)
        return t[:32]
    return page.get("slug")


def sync(e):
    """Bring `docs-nav` in line with the published pages. Returns a summary dict."""
    docs = pages.content_pages(e)
    mid, items = menus.ensure(e, NAV_HANDLE, "Docs nav", "sidebar")
    if not mid:
        raise SystemExit(f"could not find or create the '{NAV_HANDLE}' menu")

    by_pid, dups = {}, []
    for it in items:
        pid = str(it.get("page_id") or "")
        if not pid:
            continue
        if pid in by_pid:
            dups.append(it)
        else:
            by_pid[pid] = it
    for it in dups:
        menus.delete_item(e, it.get("id"))

    live = {str(p.get("id")) for p in docs}
    orphans = [it for pid, it in by_pid.items() if pid not in live]
    for it in orphans:
        menus.delete_item(e, it.get("id"))
        by_pid.pop(str(it.get("page_id")), None)

    added, relabeled, kept = [], [], []
    for pos, p in enumerate(docs, 1):
        pid = str(p.get("id"))
        label = label_for(p)
        cur = by_pid.get(pid)
        if cur:
            if (cur.get("label") or "") != label:
                menus.relabel(e, cur.get("id"), label)
                relabeled.append(label)
            kept.append(label)
            continue
        menus.add_page_item(e, mid, label, pid, pos)
        added.append(label)
    e.clear_cache()
    return {"menu": NAV_HANDLE, "id": mid, "pages": len(docs),
            "added": added, "relabeled": relabeled, "unchanged": kept,
            "removed_dups": len(dups),
            "removed_orphans": [it.get("label") for it in orphans]}
