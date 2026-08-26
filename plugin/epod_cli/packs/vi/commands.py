"""`epod vi` — the parser and the six verbs. No store client, no token.

Ordering note for anyone extending this: `lint` is free and offline, `review`
costs one round trip per batch and `doc`/`i18n` cost one per batch of strings.
Reach for the cheap one first — most machine-translated Vietnamese fails `lint`
without anyone having to ask a model.
"""
import fnmatch
import json
import os
import sys

from . import (DEFAULT_BASE_URL, DEFAULT_EFFORT, DEFAULT_MODEL, EFFORTS,
               EFFORT_BY_VERB, Settings, save)
from . import cta, doc as doc_mod, engine, lint, locale, placeholders, prompts
from .client import Client
from .util import CliError, chunk_items, err, parse_json_object, read_json, write_json

REGISTERS = ["san-pham", "trang-trong", "than-mat"]


def add_parser(sub):
    p = sub.add_parser("vi", help="natural Vietnamese for docs and locale files "
                                  "(offline lint, model-backed translate/review)")
    s = p.add_subparsers(dest="sub", required=True, metavar="<verb>")

    def shared(parser, register=True):
        parser.add_argument("--model", help="gateway model id (default %s)" % DEFAULT_MODEL)
        parser.add_argument("--effort", choices=EFFORTS,
                            help="reasoning effort (default %s, %s for review)"
                                 % (DEFAULT_EFFORT, EFFORT_BY_VERB["review"]))
        parser.add_argument("--base-url", dest="base_url", help="gateway base url")
        parser.add_argument("--temperature", type=float, default=0.3)
        if register:
            parser.add_argument("--register", choices=REGISTERS,
                                help="voice: san-pham = product default, trang-trong = "
                                     "formal commerce/legal, than-mat = warm marketing")
            parser.add_argument("--region", choices=["bac", "nam"],
                                help="regional vocabulary: bac = northern, nam = southern")
        parser.add_argument("--glossary", help="path to a term glossary JSON")
        parser.add_argument("--no-glossary", action="store_true",
                            help="ignore .vi-glossary.json even if one is found")
        parser.add_argument("--ignore", help="comma-separated key globs exempt from the "
                                             "placeholder check")
        parser.add_argument("-v", "--verbose", action="store_true")
        return parser

    ins = s.add_parser("install", aliases=["login"],
                       help="store the gateway endpoint and key (0600) — do this first")
    ins.add_argument("--key", help="gateway API key; prompted for when omitted")
    ins.add_argument("--base-url", dest="base_url",
                     help="gateway base url (default %s)" % DEFAULT_BASE_URL)
    ins.add_argument("--model", help="default model (default %s)" % DEFAULT_MODEL)
    ins.add_argument("--effort", choices=EFFORTS,
                     help="pin one reasoning effort for every verb; by default\neach verb picks its own")
    ins.add_argument("--no-verify", action="store_true",
                     help="save without asking the gateway whether the key works")

    ln = s.add_parser("lint", help="free, offline: machine-translation tells in a .md or locale")
    ln.add_argument("files", nargs="+", help="Vietnamese .md or .json files")
    ln.add_argument("--strict", action="store_true", help="exit 1 when anything is found")

    d = shared(s.add_parser("doc", help="a .md becomes natural Vietnamese; code and links untouched"))
    d.add_argument("mdfile"); d.add_argument("-o", "--out", help="default: <name>.vi.md")
    d.add_argument("--dry-run", action="store_true", help="show what would be sent")

    r = shared(s.add_parser("review", help="ask the model where existing Vietnamese reads translated"))
    r.add_argument("source", help="a Vietnamese .json or .md")
    r.add_argument("--json", dest="as_json", action="store_true")
    r.add_argument("--fix", action="store_true", help="apply the rewrites (JSON only)")

    i = shared(s.add_parser("i18n", help="translate a locale JSON, missing keys only"))
    i.add_argument("source", help="source locale, e.g. locales/en.json")
    i.add_argument("-o", "--out", help="default: the sibling vi.json")
    i.add_argument("--overwrite", action="store_true", help="retranslate everything")
    i.add_argument("--keys", help="comma-separated key paths")
    i.add_argument("--prune", action="store_true", help="drop keys the source no longer has")
    i.add_argument("--check", action="store_true",
                   help="offline: missing keys, placeholder damage, CTA discipline")
    i.add_argument("--dry-run", action="store_true")

    t = shared(s.add_parser("translate", help="one string or stdin, straight to Vietnamese"))
    t.add_argument("text", nargs="*", help="omit to read stdin")
    t.add_argument("-f", "--file", help="read the text from a file")
    t.add_argument("--kind", choices=["ui", "doc", "prose"], default="ui")

    shared(s.add_parser("doctor", help="settings, gateway reachability, one live round trip"))


