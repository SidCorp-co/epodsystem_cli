---
name: epod-docs
description: >-
  Build, publish and sync documentation sites on epod with `epod docs` — .md to
  page and back, menu-driven sidebar, home page, fresh-store bootstrap. Invoke
  before touching an epod doc page, its nav or its sections.
---

# Skill: epod-docs

The `docs` pack of the `epod` CLI. Read the `epod` skill first for project scoping and the
rules that hold for every pack; this file is the docs workflow and its traps.

```bash
epod docs --help                      # every verb, then `epod docs <verb> --help`
epod docs build file.md --slug <slug> # .md → page, created or updated, published
epod docs sync <page_id> file.md      # page → .md body, the other direction
epod docs nav                         # rebuild the sidebar from published pages
epod docs doctor                      # can this store render a doc page at all?
```

## Workflow

- **Content is source-of-truth on epod, .md syncs after.** New page: `epod docs build file.md
  --slug <slug>`. Edit an existing one on epod (`epod docs get-block` / `put-block`), then
  `epod docs sync <id> file.md` back to the .md. **Don't re-`build` an existing page** — it
  loses manual edits and resets anchors.
- **Stand up a docs site (fresh store):** `epod docs doctor` → `install` → `epod docs build`
  each doc → `epod docs nav` → `epod docs home` → browser-verify.
- **After `sync`, always `git diff` the .md.** md2doc preserves `###` levels and list blocks
  via `data-md-level`, but only for HTML built by the *current* md2doc — a page last written
  by an older version round-trips back with headings demoted and lists split into loose
  paragraphs. Fix: `build` that page once to refresh its HTML, then sync. Revert the bad .md,
  don't hand-patch.

## Project configuration

Cross-doc links, sidebar labels and the hero default to nothing project-specific. A project
that wants them writes `.epod.json` beside its `.mcp.json`:

```json
{
  "docs": {
    "links":  { "01-BRD.md": "brd", "02-SRS.md": "srs" },
    "labels": { "RUNBOOK": "Operations Runbook" },
    "hero":   { "heading": "Project name", "mark": "PN",
                "nav_title": "Documentation", "toc_title": "On this page" }
  }
}
```

`links` is what rewrites a `[…](02-SRS.md)` in the markdown to `/pages/srs` and back again on
sync — without it a cross-doc link stays a filename and 404s. `labels` **extends** the built-in
document-type table; only add a code the defaults miss.

## Traps (most are CLI-handled — run the command)

| Trap | What happens | Handling |
|---|---|---|
| **Empty store → BLANK page** | a fresh store has no section templates; publish "succeeds", curl 200, but the page renders only header/footer | `epod docs doctor` / `verify <slug>` detect it; `install` fixes it |
| **Design-contract linter** | `epod theme put` rejects hard-coded hex, a missing Style group, or an unclosed tag | `epod docs install` pre-lints before upload; `epod theme lint <file>` runs it standalone, no token. Hex is fine in `:root{}`/`var(--x,#fff)`/`rgba()`/`hsl()`; a literal hex meant for display belongs in page content, not a section |
| **Must publish + verify** | live serves only the *published* build; clear-cache ≠ publish; curl can't see JS-injected content | write commands auto-publish; `verify` warns on 404/blank; the REAL check is `browser_navigate` + `browser_evaluate` on the DOM |
| **Nav / adding pages** | editing every page's nav by hand | nav is a runtime **menu**; add a page → `epod docs nav`, zero edits to old pages |
| **Vietnamese mojibake** | `Ká»ch báº£n` when HTTP is hand-rolled | the CLI always sends UTF-8; repair an already-damaged page with `epod page fix-mojibake <id>` (eyeball it — the detector can false-positive) |
| **Markdown `>` blockquotes are DROPPED** | md2doc strips `>` lines as editor notes, so a mid-document callout vanishes silently — content loss a 200 won't reveal | don't use `>` for body callouts; lead the paragraph with `**⚠ Label.**` instead |
| **Inline code in a table HEADER is invisible** | `` `code` `` inside a `\| th \|` renders white-on-pale against the blue header → unreadable | use `**bold**` in header cells; keep backticks for body cells |
| **ASCII diagram wider than ~62 chars overflows** | the content column is 525px, so a wide ``` block scrolls sideways instead of wrapping. Nothing is lost and `verify` stays green, but a two-column diagram no longer compares | **prefer `<pre class="mermaid">`** — it reflows and never clips. If ASCII is unavoidable, keep lines ≤62 chars and check `scrollWidth` vs `clientWidth` on every `pre` with `browser_evaluate` |
| **Sidebar label falls back to the long page title** | `epod docs nav` maps a doc code → short English label; an unlisted code shows the full title, truncated mid-word | add the code to `docs.labels` in the project's `.epod.json`, then re-run `epod docs nav` (it relabels in place) |

Browser stuck ("already in use"): `pkill -f chrome-for-testing && rm -f ~/.cache/ms-playwright-mcp/*/Singleton*`.

## Deeper knowledge (read only when you hit that area)

Both live beside this file:

- `references/internals.md` — TOC/anchor generation, mermaid, colour-token injection, the data
  model, why nav must be menu-driven, the home-page/index-template trap.
- `references/sections.md` — the 6 bundled sections (roles, shared `:root` tokens, linter rules).
- The project's own docs for this store's real ids/slugs/colours. This skill is shared logic only.
