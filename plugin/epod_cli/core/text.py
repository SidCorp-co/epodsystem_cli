"""String helpers shared by every resource and pack."""
import html
import re

MOJIBAKE_RE = re.compile(r"Ã.|á»|áº|Æ°|Ä[^\s]")


def slugify(s):
    """Match the slugify in sections/doc-layout.liquid, which derives anchor ids:
    lowercase -> [^a-z0-9À-ỹ]+ becomes '-' -> trim '-' -> cut to 60 chars."""
    s = html.unescape(s or "").lower()  # &amp; -> &, matching DOM textContent
    s = re.sub(r"[^a-z0-9À-ỹ]+", "-", s)
    s = s.strip("-")
    return s[:60]


def demojibake(s):
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def walk(obj, fn):
    if isinstance(obj, dict):
        return {k: walk(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk(x, fn) for x in obj]
    return fn(obj)
