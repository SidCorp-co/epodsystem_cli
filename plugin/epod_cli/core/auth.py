"""Credential and project resolution.

One global install serves every epod project, so the token is resolved from the
CWD upward — never from the script's own location. Each project's `.mcp.json`
carries its own store's token; resolving from anywhere but the checkout you are
standing in publishes to the wrong store.
"""
import json
import os

CONFIG_DIR = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "epod")
KNOWN_PROJECTS_PATH = os.path.join(CONFIG_DIR, "known-projects.json")


def _epod_auth(path):
    """Bearer token in <path>'s epodsystem server, or None if it serves another store."""
    try:
        cfg = json.load(open(path, encoding="utf-8"))
        headers = cfg["mcpServers"]["epodsystem"]["headers"]
    except (ValueError, KeyError, TypeError, OSError):
        return None
    auth = headers.get("Authorization") or headers.get("authorization")
    if not auth:
        return None
    return auth.split(None, 1)[1] if auth.lower().startswith("bearer") else auth


def find_mcp_json():
    """Walk up from the CWD for a .mcp.json that carries an epodsystem token."""
    d = os.getcwd()
    without_epod = []
    while True:
        p = os.path.join(d, ".mcp.json")
        if os.path.isfile(p):
            if _epod_auth(p):
                return p
            without_epod.append(p)
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    raise SystemExit(_no_project_message(without_epod))


def project_root():
    """The epod project directory, or None when the token came from the environment."""
    if os.environ.get("EPOD_TOKEN"):
        return None
    return os.path.dirname(find_mcp_json())


def _no_project_message(without_epod):
    lines = [f"No epod project above {os.getcwd()}."]
    if without_epod:
        lines.append("Found .mcp.json without an mcpServers.epodsystem token:")
        lines += [f"  {p}" for p in without_epod]
    lines.append("cd into an epod project, or set EPOD_TOKEN=<token>.")
    known = [p for p in _known_projects() if os.path.isfile(os.path.join(p, ".mcp.json"))]
    if known:
        lines.append("epod projects used before:")
        lines += [f"  {p}" for p in known]
    return "\n".join(lines)


def _known_projects():
    try:
        return json.load(open(KNOWN_PROJECTS_PATH, encoding="utf-8"))["projects"]
    except (ValueError, KeyError, TypeError, OSError):
        return []


def _remember_project(root):
    """Record the project root so a later refusal can name where the tokens live."""
    known = _known_projects()
    if root in known:
        return
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(KNOWN_PROJECTS_PATH, "w", encoding="utf-8") as f:
            json.dump({"projects": sorted(known + [root])}, f, indent=1)
    except OSError:
        pass


def load_token():
    if os.environ.get("EPOD_TOKEN"):
        return os.environ["EPOD_TOKEN"]
    path = find_mcp_json()
    _remember_project(os.path.dirname(path))
    return _epod_auth(path)
