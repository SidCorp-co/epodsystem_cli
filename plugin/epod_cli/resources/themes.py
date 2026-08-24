"""Theme files, and the design contract they must satisfy.

The server rejects a bad section with a terse message, so the same three rules
are checked locally first. Nothing here is docs-specific: any pack that ships a
`.liquid` section lints it through `lint_section`.
"""
import re

# The canonical Style settings group every section's schema must declare.
_STYLE_KEYS = ("visible", "bg_color", "text_color", "heading_color",
               "padding_top", "padding_bottom", "border_color",
               "border_width", "border_radius")
# Paired tags that need closing (excludes void and optional-close tags).
_PAIR_TAGS = ("section", "div", "aside", "nav", "main", "header", "footer",
              "article", "a", "ul", "ol", "button", "pre", "table", "span", "h1",
              "h2", "h3", "h4")


def get_file(e, path, theme_id=None):
    args = {"path": path}
    if theme_id:
        args["theme_id"] = str(theme_id)
    res = e.tool("get_theme_file", args)
    tf = res.get("themeFile", res) if isinstance(res, dict) else res
    return tf.get("content") if isinstance(tf, dict) else tf


def put_file(e, path, content, theme_id=None, content_type=None, clear_cache=True):
    args = {"path": path, "content": content}
    if theme_id:
        args["theme_id"] = str(theme_id)
    if content_type:
        args["content_type"] = content_type
    result = {"upsert": e.tool("upsert_theme_file", args)}
    if clear_cache:
        result["clear_cache"] = e.clear_cache()
    return result


def list_files(e, theme_id=None):
    args = {}
    if theme_id:
        args["theme_id"] = str(theme_id)
    r = e.tool("list_theme_files", args)
    return (r.get("themeFiles", r) if isinstance(r, dict) else r) or []


def installed(e, path, theme_id):
    """True when the theme already holds this file with non-empty content."""
    try:
        c = get_file(e, path, theme_id=theme_id)
    except SystemExit:
        return False
    return bool(c) and c != "None"


def lint_section(content):
    """[(severity, message)] for one section file. 'error' = the server will reject."""
    problems = []

    for css in re.findall(r"<style\b[^>]*>(.*?)</style>", content, re.S | re.I):
        # :root{} defines the tokens, and var()/rgba()/hsl() are allowed to carry
        # a literal — only a raw hex in body CSS is a violation.
        css_scan = re.sub(r":root\s*\{.*?\}", "", css, flags=re.S)
        css_scan = re.sub(r"var\([^)]*\)", "", css_scan)
        css_scan = re.sub(r"(?:rgba?|hsla?)\([^)]*\)", "", css_scan)
        m = re.search(r"#[0-9a-fA-F]{3,8}\b", css_scan)
        if m:
            problems.append(("error",
                f"hard-coded hex {m.group(0)} in body CSS (outside :root/var/rgba/hsl) "
                f"→ use var(--…)/hsl()/rgba()"))

    msch = re.search(r"\{%\s*schema\s*%\}(.*?)\{%\s*endschema\s*%\}", content, re.S | re.I)
    if msch:
        missing = [k for k in _STYLE_KEYS if f'"{k}"' not in msch.group(1)]
        if missing:
            problems.append(("error",
                f"schema is MISSING Style settings: {', '.join(missing)} "
                f"→ add the 'Style' header group and the canonical keys"))
    else:
        problems.append(("warn", "no {% schema %} found — does the section have settings?"))

    # Count real markup only: script/style/comments and Liquid tags are stripped
    # first, so a tag name inside a string does not read as an unclosed tag.
    markup = re.sub(r"<script\b.*?</script>", "", content, flags=re.S | re.I)
    markup = re.sub(r"<style\b.*?</style>", "", markup, flags=re.S | re.I)
    markup = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
    markup = re.sub(r"\{%.*?%\}", "", markup, flags=re.S)
    markup = re.sub(r"\{\{.*?\}\}", "", markup, flags=re.S)
    for tag in _PAIR_TAGS:
        opens = len(re.findall(rf"<{tag}\b", markup))
        closes = len(re.findall(rf"</{tag}>", markup))
        if opens > closes:
            problems.append(("error",
                f"<{tag}> opened {opens} times but closed {closes} "
                f"→ {opens - closes} missing close tag(s)"))
    return problems


def install_sections(e, sections, theme_id, force=False, lint=True):
    """Upload {name: (path, content)} into the theme. Returns {path: (outcome, messages)}.

    Pre-lints locally, and reads each file back — the server answers a contract
    violation with a string rather than an error, so a write that "succeeded"
    still has to be confirmed.
    """
    results = {}
    for name, (path, content) in sections.items():
        exists = installed(e, path, theme_id)
        if exists and not force:
            results[path] = ("skip (exists)", [])
            continue
        errs = [m for sev, m in lint_section(content) if sev == "error"] if lint else []
        if errs:
            results[path] = ("REJECTED (pre-lint)", errs)
            continue
        res = e.tool("upsert_theme_file",
                     {"path": path, "content": content, "theme_id": str(theme_id)})
        if isinstance(res, str) and ("rejected" in res or "violation" in res):
            results[path] = ("REJECTED", [res])
            continue
        e.clear_cache()
        persisted = installed(e, path, theme_id)
        results[path] = (("overwritten" if exists else "installed") if persisted
                         else "FAILED (not persisted)", [])
    return results