def run(e, a):
    """`e` is always None: this pack never touches the store. See the package docstring."""
    try:
        return VERBS[ALIASES.get(a.sub, a.sub)](a)
    except CliError as exc:
        err("epod vi: %s" % exc)
        return 1


# ------------------------------------------------------------------ plumbing
def settings(a):
    opts = {k: getattr(a, k, None) for k in
            ("model", "base_url", "effort", "glossary", "register", "region", "ignore")}
    opts["no_glossary"] = getattr(a, "no_glossary", False)
    # Which verb is running decides how hard the model should think when
    # nothing overrides it: see EFFORT_BY_VERB.
    opts["verb"] = ALIASES.get(getattr(a, "sub", None), getattr(a, "sub", None))
    cfg = Settings(opts)
    return cfg, Client(cfg, verbose=getattr(a, "verbose", False))


def matches_any(name, patterns):
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


# ------------------------------------------------------------------- verbs
def cmd_lint(a):
    dirty = lint.run(a.files)
    return 1 if (dirty and a.strict) else 0


def cmd_doc(a):
    with open(a.mdfile, encoding="utf-8") as handle:
        pieces = doc_mod.segment(handle.read())
    trails = doc_mod.heading_trails(pieces, root=os.path.basename(a.mdfile))
    slots, items, index_map, contexts = [], [], {}, {}
    for index, (kind, block) in enumerate(pieces):
        if kind != "text":
            continue
        key = str(len(items))
        index_map[key] = index
        # Where the block sits, so a paragraph is not translated out of its section.
        contexts[key] = trails.get(index, "")
        items.append((key, doc_mod.protect_inline(block, slots)))
    if not items:
        raise CliError("no translatable prose in %s" % a.mdfile)

    stem, ext = os.path.splitext(a.mdfile)
    out_path = a.out or stem + ".vi" + (ext or ".md")
    if a.dry_run:
        print("%d block(s) would become Vietnamese in %s" % (len(items), out_path))
        for _, block in items[:10]:
            print("  ---\n  " + block.replace("\n", "\n  "))
        return 0

    cfg, client = settings(a)
    glossary = cfg.glossary()
    err("translating %d block(s) with %s (%s)" % (len(items), cfg.model, cfg.register()))
    results, problems = engine.translate_items(
        client, items, kind="doc", task=prompts.DOC_TASK, glossary=glossary,
        temperature=a.temperature, verbose=a.verbose, verify=doc_mod.verify,
        register=cfg.register(), region=cfg.region(), contexts=contexts)

    # A block that failed verification keeps its English original, which is already
    # sitting in `pieces`; only the verified ones are replaced.
    out = list(pieces)
    for key, translated in results.items():
        out[index_map[key]] = ("text", doc_mod.restore_inline(translated, slots))
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write("".join(block for _, block in out))
    print("%s: %d block(s) translated, %d left in English (%s)"
          % (out_path, len(results), len(problems), client.usage_note()))
    for problem in problems:
        err("  block %s: %s" % (problem.key, problem.reason))
    print("next: epod docs build %s --slug <slug>" % out_path)
    return 2 if problems else 0


