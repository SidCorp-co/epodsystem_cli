"""epod — one CLI over the epod platform.

Two axes. A RESOURCE is a verb on an epod noun and carries no use case:
`epod page`, `epod theme`, `epod menu`, `epod schema`. A PACK is a workflow that
owns its own policy and assets: `epod docs` builds documentation sites. A second
pack is a directory under epod_cli/packs and one entry in PACKS below.

Global but project-scoped: the token comes from the `.mcp.json` found by walking
up from the CWD, and project data from a `.epod.json` beside it, so every command
acts on the store belonging to the checkout you are standing in.
"""
import argparse
import json
import os
import sys

from .core import config
from .core.client import Epod
from .core.context import context
from .core.text import MOJIBAKE_RE, demojibake, walk
from .resources import menus, pages, schema, themes

EPILOG = """\
examples:
  epod context                          which store am I on?
  epod page list                        pages (id/slug/status)
  epod docs build docs/02-SRS.md --slug srs
  epod docs nav                         rebuild the sidebar from published pages
  epod schema liquid                    what a theme can read at runtime

Project data (doc link map, sidebar labels, hero defaults) lives in .epod.json
beside the project's .mcp.json — never in this CLI. See `epod paths`.
Every write publishes and clears the storefront cache unless --no-publish.
"""


def emit(obj):
    # Several tools answer with prose rather than JSON; re-encoding it would
    # print one escaped line instead of the document it is.
    print(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False, indent=2))


def _read(path):
    return open(path, encoding="utf-8").read()


def _write(path, content, note):
    open(path, "w", encoding="utf-8").write(content)
    print(f"{note} -> {path} ({len(content)} bytes)")


# ---------------------------------------------------------------- resources
def add_page_parser(sub):
    p = sub.add_parser("page", help="CMS pages: list, read and write sections_data")
    s = p.add_subparsers(dest="sub", required=True, metavar="<verb>")
    s.add_parser("list", help="list pages (id/slug/status)")
    g = s.add_parser("get", help="read the whole sections_data of a page")
    g.add_argument("page_id"); g.add_argument("--out", help="write to a JSON file")
    u = s.add_parser("put", help="write the whole sections_data from a JSON file")
    u.add_argument("page_id")
    u.add_argument("--in", dest="infile", required=True, help="sections_data JSON")
    u.add_argument("--no-publish", action="store_true", help="save a draft only")
    c = s.add_parser("create", help="create a page, then set sections_data and publish")
    c.add_argument("--title", required=True); c.add_argument("--slug", required=True)
    c.add_argument("--sections", dest="infile", help="sections_data JSON (omit for an empty page)")
    c.add_argument("--store-id", dest="store_id", help="default: from get_context")
    c.add_argument("--no-publish", action="store_true")
    pb = s.add_parser("publish", help="publish a page (sections_data -> live)")
    pb.add_argument("page_id")
    fm = s.add_parser("fix-mojibake", help="repair latin-1/utf-8 damaged text, then publish")
    fm.add_argument("page_id"); fm.add_argument("--dry", action="store_true")


def run_page(e, a):
    if a.sub == "list":
        return emit(pages.listing(e))
    if a.sub == "get":
        sd = pages.get_sections(e, a.page_id)
        s = json.dumps(sd, ensure_ascii=False, indent=2)
        return _write(a.out, s, "saved sections_data") if a.out else print(s)
    if a.sub == "put":
        return emit(pages.put_sections(e, a.page_id, json.loads(_read(a.infile)),
                                       publish=not a.no_publish))
    if a.sub == "create":
        sd = json.loads(_read(a.infile)) if a.infile else None
        return emit(pages.create(e, a.title, a.slug, sd=sd, store_id=a.store_id,
                                 publish_=not a.no_publish))
    if a.sub == "publish":
        return emit(pages.publish(e, a.page_id))
    if a.sub == "fix-mojibake":
        sd = pages.get_sections(e, a.page_id)
        found = []
        walk(sd, lambda x: found.append(x[:60])
             if isinstance(x, str) and MOJIBAKE_RE.search(x) else x)
        print(f"suspect strings: {len(found)}")
        for s in found[:5]:
            print("  -", s, "->", demojibake(s)[:60])
        if a.dry:
            return print("(dry run, nothing written)")
        if not found:
            return print("nothing to fix.")
        return emit(pages.put_sections(e, a.page_id, walk(sd, demojibake)))


def add_theme_parser(sub):
    p = sub.add_parser("theme", help="theme files, and the design contract they must pass")
    s = p.add_subparsers(dest="sub", required=True, metavar="<verb>")
    ls = s.add_parser("list", help="list the theme's files")
    ls.add_argument("--theme", dest="theme_id", help="default: the active theme")
    g = s.add_parser("get", help="read one theme file")
    g.add_argument("path", help="e.g. sections/doc-layout.liquid")
    g.add_argument("--out"); g.add_argument("--theme", dest="theme_id")
    u = s.add_parser("put", help="write one theme file, then clear the cache")
    u.add_argument("path"); u.add_argument("--in", dest="infile", required=True)
    u.add_argument("--theme", dest="theme_id")
    u.add_argument("--no-publish", action="store_true", help="skip the cache clear")
    ln = s.add_parser("lint", help="check a .liquid section against the design contract")
    ln.add_argument("files", nargs="+", help="local .liquid files")


