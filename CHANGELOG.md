# Changelog

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