def cmd_review(a):
    cfg, client = settings(a)
    is_json = a.source.endswith(".json")
    if is_json:
        tree = read_json(a.source, {}) or {}
        entries = {locale.label(p): t for p, t in locale.flatten(tree) if t.strip()}
    else:
        with open(a.source, encoding="utf-8") as handle:
            pieces = doc_mod.segment(handle.read())
        entries = {str(i): b for i, (kind, b) in enumerate(pieces) if kind == "text"}
        # The heading above a paragraph is the key path a spec never had.
        contexts = doc_mod.heading_trails(pieces, root=os.path.basename(a.source))
        contexts = {str(i): t for i, t in contexts.items()}
    if not entries:
        raise CliError("nothing to review in %s" % a.source)

    system = prompts.system_prompt("ui" if is_json else "doc", cfg.glossary(),
                                   cfg.register(), cfg.region(),
                                   key_context=not is_json)
    findings = []
    for batch in chunk_items(list(entries.items()), engine.MAX_CHARS, engine.MAX_ITEMS):
        if is_json:
            body = dict(batch)
        else:
            body = {k: {"k": contexts.get(k, ""), "s": v} for k, v in batch}
        payload = json.dumps(body, ensure_ascii=False, indent=2)
        answer = parse_json_object(
            client.chat(system, "%s\n\n%s" % (prompts.REVIEW_TASK, payload), temperature=0.2))
        findings.extend(answer.get("findings") or [])
    findings = [f for f in findings if isinstance(f, dict) and f.get("key") in entries]

    if a.as_json:
        print(json.dumps({"file": a.source, "findings": findings},
                         ensure_ascii=False, indent=2))
    elif not findings:
        print("%s: reads naturally, nothing to flag." % a.source)
    else:
        print("%s: %d finding(s)\n" % (a.source, len(findings)))
        for finding in findings:
            print("  %s — %s" % (finding.get("key"), finding.get("issue", "")))
            print("      now: %s" % finding.get("current", ""))
            print("      →    %s\n" % finding.get("suggested", ""))

    if a.fix and findings:
        if not is_json:
            raise CliError("--fix only supports JSON locale files")
        return apply_fixes(a.source, findings)
    if a.verbose:
        err(client.usage_note())
    return 1 if findings and not a.fix else 0


def apply_fixes(path, findings):
    tree = read_json(path, {}) or {}
    by_label = {locale.label(p): p for p, _ in locale.flatten(tree)}
    applied, refused = 0, []
    for finding in findings:
        key, suggested = finding.get("key"), finding.get("suggested")
        if key not in by_label or not isinstance(suggested, str) or not suggested.strip():
            continue
        problem = placeholders.diff(locale.get_path(tree, by_label[key]), suggested)
        if problem:
            refused.append("%s (%s)" % (key, problem))
            continue
        locale.set_path(tree, by_label[key], suggested)
        applied += 1
    write_json(path, tree)
    print("applied %d rewrite(s) to %s" % (applied, path))
    for name in refused:
        err("  refused, placeholders would change: %s" % name)
    return 0


def default_locale_target(source):
    directory, name = os.path.split(source)
    stem, ext = os.path.splitext(name)
    for pattern, replacement in (("en", "vi"), ("en-US", "vi-VN"), ("en_US", "vi_VN")):
        if stem == pattern:
            return os.path.join(directory, "vi" + ext)
        if stem.startswith(pattern + "."):
            return os.path.join(directory, stem.replace(pattern, replacement, 1) + ext)
    if os.sep + "en" + os.sep in source:
        return source.replace(os.sep + "en" + os.sep, os.sep + "vi" + os.sep, 1)
    return os.path.join(directory, stem + ".vi" + ext)


def reorder(source, target):
    """Give the target the source's key order; keep anything extra at the end."""
    if isinstance(source, dict) and isinstance(target, dict):
        out = {k: reorder(v, target[k]) for k, v in source.items() if k in target}
        for key, value in target.items():
            out.setdefault(key, value)
        return out
    return target


