"""Offline calque check: the machine-translation tells, found without a gateway.

Every phrase this looks for is already written down in `prompts.STYLE`, in the
block the model is told to obey. Restating them here as a second hand-maintained
list would guarantee the two drift, and the day they disagree the lint is wrong
in exactly the cases it exists to catch. So the patterns are parsed out of the
contract at import time: the contract stays the single source of truth, and a
phrase added to it starts being flagged the same day.

This runs on a .md or a locale .json, costs nothing, and needs no network — it is
the check to run before `epod docs build`, when `epod vi review` (which asks the
model) is the check to run when this one fires or the document is new.
"""
import os
import re

from . import doc as doc_mod
from . import locale, prompts
from .util import CliError, read_json

# `✗ "bad"  ✓ "good"` and `"bad" → "good"` are the two shapes the contract uses.
_MARKED = re.compile(r'✗\s*"([^"]+)"\s*✓\s*"([^"]+)"')
_ARROW = re.compile(r'"([^"]+)"\s*→\s*"([^"]+)"')


def phrases():
    """{bad phrase: what the contract says to write instead}."""
    out = {}
    for line in prompts.STYLE.splitlines():
        for bad, good in _MARKED.findall(line):
            out.setdefault(bad.lower(), good)
        if "✗" in line:
            continue  # the ✓ half of a marked pair is not an arrow rule
        for bad, good in _ARROW.findall(line):
            out.setdefault(bad.lower(), good)
    return out


PHRASES = phrases()
_PHRASE_RE = [(re.compile(re.escape(bad), re.I | re.U), bad, good)
              for bad, good in sorted(PHRASES.items(), key=lambda kv: -len(kv[0]))]

# Three rules the contract states as grammar plus an example, which no quoted
# pair can express: the "được X bởi Y" passive, "sự/việc + verb" nominalization,
# and plural markers scattered where Vietnamese does not need them. The verb list
# is closed and grammatical, so unlike a phrase list it does not drift.
_PASSIVE = re.compile(r"\bđược\b[^.!?]{1,40}?\bbởi\b", re.I | re.U)
_NOMINAL = re.compile(
    r"\b(sự|việc) (thay đổi|xóa|xoá|tạo|thêm|sửa|lưu|gửi|cập nhật|sử dụng|thực hiện|"
    r"kiểm tra|kết nối|đăng nhập|đăng ký|đăng xuất|thanh toán|cài đặt|quản lý|xử lý|"
    r"tải|chọn|lựa chọn|hủy|huỷ|khôi phục)\b", re.I | re.U)
# Two constructions where the nominalization is not padding but grammar, and
# flagging them makes the linter wrong on correct Vietnamese. After a preposition
# or a quantifier there is no other way to say it — "hậu quả của việc sửa", "thay
# cho việc tải tay", "bốn việc Thêm · Xem · Sửa". And a nominalization that is the
# subject of its own clause is the normal way to make a verb the topic — "Việc xóa
# bị chặn". What the contract objects to is the *object* form, "thực hiện việc xóa
# tài khoản", which neither guard covers.
_NOMINAL_BEFORE = re.compile(
    r"(của|cho|về|với|trong|ngoài|vì|do|nhờ|bằng|"
    r"một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|mọi|từng|nhiều|vài)\s+$", re.I | re.U)
_NOMINAL_AFTER = re.compile(
    r"^[\s*_]*(vẫn|bị|là|không|đã|sẽ|có|cũng|phải|luôn|chỉ|khiến|làm|nên|thì)\b",
    re.I | re.U)
_PLURAL = re.compile(r"\b(các|những)\b", re.I | re.U)

# Vietnamese only. An English UI string is a missing translation, not a calque.
_DIACRITIC = re.compile(r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệ"
                        r"ìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", re.I | re.U)


def is_vietnamese(text):
    return bool(_DIACRITIC.search(text))


