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

Vietnamese here goes through `epod vi`, which hands it to Gemini with a written style
contract attached. It is worth the extra step for a reason that is easy to miss.

Vietnamese typed straight into an edit parses, publishes, and reads like a machine —
`sự thay đổi của bạn đã được lưu lại một cách thành công`. Everyone reviewing the build
sees a 200 and valid JSON, so nothing looks wrong. Only a Vietnamese reader notices, and
usually after it has shipped. Routing through the CLI attaches the style contract, the
placeholder gate and the model's own read of the sentence, none of which an edit gets.

`epod vi` works on local files only — no store token, no connection, happy in a checkout
with no `.mcp.json`. It does want its own credential once per machine:
`epod vi install --key <key>` stores the gateway endpoint and key at 0600 and checks them
against the gateway first. If a command answers `no gateway key configured`, the key is
worth asking the user for; the rest of `epod` carries on fine without it. The `epod` skill
covers project scoping, and `epod-docs` owns the publishing this feeds into.

```bash
epod vi install --key <key>    # once per machine: the gateway endpoint and key
epod vi review guide.vi.md     # ask Gemini: does this read like Vietnamese?
epod vi doc   guide.md         # → guide.vi.md, code/links/structure untouched
epod vi lint  <file...>        # free, offline: named phrases only, no judgement
epod vi i18n  locales/en.json  # → locales/vi.json, missing keys only
epod vi translate "Delete this item permanently?"
epod vi doctor                 # settings, gateway, one live round trip
```

## Two questions, two tools

It helps to know which question is on the table.

**"Does this read like Vietnamese?"** — that one goes to Gemini, through
`epod vi review`. It is the question that matters, and the model is the only thing here
that can answer it. What it catches is the sentence carrying three ideas with no clear
subject, the clause where nothing says what modifies what, the phrase that has to be read
twice. Those sentences are grammatical and contain no suspicious phrase, so nothing
mechanical will ever flag them.

```bash
epod vi review docs/02-SRS.vi.md      # findings with a suggested rewrite for each
epod vi review locales/vi.json --json # machine-readable, good for collecting
epod vi review locales/vi.json --fix  # applies them (JSON only, placeholder-checked)
```

**"Does this contain a phrase the contract names?"** — that is `epod vi lint`, which is
free, offline and quite literal. It knows calques the contract lists (`một cách nhanh
chóng`, `trong trường hợp`, `vui lòng lưu ý rằng`), `được X bởi Y` passives,
`sự/việc + verb` where it pads rather than does grammatical work, and plural markers
scattered where Vietnamese does not need them. Fenced code, frontmatter and inline code
are skipped, and so are English strings — an untranslated string is a missing translation,
not a calque.

Its patterns are parsed out of the style contract (`packs/vi/prompts.py`) at import time,
so the rules Gemini is given and the rules the linter checks stay in step. It is a
tripwire, and a useful one in CI (`--strict` exits 1 on a finding). It just cannot read,
so a clean result means nothing tripped rather than that the Vietnamese is good — the
model's read is still the one to get.

## Wrong / Right

The four places a well-meant edit does real damage.

| | Wrong | Right |
|---|---|---|
| **Producing Vietnamese** | typing it into the edit, or translating it in your head | `epod vi doc`, `epod vi translate`, `epod vi i18n` |
| **Judging Vietnamese** | reading it yourself, or reporting a clean `lint` as a pass | `epod vi review` — Gemini decides, not you and not a pattern |
| **`Vui lòng`** | stripping it for brevity, or reporting it as padding | leave it. It is ordinary polite Vietnamese and belongs in a request, error messages included |
| **A refused string (exit 2)** | patching the gap with hand-written Vietnamese | read the refused keys out to the user and leave them in English |

## The docs path

```bash
epod vi doc docs/02-SRS.md            # → docs/02-SRS.vi.md
epod vi review docs/02-SRS.vi.md      # Gemini reads it before anyone else does
epod docs build docs/02-SRS.vi.md --slug srs-vi
```

