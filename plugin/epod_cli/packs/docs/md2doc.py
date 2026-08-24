#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2doc.py — chuyển file Markdown tài liệu (01-BRD.md, 04-Tech-Design.md…) thành
doc blocks cho section doc-layout của epod.

Quy ước (chốt với người dùng):
- Mỗi heading `## <num>. <title>` = 1 doc block (num = số đầu, title = phần còn lại).
  `## <title>` không có số cũng thành block (num rỗng).
- `###` / `####` bên trong → `<h4>` (TOC tự sinh từ h4).
- Hỗ trợ: bảng GFM, list (ul/ol), đoạn văn, `**bold**`, `` `code` ``, `[text](url)`, *italic*.
- Link nội bộ `./02-SRS.md#anchor` → `/pages/<slug>#<anchor>` (map slug theo --link).
  Anchor giữ NGUYÊN như trong .md — nếu lệch title block epod, sửa thủ công sau
  (tra bằng `epod anchors <page>`).
- Header tài liệu (bảng metadata + blockquote ghi chú + `---` đầu file) và dòng
  trước block đầu tiên được bỏ qua (đưa vào hero, không vào body).
- Diagram: bảng .md giữ thành <table>; muốn .dl-diagram đẹp thì sửa tay sau.

Dùng:
  from md2doc import md_to_doc_blocks, build_nav
  blocks = md_to_doc_blocks(open("docs/04-Tech-Design.md").read(), link_map={"02-SRS.md":"srs-may-cham-cong", ...})
Hoặc chạy trực tiếp để xem JSON:
  python3 tools/md2doc.py docs/04-Tech-Design.md
"""
import html as _html
import json
import re
import sys

# ---------------------------------------------------------------- inline
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC_RE = re.compile(r"(?<![\*\w])\*([^*\n]+)\*(?![\*\w])")
_CODE_RE = re.compile(r"`([^`]+)`")


def _map_link(url, link_map):
    """Đổi link .md nội bộ -> /pages/<slug>#anchor. Link ngoài giữ nguyên."""
    if not link_map:
        return url
    m = re.match(r"\.?/?([\w.-]+\.md)(#.*)?$", url)
    if not m:
        return url
    fname, frag = m.group(1), (m.group(2) or "")
    slug = link_map.get(fname)
    return f"/pages/{slug}{frag}" if slug else url


def inline(text, link_map=None):
    """Chuyển inline markdown -> HTML. Escape trước, chèn tag sau."""
    # tách code span ra placeholder để không escape/format bên trong
    codes = []

    def _stash(m):
        codes.append(m.group(1))
        return f"\x00{len(codes)-1}\x00"

    text = _CODE_RE.sub(_stash, text)
    text = _html.escape(text, quote=False)

    def _link(m):
        label = _BOLD_RE.sub(r"<strong>\1</strong>", m.group(1))
        return f'<a href="{_map_link(m.group(2), link_map)}">{label}</a>'

    text = _LINK_RE.sub(_link, text)
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC_RE.sub(r"<em>\1</em>", text)

    def _unstash(m):
        return f"<code>{_html.escape(codes[int(m.group(1))], quote=False)}</code>"

    return re.sub(r"\x00(\d+)\x00", _unstash, text)


