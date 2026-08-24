"""Store context: what store, what theme, what domain — resolved live, never pinned.

Env overrides exist because get_context cannot always be trusted to report the
storefront domain or the theme a write should target.
"""
import os


def context(e):
    """get_context flattened to {store_id, store_slug, theme_id, ...}."""
    ctx = e.tool("get_context", {})
    if not isinstance(ctx, dict):
        raise SystemExit(f"get_context did not return a dict: {str(ctx)[:200]}")
    flat = dict(ctx)
    store = ctx.get("store") if isinstance(ctx.get("store"), dict) else {}
    for k in ("id", "slug", "name"):
        if store.get(k) and f"store_{k}" not in flat:
            flat[f"store_{k}"] = store[k]
    return flat


def store_id(e, ctx=None):
    ctx = ctx if ctx is not None else context(e)
    for k in ("store_id", "storeId"):
        if ctx.get(k):
            return str(ctx[k])
    raise SystemExit(f"could not determine store_id from get_context: {str(ctx)[:300]}")


def resolve_domain(ctx):
    """Storefront domain: env, then context, then <slug>.epodsystem.com."""
    if os.environ.get("EPOD_STORE_DOMAIN"):
        return os.environ["EPOD_STORE_DOMAIN"]
    for k in ("storefront_domain", "store_domain", "domain", "primary_domain"):
        if ctx.get(k):
            return str(ctx[k]).replace("https://", "").replace("http://", "").strip("/")
    slug = ctx.get("store_slug") or ctx.get("store_name")
    if slug:
        return f"{slug}.epodsystem.com"
    raise SystemExit("could not infer the storefront domain — set EPOD_STORE_DOMAIN")


def resolve_theme_id(ctx):
    return os.environ.get("EPOD_THEME_ID") or str(ctx.get("theme_id") or "") or None
