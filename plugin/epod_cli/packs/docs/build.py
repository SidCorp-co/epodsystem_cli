"""Markdown → a doc-layout page.

Builds the whole sections_data for a doc page: the `doc` section carrying one
block per '## <num>. <title>' heading, and the `brd-hero` section above it. The
sidebar is deliberately absent — it resolves from the docs-nav menu at runtime,
so no navitem block is ever injected here.
"""
import re

from ...resources import pages
from . import hero_defaults, link_map
from . import md2doc


def sections_data(md, hero, nav_title, toc_title):
    blocks = md2doc.md_to_doc_blocks(md, link_map=link_map())
    if not blocks:
        raise SystemExit("no blocks found in the .md — headings must read '## <num>. <title>'")
    return {"order": ["doc", "hero"],
            "sections": {
                "doc": {"type": "doc-layout",
                        "settings": {"nav_title": nav_title, "toc_title": toc_title},
                        "blocks": blocks},
                "hero": {"type": "brd-hero", "settings": hero}}}, blocks


def hero_settings(md, args):
    """Hero settings: the CLI flag wins, then `.epod.json` docs.hero, then empty.

    doc_type comes off the H1 — the part before an em-dash or colon, uppercased
    ('# Test Plan — Foo' → 'TEST PLAN'). The subheading is never auto-grabbed
    from a '### ' line: the first one is usually a section number, not a summary.
    """
    d = hero_defaults()
    m = re.search(r"^#\s+(.+)$", md, re.M)
    h1 = m.group(1).strip() if m else ""
    doc_type = re.split(r"\s+[—–:-]\s+", h1)[0].strip().upper() if h1 else ""

    def pick(name, fallback=""):
        return getattr(args, name, None) or d.get(name) or fallback

    return {"mark": pick("mark"), "doc_type": doc_type,
            "heading": pick("heading"), "subheading": pick("subheading"),
            "chip1": pick("chip1"), "chip2": pick("chip2"), "chip3": pick("chip3"),
            "note": pick("note"), "logo": ""}, h1


def run(e, args):
    md = open(args.mdfile, encoding="utf-8").read()
    d = hero_defaults()
    hero, h1 = hero_settings(md, args)
    sd, blocks = sections_data(
        md, hero,
        nav_title=args.nav_title or d.get("nav_title") or "Project Documentation",
        toc_title=args.toc_title or d.get("toc_title") or "On this page")

    if args.out:
        import json
        open(args.out, "w", encoding="utf-8").write(
            json.dumps(sd, ensure_ascii=False, indent=2))
        return {"wrote": args.out, "blocks": len(blocks), "pushed": False}

    title = args.title or h1 or args.slug
    action, result = pages.upsert_sections(e, args.slug, title, sd,
                                           publish=not args.no_publish)
    return {"slug": args.slug, "action": action, "blocks": len(blocks),
            "result": result}
