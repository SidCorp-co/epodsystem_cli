> **Archived (2026-11-05).** This repository is no longer maintained. The epod CLI is now one
> binary built and served by the epod platform itself. Install it with
>
> ```sh
> curl -fsSL https://epodsystem.com/cli/install.sh | sh        # macOS, Linux
> irm https://epodsystem.com/cli/install.ps1 | iex             # Windows PowerShell
> ```
>
> then run `epod login`. `epod --help` lists what it does.

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
epod vi lint docs/02-SRS.vi.md          # the vi pack: does the Vietnamese read translated?
epod vi doc docs/02-SRS.md              # write it in natural Vietnamese instead
```

`epod --help` lists the groups; `epod <group> --help` the verbs.

## Two axes

A **resource** is a verb on an epod noun and carries no use case — `page`, `theme`, `menu`,
`schema`. A **pack** is a workflow that owns its own policy and bundled assets — `docs`
builds documentation sites, `vi` writes and audits the Vietnamese that goes into them. The
split is what makes a second use case cheap: it is a directory under `epod_cli/packs/` and
one entry in `PACKS`, with no change to the layers below it.

```text
epod_cli/
  core/         transport, auth, store context, project config, text helpers
  resources/    pages · themes (+ the design-contract linter) · menus · schema
  packs/docs/   md2doc, doc blocks, build/sync, nav, bootstrap, sections/*.liquid
  packs/vi/     the Vietnamese style contract, its gateway client, lint and CTA audits
  cli.py        dispatch
```

A pack may import `core/` and `resources/`. Nothing in `core/` or `resources/` may import a
pack, and pack code does not call `e.tool()` directly — a missing verb is added to
`resources/` instead. `vi` is the one pack that imports neither transport nor resources: it
talks to a text gateway rather than the store, so `main()` dispatches it before the client is
built and it runs in a checkout with no `.mcp.json`.

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

## Vietnamese that does not read translated

A model asked in passing for Vietnamese returns Vietnamese that parses, publishes and reads
like a machine — `sự thay đổi của bạn đã được lưu lại một cách thành công`. On a docs site
nobody catches it, because nobody reviewing the build reads Vietnamese: the page is 200, the
JSON is valid, the tiếng Việt is just wrong. The `vi` pack exists to stop that.

```sh
epod vi install --key <gateway-key>          # once per machine, before the rest
epod vi lint docs/*.vi.md locales/vi.json   # free, offline, CI-safe with --strict
epod vi doc docs/02-SRS.md                  # → 02-SRS.vi.md, code and links untouched
epod vi review docs/02-SRS.vi.md            # where existing Vietnamese reads translated
epod vi i18n locales/en.json                # → vi.json, missing keys only
epod vi i18n locales/en.json --check        # offline: placeholders + CTA discipline
```

Four things make it more than a `curl` wrapper:

1. **A written style contract** (`packs/vi/prompts.py`) — xưng hô rules, bare imperative UI
   verbs, the specific calques to delete, which technical terms stay in English. It is
   versioned with the code, so a bad translation is a diff you can argue with rather than a
   prompt someone improvised.
2. **An offline linter derived from that same contract, and an honest account of what it
   is for.** `epod vi lint` parses its patterns out of `STYLE` at import time, so the rules
   the translator obeys and the rules the linter enforces cannot drift. It is a tripwire for
   named phrases, not a judge of Vietnamese: a sentence can pass it clean and still be one
   no reader parses on the first try. That question goes to `epod vi review`, which asks the
   model — and it is the question that matters.
3. **A voice you choose.** `register`: `san-pham` (bạn), `trang-trong` (quý khách),
   `than-mat`. Vietnamese encodes the relationship in the pronouns, and picking wrong is the
   most visible localization error there is.
4. **A verification gate.** Placeholders — `{{name}}`, `%1$s`, `%(name)s`, ICU plurals, HTML
   tags — are compared source against translation; a string that loses one is retried once,
   then left in English and reported. And a bare English CTA that comes back with an object
   (`Save` → `Lưu khách hàng`) is refused, so one `Lưu` keeps working on every form.

Project voice and vocabulary go in `.epod.json` under `vi`; the gateway key does **not** —
that file is committed. `epod vi install` writes it to `~/.config/vi-natural/config.json`
at 0600, or set `MUSETOOLS_API_KEY`. `epod vi doctor` prints what resolved.

## Requirements

- Python 3 with [`requests`](https://pypi.org/project/requests/) — the only dependency
  (md2doc, the design linter and the whole `vi` pack are stdlib-only)
- `~/.local/bin` on `PATH`, for use outside Claude Code

## Install

```sh
git clone git@github.com:SidCorp-co/epodsystem_cli.git
claude plugin marketplace add ./epodsystem_cli
claude plugin install epod@epodsystem-cli
```

That is the whole install for Claude Code: the plugin's `bin/` is added to the Bash tool's
`PATH`, so `epod` resolves inside a session with no linking at all.

One group needs a credential of its own. `epod vi` talks to a text gateway rather than to
the store, so no `.mcp.json` can supply its key:

```sh
epod vi install --key <gateway-key>     # verifies against the gateway, then writes 0600
epod vi doctor                          # confirms what resolved
```

Every other group works without it, so this is a notice at install time rather than a
failure. The key goes to `~/.config/vi-natural/config.json` — machine-level, because it
belongs to no project, and never to `.epod.json`, which is committed.

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
epod vi lint <any .vi.md>                                      # same, via the vi pack
cd <an epod project> && epod context
```

## Skills

Three, so a docs task does not pay for a catalog task and vice versa:

- `epod` — orientation, project scoping, the resource verbs, the rules that hold everywhere.
- `epod-docs` — the docs workflow, its traps, and `references/` for TOC/anchors, mermaid,
  colour tokens and the six bundled sections.
- `epod-vi` — when Vietnamese is about to be written, translated or reviewed. Its first rule
  is that the model does not write the Vietnamese itself.

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
  skills/epod-vi/SKILL.md
```

This repo is the source of truth for the skills. If a copy of either also exists as a project
skill under any `.claude/skills/`, delete that copy once the plugin is installed, or the same
skill loads twice under one name.

## License

MIT — see [LICENSE](LICENSE).
