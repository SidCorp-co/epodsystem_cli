# epod — Claude Code plugin for the epod documentation-site system

One global command for building documentation sites on epod (a Shopify-like CMS: pages made
of `sections_data`, a Liquid theme, a runtime nav menu), plus the skill that explains what
`--help` cannot.

```sh
epod context                     # which store am I on?
epod list                        # pages (id/slug/status)
epod build-doc file.md --slug x  # markdown → page, published
epod sync-md 883 file.md         # page → markdown, the other direction
epod store doctor                # is this store able to render a page at all?
epod store install               # upload the six bundled sections
epod store sync-nav              # rebuild the sidebar menu from published pages
epod skill-root                  # where the skill's references/ and assets/ live
```

`epod --help` lists every page and theme command; `epod store --help` the site-bootstrap
ones.

## Global command, project-scoped credential

The CLI is installed once for the machine, but it holds no credential of its own. Each epod
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
   it never falls back to a default store, because publishing docs to the wrong company is
   not a recoverable mistake.

`EPOD_MCP_URL`, `EPOD_STORE_DOMAIN` and `EPOD_THEME_ID` override the endpoint, storefront
domain and target theme when the context call cannot be trusted.

## Requirements

- Python 3 with [`requests`](https://pypi.org/project/requests/) — the only dependency
  (`md2doc` and the design linter are stdlib-only)
- `~/.local/bin` on `PATH`

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
changes on every update. The wrapper resolves its own symlink, so the bundled scripts and
`sections/*.liquid` are found wherever the checkout lives.

## Verify

```sh
epod store doctor --local   # pre-lints the six bundled sections, no network, no token
cd <an epod project> && epod context
```

## Layout

```text
LICENSE                           MIT
.claude-plugin/marketplace.json   the epodsystem-cli marketplace
plugin/
  .claude-plugin/plugin.json
  bin/epod                        the one command; resolves its own symlink
  hooks/hooks.json                SessionStart → link-cli.sh
  hooks/link-cli.sh               links ~/.local/bin/epod, idempotently
  skills/epod/
    SKILL.md                      workflow + traps
    references/internals.md       TOC/anchors, mermaid, color tokens, the index-template trap
    references/sections.md        the six sections and the linter's rules
    scripts/cli.py                dispatch: page commands, `store`, `skill-root`
    scripts/epod.py               page/theme CLI, MCP client, credential resolution
    scripts/store_init.py         store bootstrap + design-contract linter
    scripts/md2doc.py             markdown → doc blocks (imported by epod.py)
    assets/store-theme/sections/  the six Liquid sections
```

This repo is the source of truth for the skill. If a copy of it also exists as a project
skill under any `.claude/skills/epod`, delete that copy once the plugin is installed, or the
same skill loads twice under one name.

## License

MIT — see [LICENSE](LICENSE).
