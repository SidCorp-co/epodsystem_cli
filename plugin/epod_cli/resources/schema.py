"""What the store can actually do — the surface a new pack is written against.

Reach for these before hand-writing a GraphQL string: `introspect` reports the
real types and `liquid_objects` reports what a theme can read at runtime, which
is how the docs pack learned nav had to be menu-driven.
"""


def introspect(e, type_name=None):
    args = {}
    if type_name:
        args["type"] = type_name
    return e.tool("introspect_schema", args)


def liquid_objects(e):
    return e.tool("list_liquid_objects", {})


def tools(e):
    return [{"name": t.get("name"), "description": (t.get("description") or "").strip()}
            for t in e.tools()]
