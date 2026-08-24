"""What the store can actually do — the surface a new pack is written against."""


def introspect(e, type_name=None):
    return e.tool("introspect_schema", {"type": type_name} if type_name else {})


def liquid_objects(e):
    return e.tool("list_liquid_objects", {})


def tools(e):
    return [{"name": t.get("name"), "description": (t.get("description") or "").strip()}
            for t in e.tools()]
