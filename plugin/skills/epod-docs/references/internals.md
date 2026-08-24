# epod internals — hidden logic (read when you hit the specific area)

## TOC & anchors (doc-layout)
ids + TOC are generated in JS at runtime, NOT from .md headings.
- section id = `slugify(block TITLE)`; keeps old `sec-N` as an alias so old links survive.
- sub-heading (h3/h4) id = `<section-id>-<slugify(text)>`.
- `slugify`: lowercase, keep Vietnamese chars, non-word → `-`, truncate.
- Get the real anchor with `epod anchors <id> --url` — don't guess from headings.
- **`epod docs build` trap**: `./other.md#anchor` links get the slug mapped but the anchor kept as-is → usually mismatches the real epod anchor. After `epod docs build`, reconcile hrefs against `epod docs anchors <target> --url`.

## Diagrams
- Mermaid: `<pre class="mermaid">…</pre>`; the section lazy-loads mermaid from CDN only when `pre.mermaid` exists; colors map to theme tokens; nodes hidden until rendered, text restored on CDN failure.
- Static diagrams: plain HTML/CSS (e.g. `.dl-diagram`). md2doc keeps the raw block instead of escaping — check the project's md2doc before editing.

## Colors / theme tokens
- Global vars (`--accent`, `--ink`, `--paper`, `--line`, `--font-*`…) are injected by the platform wrapper, NOT in the theme file — editing a section file won't change them.
- Recolor the whole store: inject `<style>:root{ --accent:…; }</style>` into **every** section that appears on the target page; if a page lacks the shared section, put `:root` into one it does have, or it loses color. Keep every `:root` block identical.
- Read the current value first: `browser_evaluate` → `getComputedStyle(document.documentElement).getPropertyValue('--accent')`.

## Data model
- Page = `sections_data`: `{ "order":[keys], "sections": { key: {type, settings, blocks} } }`.
- Section `type` → theme file `sections/<type>.liquid`; `blocks` are children (`type` + `settings`).
- Page text = a block's `settings.body` (richtext/HTML) = **content** (not linted). CSS lives in the `.liquid` file (linted, see linter rules in `sections.md`).

## Dynamic menu nav — why & details
Verified via `list_liquid_objects`: storefront Liquid has NO `pages` object (a section can't loop pages), but DOES expose `linklists['<handle>']` and `content.<type>`. So nav must be menu-driven.
- Sidebar (`doc-layout`) reads the **`docs-nav`** menu (full list); header reads **`main-menu`** (keep lean — a few links, not every page).
- Current item = `link.url == request.path` (auto, no per-page flag).
- `list_menus` returns EMPTY `items` — read real items via `graphql_query storeMenu(id){ items{ id label page_id url } }`.
- `sync-nav` maintains `docs-nav`: adds missing, de-dupes by `page_id`, labels generically by doc type.

## Home-page trap
`/` is rendered by the **`index` template** (`templates/index.json`), NOT a `page_type=home` page (created but ignored). `epod docs home` sets `web-hero`+`docs-toc` on the index template via `set_section_settings template:"index"` and trims `index.json` to just those two (dropping default `web-feature-grid`/`web-cta`).
