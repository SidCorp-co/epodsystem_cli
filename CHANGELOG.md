# Changelog

## 2.1.0

A second pack: `epod vi`, natural Vietnamese for the documentation the docs pack
publishes. `epod docs build` was shipping Vietnamese a model had written in
passing — valid, published, and obviously not written by a Vietnamese person.
Nobody reviewing the build reads Vietnamese, so nothing caught it.

- `packs/vi/`: `lint` (free, offline), `doc`, `review`, `i18n`, `translate`,
  `doctor`. Stdlib only, its own gateway client, no `requests` and no store
  token — `main()` dispatches `vi` before `Epod()` is built, so it works in a
  checkout with no `.mcp.json`. It is the one pack handler that ignores `e`.
- `packs/vi/prompts.py` is the actual product: a written Vietnamese style
  contract — xưng hô, bare imperative UI verbs, the calques to delete, which
  technical terms stay in English — versioned with the code.
- `packs/vi/lint.py` parses its patterns out of that contract at import time
  rather than restating them. A second hand-maintained list would drift, and the
  day the two disagreed the linter would be wrong in exactly the cases it exists
  for. 17 phrase rules today, plus passive `được X bởi Y`, `sự/việc + verb`
  nominalization, and per-file `vui lòng` / plural-marker density.
- Placeholder gate on every translated string (`{{name}}`, `%1$s`, `%(name)s`,
  ICU plurals, HTML tags): a string that loses or renames one is retried once,
  then left in English and reported. Exit code 2 means written-but-refused.
- CTA discipline: a bare English CTA that comes back with an object (`Save` →
  `Lưu khách hàng`) is refused on translation and reported by `i18n --check`,
  which also names the per-screen action keys one shared `common.save` covers.
- `.epod.json` gains a `vi` block — `register`, `region`, `glossary`, `ignore`.
  The gateway key is deliberately not read from it: that file is committed. It
  comes from `MUSETOOLS_API_KEY` or `~/.config/vi-natural/config.json`.
- `DOC_CONTEXT` no longer hard-codes `bạn`. Documentation tone was overriding the
  register, so a `trang-trong` project got `bạn` in its docs and `quý khách`
  everywhere else.
- New skill `epod-vi`; `epod-docs` gains the Vietnamese step in its workflow and
  a trap row for Vietnamese that reads machine-translated.

## 2.0.2

- `packs/docs/build.py`: a `.md` with no `# ` heading gets the slug as its hero
  `doc_type` again, as it did in 1.x. The 2.0.0 rewrite left the badge empty.
- `packs/docs/bootstrap.py`: `install` was binding a store context it never read.

## 2.0.1

A concision pass over 2.0.0. No behaviour change.

- `packs/docs/build.py`: three functions collapsed into one. Two of them returned
  tuples and were each called once, and `hero_defaults()` was read twice per run.
- `resources/themes.py`: `install_sections` returns one shape for every outcome
  — `(outcome, messages)` — so the caller no longer branches on `isinstance`.
- `packs/docs/bootstrap.py`: `_store(e)` replaces five hand-written
  `context(e)` + `resolve_theme_id(ctx)` pairs.
- `packs/docs/nav.py`: `label_for` was rebuilding the merged label table a second
  time through `doc_code`; it now passes the one it already has.
- Dropped `HEADER_MENU_HANDLE`, a constant nothing read.
- Trimmed docstrings that restated the README or the skills: the `.epod.json`
  example lived in three places, and the md2doc-version trap in two.
- `epod theme lint` declares `local=True` on its parser instead of the dispatcher
  inferring offline-ness from a missing attribute.

## 2.0.0

The CLI was a documentation-site builder with a store underneath it. It is now a CLI for the
epod platform, with documentation sites as its first pack. The command surface changed to
match, and the old names are gone rather than aliased — see the mapping below.

### Structure

- `epod_cli/` is a package at the plugin root, replacing `skills/epod/scripts/`. Three layers:
  `core/` (transport, auth, store context, project config), `resources/` (a verb on an epod
  noun, no use case), `packs/` (a workflow owning its policy and assets). A pack may import
  the layers below it; neither lower layer may import a pack.
- The design-contract linter moved out of the docs bootstrapper into `resources/themes.py`,
  where any pack shipping a `.liquid` section can reach it, and is now exposed as
  `epod theme lint` — offline, no token.
- Doc-block knowledge (`doc_blocks`, `find_block`) moved off the transport class into
  `packs/docs/blocks.py`.
- One skill became two: `epod` (orientation, resources, rules) and `epod-docs` (the docs
  workflow and its traps), so a task pays only for the pack it uses.

### Project data moved out of the tool

`epod.py` hard-coded one project's data while telling its reader never to do that. All of it
now comes from an optional `.epod.json` beside the project's `.mcp.json`:

- `docs.links` replaces the built-in `DOC_LINK_MAP`. **Behaviour change:** a project with no
  `.epod.json` no longer rewrites `[…](02-SRS.md)` to `/pages/srs`, in either direction.
- `docs.hero` replaces the `--heading` and `--mark` defaults, which named a specific project.
  The flags still win when passed.
- `docs.labels` **extends** the built-in document-type label table — those are generic
  document types, so they stay in the pack. Nobody edits library code to add a label now.

Also removed: an epilog naming specific page ids, a theme id in `--theme` help text, and a
storefront domain in a verify hint.

### New

- `epod schema introspect|liquid|tools` — the GraphQL types, what a theme can read at
  runtime, and all 77 server tools. This is the surface a new pack is written against.
- `epod theme list|lint`, `epod menu list|get`, `epod paths`.

### Command mapping

| 1.x | 2.0 |
|---|---|
| `epod list` | `epod page list` |
| `epod get\|put\|create\|publish` | `epod page get\|put\|create\|publish` |
| `epod fix-mojibake <id>` | `epod page fix-mojibake <id>` |
| `epod clear-cache` | `epod cache clear` |
| `epod get-theme\|put-theme <path>` | `epod theme get\|put <path>` |
| `epod build-doc f.md --slug s` | `epod docs build f.md --slug s` |
| `epod sync-md <id> f.md` | `epod docs sync <id> f.md` |
| `epod list-blocks <id>` | `epod docs blocks <id>` |
| `epod anchors <id>` | `epod docs anchors <id>` |
| `epod get-block\|put-block` | `epod docs get-block\|put-block` |
| `epod store check\|doctor\|install\|verify\|home` | `epod docs check\|doctor\|install\|verify\|home` |
| `epod store sync-nav` | `epod docs nav` |
| `epod skill-root` | `epod paths` (reports every directory, not one) |
| `epod context`, `epod query` | unchanged |

Help text is English throughout; 1.x mixed English and Vietnamese. User content is untouched —
every write still sends UTF-8 bytes, which is what keeps Vietnamese intact.

## 1.1.0

- One global `epod` command, its token read from the project it stands in, replacing the
  per-script `epod-store-init` and `epod-skill-root` binaries.
- A `SessionStart` hook links `~/.local/bin/epod` so the command works outside Claude Code.

## 1.0.0

- The epod skill packaged as a Claude Code plugin, addressable by command name.
