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

Send Vietnamese through `epod vi`; it goes to Gemini with the style contract attached.
`epod vi --help` lists the verbs, `epod vi <verb> --help` the flags.

## Pick the verb

| Situation | Do this |
|---|---|
| Write Vietnamese that does not exist yet | `epod vi doc file.md` · `epod vi translate "…"` · `epod vi i18n locales/en.json` |
| Judge Vietnamese that already exists | `epod vi review file` — Gemini answers, then read the findings out |
| Gate a build, or sweep before asking Gemini | `epod vi lint file…` (`--strict` exits 1) |
| A term keeps coming out wrong | add it to `vi.glossary` in `.epod.json`, do not fix each hit |
| A translation was refused (exit 2) | report the keys, leave them in English |
| `no gateway key configured` | `epod vi install --key <key>` — ask the user for the key |

`lint` matches phrases the contract names. It cannot tell whether a sentence is readable —
send that to `review`, and treat a clean `lint` as "nothing tripped", not as a pass.

## Wrong / Right

| | Wrong | Right |
|---|---|---|
| **Producing Vietnamese** | typing it into the edit, or translating it in your head | `epod vi doc` · `translate` · `i18n` |
| **Judging Vietnamese** | reading it yourself, or reporting a clean `lint` as a pass | `epod vi review` — Gemini decides, not you and not a pattern |
| **`Vui lòng`** | stripping it for brevity, or reporting it as padding | leave it. Ordinary polite Vietnamese, error messages included |
| **A refused string** | patching the gap with hand-written Vietnamese | name the keys to the user, leave them English |

## Docs

```bash
epod vi doc docs/02-SRS.md            # → docs/02-SRS.vi.md
epod vi review docs/02-SRS.vi.md      # before anyone publishes it
epod docs build docs/02-SRS.vi.md --slug srs-vi
```

Code fences, frontmatter, inline code, link targets and heading levels come through
byte-identical. Frontmatter *values* stay English — translate a title by hand. For
Vietnamese already published, `epod docs sync <id> file.md` first.

## Locale files

```bash
epod vi i18n locales/en.json            # missing keys only — rerunning is cheap
epod vi i18n locales/en.json --check    # offline: missing, placeholders, CTA discipline
epod vi i18n locales/en.json --overwrite --keys billing,common
epod vi review locales/vi.json --fix    # machine-written files only
```

Placeholders are verified on every string; one that loses `{{name}}` or `%1$s` never
reaches the file. A string that talks *about* braces trips that gate — exempt it with
`--ignore 'codePatterns.*'` or `vi.ignore`, rather than editing around it.

`--check` also reports CTA discipline: **inflated** (`Remove` → `Xóa tỷ giá`, a reusable
button turned into a one-screen button — use `Xóa`) and **collapse** (N keys saying
`Tạo <object>` where one `common.create` would serve).

## Voice and vocabulary

```json
{
  "vi": {
    "register": "trang-trong",
    "region": "nam",
    "ignore": ["codePatterns.*"],
    "glossary": { "workspace": null, "storefront": "gian hàng", "khai": "khai" }
  }
}
```

Set `register` once per project in `.epod.json`: `san-pham` (**bạn**) for most apps,
`trang-trong` (**quý khách**) for commerce, invoices, legal and transactional email,
`than-mat` for marketing. `--register` overrides one run. Pin domain terms in `glossary`
before a large `review`, or it will offer plainer everyday words for them; `null` keeps a
term in English. A `.vi-glossary.json` above the CWD layers on top.

## Traps

| Trap | What happens | Handling |
|---|---|---|
| **Key in the wrong file** | committed secret | the key goes to `epod vi install` or `MUSETOOLS_API_KEY`, never `.epod.json` |
| **`--fix` on a human catalogue** | a translator's Vietnamese comes back wordier | read `review` findings first; `--fix` is for machine-written files |
| **`review` flattens domain words** | offers `thêm` for `khai` | pin them in `vi.glossary` before the run |
| **Register ignored in a doc** | doc tone used to hard-code `bạn` | fixed — `epod vi doctor` prints the active voice |

## Exit codes

`0` clean · `1` error, `review` found something, or `lint --strict` fired ·
`2` written, some strings refused.

## Configuration

Precedence: flag → environment → `.epod.json` `"vi"` → `~/.config/vi-natural/config.json`
(0600, written by `epod vi install`, shared with the standalone `vi-natural` CLI). Default
model `gm/gemini-3.5-flash`; reach for a pro model only when tone outweighs turnaround.
