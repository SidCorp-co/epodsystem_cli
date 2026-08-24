"""The docs pack: a documentation site made of doc-layout pages, a menu-driven
sidebar, and a home page served by the index template.

Everything project-shaped — which .md maps to which slug, what a doc type is
called in the sidebar, what the hero says — comes from the project's
`.epod.json` under "docs". The defaults here are document-type knowledge, true
of any project; nothing in this package names a company, a store or a page id.
"""
import os

from ...core import config

SECTIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sections")

NAV_HANDLE = "docs-nav"  # the sidebar menu: the full doc list

# Short, generic sidebar labels keyed by document code. A project extends or
# overrides this through `.epod.json` → docs.labels; it never edits this table.
DEFAULT_LABELS = {
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


def _docs_config():
    return config.section("docs")


def link_map():
    """{'01-BRD.md': 'brd'} for rewriting cross-doc links; empty unless configured."""
    v = _docs_config().get("links")
    return v if isinstance(v, dict) else {}


def labels():
    merged = dict(DEFAULT_LABELS)
    v = _docs_config().get("labels")
    if isinstance(v, dict):
        merged.update({str(k).upper(): str(val) for k, val in v.items()})
    return merged


def hero_defaults():
    v = _docs_config().get("hero")
    return v if isinstance(v, dict) else {}


def local_sections():
    """{name: (theme_path, content)} for the bundled doc sections."""
    if not os.path.isdir(SECTIONS_DIR):
        raise SystemExit(f"missing bundled sections directory: {SECTIONS_DIR}")
    out = {}
    for fn in sorted(os.listdir(SECTIONS_DIR)):
        if fn.endswith(".liquid"):
            out[fn[:-len(".liquid")]] = (
                f"sections/{fn}",
                open(os.path.join(SECTIONS_DIR, fn), encoding="utf-8").read())
    return out