Fenced code, frontmatter, inline code spans, link targets, heading levels and blank-line
structure come through byte-identical; only prose is translated. A block whose structure
would change is refused and keeps its English — exit code 2, with the block named.
Frontmatter *values* are left alone, so a title that needs translating is a hand edit.

For Vietnamese that is already published, `epod docs sync <id> file.md` brings it back
down first, and then it is an ordinary file to review.

## Locale files

```bash
epod vi i18n locales/en.json            # missing keys only — rerunning is cheap
epod vi i18n locales/en.json --check    # offline audit, no API calls, CI-safe
epod vi i18n locales/en.json --overwrite --keys billing,common
```

`--check` reports missing keys, damaged placeholders, stale keys, and call-to-action
discipline: *inflated* (English `Remove`, Vietnamese `Xóa tỷ giá` — a reusable button that
became a one-screen button) and *collapse* (N keys saying `Tạo <object>` where one shared
`common.create` = `Tạo` would serve). Translation holds the same line going forward: a
bare English CTA that comes back carrying an object is retried once, then refused. One
`Lưu` works on every form, while a per-entity label needs its own key and drifts from its
siblings the first time someone edits one of them.

Every translated string is checked against its source for placeholders — `{{name}}`,
`{name}`, `%s`, `%1$s`, `%(name)s`, `:name`, ICU plurals, HTML tags. One that loses or
renames a placeholder never reaches the file.

A string that talks *about* brace syntax ("a `{` is never closed by a `}`") looks like an
interpolation and gets refused. Exempting those keys is tidier than hand-editing around
them: `--ignore 'codePatterns.*'`, or `vi.ignore` in `.epod.json`.

## Voice — worth picking once per project

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

`.epod.json`, beside the project's `.mcp.json`. `san-pham` (the default, says **bạn**)
suits almost every app; `trang-trong` (**quý khách**) fits commerce, invoices, legal and
transactional email; `than-mat` is for marketing and onboarding. The pronoun pair is the
most visible localization choice in Vietnamese — `bạn` in an invoice reads careless,
`quý khách` in a dev tool reads stiff — so it is a good thing to settle early.
`--register` overrides for a single run, and a `.vi-glossary.json` above the CWD layers on
top of `vi.glossary` when a docs subtree needs a term the rest of the project does not.

In the glossary, `null` keeps a word in English. Glossary entries outrank the built-in
style rules, which is how a project pins its own vocabulary — and it is what keeps
`review` from offering to replace domain terms with plainer everyday words. When a term
keeps coming out inconsistently, the glossary is a better answer than fixing each hit, so
it is worth mentioning to the user.

## Traps

| Trap | What happens | Handling |
|---|---|---|
| **Key not configured** | `no gateway key configured` | `epod vi install --key <key>` (alias `login`), or `export MUSETOOLS_API_KEY=…`. Not `.epod.json` — that file is committed |
| **`--fix` on a human catalogue** | a translator's good Vietnamese comes back wordier | run `review` without `--fix` first and read the findings; `--fix` earns its place on machine-written files |
| **`review` flattens domain words** | it offers `thêm` for `khai`, plain words for accounting terms | pin them in `vi.glossary` before a large run, and the noise goes away |
| **Register ignored in a doc** | doc tone used to hard-code `bạn` | fixed — the VĂN PHONG block wins. `epod vi doctor` prints the active voice |

## Exit codes

`0` clean · `1` error, `review` found something, or `lint --strict` fired ·
`2` the file was written but some strings were refused.

## Configuration

`epod vi install` writes the endpoint, key and default model to
`~/.config/vi-natural/config.json` (0600, shared with the standalone `vi-natural` CLI);
`--base-url` and `--model` override the defaults, and `--no-verify` skips the gateway
check. Voice and vocabulary are kept out of that file on purpose — they are
project-shaped, so they live in `.epod.json`.

Precedence: flag → environment → `.epod.json` `"vi"` → `~/.config/vi-natural/config.json`.
The default model is `gm/gemini-3.5-flash`; `--model` overrides per run, and a pro model
earns its cost mainly on marketing copy or a long document where tone outweighs turnaround.
