# epod — a CLI for the epod platform, packaged as a Claude Code plugin

`epod` drives an epod store from the terminal: a Shopify-like platform of CMS pages, a Liquid
theme, catalog and commerce, exposed over an MCP endpoint. Documentation sites are the first
**pack** built on it, not the whole of it.

```sh
epod context                            # which store am I on?
epod page list                          # pages (id/slug/status)
epod theme get sections/doc-layout.liquid
epod schema liquid                      # what a theme can read at runtime
epod docs build file.md --slug srs      # the docs pack: markdown → page, published
epod docs nav                           # rebuild the sidebar from published pages
```

`epod --help` lists the groups; `epod <group> --help` the verbs.

## Two axes

A **resource** is a verb on an epod noun and carries no use case — `page`, `theme`, `menu`,
`schema`. A **pack** is a workflow that owns its own policy and bundled assets — `docs`
builds documentation sites. The split is what makes a second use case cheap: it is a
directory under `epod_cli/packs/` and one entry in `PACKS`, with no change to the layers
below it.

```text
epod_cli/
  core/         transport, auth, store context, project config, text helpers
  resources/    pages · themes (+ the design-contract linter) · menus · schema
  packs/docs/   md2doc, doc blocks, build/sync, nav, bootstrap, sections/*.liquid
  cli.py        dispatch
```

A pack may import `core/` and `resources/`. Nothing in `core/` or `resources/` may import a
pack, and pack code does not call `e.tool()` directly — a missing verb is added to
`resources/` instead.

## Global command, project-scoped credential

The CLI is installed once for the machine and holds no credential of its own. Each epod
project's `.mcp.json` carries its own store's token, and `epod` resolves one by walking up
**from the current directory** — never from the script's own location. So the store you act
on is always the checkout you are standing in, and six projects with six different tokens
need no profiles, no login, and no duplicated secrets.

Resolution order:

1. `EPOD_TOKEN` in the environment, if set.
2. The nearest `.mcp.json` at or above the cwd that has an `mcpServers.epodsystem` bearer
   token. A `.mcp.json` without that server is skipped, not treated as a failure.
3. Nothing else. Outside every epod checkout the command refuses and names the projects it
   has resolved before (recorded, paths only, in `~/.config/epod/known-projects.json`) —
   it never falls back to a default store, because publishing to the wrong company is not a
   recoverable mistake.

`EPOD_MCP_URL`, `EPOD_STORE_DOMAIN` and `EPOD_THEME_ID` override the endpoint, storefront
domain and target theme when the context call cannot be trusted.

## Project data lives in the project

Nothing project-shaped belongs in this repo. A project that needs cross-doc links, extra
sidebar labels or hero defaults writes `.epod.json` beside its `.mcp.json`; every key is
optional, and `epod paths` reports which file was found.

```json
{
  "docs": {
    "links":  { "01-BRD.md": "brd", "02-SRS.md": "srs" },
    "labels": { "RUNBOOK": "Operations Runbook" },
    "hero":   { "heading": "Project name", "mark": "PN" }
  }
}
```

## Requirements

- Python 3 with [`requests`](https://pypi.org/project/requests/) — the only dependency
  (md2doc and the design linter are stdlib-only)
- `~/.local/bin` on `PATH`, for use outside Claude Code

## Install

```sh
git clone git@github.com:SidCorp-co/epodsystem_cli.git
claude plugin marketplace add ./epodsystem_cli
claude plugin install epod@epodsystem-cli
```

That is the whole install for Claude Code: the plugin's `bin/` is added to the Bash tool's
`PATH`, so `epod` resolves inside a session with no linking at all.

Your own terminal is a separate `PATH`. A `SessionStart` hook links `~/.local/bin/epod` to
the bundled CLI on the next session so the command works there too — hooks are where
`${CLAUDE_PLUGIN_ROOT}` is substituted, which is what lets the link point at the install
wherever it lives. The hook is idempotent, silent unless it changes something, and refuses
to touch `~/.local/bin/epod` if it is a real file rather than its own symlink. To skip the
hook, link it yourself from the clone:

```sh
ln -sf "$PWD/epodsystem_cli/plugin/bin/epod" ~/.local/bin/epod
```

Link the checkout, not the plugin cache: `claude plugin install` from a `directory`
marketplace points at the clone in place, whereas a cache path carries a version that
changes on every update. The wrapper resolves its own symlink, so the package and its
bundled `sections/*.liquid` are found wherever the checkout lives.

## Verify

```sh
epod theme lint plugin/epod_cli/packs/docs/sections/*.liquid   # no network, no token
epod docs doctor --local                                       # same, via the pack
cd <an epod project> && epod context
```

## Skills

Two, so a docs task does not pay for a catalog task and vice versa:

- `epod` — orientation, project scoping, the resource verbs, the rules that hold everywhere.
- `epod-docs` — the docs workflow, its traps, and `references/` for TOC/anchors, mermaid,
  colour tokens and the six bundled sections.

## Layout

```text
LICENSE                           MIT
CHANGELOG.md
.claude-plugin/marketplace.json   the epodsystem-cli marketplace
plugin/
  .claude-plugin/plugin.json
  bin/epod                        the one command; resolves its own symlink
  hooks/hooks.json                SessionStart → link-cli.sh
  hooks/link-cli.sh               links ~/.local/bin/epod, idempotently
  epod_cli/                       the package (core / resources / packs)
  skills/epod/SKILL.md
  skills/epod-docs/SKILL.md
  skills/epod-docs/references/    internals.md · sections.md
```

This repo is the source of truth for the skills. If a copy of either also exists as a project
skill under any `.claude/skills/`, delete that copy once the plugin is installed, or the same
skill loads twice under one name.

## License

MIT — see [LICENSE](LICENSE).
