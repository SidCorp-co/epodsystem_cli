---
name: epod
description: >-
  Drive an epod store from the terminal with the `epod` CLI — pages, theme files,
  menus, GraphQL and schema introspection. Start here for any epod task; the
  epod-docs skill covers documentation sites specifically.
---

# Skill: epod

`epod` is on PATH. It is global but **project-scoped**: the token comes from the `.mcp.json`
found by walking up from the current directory, and project data from a `.epod.json` beside
it, so every command acts on the store belonging to the checkout you are standing in.

Two axes. A **resource** is a verb on an epod noun and carries no use case. A **pack** is a
workflow that owns its own policy and assets.

```bash
epod context          # which store/org/theme am I on? run this first
epod --help           # the groups; then `epod <group> --help`
epod paths            # where the CLI, its bundled assets and the project config are

epod page   list|get|put|create|publish|fix-mojibake
epod theme  list|get|put|lint
epod menu   list|get
epod schema introspect|liquid|tools
epod query '<graphql>'
epod cache clear

epod docs   …         # the documentation-site pack → skill: epod-docs
epod vi     …         # natural Vietnamese for docs and locales → skill: epod-vi
                      #   (no token, no connection: local files + a text gateway)
```

## Rules

- **Never hard-code an id, slug, theme, domain or token** — read it live with `epod context`,
  `epod page list`, `epod menu get`. A number pasted from a previous session belongs to
  whichever store that session was on.
- **Project data goes in `.epod.json`**, beside the project's `.mcp.json` — never in the CLI
  and never in a flag you retype. `epod paths` reports whether one was found.
- **Every write publishes and clears the cache.** Live serves the *published* build, so a
  clear-cache is not a publish. `--no-publish` is for a draft you intend to inspect.
- **A 200 is not a render.** Section bodies are JS-injected, so `curl` sees a shell. A real
  check is `browser_navigate` then `browser_evaluate` against the DOM.
- **`epod schema` before writing anything new.** `introspect` reports the real GraphQL types
  and `liquid` reports what a theme can read at runtime — that is how the docs pack learned
  nav had to be menu-driven rather than a block per page. `epod schema tools` lists all 77
  server tools, which is the surface a new pack is built from.
- Missing `requests` → ask the user to install it; don't self-install. Don't curl internal
  endpoints (`go-backend:8080`) — go through the CLI.

## Two failures that are about the environment, not the store

- `epod: command not found` — inside a Claude Code session this cannot happen, the plugin's
  `bin/` is on PATH. In a user's own terminal it means the `SessionStart` hook has not run
  yet; `ln -sf <plugin>/bin/epod ~/.local/bin/epod` fixes it. Never work around it by hunting
  for the .py files.
- `No epod project above <cwd>` — you are outside every epod checkout, or this project's
  `.mcp.json` has no `mcpServers.epodsystem`. `cd` into the project; the message lists the
  epod projects used before. **Never borrow another project's token** to make a command run.

## Adding a use case

A pack is a directory under `epod_cli/packs/` plus one entry in `PACKS` in `epod_cli/cli.py`.
It may import `core/` and `resources/`; it owns its own policy, labels and `.liquid` assets.
Nothing in `core/` or `resources/` may import a pack. If a pack needs a resource verb that
does not exist yet, add it to `resources/` — don't call `e.tool()` from pack code.
