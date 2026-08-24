"""Standing up a docs site: install the sections, set the home page, diagnose.

The trap this exists for: a fresh store has no section templates, so a published
page returns HTTP 200 and renders BLANK. `doctor` catches that before you go
looking for it in a browser, and `install` is what fixes it.
"""
import json
import random
import sys

import requests

from ...core.context import context, resolve_domain, resolve_theme_id
from ...resources import menus, pages, themes
from . import NAV_HANDLE, local_sections
from . import nav as nav_mod


def doctor(e, local_only=False):
    """Pre-lint the bundled sections, then diagnose the live store. Returns rc."""
    rc = 0
    print("== pre-lint sections (local) ==")
    for name, (path, content) in local_sections().items():
        probs = themes.lint_section(content)
        if not probs:
            print(f"  OK    {path}")
        for sev, msg in probs:
            print(f"  {'ERROR' if sev == 'error' else 'warn '} {path}: {msg}")
        if any(sev == "error" for sev, _ in probs):
            rc = 1

    if not local_only:
        try:
            ctx = context(e)
            theme_id = resolve_theme_id(ctx)
            print("\n== store (live) ==")
            miss = [p for _, (p, _) in local_sections().items()
                    if not themes.installed(e, p, theme_id)]
            if miss:
                rc = 1
                print(f"  ERROR {len(miss)} section(s) NOT installed in theme {theme_id}: "
                      f"{', '.join(miss)}")
                print("        → pages will render BLANK. Run: epod docs install")
            else:
                print(f"  OK    all sections present in theme {theme_id}")
            mid, items = menus.find(e, NAV_HANDLE)
            if not mid:
                print(f"  warn  no '{NAV_HANDLE}' menu yet (empty sidebar) → run: epod docs nav")
            else:
                print(f"  OK    menu {NAV_HANDLE} ({len(items)} items)")
            print(f"  domain: {resolve_domain(ctx)}")
        except SystemExit as ex:
            print(f"  (skipping live check: {str(ex)[:120]})")

    print("\nDoctor:", "FAIL (fix the ERRORs above before install/publish)" if rc else "OK")
    return rc


def check(e):
    ctx = context(e)
    theme_id = resolve_theme_id(ctx)
    print(json.dumps({
        "store_id": ctx.get("store_id"),
        "store_slug": ctx.get("store_slug") or ctx.get("store_name"),
        "theme_id": theme_id,
        "domain": resolve_domain(ctx),
    }, ensure_ascii=False, indent=2))
    print("--- sections ---")
    for name, (path, _) in local_sections().items():
        print(f"  {'installed' if themes.installed(e, path, theme_id) else 'MISSING':10} {path}")


def install(e, force=False, only=None, lint=True):
    ctx = context(e)
    theme_id = resolve_theme_id(ctx)
    wanted = local_sections()
    if only:
        keep = {x.strip() for x in only.split(",")}
        wanted = {k: v for k, v in wanted.items() if k in keep}
    results = themes.install_sections(e, wanted, theme_id, force=force, lint=lint)
    plain = {}
    for path, outcome in results.items():
        if isinstance(outcome, tuple):
            plain[path] = outcome[0]
            print(f"\n!! {path}:", file=sys.stderr)
            for m in outcome[1]:
                print(f"   - {m}", file=sys.stderr)
        else:
            plain[path] = outcome
    print(json.dumps({"theme_id": theme_id, "results": plain}, ensure_ascii=False, indent=2))
    print("\nNext: epod docs build each .md, then: epod docs verify <slug>")
    return 1 if any("REJECTED" in v or "FAILED" in v for v in plain.values()) else 0


