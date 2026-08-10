# epod — Claude Code plugin for the epod documentation-site system

A skill plus two CLIs for building documentation sites on epod (a Shopify-like CMS: pages
made of `sections_data`, a Liquid theme, a runtime nav menu).

- `epod` — pages and blocks: `context`, `list`, `build-doc` (.md → page), `sync-md`
  (page → .md), `get-block` / `put-block`, `publish`, `get-theme` / `put-theme`,
  `fix-mojibake`.
- `epod-store-init` — whole-site bootstrap: `doctor`, `install` (upload the six bundled
  sections), `sync-nav`, `home`, `verify <slug>`.
- The `epod` skill — the part `--help` cannot tell you: runtime TOC/anchor generation, the
  empty-store BLANK-render trap, the design-contract linter, why nav must be menu-driven,
  and the markdown constructs that silently vanish.

Nothing about a store, theme, domain, or page id is hard-coded. Everything is resolved live
from the API, so one install serves every epod project on the machine.

## Requirements

- Python 3 with [`requests`](https://pypi.org/project/requests/) (the only dependency;
  `md2doc` and the linter are stdlib-only)
- A project holding an `.mcp.json` with an epodsystem token, or `EPOD_TOKEN` in the
  environment

## Install

```sh
claude plugin marketplace add /run/media/thanh/New/ai-project/epod-plugin
claude plugin install epod@epod-local
```

Then link the two commands onto `PATH` — the skill calls them by bare name, because
`${CLAUDE_PLUGIN_ROOT}` is substituted only in hook and MCP commands, not exported to the
shell a skill runs in:

```sh
ln -sf /run/media/thanh/New/ai-project/epod-plugin/plugin/bin/epod           ~/.local/bin/epod
ln -sf /run/media/thanh/New/ai-project/epod-plugin/plugin/bin/epod-store-init ~/.local/bin/epod-store-init
ln -sf /run/media/thanh/New/ai-project/epod-plugin/plugin/bin/epod-skill-root ~/.local/bin/epod-skill-root
```

Link the checkout, not the install cache: `claude plugin install` from a `directory`
marketplace points at this repo in place, but a cache path carries a version number that
changes on every update. The wrappers resolve their own symlink, so they find the bundled
scripts and `sections/*.liquid` wherever the checkout lives.

`epod-skill-root` prints the skill directory; the skill uses it to read its own
`references/*.md`.

## Verify

```sh
epod-store-init doctor --local   # pre-lints the six bundled sections, no network
epod context                     # needs a token: prints active org/store/theme id
```

## Layout

```text
.claude-plugin/marketplace.json   the epod-local marketplace
plugin/
  .claude-plugin/plugin.json
  bin/{epod,epod-store-init,epod-skill-root}
  skills/epod/
    SKILL.md                      workflow + traps
    references/internals.md       TOC/anchors, mermaid, color tokens, the index-template trap
    references/sections.md        the six sections and the linter's rules
    scripts/epod.py               page/theme CLI + MCP client
    scripts/store_init.py         store bootstrap + design-contract linter
    scripts/md2doc.py             markdown → doc blocks (imported by epod.py)
    assets/store-theme/sections/  the six Liquid sections
```

This repo is the source of truth for the skill. It began as
`sid-trai-heo/.claude/skills/epod`; that copy should be deleted once the plugin is
installed, or the same skill loads twice under one name.

## License

MIT