def cmd_i18n(a):
    source = locale.load_tree(a.source, read_json(a.source))
    out_path = a.out or default_locale_target(a.source)
    target = read_json(out_path, {}) or {}

    if a.check:
        cfg = Settings({"glossary": a.glossary, "no_glossary": a.no_glossary,
                        "ignore": a.ignore})
        return check_locale(source, target, a.source, out_path, cfg.ignore_patterns())

    keys = [k.strip() for k in a.keys.split(",")] if a.keys else None
    todo = locale.pending(source, target, overwrite=a.overwrite, keys=keys)
    if not todo:
        print("%s is already complete (%d strings)."
              % (out_path, len(locale.flatten(source))))
        return 0
    if a.dry_run:
        print("%d string(s) would be translated into %s:" % (len(todo), out_path))
        for path, text in todo[:40]:
            print("  %s = %s" % (locale.label(path), text))
        if len(todo) > 40:
            print("  ... and %d more" % (len(todo) - 40))
        return 0

    cfg, client = settings(a)
    ids = {str(i): path for i, (path, _) in enumerate(todo)}
    items = [(str(i), text) for i, (_, text) in enumerate(todo)]
    contexts = {str(i): locale.label(path) for i, (path, _) in enumerate(todo)}
    ignore = cfg.ignore_patterns()
    ignored = {i for i, name in contexts.items() if matches_any(name, ignore)}
    err("translating %d string(s) with %s (%s)" % (len(items), cfg.model, cfg.register()))
    results, problems = engine.translate_items(
        client, items, kind="ui", glossary=cfg.glossary(), temperature=a.temperature,
        verbose=a.verbose, register=cfg.register(), region=cfg.region(),
        contexts=contexts, skip_verify=ignored,
        bare_cta=bare_cta_keys(todo, contexts, ignore),
        cta_index=cta.generic_index(cta_pairs(source, target)))

    merged = locale.merge(target, {ids[i]: text for i, text in results.items()})
    if a.prune:
        merged = locale.prune(merged, source)
    write_json(out_path, reorder(source, merged))
    print("%s: %d translated, %d skipped (%s)"
          % (out_path, len(results), len(problems), client.usage_note()))
    if problems:
        err("\nleft untranslated — fix by hand or rerun:")
        for problem in problems:
            name = locale.label(ids[problem.key]) if problem.key in ids else problem.key
            err("  %s: %s\n      source: %s" % (name, problem.reason, problem.source))
        return 2
    return 0


def check_locale(source, target, source_path, target_path, ignore=()):
    """Offline audit: what is missing, what has broken placeholders, CTA discipline."""
    missing, damaged, skipped = [], [], 0
    for path, text in locale.flatten(source):
        existing = locale.get_path(target, path)
        if not isinstance(existing, str) or not existing.strip():
            missing.append(locale.label(path))
            continue
        if matches_any(locale.label(path), ignore):
            skipped += 1
            continue
        problem = placeholders.diff(text, existing)
        if problem:
            damaged.append((locale.label(path), problem, text, existing))
    extra = [locale.label(p) for p, _ in locale.flatten(target)
             if locale.get_path(source, p) is None]

    pairs = cta_pairs(source, target)
    index = cta.generic_index(pairs)
    inflated = [f for f in cta.inflated(pairs, index) if not matches_any(f["key"], ignore)]
    groups = cta.collapse_groups(pairs, index)

    print("%s vs %s: %d source strings, %d missing, %d with placeholder damage, %d stale%s"
          % (source_path, target_path, len(locale.flatten(source)), len(missing),
             len(damaged), len(extra), ", %d ignored" % skipped if skipped else ""))
    for name in missing[:50]:
        print("  missing: %s" % name)
    for name, problem, want, got in damaged:
        print("  damaged: %s — %s\n      en: %s\n      vi: %s" % (name, problem, want, got))
    for name in extra[:50]:
        print("  stale:   %s" % name)
    report_cta(inflated, groups)
    return 1 if (missing or damaged) else 0


def cta_pairs(source, target):
    """(key label, english, vietnamese) for every string that has both sides."""
    pairs = []
    for path, text in locale.flatten(source):
        existing = locale.get_path(target, path)
        if isinstance(existing, str) and existing.strip():
            pairs.append((locale.label(path), text, existing))
    return pairs


def report_cta(inflated, groups):
    """Style findings: reported, never a failure. A verbose button is not a bug."""
    if not inflated and not groups:
        return
    print("\ncall-to-action: %d inflated label(s), %d verb group(s) a shared key would cover"
          % (len(inflated), len(groups)))
    for finding in inflated:
        owner = " — %s already says it" % finding["existing"] if finding["existing"] else ""
        print("  inflated: %s\n      en: %s\n      vi: %s → %s%s"
              % (finding["key"], finding["en"], finding["vi"], finding["suggested"], owner))
    for group in groups:
        print('  collapse: %d keys say "%s <object>" — %s'
              % (len(group["members"]), group["bare"],
                 group["existing"] or "no generic key yet"))
        for member in group["members"][:4]:
            print("      %-44s %s" % (member["key"], member["vi"]))
        if len(group["members"]) > 4:
            print("      … and %d more" % (len(group["members"]) - 4))


def bare_cta_keys(todo, contexts, ignore):
    """Ids whose English source is a bare CTA, so the translation must be one too."""
    keys = set()
    for index, (_, text) in enumerate(todo):
        name = contexts[str(index)]
        if matches_any(name, ignore) or not cta.is_action_key(name):
            continue
        if cta.normalize(text) in cta.GENERIC:
            keys.add(str(index))
    return keys