def verify(e, slug):
    """Live URL plus the two failures a fetch can actually see: a 404, and a
    section type with no template. Section bodies are JS-injected, so a real
    verify is still browser_navigate + browser_evaluate on the DOM."""
    ctx = context(e)
    theme_id = resolve_theme_id(ctx)
    url = f"https://{resolve_domain(ctx)}/pages/{slug}?v={random.randint(1, 99999)}"
    print(url)
    rc = 0
    try:
        pid = pages.id_by_slug(e, slug)
        if not pid:
            rc = 1
            print(f"  ERROR: no page with slug '{slug}' (not built yet?).")
        else:
            sd = pages.get_sections(e, pid)
            types = {v.get("type") for v in (sd.get("sections") or {}).values()}
            missing = [t for t in types
                       if t and not themes.installed(e, f"sections/{t}.liquid", theme_id)]
            if missing:
                rc = 1
                print(f"  ERROR: theme is MISSING templates for: {', '.join(missing)}")
                print("         → the page renders BLANK even when published. "
                      "Run: epod docs install")
            else:
                print(f"  OK: every section type on the page has a template in theme {theme_id}.")
    except SystemExit as ex:
        print(f"  (couldn't read sections_data: {str(ex)[:100]})")
    try:
        r = requests.get(url, timeout=20)
        print(f"  HTTP {r.status_code}"
              + ("" if r.status_code == 200 else "  ← NOT 200, re-check"))
        if r.status_code != 200:
            rc = 1
    except requests.RequestException as ex:
        print(f"  (couldn't fetch: {str(ex)[:100]})")
    print("REAL verify in a browser: browser_navigate the URL above → browser_evaluate the "
          "DOM (the body must contain .dl-article content, not just header/footer).")
    return rc


def home(e, heading=None, eyebrow=None, subheading=None):
    """Set `/` to web-hero + docs-toc.

    `/` is rendered by the `index` TEMPLATE, not by a page_type=home page — that
    page is ignored — so this writes through set_section_settings on 'index'.
    """
    ctx = context(e)
    theme_id = resolve_theme_id(ctx)
    docs = pages.content_pages(e)
    cards = [{"type": "card", "settings": {
        "tag": nav_mod.doc_code(p),
        "num": "",
        "title": nav_mod.label_for(p),
        "desc": "",
        "url": f"/pages/{p.get('slug')}",
        "featured": (i == 0),
    }} for i, p in enumerate(docs)]

    store = ctx.get("store_slug") or ctx.get("store_name") or "Docs"
    e.tool("set_section_settings", {
        "template": "index", "section_id": "hero", "type": "web-hero", "position": 0,
        "theme_id": str(theme_id),
        "settings": {
            "eyebrow": eyebrow or "Documentation",
            "heading": heading or f"{store} documentation",
            "subheading": subheading or "",
            "cta_label": ("Read the docs" if cards else ""),
            "cta_url": (cards[0]["settings"]["url"] if cards else ""),
        }})
    e.tool("set_section_settings", {
        "template": "index", "section_id": "toc", "type": "docs-toc", "position": 1,
        "theme_id": str(theme_id),
        "settings": {"eyebrow": "Contents", "heading": "Documents",
                     "intro": "All project documentation."},
        "blocks": cards})

    # Drop the theme's default sections so index.json holds only hero + toc.
    try:
        raw = themes.get_file(e, "templates/index.json", theme_id=theme_id)
        tpl = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(tpl, dict) and "sections" in tpl:
            tpl["order"] = ["hero", "toc"]
            tpl["sections"] = {k: v for k, v in tpl["sections"].items()
                               if k in ("hero", "toc")}
            themes.put_file(e, "templates/index.json",
                            json.dumps(tpl, ensure_ascii=False, indent=2),
                            theme_id=theme_id, clear_cache=False)
    except (ValueError, SystemExit) as ex:
        print(f"(warning: couldn't trim index.json: {str(ex)[:120]})", file=sys.stderr)

    e.clear_cache()
    print(json.dumps({"home": "set (index template)", "cards": len(cards)},
                     ensure_ascii=False, indent=2))
    print(f"verify: https://{resolve_domain(ctx)}/?v=1")
