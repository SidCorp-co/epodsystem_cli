---
name: epod-vi
description: >-
  Write and audit Vietnamese with `epod vi` — natural tiếng Việt for docs pages
  and locale files instead of machine-sounding translation. Invoke whenever
  Vietnamese text is about to be written, translated or reviewed: a .md destined
  for `epod docs build`, an en.json → vi.json, or existing Vietnamese that reads
  translated. Triggers on Vietnamese, tiếng Việt, dịch, bản địa hóa, vi.json,
  vi-VN, i18n, l10n, "translate to Vietnamese".
---

# Skill: epod-vi

**Do not write the Vietnamese yourself.** Route it through `epod vi`.

A model asked in passing for Vietnamese returns Vietnamese that parses, publishes and
reads like a machine — `sự thay đổi của bạn đã được lưu lại một cách thành công`. The
failure is invisible to everyone reviewing the build who does not read Vietnamese: the
page is 200, the JSON is valid, the tiếng Việt is just wrong in register. Vietnamese
typed straight into an edit gets no style contract, no placeholder gate and no review.

`epod vi` needs no store token and never opens a connection — it works in a checkout
with no `.mcp.json`, on local files only. It does need its own credential, once per
machine: `epod vi install --key <key>` stores the gateway endpoint and key at 0600 and
verifies both against the gateway before writing. Every other `epod` group works without
it. If a command answers `no gateway key configured`, that is the fix — ask the user for
the key rather than writing the Vietnamese yourself. Read the `epod` skill for project scoping;
`epod-docs` owns the publish workflow this feeds.

```bash
epod vi install --key <key>    # once per machine: the gateway endpoint and key
epod vi lint  <file...>        # FREE, offline: the tells a machine leaves
epod vi doc   guide.md         # → guide.vi.md, code/links/structure untouched
epod vi review guide.vi.md     # ask the model where existing Vietnamese reads translated
epod vi i18n  locales/en.json  # → locales/vi.json, missing keys only
epod vi translate "Delete this item permanently?"
epod vi doctor                 # settings, gateway, one live round trip
```

## Reach for lint first

`lint` costs nothing and needs no network, and most machine-translated Vietnamese fails
it without a model ever being asked. Its patterns are parsed out of the style contract
(`packs/vi/prompts.py`) at import time, so the rules the translator is told to obey and
the rules the linter enforces cannot drift apart.

```bash
epod vi lint docs/*.vi.md locales/vi.json
epod vi lint docs/02-SRS.vi.md --strict   # exit 1 when anything is found — for CI
```

It flags: calques the contract names (`một cách nhanh chóng`, `trong trường hợp`,
`vui lòng lưu ý rằng`), `được X bởi Y` passives, `sự/việc + verb` nominalization, and —
per file — `vui lòng` used more than once or plural markers scattered where Vietnamese
does not need them. Fenced code, frontmatter and inline code are exempt; English strings
are skipped, because an untranslated string is a missing translation, not a calque.

When lint fires, `epod vi review <file>` asks the model for a rewrite of each finding.
`epod vi doc` writes it properly in the first place.

## The docs path

```bash
epod vi doc docs/02-SRS.md            # → docs/02-SRS.vi.md
epod vi lint docs/02-SRS.vi.md        # confirm before it goes live
epod docs build docs/02-SRS.vi.md --slug srs-vi
```

Fenced code, frontmatter, inline code spans, link targets, heading levels and blank-line
structure pass through byte-identical; only prose is translated. A block whose structure
would change is refused and keeps its English — exit code 2, with the block reported.
Frontmatter *values* are never translated; edit a title by hand.

For Vietnamese already published, `epod docs sync <id> file.md` first, then lint the .md.

## Locale files

```bash
epod vi i18n locales/en.json            # missing keys only — rerunning is cheap
epod vi i18n locales/en.json --check    # offline audit, no API calls, CI-safe
epod vi i18n locales/en.json --overwrite --keys billing,common
```

`--check` reports missing keys, damaged placeholders, stale keys, and **call-to-action
discipline**: *inflated* (English `Remove`, Vietnamese `Xóa tỷ giá` — a reusable button
became a one-screen button) and *collapse* (N keys saying `Tạo <object>` where one shared
`common.create` = `Tạo` would serve). Translation enforces the same rule going forward:
a bare English CTA that comes back with an object is retried once, then refused. One
`Lưu` works on every form; a per-entity label needs its own key and drifts from its
siblings the first time someone edits one.

Every translated string is compared against its source for placeholders — `{{name}}`,
`{name}`, `%s`, `%1$s`, `%(name)s`, `:name`, ICU plurals, HTML tags. A string that loses
or renames one never reaches the file.

A string that talks *about* brace syntax ("a `{` is never closed by a `}`") parses as an
interpolation and gets refused. Exempt those keys rather than hand-editing around them:
`--ignore 'codePatterns.*'`, or `vi.ignore` in `.epod.json`.

## Voice — pick once per project

```json
{
  "vi": {
    "register": "trang-trong",
    "region": "nam",
    "ignore": ["codePatterns.*"],
    "glossary": { "workspace": null, "storefront": "gian hàng", "Billing": "Thanh toán" }
  }
}
```

`.epod.json`, beside the project's `.mcp.json`. `san-pham` (default, says **bạn**) is
right for almost every app; `trang-trong` (**quý khách**) for commerce, invoices, legal
and transactional email; `than-mat` for marketing and onboarding. Getting the pronoun
pair wrong is the single most visible localization mistake in Vietnamese — `bạn` in an
invoice reads careless, `quý khách` in a dev tool reads stiff. `--register` overrides for
one run. A `.vi-glossary.json` found above the CWD layers on top of `vi.glossary`, so a
docs subtree can pin a term the whole project does not.

In the glossary, `null` means "leave this word in English". Glossary entries outrank the
built-in style rules — this is how a project pins its own product vocabulary. When a term
keeps coming out inconsistently, tell the user to add it here rather than fixing each hit.

## Traps

| Trap | What happens | Handling |
|---|---|---|
| **Model-written Vietnamese** | reads translated; nobody reviewing notices | never hand-write it — `epod vi doc` / `translate`, and `epod vi lint` before publish |
| **Key not configured** | `no gateway key configured` | `epod vi install --key <key>` (alias `login`), or `export MUSETOOLS_API_KEY=…`. **Never `.epod.json`** — that file is committed |
| **Exit code 2** | file written, some strings refused and left in English | read the refused keys out to the user; do not patch them with hand-written Vietnamese |
| **`--fix` on a human catalog** | a translator's good Vietnamese gets rewritten wordier | `review` without `--fix` first, read the findings; `--fix` is for machine-written files |
| **Register ignored in a doc** | doc tone used to hard-code `bạn` | fixed — the VĂN PHONG block wins. Verify with `epod vi doctor`, which prints the active voice |

## Exit codes

`0` clean · `1` error, `review` found something, or `lint --strict` fired ·
`2` the file was written but some strings were refused.

## Configuration

`epod vi install` writes the endpoint, key and default model to
`~/.config/vi-natural/config.json` (0600, shared with the standalone `vi-natural` CLI);
`--base-url` and `--model` override the defaults, `--no-verify` skips the gateway check.
Voice and vocabulary are deliberately not stored there — they are project-shaped and
belong in `.epod.json`.

Precedence: flag → environment → `.epod.json` `"vi"` → `~/.config/vi-natural/config.json`.
Default model `gm/gemini-3.5-flash`; `--model` overrides per run, and a pro model is worth
it only for marketing copy or a long document where tone outweighs turnaround.
