"""The vi pack: Vietnamese that reads like a Vietnamese product wrote it.

An LLM asked in passing to "write this in Vietnamese" returns Vietnamese that
parses, publishes, and reads like a machine — `sự thay đổi của bạn đã được lưu
lại một cách thành công`. On a docs site nobody catches it, because nobody
reviewing the build reads Vietnamese. So this pack does not ask a model to
"translate nicely": it carries a written style contract (`prompts.py` — xưng hô,
bare imperative UI verbs, the exact calques to delete, which technical terms stay
in English), and it refuses any string that comes back with a damaged placeholder
or a button label that grew an object the English never had.

The pack is deliberately self-contained: stdlib only, its own gateway client, no
epod client and no store token. `epod vi` never opens a connection to the store —
`cli.main` dispatches it before `Epod()` is built, so it runs in a checkout with
no `.mcp.json` at all. Its handler is the one pack handler that ignores `e`.

Settings come from `.epod.json` → "vi", which is the right home for the
project-shaped half (register, region, glossary, ignore globs). The gateway key
is not project-shaped and `.epod.json` gets committed, so the key is read from
the environment or from `~/.config/vi-natural/config.json` and never from here.
"""
import os

from ...core import config as project_config
from .util import CliError, read_json

# Written by the standalone vi-natural CLI; read here so one key serves both.
USER_CONFIG = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    "vi-natural", "config.json",
)
GLOSSARY_FILE = ".vi-glossary.json"

DEFAULT_BASE_URL = "https://serp-api.musetools.com/v1"
DEFAULT_MODEL = "gm/gemini-3.5-flash"


def find_up(filename, start=None):
    current = os.path.abspath(start or os.getcwd())
    while True:
        candidate = os.path.join(current, filename)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


class Settings:
    """Flag → environment → `.epod.json` "vi" → `~/.config/vi-natural/config.json`.

    The project file wins over the user file because a project's voice is a
    property of the project; the flag wins over both because it is a decision
    someone is making right now.
    """

    def __init__(self, opts=None):
        self.opts = opts or {}
        self.project = project_config.section("vi")
        self.user = read_json(USER_CONFIG, {}) or {}
        self.glossary_path = None
        self.glossary_meta = {}
        self._terms = None

    def _pick(self, key, env_names, default=None):
        if self.opts.get(key):
            return self.opts[key]
        for name in env_names:
            if os.environ.get(name):
                return os.environ[name]
        if self.project.get(key):
            return self.project[key]
        if self.user.get(key):
            return self.user[key]
        return default

    @property
    def base_url(self):
        return self._pick("base_url", ("VI_NATURAL_BASE_URL", "MUSETOOLS_BASE_URL"),
                          DEFAULT_BASE_URL).rstrip("/")

    @property
    def api_key(self):
        # Deliberately not read from `.epod.json`: that file lives in the repo.
        key = (self.opts.get("api_key")
               or os.environ.get("MUSETOOLS_API_KEY")
               or os.environ.get("VI_NATURAL_API_KEY")
               or self.user.get("api_key"))
        if not key:
            raise CliError(
                "no gateway key configured.\n"
                "  export MUSETOOLS_API_KEY=<key>\n"
                "  or put it in %s (chmod 600)\n"
                "  it does not belong in .epod.json — that file is committed" % USER_CONFIG)
        return key

    @property
    def model(self):
        return self._pick("model", ("VI_NATURAL_MODEL",), DEFAULT_MODEL)

    def glossary(self):
        """Project terms that outrank the built-in style rules.

        `.epod.json` → vi.glossary is the project's own vocabulary; a
        `.vi-glossary.json` found above the CWD layers on top, so a docs
        subtree can pin a term the whole project does not. A `null` value
        means "leave this word in English".
        """
        if self._terms is not None:
            return self._terms
        if self.opts.get("no_glossary"):
            self._terms = {}
            return self._terms
        terms = dict(self.project.get("glossary") or {})
        path = self.opts.get("glossary") or find_up(GLOSSARY_FILE)
        if path:
            data = read_json(path, {}) or {}
            if not isinstance(data, dict):
                raise CliError("%s must be a JSON object of term -> translation" % path)
            self.glossary_path = path
            self.glossary_meta = {k: v for k, v in data.items() if k.startswith("_")}
            terms.update({k: v for k, v in data.items() if not k.startswith("_")})
        self._terms = terms
        return terms

    def register(self):
        """Which voice to write in. `san-pham` unless the project says otherwise."""
        self.glossary()
        return (self.opts.get("register")
                or os.environ.get("VI_NATURAL_REGISTER")
                or self.glossary_meta.get("_register")
                or self.project.get("register")
                or self.user.get("register")
                or "san-pham")

    def region(self):
        self.glossary()
        return (self.opts.get("region")
                or os.environ.get("VI_NATURAL_REGION")
                or self.glossary_meta.get("_region")
                or self.project.get("region")
                or self.user.get("region"))

    def ignore_patterns(self):
        """Key globs whose placeholder check is a known false alarm.

        A string that talks *about* syntax — "A { is never closed by a }" —
        parses as an interpolation named `is`. Rather than weaken detection for
        every catalog, a project names the handful of keys that are prose.
        """
        self.glossary()
        raw = self.opts.get("ignore")
        if isinstance(raw, str):
            raw = [part.strip() for part in raw.split(",") if part.strip()]
        raw = raw or self.glossary_meta.get("_ignore") or self.project.get("ignore")
        if isinstance(raw, str):
            raw = [raw]
        return list(raw or [])
