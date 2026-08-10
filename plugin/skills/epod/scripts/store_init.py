#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
store_init.py — initialize an epod store for the documentation workflow (doc pages).

Problem it solves: epod.py was written for the RS store and assumes the target store
ALREADY HAS the theme sections (doc-layout, brd-hero...). A fresh store is EMPTY — a
published page renders BLANK because the section templates are missing. This script
INSTALLS the needed sections into the ACTIVE store's theme, sets up the home page, and
syncs the sidebar nav menu.

Nothing about store/theme/domain is hard-coded. Everything is resolved live from get_context:
  - token   : env EPOD_TOKEN or .mcp.json (reuses epod.py's loader)
  - store   : get_context -> store_id / store_slug / theme_id
  - domain  : get_context -> storefront domain (inferred if context omits it)

Section source: assets/store-theme/sections/*.liquid (bundled in the skill).

Usage:
  epod-store-init doctor [--local]   # pre-lint sections + diagnose store
  epod-store-init check              # context + which sections are installed/missing
  epod-store-init install [--force]  # install sections (pre-lints before upload)
  epod-store-init sync-nav           # sync the docs-nav menu from published pages
  epod-store-init home [--heading .. --eyebrow .. --subheading ..]  # set the home page
  epod-store-init verify <slug>      # print live URL + warn on 404/blank-render

Env overrides (multi-project):
  EPOD_TOKEN            bearer token (bypasses .mcp.json)
  EPOD_MCP_URL          MCP endpoint (default https://mcp.epodsystem.com/mcp)
  EPOD_STORE_DOMAIN     storefront domain (e.g. youtube.epodsystem.com) to force it
  EPOD_THEME_ID         target theme id (default: active theme from context)
"""
import argparse
import json
import os
import re
import sys

# dùng lại client + loader của epod.py (cùng thư mục)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import epod  # noqa: E402

# Section templates bundled trong skill: <skill>/assets/store-theme/sections/.
# Fallback: layout cũ (cạnh script) hoặc tools/store-theme, để không vỡ nếu chạy bản cũ.
def _find_sections_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "assets", "store-theme", "sections"),  # bundled skill
        os.path.join(here, "store-theme", "sections"),                   # cạnh script (cũ)
        os.path.join(here, "..", "store-theme", "sections"),
    ]
    for c in candidates:
        c = os.path.abspath(c)
        if os.path.isdir(c):
            return c
    return os.path.abspath(candidates[0])  # mặc định bundled (sẽ báo lỗi rõ nếu thiếu)


SECTIONS_DIR = _find_sections_dir()


def context(e):
    """get_context chuẩn hoá về dict phẳng {store_id, store_slug, theme_id, ...}."""
    ctx = e.tool("get_context", {})
    if not isinstance(ctx, dict):
        raise SystemExit(f"get_context không trả dict: {str(ctx)[:200]}")
    flat = dict(ctx)
    store = ctx.get("store") if isinstance(ctx.get("store"), dict) else {}
    for k in ("id", "slug", "name"):
        if store.get(k) and f"store_{k}" not in flat:
            flat[f"store_{k}"] = store[k]
    return flat


def resolve_domain(ctx):
    """Suy domain storefront. Ưu tiên env, rồi context, rồi <slug>.epodsystem.com."""
    if os.environ.get("EPOD_STORE_DOMAIN"):
        return os.environ["EPOD_STORE_DOMAIN"]
    for k in ("storefront_domain", "store_domain", "domain", "primary_domain"):
        if ctx.get(k):
            return str(ctx[k]).replace("https://", "").replace("http://", "").strip("/")
    slug = ctx.get("store_slug") or ctx.get("store_name")
    if slug:
        return f"{slug}.epodsystem.com"
    raise SystemExit("không suy được domain — set EPOD_STORE_DOMAIN")


def resolve_theme_id(ctx):
    return os.environ.get("EPOD_THEME_ID") or str(ctx.get("theme_id") or "") or None


def local_sections():
    """{name: (theme_path, content)} từ tools/store-theme/sections/*.liquid."""
    out = {}
    if not os.path.isdir(SECTIONS_DIR):
        raise SystemExit(f"thiếu thư mục section nguồn: {SECTIONS_DIR}")
    for fn in sorted(os.listdir(SECTIONS_DIR)):
        if fn.endswith(".liquid"):
            name = fn[:-len(".liquid")]
            path = f"sections/{fn}"
            content = open(os.path.join(SECTIONS_DIR, fn), encoding="utf-8").read()
            out[name] = (path, content)
    return out


def installed(e, path, theme_id):
    """True nếu theme đã có file section (get_theme_file trả nội dung không rỗng)."""
    try:
        c = e.get_theme_file(path, theme_id=theme_id)
    except SystemExit:
        return False
    return bool(c) and c != "None" and c is not None


# ---------------------------------------------------------------- pre-linter
# Catch design-contract errors LOCALLY before upload, to avoid a cryptic server
# reject (SKILL §6). The three rules the server rejects on:
#   (a) hard-coded brand hex in body CSS (outside :root{})
#   (b) schema missing the canonical Style settings group
#   (c) an unclosed tag — the server even SCANS tag strings inside <script> (e.g. '<pre')
_STYLE_KEYS = ("visible", "bg_color", "text_color", "heading_color",
               "padding_top", "padding_bottom", "border_color",
               "border_width", "border_radius")
# paired tags that need closing (excludes void / optional-close tags)
_PAIR_TAGS = ("section", "div", "aside", "nav", "main", "header", "footer",
              "article", "a", "ul", "ol", "button", "pre", "table", "span", "h1",
              "h2", "h3", "h4")


def lint_section(content):
    """Trả list (severity, msg) cho 1 file section. severity: 'error'|'warn'.
    error = server SẼ reject; warn = nên xem."""
    problems = []

    # tách <style>…</style> để soi hex; và tách schema JSON
    styles = re.findall(r"<style\b[^>]*>(.*?)</style>", content, re.S | re.I)
    for css in styles:
        # bỏ khối :root{...} (hex ở đây HỢP LỆ — định nghĩa token)
        css_scan = re.sub(r":root\s*\{.*?\}", "", css, flags=re.S)
        # bỏ hex nằm trong var(--x,#fff) FALLBACK và trong rgba()/hsl() — server CHO PHÉP
        css_scan = re.sub(r"var\([^)]*\)", "", css_scan)
        css_scan = re.sub(r"(?:rgba?|hsla?)\([^)]*\)", "", css_scan)
        m = re.search(r"#[0-9a-fA-F]{3,8}\b", css_scan)
        if m:
            problems.append(("error",
                f"hard-code hex {m.group(0)} trong body CSS (ngoài :root/var/rgba/hsl) "
                f"→ dùng var(--…)/hsl()/rgba()"))

    # schema Style settings group
    msch = re.search(r"\{%\s*schema\s*%\}(.*?)\{%\s*endschema\s*%\}", content, re.S | re.I)
    if msch:
        sch = msch.group(1)
        missing = [k for k in _STYLE_KEYS if f'"{k}"' not in sch]
        if missing:
            problems.append(("error",
                f"schema THIẾU Style settings: {', '.join(missing)} → thêm nhóm header 'Style' + các key chuẩn"))
    else:
        problems.append(("warn", "không thấy {% schema %} — section không có settings?"))

    # unclosed tags — CHỈ đếm markup THẬT. Bỏ <script>/<style>/comment/{% %}/{{ }}
    # và literal tag trong chuỗi '...'/"..." (server có quét chuỗi, nhưng ở local ta
    # ưu tiên KHÔNG báo nhầm — literal an toàn nếu đã nối chuỗi 'p'+'re').
    markup = re.sub(r"<script\b.*?</script>", "", content, flags=re.S | re.I)
    markup = re.sub(r"<style\b.*?</style>", "", markup, flags=re.S | re.I)
    markup = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
    markup = re.sub(r"\{%.*?%\}", "", markup, flags=re.S)     # liquid tag
    markup = re.sub(r"\{\{.*?\}\}", "", markup, flags=re.S)   # liquid output
    for tag in _PAIR_TAGS:
        opens = len(re.findall(rf"<{tag}\b", markup))
        closes = len(re.findall(rf"</{tag}>", markup))
        if opens > closes:
            problems.append(("error",
                f"thẻ <{tag}> mở {opens} nhưng đóng {closes} → thiếu {opens-closes} thẻ đóng"))
    return problems


def cmd_doctor(e, args):
    """Kiểm tra LOCAL (pre-lint section) + LIVE (chẩn đoán store) trước/sau khi cài.
    Mục tiêu: bắt lỗi trước khi server reject, và tự phát hiện bẫy store trống."""
    rc = 0
    # 1) pre-lint every local section
    print("== pre-lint sections (local) ==")
    for name, (path, content) in local_sections().items():
        probs = lint_section(content)
        errs = [p for p in probs if p[0] == "error"]
        if not probs:
            print(f"  OK    {path}")
        for sev, msg in probs:
            mark = "ERROR" if sev == "error" else "warn "
            print(f"  {mark} {path}: {msg}")
        if errs:
            rc = 1
    # 2) diagnose the live store (if online)
    if not args.local:
        try:
            ctx = context(e)
            theme_id = resolve_theme_id(ctx)
            domain = resolve_domain(ctx)
            print("\n== store (live) ==")
            miss = [p for n, (p, _) in local_sections().items()
                    if not installed(e, p, theme_id)]
            if miss:
                rc = 1
                print(f"  ERROR {len(miss)} section(s) NOT installed in theme {theme_id}: "
                      f"{', '.join(miss)}")
                print("        → pages will render BLANK. Run: epod-store-init install")
            else:
                print(f"  OK    all sections present in theme {theme_id}")
            # does the docs-nav menu exist?
            mid, items = _find_menu(e, DOCS_NAV_HANDLE)
            if not mid:
                print(f"  warn  no '{DOCS_NAV_HANDLE}' menu yet (empty sidebar) → run sync-nav")
            else:
                print(f"  OK    menu {DOCS_NAV_HANDLE} ({len(items)} items)")
            print(f"  domain: {domain}")
        except SystemExit as ex:
            print(f"  (skipping live check: {str(ex)[:120]})")
    print("\nDoctor:", "FAIL (fix the ERRORs above before install/publish)" if rc else "OK")
    if rc:
        sys.exit(1)


def cmd_check(e, args):
    ctx = context(e)
    theme_id = resolve_theme_id(ctx)
    domain = resolve_domain(ctx)
    print(json.dumps({
        "store_id": ctx.get("store_id"),
        "store_slug": ctx.get("store_slug") or ctx.get("store_name"),
        "theme_id": theme_id,
        "domain": domain,
    }, ensure_ascii=False, indent=2))
    print("--- sections ---")
    for name, (path, _) in local_sections().items():
        state = "installed" if installed(e, path, theme_id) else "MISSING"
        print(f"  {state:10} {path}")


def cmd_install(e, args):
    ctx = context(e)
    theme_id = resolve_theme_id(ctx)
    only = set(x.strip() for x in args.only.split(",")) if args.only else None
    results = {}
    for name, (path, content) in local_sections().items():
        if only and name not in only:
            continue
        exists = installed(e, path, theme_id)
        if exists and not args.force:
            results[path] = "skip (exists)"
            continue
        # PRE-LINT local trước khi upload — bắt lỗi contract sớm, thông báo rõ ràng
        # thay vì để server reject bằng chuỗi khó hiểu (SKILL §6).
        lint_errs = [m for sev, m in lint_section(content) if sev == "error"]
        if lint_errs and not args.no_lint:
            results[path] = "REJECTED (pre-lint)"
            print(f"\n!! pre-lint {path}:", file=sys.stderr)
            for m in lint_errs:
                print(f"   - {m}", file=sys.stderr)
            continue
        res = e.tool("upsert_theme_file",
                     {"path": path, "content": content, "theme_id": str(theme_id)})
        # linter trả CHUỖI lỗi thay vì raise — phải bắt để không báo "installed" giả.
        if isinstance(res, str) and ("rejected" in res or "violation" in res):
            results[path] = "REJECTED"
            print(f"\n!! theme file rejected: {path}\n{res}\n", file=sys.stderr)
            continue
        e.tool("clear_storefront_cache", {})
        # confirm it actually persisted (read back)
        results[path] = ("overwritten" if exists else "installed") \
            if installed(e, path, theme_id) else "FAILED (not persisted)"
    print(json.dumps({"theme_id": theme_id, "results": results},
                     ensure_ascii=False, indent=2))
    print("\nNext: re-run build-doc (or publish) then verify:")
    print(f"  epod-store-init verify <slug>")


def cmd_verify(e, args):
    """Print live URL + fetch the page, warn if the SSR shell is empty.
    NOTE: section content is JS-injected so a fetch only sees the shell — a REAL verify
    still needs the browser (browser_evaluate to measure the DOM). But this catches:
    HTTP != 200, a missing page (404), or a section type with no template (blank-render)."""
    ctx = context(e)
    theme_id = resolve_theme_id(ctx)
    domain = resolve_domain(ctx)
    import random
    url = f"https://{domain}/pages/{args.slug}?v={random.randint(1, 99999)}"
    print(url)
    # blank-render warning: does each of the page's sections have a template?
    try:
        pid = e.page_id_by_slug(args.slug)
        if not pid:
            print(f"  ERROR: no page with slug '{args.slug}' (not build-doc'd yet?).")
        else:
            sd = e.get_sections(pid)
            types = {v.get("type") for v in (sd.get("sections") or {}).values()}
            missing = [t for t in types
                       if t and not installed(e, f"sections/{t}.liquid", theme_id)]
            if missing:
                print(f"  ERROR: theme is MISSING templates for section(s): {', '.join(missing)}")
                print("         → page renders BLANK even when published. Run: epod-store-init install")
            else:
                print(f"  OK: every section type on the page has a template in theme {theme_id}.")
    except SystemExit as ex:
        print(f"  (couldn't read sections_data: {str(ex)[:100]})")
    # try fetching the shell
    try:
        r = epod.requests.get(url, timeout=20)
        print(f"  HTTP {r.status_code}"
              + ("" if r.status_code == 200 else "  ← NOT 200, re-check"))
    except Exception as ex:
        print(f"  (couldn't fetch: {str(ex)[:100]})")
    print("REAL verify in a browser: browser_navigate the URL above → browser_evaluate the DOM "
          "(body must contain .dl-article/content, not just header/footer).")


# ---------------------------------------------------------------- nav helpers
# HOW NAV WORKS (verified on the storefront via list_liquid_objects):
# - Liquid does NOT expose a `pages` object, but it DOES expose `linklists['<handle>']`.
# - ⇒ dynamic nav at RUNTIME via a MENU, no navitem block per page.
# - The left sidebar reads the `docs-nav` menu (full doc list); the header reads
#   `main-menu` (keep it LEAN — a few top-level links, NOT every page).
# - Adding a page = one menu item into `docs-nav` (create_menu_item). EVERY page's
#   sidebar updates IMMEDIATELY, with no edits to old pages. `sync-nav` just syncs the
#   `docs-nav` menu to the published-page list (adds missing; current is computed at runtime).
DOCS_NAV_HANDLE = "docs-nav"     # sidebar (full list)
HEADER_MENU_HANDLE = "main-menu"  # header (lean)


def _find_menu(e, handle):
    """Trả (menu_id, [items]) của menu theo handle, hoặc (None, []).
    LƯU Ý: list_menus trả items RỖNG — phải query storeMenu(id) để lấy items thật."""
    r = e.tool("list_menus", {})
    menus = r.get("storeMenus", r) if isinstance(r, dict) else r
    for m in menus or []:
        if m.get("handle") == handle:
            mid = str(m.get("id"))
            q = e.tool("graphql_query", {
                "query": f"query {{ storeMenu(id: {mid}) {{ items {{ id label page_id url link_type }} }} }}"})
            sm = q.get("storeMenu", q) if isinstance(q, dict) else {}
            items = (sm or {}).get("items", []) if isinstance(sm, dict) else []
            return mid, items
    return None, []


def _ensure_menu(e, handle, name, location):
    mid, items = _find_menu(e, handle)
    if mid:
        return mid, items
    r = e.tool("create_menu", {"name": name, "handle": handle, "location": location})
    m = re.search(r'"id":\s*(\d+)', r if isinstance(r, str) else json.dumps(r))
    return (m.group(1) if m else None), []


def _doc_pages(e, exclude_slugs=("index",)):
    """Danh sách trang tài liệu đã publish (bỏ home/index), sort theo slug."""
    pages = e.tool("list_pages", {})
    lst = pages.get("storePages", pages) if isinstance(pages, dict) else pages
    out = []
    for p in lst or []:
        slug = p.get("slug")
        if not slug or slug in exclude_slugs:
            continue
        if p.get("page_type") == "home":
            continue
        out.append(p)
    out.sort(key=lambda p: str(p.get("slug")))
    return out


def _tag_for(slug, title=""):
    """Tag ngắn (mã tài liệu) cho card. Vd '01-brd'→BRD."""
    return _doc_code({"slug": slug, "title": title})


# Nhãn nav NGẮN, GENERIC theo LOẠI tài liệu — KHÔNG dùng tiêu đề marketing dài.
# Suy từ mã tài liệu (slug/title prefix) → tên chuẩn. Không khớp thì title đã cắt prefix.
_DOC_LABELS = {
    "HANDOFF": "Handoff",
    "BRD": "Business Requirements",
    "SRS": "Software Requirements",
    "SDD": "Software Design",
    "TECHDESIGN": "Technical Design",
    "TECHSPEC": "Technical Spec",
    "TECH": "Technical Design",
    "API": "API Spec",
    "ROUTE": "Route & Controller Spec",
    "DB": "Database Design",
    "UIUX": "UI/UX Design",
    "UI": "UI/UX Design",
    "TEST": "Test Plan",
    "TESTPLAN": "Test Plan",
    "USERSTORIES": "User Stories",
    "STORIES": "User Stories",
    "CONVENTIONS": "Conventions",
    "BUILD": "Build Plan",
    "BUILDPLAN": "Build Plan",
    "FLOW": "Dataflow",
    "DATAFLOW": "Dataflow",
    "BUSINESSDATAFLOW": "Business Dataflow",
    "BUSINESS": "Business Dataflow",
    "DESIGN": "Design System",
}


def _doc_code(page):
    """Mã tài liệu viết hoa suy từ slug ('01-brd'→BRD) hoặc prefix title ('BRD — ...')."""
    import re
    slug = page.get("slug") or ""
    s = re.sub(r"^\d+[-_.]*", "", slug)                 # bỏ '01-'
    # thử slug đầy đủ đã nén trước (vd 'tech-design'→'TECHDESIGN') để tránh
    # đụng nhãn khi nhiều slug cùng token đầu (tech-design vs tech-spec).
    full = re.sub(r"[^a-z0-9]", "", s.lower())
    if full.upper() in _DOC_LABELS:
        return full.upper()
    code = re.split(r"[-_./]", s)[0] if s else slug
    code = re.sub(r"[^a-z0-9]", "", code.lower())
    if code.upper() in _DOC_LABELS:
        return code.upper()
    m = re.match(r"^\s*([A-Z0-9]{2,8})\s*[—:\-]", (page.get("title") or ""))
    if m and m.group(1) in _DOC_LABELS:
        return m.group(1)
    return code.upper() if code else "DOC"


def _label_for(page):
    """Nhãn nav NGẮN & GENERIC theo loại tài liệu (vd 'Business Requirements').
    Không khớp bảng → dùng title đã bỏ prefix, cắt gọn; cuối cùng là slug."""
    import re
    code = _doc_code(page)
    if code in _DOC_LABELS:
        return _DOC_LABELS[code]
    t = (page.get("title") or "").strip()
    if t:
        t = re.sub(r"^\s*\d+\s*[—.\-:]\s*", "", t)
        t = re.sub(r"^\s*[A-Z0-9]{2,8}\s*[—:\-]\s*", "", t)
        return t[:32]
    return page.get("slug")


def cmd_sync_nav(e, args):
    """Đồng bộ menu `docs-nav` (sidebar) khớp danh sách trang đã publish.
    Sidebar đọc menu này lúc RUNTIME ⇒ chạy lệnh này sau khi thêm trang là XONG,
    KHÔNG phải sửa trang cũ. Idempotent: thêm item còn thiếu, gỡ item trùng và
    item mồ côi (trỏ tới trang đã xoá — xoá trang KHÔNG tự gỡ item, nó vẫn hiện
    trên sidebar và dẫn tới 404)."""
    pages = _doc_pages(e)
    mid, items = _ensure_menu(e, DOCS_NAV_HANDLE, "Docs nav", "sidebar")
    if not mid:
        raise SystemExit("không tạo/không thấy menu docs-nav")
    # gom item theo page_id; item trùng (cùng page_id) → xoá bớt để không nhân đôi
    by_pid = {}
    dups = []
    for it in items:
        pid = str(it.get("page_id") or "")
        if not pid:
            continue
        if pid in by_pid:
            dups.append(it)               # trùng → xoá
        else:
            by_pid[pid] = it
    for it in dups:
        e.tool("delete_menu_item", {"item_id": str(it.get("id"))})
    # item mồ côi: trỏ tới page_id không còn trong danh sách trang
    live_pids = {str(p.get("id")) for p in pages}
    orphans = [it for pid, it in by_pid.items() if pid not in live_pids]
    for it in orphans:
        e.tool("delete_menu_item", {"item_id": str(it.get("id"))})
        by_pid.pop(str(it.get("page_id")), None)
    print(f"docs-nav (menu {mid}) — {len(pages)} doc page(s):")
    for it in orphans:
        print(f"  - {it.get('label')}  (trang {it.get('page_id')} đã xoá)")
    added, relabeled = [], []
    for pos, p in enumerate(pages, 1):
        pid = str(p.get("id"))
        label = _label_for(p)
        cur = by_pid.get(pid)
        if cur:
            # đã có → cập nhật nhãn nếu lệch
            if (cur.get("label") or "") != label:
                e.tool("update_menu_item", {"item_id": str(cur.get("id")), "label": label})
                relabeled.append(label)
            print(f"  = {label}")
            continue
        e.tool("create_menu_item", {
            "menu_id": str(mid), "label": label,
            "link_type": "page", "page_id": pid, "position": pos})
        added.append(label)
        print(f"  + {label}")
    e.tool("clear_storefront_cache", {})
    print(json.dumps({"menu": DOCS_NAV_HANDLE, "id": mid, "pages": len(pages),
                      "added": added, "relabeled": relabeled,
                      "removed_dups": len(dups),
                      "removed_orphans": [it.get("label") for it in orphans]},
                     ensure_ascii=False, indent=2))
    print("Every doc-layout page's sidebar updates at runtime — no need to edit old pages.")


def cmd_home(e, args):
    """Set trang chủ `/` = web-hero + docs-toc.
    QUAN TRỌNG (đã kiểm chứng): `/` do TEMPLATE `index` render, KHÔNG phải trang
    page_type=home (trang đó bị bỏ qua). Nên ghi qua set_section_settings template
    'index'. docs-toc card sinh từ danh sách trang thật (build-time)."""
    ctx = context(e)
    theme_id = resolve_theme_id(ctx)
    pages = _doc_pages(e)
    cards = []
    for i, p in enumerate(pages):
        slug = p.get("slug")
        cards.append({"type": "card", "settings": {
            "tag": _tag_for(slug, p.get("title")),
            "num": "",
            "title": _label_for(p),
            "desc": "",
            "url": f"/pages/{slug}",
            "featured": (i == 0),
        }})
    store = ctx.get("store_slug") or ctx.get("store_name") or "Docs"
    heading = args.heading or f"{store} documentation"
    # hero
    e.tool("set_section_settings", {
        "template": "index", "section_id": "hero", "type": "web-hero", "position": 0,
        "theme_id": str(theme_id),
        "settings": {
            "eyebrow": args.eyebrow or "Documentation",
            "heading": heading,
            "subheading": args.subheading or "",
            "cta_label": ("Read the docs" if cards else ""),
            "cta_url": (cards[0]["settings"]["url"] if cards else ""),
        }})
    # docs-toc
    e.tool("set_section_settings", {
        "template": "index", "section_id": "toc", "type": "docs-toc", "position": 1,
        "theme_id": str(theme_id),
        "settings": {"eyebrow": "Contents", "heading": "Documents",
                     "intro": "All project documentation."},
        "blocks": cards})
    # dọn section mặc định (features/cta...) — chỉ giữ hero+toc trong index.json
    try:
        raw = e.get_theme_file("templates/index.json", theme_id=theme_id)
        tpl = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(tpl, dict) and "sections" in tpl:
            tpl["order"] = ["hero", "toc"]
            tpl["sections"] = {k: v for k, v in tpl["sections"].items()
                               if k in ("hero", "toc")}
            e.tool("upsert_theme_file", {
                "path": "templates/index.json",
                "content": json.dumps(tpl, ensure_ascii=False, indent=2),
                "theme_id": str(theme_id)})
    except Exception as ex:
        print(f"(warning: couldn't trim index.json: {str(ex)[:120]})", file=sys.stderr)
    e.tool("clear_storefront_cache", {})
    domain = resolve_domain(ctx)
    print(json.dumps({"home": "set (index template)", "cards": len(cards)},
                     ensure_ascii=False, indent=2))
    print(f"verify: https://{domain}/?v=1")


def main():
    ap = argparse.ArgumentParser(
        prog="epod-store-init",
        description="Khởi tạo store epod: cài theme section cần cho doc pages. "
                    "Env-driven, không hard-code store/domain nào.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="<command>")
    sub.add_parser("check", help="print context + which sections are installed/missing")
    dc = sub.add_parser("doctor", help="pre-lint sections + diagnose store (catch errors before reject)")
    dc.add_argument("--local", action="store_true", help="pre-lint locally only, no network")
    ins = sub.add_parser("install", help="install sections (auto pre-lints before upload)")
    ins.add_argument("--force", action="store_true", help="overwrite sections that already exist")
    ins.add_argument("--only", help="install only these sections (comma-separated)")
    ins.add_argument("--no-lint", action="store_true", help="skip pre-lint (not recommended)")
    vf = sub.add_parser("verify", help="print live URL + warn on 404/blank-render")
    vf.add_argument("slug", help="page slug to check")
    hm = sub.add_parser("home", help="set the home page / (web-hero + docs-toc, index template)")
    hm.add_argument("--heading", help="hero heading (default: '<store> documentation')")
    hm.add_argument("--eyebrow", help="hero eyebrow")
    hm.add_argument("--subheading", help="hero subheading")
    sub.add_parser("sync-nav", help="sync the docs-nav menu (sidebar) from published pages")

    a = ap.parse_args()
    # doctor --local không cần mạng; các lệnh khác cần Epod()
    if a.cmd == "doctor" and a.local:
        cmd_doctor(None, a)
        return
    e = epod.Epod()
    if a.cmd == "check":
        cmd_check(e, a)
    elif a.cmd == "doctor":
        cmd_doctor(e, a)
    elif a.cmd == "install":
        cmd_install(e, a)
    elif a.cmd == "verify":
        cmd_verify(e, a)
    elif a.cmd == "home":
        cmd_home(e, a)
    elif a.cmd == "sync-nav":
        cmd_sync_nav(e, a)


if __name__ == "__main__":
    main()
