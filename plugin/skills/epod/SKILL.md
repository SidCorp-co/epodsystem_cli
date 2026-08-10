---
name: epod
description: >-
  Work with the epod documentation-site system (Shopify-like CMS + theme
  sections) via the CLI bundled in this skill. Use it BEFORE: creating/editing/
  publishing epod pages, changing colors/theme, syncing .md ⇄ epod, OR standing
  up a whole docs site (fresh store, sticky header/footer, home page, dynamic
  sidebar nav). Explains what `--help` does not: runtime TOC/anchors, mermaid,
  color tokens, Vietnamese mojibake, the design-contract linter, mandatory
  publish, the empty-store BLANK-render trap, dynamic menu-driven nav (add a
  page without editing old pages), the home page served by the index template.
  Many traps are handled by the CLI itself (pre-lint / verify / sync-nav) — run
  the command, don't memorize. Never hard-code project data — look it up live.
version: 1.0.0
---

# Skill: epod

Two commands, installed on PATH by this plugin: `epod` (pages, blocks, theme files) and
`epod-store-init` (whole-site bootstrap). Both auto-find the project's `.mcp.json` by walking
up from the current directory, and find their bundled `sections/*.liquid` next to themselves,
so they run from any cwd inside the project. Token from `.mcp.json` or `EPOD_TOKEN`.

Orient first — the CLI is the source of truth for everything concrete:

```bash
epod context               # active org/store/theme id
epod list                  # existing pages (id/slug/status)
epod --help                # all page/theme commands (then `epod <cmd> --help`)
epod-store-init --help     # docs-site commands
```

`epod: command not found` means the plugin is installed but its commands were never linked.
Ask the user to run the two `ln -s` lines in the plugin README; never work around it by
hunting for the .py files.

Rules: never hard-code id/slug/theme/domain — read them live. Missing `requests` → ask the
user to install, don't self-install. Don't curl internal endpoints (go-backend:8080); go via CLI.

## Workflow

- **Content is source-of-truth on epod, .md syncs after.** New page: `epod build-doc file.md --slug <slug>`.
  Edit existing: on epod (`epod get-block` / `epod put-block`), then `epod sync-md <id> file.md` back to .md.
  Don't re-`build-doc` an existing page — it loses manual edits and resets anchors.
- **Stand up a docs site (fresh store):** `epod-store-init doctor` → `install` → `epod build-doc` each
  doc → `epod-store-init sync-nav` → `home` → browser-verify. Each command self-documents via `--help`.
- **After `sync-md`, always `git diff` the .md.** md2doc preserves `###` levels and list blocks
  via `data-md-level`, but only for HTML built by the *current* md2doc — a page last written by
  an older version round-trips back with headings demoted and lists split into loose paragraphs.
  Fix: `build-doc` that page once to refresh its HTML, then sync. Revert the bad .md, don't hand-patch.

## Traps (most are now CLI-handled — run the command)

| Trap | What happens | Handling |
|---|---|---|
| **Empty store → BLANK page** | fresh store has no section templates; publish "succeeds", curl 200, but page renders only header/footer | `epod-store-init doctor` / `verify <slug>` detect it; `install` fixes it |
| **Design-contract linter** | `put-theme` rejects hard-coded hex, missing Style group, or unclosed tag | `epod-store-init install` pre-lints locally; `doctor --local` runs it standalone. Hex ok in `:root{}`/`var(--x,#fff)`/`rgba()`/`hsl()`; literal hex to display → put in page content, not a section |
| **Must publish + verify** | live shows only the *published* build; clear-cache ≠ publish; curl can't see JS-injected content | write cmds auto-publish; `verify` warns on 404/blank; REAL check = `browser_navigate`+`browser_evaluate` the DOM |
| **Nav / adding pages** | editing every page's nav by hand | nav is a runtime **menu**; add a page → `epod-store-init sync-nav`, zero edits to old pages |
| **Vietnamese mojibake** | `Ká»ch báº£n` if HTTP is hand-rolled | CLI sends UTF-8; fix with `epod fix-mojibake <id>` (eyeball — can false-positive) |
| **Markdown `>` blockquotes are DROPPED** | `md2doc` strips `>` lines as editor notes (the doc-header one becomes the hero subheading), so a mid-document callout vanishes silently — content loss a 200 won't reveal | don't use `>` for body callouts; lead the paragraph with `**⚠ Label.**` instead |
| **Inline code in a table HEADER is invisible** | `` `code` `` inside a `\| th \|` renders white-on-`#f5f7fb` against the blue header → unreadable | use `**bold**` in header cells; keep backticks for body cells |
| **ASCII diagram wider than ~62 chars overflows** | content column is 525px; a wide ``` block scrolls sideways instead of wrapping. No content is lost and `verify` stays green, but a two-column diagram meant for side-by-side comparison no longer compares | **prefer `<pre class="mermaid">` over ASCII art** — it reflows to the column and never clips. If ASCII is unavoidable, keep lines ≤62 chars and check with `browser_evaluate` comparing `scrollWidth` vs `clientWidth` on every `pre` |
| **Sidebar label falls back to the long page title** | `sync-nav` maps a doc code → short English label via `_DOC_LABELS` in `store_init.py`; an unlisted slug (e.g. `business-dataflow`) shows the full Vietnamese title, truncated mid-word | add the compressed slug to `_DOC_LABELS` (`$(epod-skill-root)/scripts/store_init.py`), then re-run `sync-nav` (it relabels in place) |

Browser stuck ("already in use"): `pkill -f chrome-for-testing && rm -f ~/.cache/ms-playwright-mcp/*/Singleton*`.

## Deeper knowledge (read only when you hit that area)

Both live beside this file; `epod-skill-root` prints that directory, so read them with
`cat "$(epod-skill-root)/references/internals.md"`.

- `references/internals.md` — TOC/anchor generation, mermaid, color-token injection, the data
  model, why nav must be menu-driven, the home-page/index-template trap.
- `references/sections.md` — the 6 bundled sections (roles, shared `:root` tokens, RS origin, linter rules).
- Project memory/docs, if any, for this store's real ids/slugs/colors. This skill is shared logic only.
