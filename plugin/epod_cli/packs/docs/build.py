"""Markdown → a doc-layout page.

The sidebar is deliberately absent from the sections_data: it resolves from the
docs-nav menu at runtime, so no navitem block is ever injected here.
"""
import json
import re

from ...resources import pages
from . import hero_defaults, link_map
from . import md2doc


def run(e, args):
    md = open(args.mdfile, encoding="utf-8").read()
    d = hero_defaults()

    def pick(name, fallback=""):
        """The CLI flag wins, then .epod.json docs.hero, then the fallback."""
        return getattr(args, name, None) or d.get(name) or fallback

    blocks = md2doc.md_to_doc_blocks(md, link_map=link_map())
    if not blocks:
        raise SystemExit("no blocks found in the .md — headings must read '## <num>. <title>'")

    # doc_type is the H1 up to an em-dash or colon ('# Test Plan — Foo' → 'TEST PLAN').
    # subheading is never taken from a '### ' line: the first one is usually a
    # section number, not a summary.
    m = re.search(r"^#\s+(.+)$", md, re.M)
    h1 = m.group(1).strip() if m else args.slug
    sd = {"order": ["doc", "hero"],
          "sections": {
              "doc": {"type": "doc-layout",
                      "settings": {"nav_title": pick("nav_title", "Project Documentation"),
                                   "toc_title": pick("toc_title", "On this page")},
                      "blocks": blocks},
              "hero": {"type": "brd-hero",
                       "settings": {
                           "mark": pick("mark"),
                           "doc_type": re.split(r"\s+[—–:-]\s+", h1)[0].strip().upper(),
                           "heading": pick("heading"), "subheading": pick("subheading"),
                           "chip1": pick("chip1"), "chip2": pick("chip2"),
                           "chip3": pick("chip3"), "note": pick("note"), "logo": ""}}}}

    if args.out:
        open(args.out, "w", encoding="utf-8").write(json.dumps(sd, ensure_ascii=False, indent=2))
        return {"wrote": args.out, "blocks": len(blocks), "pushed": False}

    action, result = pages.upsert_sections(e, args.slug, args.title or h1 or args.slug, sd,
                                           publish=not args.no_publish)
    return {"slug": args.slug, "action": action, "blocks": len(blocks), "result": result}