def scan(text, where):
    """Findings in one string. `where` is a line number or a key path."""
    found = []
    if not is_vietnamese(text):
        return found
    for pattern, bad, good in _PHRASE_RE:
        match = pattern.search(text)
        if match:
            found.append({"where": where, "rule": "calque",
                          "found": match.group(0),
                          "suggest": good, "text": " ".join(text.split())[:120]})
    match = _PASSIVE.search(text)
    if match:
        found.append({"where": where, "rule": "passive",
                      "found": match.group(0),
                      "suggest": "câu chủ động, hoặc bỏ chủ ngữ",
                      "text": " ".join(text.split())[:120]})
    match = _NOMINAL.search(text)
    if match and _is_padding(text, match):
        found.append({"where": where, "rule": "nominalized",
                      "found": match.group(0),
                      "suggest": "bỏ \"%s\": %s" % (match.group(1), match.group(2)),
                      "text": " ".join(text.split())[:120]})
    return found


def _is_padding(text, match):
    """True when `sự/việc` is the padding the contract objects to, not grammar."""
    if _NOMINAL_BEFORE.search(text[:match.start()]):
        return False
    return not _NOMINAL_AFTER.match(text[match.end():])


def _markdown(path):
    """Prose blocks only: fenced code, frontmatter and inline code are exempt."""
    source = open(path, encoding="utf-8").read()
    findings, prose, line = [], [], 1
    for kind, block in doc_mod.segment(source):
        if kind == "text":
            slots = []
            masked = doc_mod.protect_inline(block, slots)
            for finding in scan(masked, line):
                findings.append(locate(finding, block, line))
            prose.append(masked)
        line += block.count("\n")
    # Counted over prose only, for the same reason the phrase rules are: a
    # document *about* interface copy quotes the habit it is describing, and
    # counting those quotes reports the document as guilty of them.
    return findings, density("\n".join(prose))


def locate(finding, block, start_line):
    """Point a finding at its phrase rather than at the paragraph holding it.

    A markdown block is one paragraph or one list, often twenty lines of it, so
    reporting where the block starts and quoting its first 120 characters can
    name a line that does not contain the phrase at all — a finding nobody can
    navigate to. The matched text is prose, so it survives inline-code masking
    unchanged and can simply be found again in the original block.
    """
    index = block.find(finding["found"])
    if index < 0:
        return finding
    finding["where"] = start_line + block.count("\n", 0, index)
    begin = block.rfind("\n", 0, index) + 1
    end = block.find("\n", index)
    row = block[begin:] if end < 0 else block[begin:end]
    offset = index - begin
    window = " ".join(row[max(0, offset - 40):offset + 80].split())
    finding["text"] = ("…" if offset > 40 else "") + window
    return finding


def _locale(path):
    tree = read_json(path)
    if tree is None:
        raise CliError("cannot read %s" % path)
    findings, joined = [], []
    for keypath, text in locale.flatten(tree):
        findings.extend(scan(text, locale.label(keypath)))
        joined.append(text)
    return findings, density("\n".join(joined))


def density(text):
    """Whole-file habits: one occurrence is fine, a habit is the tell."""
    words = max(len(text.split()), 1)
    return {"plural": len(_PLURAL.findall(text)),
            "words": words}


def run(paths):
    """Print findings for each file. Returns the number of files that had any."""
    dirty = 0
    for path in paths:
        if not os.path.isfile(path):
            raise CliError("no such file: %s" % path)
        if path.endswith(".json"):
            findings, stats = _locale(path)
        else:
            findings, stats = _markdown(path)

        notes = []
        # Vietnamese does not mark plural unless the count is the point; one every
        # forty words means the English "the ...s" is being copied across.
        if stats["plural"] * 40 > stats["words"] and stats["plural"] > 2:
            notes.append('"các"/"những" %d times in %d words — drop the ones that '
                         "carry no information" % (stats["plural"], stats["words"]))
        if not findings and not notes:
            print("%s: clean (%d phrase rules)" % (path, len(PHRASES)))
            continue
        dirty += 1
        print("%s: %d finding(s)" % (path, len(findings) + len(notes)))
        for finding in findings:
            print('  %-28s %s: "%s" → %s'
                  % (finding["where"], finding["rule"], finding["found"],
                     finding["suggest"]))
            print("      %s" % finding["text"])
        for note in notes:
            print("  %-28s style: %s" % ("(whole file)", note))
    if dirty:
        print("\nThis check is a tripwire, not a judge: it only knows the phrases the "
              "contract names. Whether the Vietnamese actually reads clearly is a "
              "question for `epod vi review <file>`, which asks the model.")
    return dirty