def cmd_translate(a):
    if a.file:
        with open(a.file, encoding="utf-8") as handle:
            text = handle.read()
    elif a.text:
        text = " ".join(a.text)
    else:
        text = sys.stdin.read()
    if not text.strip():
        raise CliError("nothing to translate")

    cfg, client = settings(a)
    results, problems = engine.translate_items(
        client, [("1", text.strip())], kind=None if a.kind == "prose" else a.kind,
        glossary=cfg.glossary(), temperature=a.temperature, verbose=a.verbose,
        register=cfg.register(), region=cfg.region())
    if problems:
        for problem in problems:
            err("! " + problem.reason)
        return 1
    print(results["1"])
    if a.verbose:
        err(client.usage_note())
    return 0


def cmd_doctor(a):
    from . import USER_CONFIG
    from ...core import config as project_config

    cfg, client = settings(a)
    print("project file: %s" % (project_config.path() or "(no .epod.json found)"))
    print("user config : %s%s"
          % (USER_CONFIG, "" if os.path.exists(USER_CONFIG) else " (absent)"))
    print("base url    : %s" % cfg.base_url)
    print("model       : %s (effort %s)" % (cfg.model, cfg.effort))
    key = cfg.api_key
    print("api key     : %s…%s" % (key[:6], key[-4:]))
    glossary = cfg.glossary()
    print("glossary    : %d term(s)%s"
          % (len(glossary), " (+ %s)" % cfg.glossary_path if cfg.glossary_path else ""))
    print("voice       : %s%s"
          % (cfg.register(), ", region %s" % cfg.region() if cfg.region() else ""))
    print("lint rules  : %d phrase(s) from the style contract" % len(lint.PHRASES))
    ids = [m.get("id") for m in client.models()]
    print("gateway     : reachable, %d models" % len(ids))
    if cfg.model not in ids:
        err("! model %s is not in the gateway list" % cfg.model)
    results, problems = engine.translate_items(
        client, [("1", "Delete {{count}} items permanently?")], kind="ui",
        glossary=glossary, register=cfg.register(), region=cfg.region(),
        contexts={"1": "common.dialog.confirmDelete"})
    if problems:
        print("round trip  : FAILED — %s" % problems[0].reason)
        return 1
    print("round trip  : %s" % results["1"])
    print("usage       : %s" % client.usage_note())
    return 0


def cmd_install(a):
    """Make the pack usable: one machine-level credential for every checkout.

    The rest of the CLI holds no credential of its own — a store token belongs to
    a project and comes from its `.mcp.json`. The gateway key is the exception:
    it is not a property of any project, and `.epod.json` is committed, so it has
    nowhere to live but here.
    """
    key = a.key
    if not key:
        if not sys.stdin.isatty():
            raise CliError("no key given and nothing to prompt.\n"
                           "  epod vi install --key <key>")
        key = input("gateway API key: ").strip()
    if not key:
        raise CliError("no key given")

    values = {"api_key": key, "base_url": a.base_url, "model": a.model,
              "effort": a.effort}
    settings_now = Settings({k: v for k, v in values.items() if v})
    if not a.no_verify:
        # A key that does not work is worse than no key: every later command
        # fails at the point of use, with the gateway's error, not this one's.
        ids = [m.get("id") for m in Client(settings_now).models()]
        print("gateway     : %s — reachable, %d models" % (settings_now.base_url, len(ids)))
        if settings_now.model not in ids:
            err("! model %s is not in the gateway list" % settings_now.model)

    path = save(values)
    print("saved       : %s (0600)" % path)
    print("key         : %s…%s" % (key[:6], key[-4:]))
    print("model       : %s (effort %s)" % (settings_now.model, settings_now.effort))
    print("\nProject voice and vocabulary are separate, and belong in .epod.json:")
    print('  { "vi": { "register": "san-pham", "glossary": { "workspace": null } } }')
    print("\nnext: epod vi doctor")
    return 0


VERBS = {"install": cmd_install, "lint": cmd_lint, "doc": cmd_doc, "review": cmd_review, "i18n": cmd_i18n,
         "translate": cmd_translate, "doctor": cmd_doctor}

# `epod vi login` is what muscle memory types; argparse hands back the alias.
ALIASES = {"login": "install"}
