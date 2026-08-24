"""Per-project configuration: `.epod.json`, resolved by walking up from the CWD.

Project data does not belong in the tool. A doc filename, a doc-type label, a
hero heading are all facts about one company's store, so they live beside that
project's `.mcp.json` and every one of them is optional — a project with no
`.epod.json` gets documented defaults, never a different store's values.

    {
      "docs": {
        "links":  { "01-BRD.md": "brd" },
        "labels": { "RUNBOOK": "Operations Runbook" },
        "hero":   { "heading": "...", "mark": "AB",
                    "nav_title": "...", "toc_title": "..." }
      }
    }
"""
import json
import os

FILENAME = ".epod.json"
_cache = {}


def path():
    """Nearest `.epod.json` at or above the CWD, or None."""
    d = os.getcwd()
    while True:
        p = os.path.join(d, FILENAME)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load():
    p = path()
    if p is None:
        return {}
    if p in _cache:
        return _cache[p]
    try:
        cfg = json.load(open(p, encoding="utf-8"))
    except (ValueError, OSError) as ex:
        raise SystemExit(f"{p} is not readable JSON: {ex}")
    if not isinstance(cfg, dict):
        raise SystemExit(f"{p} must hold a JSON object")
    _cache[p] = cfg
    return cfg


def section(name):
    """One top-level block, e.g. section('docs'); {} when absent."""
    v = load().get(name)
    return v if isinstance(v, dict) else {}