# ---------------------------------------------------------------- block-level
def _is_table_sep(line):
    return bool(re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", line)) and "-" in line


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _render_body(lines, link_map):
    """Chuyển các dòng body của 1 block (đã bỏ heading ##) thành HTML."""
    out = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        # khối HTML thuần giữ nguyên (vd <div class="dl-diagram">…</div>): gom tới
        # thẻ đóng cân bằng, copy nguyên văn KHÔNG escape (để render, không thành text).
        mh = re.match(r"^<(\w+)([^>]*)>", s)
        if mh and any(f'"{c}"' in s or f"'{c}'" in s or f"={c}" in s
                      for c in _KEEP_HTML_CLASSES) \
                and any(c in s for c in _KEEP_HTML_CLASSES):
            tag = mh.group(1)
            raw = []
            depth = 0
            while i < n:
                raw.append(lines[i])
                depth += len(re.findall(rf"<{tag}\b", lines[i]))
                depth -= len(re.findall(rf"</{tag}>", lines[i]))
                i += 1
                if depth <= 0:
                    break
            out.append("\n".join(raw).strip())
            continue
        # fenced code block ```lang ... ``` -> <pre><code> (giữ nguyên xuống dòng)
        # ```mermaid -> <pre class="mermaid"> (mermaid.js render từ textContent)
        mf = re.match(r"^(`{3,}|~{3,})(.*)$", s)
        if mf:
            fence = mf.group(1)[0]
            lang = mf.group(2).strip().lower()
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith(fence * 3):
                code_lines.append(lines[i])
                i += 1
            i += 1  # bỏ dòng đóng fence
            code = _html.escape("\n".join(code_lines), quote=False)
            if lang == "mermaid":
                out.append(f'<pre class="mermaid">{code}</pre>')
            else:
                out.append(f"<pre><code>{code}</code></pre>")
            continue
        # h3/h4 -> <h4>. Cấp gốc giữ ở data-md-level để `epod docs sync` dựng lại đúng
        # (mọi cấp đều render <h4> nên TOC/CSS không đổi; thiếu thuộc tính này
        # thì vòng .md -> epod -> .md hạ hết ### xuống ####).
        m = re.match(r"^(#{3,6})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            out.append(f'<h4 data-md-level="{lvl}">{inline(m.group(2), link_map)}</h4>')
            i += 1
            continue
        # table: dòng | ... theo sau bởi dòng phân cách
        if s.startswith("|") and i + 1 < n and _is_table_sep(lines[i + 1]):
            header = _split_row(lines[i])
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_split_row(lines[i]))
                i += 1
            th = "".join(f"<th>{inline(c, link_map)}</th>" for c in header)
            body = ""
            for r in rows:
                tds = "".join(f"<td>{inline(c, link_map)}</td>" for c in r)
                body += f"<tr>{tds}</tr>\n"
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>\n{body}</tbody></table>")
            continue
        # list (ul / ol) — gom các dòng liên tiếp
        if re.match(r"^[-*]\s+", s) or re.match(r"^\d+\.\s+", s):
            ordered = bool(re.match(r"^\d+\.\s+", s))
            items = []
            while i < n:
                si = lines[i].strip()
                mm = re.match(r"^(?:[-*]|\d+\.)\s+(.*)$", si)
                if not mm:
                    break
                items.append(f"<li>{inline(mm.group(1), link_map)}</li>")
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>\n" + "\n".join(items) + f"\n</{tag}>")
            continue
        # đoạn văn — gom tới dòng trống / heading / bảng / list
        para = [s]
        i += 1
        while i < n:
            si = lines[i].strip()
            if (not si or si.startswith("#") or si.startswith("|")
                    or si.startswith("```") or si.startswith("~~~")
                    or re.match(r"^[-*]\s+", si) or re.match(r"^\d+\.\s+", si)):
                break
            para.append(si)
            i += 1
        out.append(f"<p>{inline(' '.join(para), link_map)}</p>")
    return "\n".join(out)


def md_to_doc_blocks(md, link_map=None):
    """Trả về list block {'type':'doc','settings':{num,title,body}} từ nội dung .md."""
    lines = md.splitlines()
    # tìm các heading ## (không phải ###) làm ranh giới block
    idxs = [k for k, l in enumerate(lines) if re.match(r"^##\s+", l)]
    # bỏ các heading không đánh số nằm TRƯỚC heading đánh số đầu tiên
    # (đó là subtitle/header tài liệu, thuộc hero — không phải block nội dung)
    first_num = next((p for p, s in enumerate(idxs)
                      if re.match(r"^##\s+\d+\.\s", lines[s])), None)
    if first_num is not None:
        idxs = idxs[first_num:]
    blocks = []
    for j, start in enumerate(idxs):
        end = idxs[j + 1] if j + 1 < len(idxs) else len(lines)
        head = lines[start][2:].strip()
        m = re.match(r"^(\d+)\.\s+(.*)$", head)
        num, title = (m.group(1), m.group(2)) if m else ("", head)
        # bỏ dòng `---` (ngăn cách md) và dòng blockquote `>` (ghi chú soạn thảo,
        # KHÔNG phải nội dung tài liệu — vd "Trên trang web (epod) sơ đồ... .dl-diagram").
        body_lines = []
        for l in lines[start + 1:end]:
            s = l.strip()
            if s == "---" or s.startswith(">"):
                continue
            body_lines.append(l)
        body = _render_body(body_lines, link_map).strip()
        blocks.append({"type": "doc", "settings": {"num": num, "title": title, "body": body}})
    return blocks


def build_nav(items, current_slug):
    """items: list (tag, label, slug|""). current_slug đánh dấu current=True."""
    nav = []
    for tag, label, slug in items:
        url = f"/pages/{slug}" if slug else ""
        nav.append({"type": "navitem", "settings": {
            "tag": tag, "label": label, "url": url,
            "current": bool(slug) and slug == current_slug}})
    return nav


# ================================================================ HTML -> MD
# Chiều ngược: đồng bộ nội dung epod về file .md sau khi publish.
# Lai: bảng/list/heading/inline -> markdown; .dl-diagram & khối HTML không map
# được -> GIỮ NGUYÊN khối HTML (markdown cho phép nhúng HTML).
from html.parser import HTMLParser

# thẻ khối giữ nguyên HTML (không có tương đương markdown gọn / dễ vỡ)
_KEEP_HTML_CLASSES = ("dl-diagram", "mermaid")


def _unmap_link(url, rev_link_map):
    """/pages/<slug>#anchor -> ./<file>.md#anchor (đảo link_map). Ngoài giữ nguyên."""
    if not rev_link_map:
        return url
    m = re.match(r"/pages/([\w-]+)(#.*)?$", url)
    if not m:
        return url
    slug, frag = m.group(1), (m.group(2) or "")
    fname = rev_link_map.get(slug)
    return f"./{fname}{frag}" if fname else url


# Tiền tố nội bộ đánh dấu một phần tử out[] là list-item; result() gỡ bỏ.
# Ký tự U+0000 không xuất hiện trong nội dung thật nên không đụng độ.
_LI = "\x00"


class _HtmlToMd(HTMLParser):
    """Chuyển một body HTML block -> markdown. Khối cần giữ (dl-diagram) copy thô."""

    def __init__(self, rev_link_map=None):
        super().__init__(convert_charrefs=True)
        self.rev = rev_link_map or {}
        self.out = []          # các đoạn markdown đã hoàn tất
        self.mode = None       # None | 'p' | 'h' | 'li' | 'table'
        self.buf = ""          # text đang gom cho p/h/li
        self.hlevel = 4
        # bảng
        self.rows = []
        self.cur_row = None
        self.cur_cell = None
        # list
        self.list_stack = []   # 'ul'|'ol'
        self.ol_idx = []
        # inline wrap
        self.inline_close = []
        # a href
        self.href = None
        # giữ HTML thô
        self.keep_depth = 0
        self.keep_tag = None
        self.keep_html = ""
        # khối code <pre> -> fence
        self.pre_mode = False
        self.pre_buf = ""

    # ---- helpers
    def _flush_para(self):
        if self.mode in ("p", "h", "li") and self.buf.strip():
            txt = re.sub(r"\s+", " ", self.buf).strip()
            if self.mode == "h":
                level = self.hlevel
                # <h4> tiểu mục đánh số 'x.y.' -> hạ về ### cho khớp .md tay
                if level >= 4 and re.match(r"^\d+\.\d+\.\s", txt):
                    level = 3
                self.out.append("#" * level + " " + txt)
            elif self.mode == "li":
                self.out.append(txt)  # xử lý prefix ở handle list
            else:
                self.out.append(txt)
        self.buf = ""
        self.mode = None

    def _emit_raw_keep(self):
        self.out.append(self.keep_html.strip())
        self.keep_html = ""
        self.keep_tag = None

    # ---- tag
    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        cls = ad.get("class", "")
        # đang trong khối giữ thô -> nối nguyên văn
        if self.keep_tag is not None:
            self.keep_depth += (tag == self.keep_tag)
            self.keep_html += self._raw_tag(tag, attrs)
            return
        # mở khối giữ thô?
        if any(c in cls.split() for c in _KEEP_HTML_CLASSES):
            self._flush_para()
            self.keep_tag = tag
            self.keep_depth = 1
            self.keep_html = self._raw_tag(tag, attrs)
            return

        if tag == "pre":
            self._flush_para()
            self.pre_mode = True
            self.pre_buf = ""
        elif self.pre_mode and tag == "code":
            pass  # <code> trong <pre> chỉ là bao, không chèn backtick
        elif tag in ("h2", "h3", "h4", "h5", "h6"):
            self._flush_para()
            self.mode = "h"
            # data-md-level giữ cấp ### gốc (md2doc render mọi cấp thành <h4>)
            self.hlevel = int(ad.get("data-md-level") or tag[1])
        elif tag == "p":
            self._flush_para()
            self.mode = "p"
        elif tag in ("ul", "ol"):
            self._flush_para()
            self.list_stack.append(tag)
            self.ol_idx.append(0)
        elif tag == "li":
            self._flush_para()
            self.mode = "li"
        elif tag == "table":
            self._flush_para()
            self.mode = "table"
            self.rows = []
        elif tag == "tr":
            self.cur_row = []
        elif tag in ("td", "th"):
            self.cur_cell = ""
            self._cell_active = True
        elif tag == "strong" or tag == "b":
            self._ins("**")
        elif tag == "em" or tag == "i":
            self._ins("*")
        elif tag == "code":
            self._ins("`")
        elif tag == "a":
            self.href = self._unmap(ad.get("href", ""))
            self._ins("[")
        elif tag == "br":
            self._ins(" ")

    def handle_startendtag(self, tag, attrs):
        if self.keep_tag is not None:
            self.keep_html += self._raw_tag(tag, attrs, selfclose=True)
        elif tag == "br":
            self._ins(" ")

    def handle_endtag(self, tag):
        if self.keep_tag is not None:
            if tag == self.keep_tag:
                self.keep_depth -= 1
                self.keep_html += f"</{tag}>"
                if self.keep_depth == 0:
                    self._emit_raw_keep()
            else:
                self.keep_html += f"</{tag}>"
            return

        if tag == "pre":
            code = self.pre_buf.strip("\n")
            self.out.append("```\n" + code + "\n```")
            self.pre_mode = False
            self.pre_buf = ""
        elif self.pre_mode and tag == "code":
            pass
        elif tag in ("h2", "h3", "h4", "h5", "h6", "p"):
            self._flush_para()
        elif tag == "li":
            txt = re.sub(r"\s+", " ", self.buf).strip()
            depth = max(0, len(self.list_stack) - 1)
            indent = "  " * depth
            # _LI đánh dấu để result() nối các item liền kề bằng '\n' thay vì
            # '\n\n' — nếu không, mỗi gạch đầu dòng bị tách thành một đoạn rời.
            if self.list_stack and self.list_stack[-1] == "ol":
                self.ol_idx[-1] += 1
                self.out.append(_LI + f"{indent}{self.ol_idx[-1]}. {txt}")
            else:
                self.out.append(_LI + f"{indent}- {txt}")
            self.buf = ""
            self.mode = None
        elif tag in ("ul", "ol"):
            if self.list_stack:
                self.list_stack.pop()
                self.ol_idx.pop()
        elif tag == "table":
            self._flush_table()
        elif tag == "tr":
            if self.cur_row is not None:
                self.rows.append(self.cur_row)
                self.cur_row = None
        elif tag in ("td", "th"):
            if self.cur_row is not None:
                self.cur_row.append(re.sub(r"\s+", " ", self.cur_cell).strip())
            self.cur_cell = ""
            self._cell_active = False
        elif tag in ("strong", "b"):
            self._ins("**")
        elif tag in ("em", "i"):
            self._ins("*")
        elif tag == "code":
            self._ins("`")
        elif tag == "a":
            self._ins(f"]({self.href})")
            self.href = None

    def handle_data(self, data):
        if self.keep_tag is not None:
            self.keep_html += data
        elif self.pre_mode:
            self.pre_buf += data
        else:
            self._ins(data)

    # ---- low level
    def _ins(self, s):
        if getattr(self, "_cell_active", False):
            self.cur_cell += s
        else:
            self.buf += s

    def _unmap(self, url):
        return _unmap_link(url, self.rev)

    def _flush_table(self):
        if not self.rows:
            self.mode = None
            return
        header = self.rows[0]
        body = self.rows[1:]
        line1 = "| " + " | ".join(header) + " |"
        sep = "|" + "|".join(["---"] * len(header)) + "|"
        out = [line1, sep]
        for r in body:
            r = r + [""] * (len(header) - len(r))
            out.append("| " + " | ".join(r) + " |")
        self.out.append("\n".join(out))
        self.rows = []
        self.mode = None

    @staticmethod
    def _raw_tag(tag, attrs, selfclose=False):
        a = "".join(f' {k}="{v}"' for k, v in attrs)
        return f"<{tag}{a}{'/' if selfclose else ''}>"

    def result(self):
        self._flush_para()
        parts = [x for x in self.out if x.strip(_LI).strip()]
        buf = ""
        for i, x in enumerate(parts):
            is_li = x.startswith(_LI)
            if i:
                # item liền sau item khác: xuống 1 dòng để giữ nguyên khối list
                buf += "\n" if (is_li and parts[i - 1].startswith(_LI)) else "\n\n"
            buf += x[len(_LI):] if is_li else x
        return buf


def html_to_md(body, rev_link_map=None):
    p = _HtmlToMd(rev_link_map)
    p.feed(body or "")
    return p.result()


def blocks_to_md_body(blocks, rev_link_map=None):
    """Ghép các doc block -> phần thân .md (mỗi block = '## num. title' + body md)."""
    parts = []
    for b in blocks:
        s = b.get("settings", {})
        num, title = str(s.get("num", "")).strip(), s.get("title", "")
        head = f"## {num}. {title}" if num else f"## {title}"
        parts.append(head + "\n\n" + html_to_md(s.get("body", ""), rev_link_map))
    return "\n\n---\n\n".join(parts)


def splice_md_body(existing_md, new_body):
    """Giữ header .md cũ (tới trước '## <num>.' đầu tiên), thay phần thân bằng new_body.
    Giữ luôn dòng footer '---\\n*...*' cuối file nếu có."""
    lines = existing_md.splitlines()
    idxs = [k for k, l in enumerate(lines) if re.match(r"^##\s+\d+\.\s", l)]
    if not idxs:
        idxs = [k for k, l in enumerate(lines) if re.match(r"^##\s+", l)]
    if not idxs:
        # không có heading -> nối thêm
        return existing_md.rstrip() + "\n\n" + new_body + "\n"
    header = "\n".join(lines[:idxs[0]]).rstrip()
    return header + "\n\n" + new_body.strip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("dùng: python3 tools/md2doc.py <file.md>")
    md = open(sys.argv[1], encoding="utf-8").read()
    bl = md_to_doc_blocks(md)
    for b in bl:
        print(f'--- num={b["settings"]["num"]!r} title={b["settings"]["title"]!r} (bodylen={len(b["settings"]["body"])})')
    print(f"\nTổng: {len(bl)} block")
