---
name: epod
description: >-
  Build, publish and sync documentation sites on epod — a Shopify-like CMS of
  pages, Liquid theme sections and a runtime nav menu — with the bundled `epod`
  CLI. Invoke before touching an epod page, theme, nav or store.
version: 1.1.0
---

# Skill: epod

One command on PATH, installed globally by this plugin: `epod` for pages, blocks and theme
files, `epod store` for whole-site bootstrap. It is global but **project-scoped**: the token
comes from the `.mcp.json` found by walking up from the current directory, so every command
acts on the store belonging to the checkout you are standing in. Bundled
`sections/*.liquid` are found next to the script, so any cwd inside the project works.

Orient first — the CLI is the source of truth for everything concrete:

```bash
epod context        # active org/store/theme id — run this to confirm which store you are on
epod list           # existing pages (id/slug/status)
epod --help         # page/theme commands + the groups (then `epod <cmd> --help`)
epod store --help   # docs-site commands
```

Two failures that are about the environment, not the store:

- `epod: command not found` — the plugin is installed but the CLI was never linked. Ask the
  user to run `ln -sf <plugin>/bin/epod ~/.local/bin/epod`; never work around it by hunting
  for the .py files.
- `No epod project above <cwd>` — you are outside every epod checkout, or this project's
  `.mcp.json` has no `mcpServers.epodsystem`. `cd` into the project; the message lists the
  epod projects used before. Never borrow another project's token to make a command run.

Rules: never hard-code id/slug/theme/domain — read them live. Missing `requests` → ask the
user to install, don't self-install. Don't curl internal endpoints (go-backend:8080); go via CLI.

## Workflow

- **Content is source-of-truth on epod, .md syncs after.** New page: `epod build-doc file.md --slug <slug>`.
  Edit existing: on epod (`epod get-block` / `epod put-block`), then `epod sync-md <id> file.md` back to .md.
  Don't re-`build-doc` an existing page — it loses manual edits and resets anchors.
- **Stand up a docs site (fresh store):** `epod store doctor` → `install` → `epod build-doc` each
  doc → `epod store sync-nav` → `home` → browser-verify. Each command self-documents via `--help`.
- **After `sync-md`, always `git diff` the .md.** md2doc preserves `###` levels and list blocks
  via `data-md-level`, but only for HTML built by the *current* md2doc — a page last written by
  an older version round-trips back with headings demoted and lists split into loose paragraphs.
  Fix: `build-doc` that page once to refresh its HTML, then sync. Revert the bad .md, don't hand-patch.

## Traps (most are now CLI-handled — run the command)

| Trap | What happens | Handling |
|---|---|---|
| **Empty store → BLANK page** | fresh store has no section templates; publish "succeeds", curl 200, but page renders only header/footer | `epod store doctor` / `verify <slug>` detect it; `install` fixes it |
| **Design-contract linter** | `put-theme` rejects hard-coded hex, missing Style group, or unclosed tag | `epod store install` pre-lints locally; `doctor --local` runs it standalone. Hex ok in `:root{}`/`var(--x,#fff)`/`rgba()`/`hsl()`; literal hex to display → put in page content, not a section |
| **Must publish + verify** | live shows only the *published* build; clear-cache ≠ publish; curl can't see JS-injected content | write cmds auto-publish; `verify` warns on 404/blank; REAL check = `browser_navigate`+`browser_evaluate` the DOM |
| **Nav / adding pages** | editing every page's nav by hand | nav is a runtime **menu**; add a page → `epod store sync-nav`, zero edits to old pages |
| **Vietnamese mojibake** | `Ká»ch báº£n` if HTTP is hand-rolled | CLI sends UTF-8; fix with `epod fix-mojibake <id>` (eyeball — can false-positive) |
| **Markdown `>` blockquotes are DROPPED** | `md2doc` strips `>` lines as editor notes (the doc-header one becomes the hero subheading), so a mid-document callout vanishes silently — content loss a 200 won't reveal | don't use `>` for body callouts; lead the paragraph with `**⚠ Label.**` instead |
| **Inline code in a table HEADER is invisible** | `` `code` `` inside a `\| th \|` renders white-on-`#f5f7fb` against the blue header → unreadable | use `**bold**` in header cells; keep backticks for body cells |
| **ASCII diagram wider than ~62 chars overflows** | content column is 525px; a wide ``` block scrolls sideways instead of wrapping. No content is lost and `verify` stays green, but a two-column diagram meant for side-by-side comparison no longer compares | **prefer `<pre class="mermaid">` over ASCII art** — it reflows to the column and never clips. If ASCII is unavoidable, keep lines ≤62 chars and check with `browser_evaluate` comparing `scrollWidth` vs `clientWidth` on every `pre` |
| **Sidebar label falls back to the long page title** | `sync-nav` maps a doc code → short English label via `_DOC_LABELS` in `store_init.py`; an unlisted slug (e.g. `business-dataflow`) shows the full Vietnamese title, truncated mid-word | add the compressed slug to `_DOC_LABELS` (`$(epod skill-root)/scripts/store_init.py`), then re-run `sync-nav` (it relabels in place) |

Browser stuck ("already in use"): `pkill -f chrome-for-testing && rm -f ~/.cache/ms-playwright-mcp/*/Singleton*`.

## Deeper knowledge (read only when you hit that area)

Both live beside this file; `epod skill-root` prints that directory, so read them with
`cat "$(epod skill-root)/references/internals.md"`.

- `references/internals.md` — TOC/anchor generation, mermaid, color-token injection, the data
  model, why nav must be menu-driven, the home-page/index-template trap.
- `references/sections.md` — the 6 bundled sections (roles, shared `:root` tokens, RS origin, linter rules).
- Project memory/docs, if any, for this store's real ids/slugs/colors. This skill is shared logic only.