def run_theme(e, a):
    if a.sub == "lint":
        rc = 0
        for f in a.files:
            probs = themes.lint_section(_read(f))
            if not probs:
                print(f"  OK    {f}")
            for sev, msg in probs:
                print(f"  {'ERROR' if sev == 'error' else 'warn '} {f}: {msg}")
            if any(sev == "error" for sev, _ in probs):
                rc = 1
        return rc
    if a.sub == "list":
        return emit(themes.list_files(e, theme_id=a.theme_id))
    if a.sub == "get":
        content = themes.get_file(e, a.path, theme_id=a.theme_id) or ""
        return _write(a.out, content, f"saved {a.path}") if a.out else print(content)
    if a.sub == "put":
        return emit(themes.put_file(e, a.path, _read(a.infile), theme_id=a.theme_id,
                                    clear_cache=not a.no_publish))


def add_menu_parser(sub):
    p = sub.add_parser("menu", help="store menus — nav resolves through these at runtime")
    s = p.add_subparsers(dest="sub", required=True, metavar="<verb>")
    s.add_parser("list", help="list menus")
    g = s.add_parser("get", help="one menu's items, by handle")
    g.add_argument("handle", help="e.g. docs-nav, main-menu")


def run_menu(e, a):
    if a.sub == "list":
        return emit(e.tool("list_menus", {}))
    if a.sub == "get":
        mid, items = menus.find(e, a.handle)
        if not mid:
            raise SystemExit(f"no menu with handle '{a.handle}'")
        return emit({"handle": a.handle, "id": mid, "items": items})


def add_schema_parser(sub):
    p = sub.add_parser("schema", help="what this store can do — read before writing a new pack")
    s = p.add_subparsers(dest="sub", required=True, metavar="<verb>")
    i = s.add_parser("introspect", help="GraphQL types")
    i.add_argument("--type", dest="type_name", help="one type instead of the whole schema")
    s.add_parser("liquid", help="objects a theme can read at runtime")
    s.add_parser("tools", help="every MCP tool the server exposes")


def run_schema(e, a):
    if a.sub == "introspect":
        return emit(schema.introspect(e, a.type_name))
    if a.sub == "liquid":
        return emit(schema.liquid_objects(e))
    if a.sub == "tools":
        tools = schema.tools(e)
        print(f"{len(tools)} tools")
        for t in tools:
            print(f"  {t['name']:<28} {t['description'].splitlines()[0][:80] if t['description'] else ''}")
        return


# ---------------------------------------------------------------- packs
def add_docs_parser(sub):
    p = sub.add_parser("docs", help="documentation sites: build, sync, nav, home, bootstrap")
    s = p.add_subparsers(dest="sub", required=True, metavar="<verb>")
    b = s.add_parser("build", help="a .md becomes a doc page, created or updated, then published")
    b.add_argument("mdfile"); b.add_argument("--slug", required=True)
    b.add_argument("--title", help="page title (default: the .md H1)")
    for flag in ("heading", "mark", "subheading", "chip1", "chip2", "chip3", "note"):
        b.add_argument(f"--{flag}", help=f"hero {flag} (default: .epod.json docs.hero)")
    b.add_argument("--nav-title", dest="nav_title", help="left sidebar heading")
    b.add_argument("--toc-title", dest="toc_title", help="right TOC heading")
    b.add_argument("--out", help="write sections_data to a file, do not push")
    b.add_argument("--no-publish", action="store_true")
    y = s.add_parser("sync", help="a published page becomes the body of its .md (header kept)")
    y.add_argument("page_id"); y.add_argument("mdfile")
    y.add_argument("--stdout", action="store_true")
    bl = s.add_parser("blocks", help="list a page's doc blocks (num + title)")
    bl.add_argument("page_id")
    an = s.add_parser("anchors", help="each block's anchor slug, for cross-doc #links")
    an.add_argument("page_id"); an.add_argument("--url", action="store_true")
    gb = s.add_parser("get-block", help="one block's body as plain HTML, to edit")
    gb.add_argument("page_id"); gb.add_argument("num"); gb.add_argument("--out")
    pu = s.add_parser("put-block", help="load one block's body back from an HTML file")
    pu.add_argument("page_id"); pu.add_argument("num")
    pu.add_argument("--in", dest="infile", required=True)
    pu.add_argument("--title", help="also retitle the block")
    pu.add_argument("--no-publish", action="store_true")
    s.add_parser("nav", help="sync the docs-nav sidebar menu from published pages")
    hm = s.add_parser("home", help="set / to web-hero + docs-toc (index template)")
    hm.add_argument("--heading"); hm.add_argument("--eyebrow"); hm.add_argument("--subheading")
    dc = s.add_parser("doctor", help="pre-lint the bundled sections + diagnose the store")
    dc.add_argument("--local", action="store_true", help="lint locally only, no network")
    s.add_parser("check", help="context + which sections are installed")
    ins = s.add_parser("install", help="install the bundled doc sections into the theme")
    ins.add_argument("--force", action="store_true", help="overwrite sections that exist")
    ins.add_argument("--only", help="comma-separated section names")
    ins.add_argument("--no-lint", action="store_true", help="skip the pre-lint (not advised)")
    vf = s.add_parser("verify", help="live URL + warn on 404 or a blank render")
    vf.add_argument("slug")


