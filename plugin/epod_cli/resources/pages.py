"""CMS pages: the `sections_data` document, and the page record around it.

updatePage replaces sections_data WHOLE, so every edit is read-modify-write of
the entire document. Patch it in memory and put it back; never send one block.
"""
from ..core import context as ctx_mod

_SAVE = ("mutation Save($id: ID!, $input: UpdatePageInput!)"
         "{ updatePage(id:$id, input:$input){ id slug status } }")
_CREATE = ("mutation New($input: CreatePageInput!)"
           "{ createPage(input:$input){ id slug status } }")


def listing(e):
    r = e.tool("list_pages", {})
    return (r.get("storePages", r) if isinstance(r, dict) else r) or []


def content_pages(e, exclude_slugs=("index",)):
    """Published content pages, home excluded, sorted by slug."""
    out = [p for p in listing(e)
           if p.get("slug") and p.get("slug") not in exclude_slugs
           and p.get("page_type") != "home"]
    out.sort(key=lambda p: str(p.get("slug")))
    return out


def id_by_slug(e, slug):
    for p in listing(e):
        if p.get("slug") == slug:
            return str(p.get("id"))
    return None


def slug_by_id(e, page_id):
    for p in listing(e):
        if str(p.get("id")) == str(page_id):
            return p.get("slug")
    return None


def get_sections(e, page_id):
    q = e.query(f"query {{ storePage(id: {page_id}) {{ sections_data }} }}")
    sp = q.get("storePage", q)
    return sp["sections_data"]


def put_sections(e, page_id, sd, publish=True):
    result = {"update": e.mutation(_SAVE, {"id": str(page_id),
                                           "input": {"sections_data": sd}})}
    if publish:
        result["publish"] = e.tool("publish_page", {"id": str(page_id)})
        result["clear_cache"] = e.clear_cache()
    return result


def publish(e, page_id):
    return e.tool("publish_page", {"id": str(page_id)})


def create(e, title, slug, sd=None, store_id=None, page_type="custom", publish_=True):
    sid = store_id or ctx_mod.store_id(e)
    created = e.mutation(_CREATE, {"input": {"store_id": str(sid), "page_type": page_type,
                                             "title": title, "slug": slug}})
    page = created.get("createPage", created) if isinstance(created, dict) else created
    pid = page.get("id") if isinstance(page, dict) else None
    if not pid:
        raise SystemExit(f"createPage returned no id: {str(created)[:400]}")
    result = {"create": created}
    if sd is not None:
        result["update"] = e.mutation(_SAVE, {
            "id": str(pid), "input": {"content_mode": "sections", "sections_data": sd}})
        if publish_:
            result["publish"] = e.tool("publish_page", {"id": str(pid)})
            result["clear_cache"] = e.clear_cache()
    return result


def upsert_sections(e, slug, title, sd, publish=True):
    """Update the page at `slug` if it exists, otherwise create it. Returns (action, result)."""
    pid = id_by_slug(e, slug)
    if pid:
        return "updated", put_sections(e, pid, sd, publish=publish)
    return "created", create(e, title, slug, sd=sd, publish_=publish)
