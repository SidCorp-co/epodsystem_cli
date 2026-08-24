"""Doc blocks inside a page's sections_data, and the anchors they render as."""
from ...core.text import slugify


def doc_blocks(sd):
    return [b for b in sd["sections"]["doc"]["blocks"] if b.get("type") == "doc"]


def find_block(sd, num):
    for b in doc_blocks(sd):
        if str(b["settings"].get("num")) == str(num):
            return b
    return None


def anchors(sd):
    """[(num, anchor, title)] — the anchor is what doc-layout.liquid derives."""
    out = []
    for b in doc_blocks(sd):
        title = b["settings"].get("title", "")
        out.append((b["settings"].get("num"), slugify(title), title))
    return out
