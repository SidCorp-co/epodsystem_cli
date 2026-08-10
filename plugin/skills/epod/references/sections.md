# Bundled sections (generalized RS format)

Location: `$SK/assets/store-theme/sections/*.liquid`. Installed into a store's theme by
`epod store install`. All six share one `:root` token set, so recoloring the whole
site = editing those tokens (see SKILL §5). Every section carries the canonical **Style
settings group** in its `{% schema %}` (required by the design-contract linter, SKILL §6).

| Section | Role |
|---|---|
| `doc-layout` | Documentation page: 3-column grid (left nav · center articles · right TOC). ids/anchors + TOC generated at runtime (SKILL §3), mermaid (§4), `.dl-diagram`. **Left nav reads the `docs-nav` MENU at runtime** (SKILL §11), falling back to navitem blocks if the menu is empty. |
| `brd-hero` | Documentation-page hero (settings: mark / doc_type / heading / subheading / chip1..3 / note). |
| `web-header` | Sticky header (`position:sticky;top:0;z-index:100`), brand monogram + nav reading `main-menu` (keep it lean), mobile burger drawer. |
| `web-footer` | 3-column dark footer + copyright bar. **Note `margin-top:0!important`** — the platform layout injects a 72px top margin that otherwise leaves a dead band. |
| `web-hero` | Home-page hero: eyebrow / heading / subheading + CTA button. |
| `docs-toc` | Home-page: responsive card grid of documents (`card` blocks, generated at build time by `epod store home` from the published-page list). |

## Origin & how to compare against real RS

These are the **RS store's section format, generalized**: pulled from the real RS theme,
then neutralized — brown palette → blue-slate `:root`, `mark:"RS"` → generic, Vietnamese/
project-specific schema defaults → English. Structure (class names, schema shape, runtime
JS) is identical to RS, so an RS section is a valid reference.

To read a real RS section for comparison (needs an RS-scoped token; this project's token
can't cross the org boundary):

```bash
EPOD_TOKEN=<rs-token> epod get-theme sections/doc-layout.liquid --theme <rs-theme-id>
```

## Linter rules the sections satisfy (enforced locally by `doctor`)

1. No hard-coded brand hex in body CSS — use `var(--…)`, or a `var(--x,#fff)` fallback, or `rgba()`/`hsl()`. Hex is legal only inside `:root{}` token definitions.
2. The `{% schema %}` includes the canonical Style group: `visible`, `bg_color`, `text_color`, `heading_color`, `padding_top`, `padding_bottom`, `border_color`, `border_width`, `border_radius`.
3. No unclosed HTML tags. (The server even scans literal tag strings inside inline `<script>`; if you must reference `<pre>` in JS, build the selector by concatenation, e.g. `'p'+'re'`.)

`epod store doctor --local` checks all three offline before you upload, so a rejection
is caught in seconds with a clear message instead of a cryptic server error.