def run_docs(e, a):
    from .packs.docs import blocks as blocks_mod, bootstrap, build, nav, sync

    if a.sub == "build":
        return emit(build.run(e, a))
    if a.sub == "sync":
        body, summary = sync.run(e, a.page_id, a.mdfile, to_stdout=a.stdout)
        return print(body) if body is not None else emit(summary)
    if a.sub == "blocks":
        sd = pages.get_sections(e, a.page_id)
        for b in blocks_mod.doc_blocks(sd):
            print(f'  num={b["settings"].get("num")!s:<4} {b["settings"].get("title", "")}')
        return
    if a.sub == "anchors":
        sd = pages.get_sections(e, a.page_id)
        slug = pages.slug_by_id(e, a.page_id) if a.url else None
        for num, anchor, title in blocks_mod.anchors(sd):
            if a.url:
                print(f'  num={num!s:<4} /pages/{slug or "<slug>"}#{anchor}')
            else:
                print(f'  num={num!s:<4} #{anchor:<40} {title}')
        return
    if a.sub in ("get-block", "put-block"):
        sd = pages.get_sections(e, a.page_id)
        b = blocks_mod.find_block(sd, a.num)
        if not b:
            raise SystemExit(f"no block with num={a.num}")
        if a.sub == "get-block":
            body = b["settings"].get("body", "")
            return _write(a.out, body, f'saved block num={a.num}') if a.out else print(body)
        b["settings"]["body"] = _read(a.infile)
        if a.title:
            b["settings"]["title"] = a.title
        return emit(pages.put_sections(e, a.page_id, sd, publish=not a.no_publish))
    if a.sub == "nav":
        summary = nav.sync(e)
        emit(summary)
        return print("Every doc-layout page's sidebar updates at runtime — "
                     "no need to edit old pages.")
    if a.sub == "home":
        return bootstrap.home(e, a.heading, a.eyebrow, a.subheading)
    if a.sub == "doctor":
        return bootstrap.doctor(e, local_only=a.local)
    if a.sub == "check":
        return bootstrap.check(e)
    if a.sub == "install":
        return bootstrap.install(e, force=a.force, only=a.only, lint=not a.no_lint)
    if a.sub == "verify":
        return bootstrap.verify(e, a.slug)


PACKS = {"docs": (add_docs_parser, run_docs)}
RESOURCES = {"page": (add_page_parser, run_page),
             "theme": (add_theme_parser, run_theme),
             "menu": (add_menu_parser, run_menu),
             "schema": (add_schema_parser, run_schema)}

# Commands that never open a connection, so they work with no token and no project.
OFFLINE = {("theme", "lint"), ("docs", "doctor")}


def build_parser():
    ap = argparse.ArgumentParser(
        prog="epod", description=__doc__.splitlines()[0],
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="group", required=True, metavar="<group>")
    for add, _ in list(RESOURCES.values()) + list(PACKS.values()):
        add(sub)
    sub.add_parser("context", help="the active org/store/theme, resolved live")
    sub.add_parser("paths", help="where the CLI, the bundled assets and the config are")
    q = sub.add_parser("query", help="run one GraphQL query")
    q.add_argument("graphql", help="e.g. 'query { storePages { id slug } }'")
    ca = sub.add_parser("cache", help="storefront cache")
    ca.add_subparsers(dest="sub", required=True, metavar="<verb>").add_parser(
        "clear", help="clear the storefront cache")
    return ap


def run_paths():
    from .packs import docs as docs_pack
    cfg = config.path()
    emit({"package": os.path.dirname(os.path.abspath(__file__)),
          "packs": sorted(PACKS),
          "resources": sorted(RESOURCES),
          "docs_sections": docs_pack.SECTIONS_DIR,
          "project_config": cfg or f"(none found above {os.getcwd()})",
          "token": "EPOD_TOKEN" if os.environ.get("EPOD_TOKEN") else ".mcp.json"})


def main():
    a = build_parser().parse_args()
    sub = getattr(a, "sub", None)

    if a.group == "paths":
        return run_paths()
    if (a.group, sub) in OFFLINE and getattr(a, "local", True):
        handler = dict(RESOURCES, **PACKS)[a.group][1]
        return sys.exit(handler(None, a) or 0)

    e = Epod()
    if a.group == "context":
        return emit(context(e))
    if a.group == "query":
        return emit(e.query(a.graphql))
    if a.group == "cache":
        return emit(e.clear_cache())
    handler = dict(RESOURCES, **PACKS)[a.group][1]
    sys.exit(handler(e, a) or 0)
