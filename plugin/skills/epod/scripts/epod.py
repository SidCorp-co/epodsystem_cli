#!/usr/bin/env python3
"""
epod.py — CLI tái sử dụng để thao tác trang tài liệu trên epodsystem (store RS).

Gọi HTTP trực tiếp tới MCP endpoint (JSON-RPC/SSE), gửi UTF-8 đúng chuẩn để
KHÔNG hỏng tiếng Việt. Token đọc từ .mcp.json của project.

Cách dùng:
  epod context
  epod list
  epod create --title "..." --slug <slug> [--sections file.json]  # tạo trang mới + publish
  epod get <page_id> [--out file.json]     # lưu toàn bộ sections_data
  epod put <page_id> --in file.json [--no-publish]  # ghi sections_data + publish
  epod list-blocks <page_id>               # liệt kê các block doc (num + title)
  epod anchors <page_id> [--url]           # anchor slug từng block (link chéo #slug)
  epod build-doc <file.md> --slug <slug> [--out f.json] [--no-publish]  # .md -> page (md2doc)
  epod sync-md <page_id> <file.md> [--stdout]   # NGƯỢC: page epod -> phần thân .md (giữ header)
  epod get-block <page_id> <num> [--out body.html]  # xuất body 1 block ra HTML
  epod put-block <page_id> <num> --in body.html [--title "..."] [--no-publish]
  epod publish <page_id>
  epod clear-cache
  epod query '<graphql>'
  epod fix-mojibake <page_id> [--dry]       # sửa tiếng Việt hỏng (encode latin-1/decode utf-8)

CÁCH DỄ NHẤT sửa nội dung 1 mục (khuyên dùng): get-block → sửa HTML thuần → put-block.
  epod get-block 803 2 --out /tmp/b2.html
  # ...sửa /tmp/b2.html (HTML thuần, tiếng Việt bình thường)...
  epod put-block 803 2 --in /tmp/b2.html
Sửa cả trang: get --out → sửa JSON → put --in.

QUY TẮC (đừng vi phạm, sẽ hỏng chữ / mất dữ liệu):
- LUÔN gửi body = json.dumps(..., ensure_ascii=False).encode("utf-8"); header charset=utf-8; r.encoding="utf-8".
- LUÔN publish sau khi update (live render published_sections_data). --no-publish chỉ để nháp.
- get/put trọn sections_data (updatePage thay TOÀN BỘ) — patch trong file, đừng gửi lẻ block.
"""
import argparse, html, json, os, re, sys, requests

MCP_URL = os.environ.get("EPOD_MCP_URL", "https://mcp.epodsystem.com/mcp")

# Map file.md -> slug page (for cross-doc links inside doc bodies).
# The left sidebar nav is menu-driven at runtime (docs-nav), not built from a
# static list here — see the sidebar/menu handling, not this file.
# 00-Handoff is deliberately absent: it is a repo working file, not published.
# A link to it from a published doc would 404 — reference it by path instead.
DOC_LINK_MAP = {
    "01-BRD.md": "brd",
    "02-SRS.md": "srs",
    "03-Tech-Spec.md": "tech-spec",
    "04-Tech-Design.md": "tech-design",
    "05-Build-Plan.md": "build-plan",
    "06-UIUX-Design.md": "uiux-design",
    "07-Business-Dataflow.md": "business-dataflow",
    "08-Test-Plan.md": "test-plan",
    "09-Conventions.md": "conventions",
}

def find_mcp_json():
    # Đi NGƯỢC từ vị trí script + cwd lên tận gốc để tìm .mcp.json (project root).
    # Cho phép chạy script từ bất kỳ đâu, kể cả khi bundled sâu trong .claude/skills/.
    starts = [os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
    seen = set()
    for start in starts:
        d = start
        while d and d not in seen:
            seen.add(d)
            p = os.path.join(d, ".mcp.json")
            if os.path.isfile(p):
                return p
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    raise SystemExit("Không tìm thấy .mcp.json (chứa token epodsystem).")

def load_token():
    if os.environ.get("EPOD_TOKEN"):
        return os.environ["EPOD_TOKEN"]
    cfg = json.load(open(find_mcp_json(), encoding="utf-8"))
    auth = cfg["mcpServers"]["epodsystem"]["headers"].get("Authorization") \
        or cfg["mcpServers"]["epodsystem"]["headers"].get("authorization")
    return auth.split(None, 1)[1] if auth.lower().startswith("bearer") else auth

class Epod:
    def __init__(self):
        self.token = load_token()
        self.sid = None
        self._id = 0
        self._init()

    def _headers(self):
        h = {"Authorization": f"Bearer {self.token}",
             "Content-Type": "application/json; charset=utf-8",
             "Accept": "application/json, text/event-stream"}
        if self.sid:
            h["Mcp-Session-Id"] = self.sid
        return h

    def _post(self, payload):
        # QUAN TRỌNG: UTF-8 bytes, không phải str
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        r = requests.post(MCP_URL, headers=self._headers(), data=data, timeout=90)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r

    def _rpc(self, method, params=None):
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method}
        if params is not None:
            payload["params"] = params
        r = self._post(payload)
        out = None
        for line in r.text.splitlines():
            if line.startswith("data:"):
                out = json.loads(line[5:].strip())
        if not self.sid:
            self.sid = r.headers.get("mcp-session-id")
        return out

    def _init(self):
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                 "clientInfo": {"name": "epod-cli", "version": "1"}})
        # notify
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def tool(self, name, args):
        res = self._rpc("tools/call", {"name": name, "arguments": args})
        if not res or "result" not in res:
            raise SystemExit(f"tool {name} lỗi: {json.dumps(res, ensure_ascii=False)[:400]}")
        txt = "".join(p.get("text", "") for p in res["result"].get("content", []) if p.get("type") == "text")
        try:
            return json.loads(txt)
        except Exception:
            return txt

    # --- high level ---
    def get_sections(self, page_id):
        q = self.tool("graphql_query", {"query": f"query {{ storePage(id: {page_id}) {{ sections_data }} }}"})
        sp = q.get("storePage", q)
        return sp["sections_data"]

    def put_sections(self, page_id, sd, publish=True):
        m = self.tool("graphql_mutation", {
            "query": "mutation Save($id: ID!, $input: UpdatePageInput!){ updatePage(id:$id, input:$input){ id slug status } }",
            "variables": {"id": str(page_id), "input": {"sections_data": sd}},
        })
        result = {"update": m}
        if publish:
            result["publish"] = self.tool("publish_page", {"id": str(page_id)})
            result["clear_cache"] = self.tool("clear_storefront_cache", {})
        return result

    def page_id_by_slug(self, slug):
        pages = self.tool("list_pages", {})
        for p in (pages.get("storePages", pages) if isinstance(pages, dict) else pages):
            if p.get("slug") == slug:
                return str(p.get("id"))
        return None

    def store_id(self):
        ctx = self.tool("get_context", {})
        # get_context trả về nhiều dạng; tìm store id
        for k in ("store_id", "storeId"):
            if isinstance(ctx, dict) and ctx.get(k):
                return str(ctx[k])
        store = (ctx or {}).get("store") if isinstance(ctx, dict) else None
        if isinstance(store, dict) and store.get("id"):
            return str(store["id"])
        raise SystemExit(f"không xác định được store_id từ get_context: {json.dumps(ctx, ensure_ascii=False)[:300]}")

    def create_page(self, title, slug, sd=None, store_id=None, page_type="custom", publish=True):
        sid = store_id or self.store_id()
        created = self.tool("graphql_mutation", {
            "query": "mutation New($input: CreatePageInput!){ createPage(input:$input){ id slug status } }",
            "variables": {"input": {"store_id": str(sid), "page_type": page_type,
                                    "title": title, "slug": slug}},
        })
        page = created.get("createPage", created) if isinstance(created, dict) else created
        pid = page.get("id") if isinstance(page, dict) else None
        if not pid:
            raise SystemExit(f"createPage không trả id: {json.dumps(created, ensure_ascii=False)[:400]}")
        result = {"create": created}
        if sd is not None:
            m = self.tool("graphql_mutation", {
                "query": "mutation Save($id: ID!, $input: UpdatePageInput!){ updatePage(id:$id, input:$input){ id slug status } }",
                "variables": {"id": str(pid), "input": {"content_mode": "sections", "sections_data": sd}},
            })
            result["update"] = m
            if publish:
                result["publish"] = self.tool("publish_page", {"id": str(pid)})
                result["clear_cache"] = self.tool("clear_storefront_cache", {})
        return result

    @staticmethod
    def doc_blocks(sd):
        return [b for b in sd["sections"]["doc"]["blocks"] if b.get("type") == "doc"]

    def find_block(self, sd, num):
        for b in self.doc_blocks(sd):
            if str(b["settings"].get("num")) == str(num):
                return b
        return None

    # --- theme files (section/snippet/asset liquid, css, js) ---
    def get_theme_file(self, path, theme_id=None):
        args = {"path": path}
        if theme_id:
            args["theme_id"] = str(theme_id)
        res = self.tool("get_theme_file", args)
        tf = res.get("themeFile", res) if isinstance(res, dict) else res
        return tf.get("content") if isinstance(tf, dict) else tf

    def put_theme_file(self, path, content, theme_id=None, content_type=None, publish=True):
        args = {"path": path, "content": content}
        if theme_id:
            args["theme_id"] = str(theme_id)
        if content_type:
            args["content_type"] = content_type
        result = {"upsert": self.tool("upsert_theme_file", args)}
        if publish:
            result["clear_cache"] = self.tool("clear_storefront_cache", {})
        return result

def slugify(s):
    """Khớp hàm slugify trong sections/doc-layout.liquid:
    lowercase -> thay [^a-z0-9À-ỹ]+ bằng '-' -> trim '-' -> cắt 60 ký tự.
    Dùng để suy anchor id của block (link chéo #slug)."""
    s = html.unescape(s or "").lower()  # &amp; -> & (khớp textContent DOM)
    s = re.sub(r"[^a-z0-9À-ỹ]+", "-", s)
    s = s.strip("-")
    return s[:60]

def demojibake(s):
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s

def walk(obj, fn):
    if isinstance(obj, dict):
        return {k: walk(v, fn) for k, v in obj.items()}
    if isinstance(obj, list):
        return [walk(x, fn) for x in obj]
    return fn(obj)

MOJIBAKE_RE = re.compile(r"Ã.|á»|áº|Æ°|Ä[^\s]")

def main():
    epilog = (
        "VÍ DỤ (sửa 1 mục — khuyên dùng):\n"
        "  epod list-blocks 803\n"
        "  epod get-block 803 2 --out /tmp/b2.html\n"
        "  # sửa /tmp/b2.html (HTML thuần, tiếng Việt bình thường)\n"
        "  epod put-block 803 2 --in /tmp/b2.html\n\n"
        "Trang tài liệu: 801=BRD, 803=SRS, 804=Tech Spec.\n"
        "LƯU Ý: mọi lệnh ghi (put/put-block/fix-mojibake) tự publish + clear cache.\n"
        "Token lấy từ .mcp.json; script luôn gửi UTF-8 nên KHÔNG hỏng tiếng Việt.\n"
        "Verify sau khi ghi: mở https://rs.epodsystem.com/pages/<slug>?v=N bằng trình duyệt."
    )
    ap = argparse.ArgumentParser(
        prog="epod",
        description="CLI thao tác trang tài liệu epodsystem (store RS) — gọi HTTP trực tiếp, gửi UTF-8 đúng.",
        epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="<command>")
    sub.add_parser("context", help="in org/store/theme id hiện tại")
    sub.add_parser("list", help="liệt kê các trang CMS (id/slug/status)")
    sub.add_parser("clear-cache", help="xóa cache storefront")
    g = sub.add_parser("get", help="lấy TOÀN BỘ sections_data của trang")
    g.add_argument("page_id"); g.add_argument("--out", help="lưu ra file JSON (mặc định in ra stdout)")
    p = sub.add_parser("put", help="ghi TOÀN BỘ sections_data từ file JSON rồi publish")
    p.add_argument("page_id"); p.add_argument("--in", dest="infile", required=True, help="file JSON sections_data"); p.add_argument("--no-publish", action="store_true", help="chỉ lưu nháp, không publish")
    cr = sub.add_parser("create", help="tạo trang CMS mới (page_type=custom) rồi set sections_data + publish")
    cr.add_argument("--title", required=True, help="tiêu đề trang")
    cr.add_argument("--slug", required=True, help="slug trang, vd sdd-may-cham-cong")
    cr.add_argument("--sections", dest="infile", help="file JSON sections_data (bỏ trống = tạo trang rỗng)")
    cr.add_argument("--store-id", dest="store_id", help="store id (mặc định lấy từ get_context)")
    cr.add_argument("--no-publish", action="store_true", help="chỉ lưu nháp, không publish")
    lb = sub.add_parser("list-blocks", help="liệt kê block doc của trang (num + title)")
    lb.add_argument("page_id")
    an = sub.add_parser("anchors", help="liệt kê anchor slug từng block (để link chéo #slug)")
    an.add_argument("page_id")
    an.add_argument("--url", action="store_true", help="in kèm URL đầy đủ /pages/<slug>#anchor")
    bd = sub.add_parser("build-doc", help="dựng doc blocks từ file .md rồi tạo/cập nhật page (dùng md2doc)")
    bd.add_argument("mdfile", help="file Markdown, vd docs/04-Tech-Design.md")
    bd.add_argument("--slug", required=True, help="slug page đích (tạo mới nếu chưa có, ngược lại cập nhật)")
    bd.add_argument("--title", help="tiêu đề page (mặc định lấy từ doc_type/tên file)")
    # hero + doc-layout settings (English defaults; override per doc as needed)
    bd.add_argument("--heading", default="AI-Assisted YouTube Video Production Pipeline",
                    help="hero heading (project title)")
    bd.add_argument("--mark", default="YT", help="hero mark/badge")
    bd.add_argument("--subheading", help="hero subheading (default: the doc's '### ...' line)")
    bd.add_argument("--chip1", help="hero chip 1")
    bd.add_argument("--chip2", help="hero chip 2")
    bd.add_argument("--chip3", help="hero chip 3")
    bd.add_argument("--note", help="hero note")
    bd.add_argument("--nav-title", dest="nav_title", default="Project Documentation",
                    help="left sidebar heading")
    bd.add_argument("--toc-title", dest="toc_title", default="On this page",
                    help="right TOC heading")
    bd.add_argument("--out", help="chỉ ghi sections_data ra file JSON, KHÔNG đẩy lên epod")
    bd.add_argument("--no-publish", action="store_true", help="chỉ lưu nháp, không publish")
    sm = sub.add_parser("sync-md", help="đồng bộ NGƯỢC: đọc page epod (đã publish) → ghi lại phần thân file .md")
    sm.add_argument("page_id", help="id page nguồn trên epod")
    sm.add_argument("mdfile", help="file .md đích — GIỮ header cũ, chỉ thay phần thân từ '## <num>.'")
    sm.add_argument("--stdout", action="store_true", help="in ra stdout thay vì ghi đè file")
    gb = sub.add_parser("get-block", help="xuất body HTML của 1 block (theo num) để sửa")
    gb.add_argument("page_id"); gb.add_argument("num", help="số thứ tự block, xem list-blocks"); gb.add_argument("--out", help="lưu ra file .html")
    pb = sub.add_parser("put-block", help="nạp lại body 1 block từ file HTML rồi publish")
    pb.add_argument("page_id"); pb.add_argument("num"); pb.add_argument("--in", dest="infile", required=True, help="file HTML body"); pb.add_argument("--title", help="đổi luôn tiêu đề block"); pb.add_argument("--no-publish", action="store_true")
    pub = sub.add_parser("publish", help="publish trang (đưa sections_data -> live)")
    pub.add_argument("page_id")
    qq = sub.add_parser("query", help="chạy 1 GraphQL query tùy ý")
    qq.add_argument("graphql", help="chuỗi GraphQL, vd 'query { storePages { id slug } }'")
    fm = sub.add_parser("fix-mojibake", help="sửa tiếng Việt hỏng (latin-1<->utf-8) rồi publish")
    fm.add_argument("page_id"); fm.add_argument("--dry", action="store_true", help="chỉ xem, không ghi")
    gt = sub.add_parser("get-theme", help="đọc 1 file theme (section/snippet/asset...) ra stdout hoặc file")
    gt.add_argument("path", help="vd sections/doc-layout.liquid")
    gt.add_argument("--out", help="lưu ra file (mặc định in stdout)")
    gt.add_argument("--theme", dest="theme_id", help="theme id (mặc định active = 2565)")
    pt = sub.add_parser("put-theme", help="ghi 1 file theme từ file cục bộ rồi clear cache")
    pt.add_argument("path", help="đường dẫn theme, vd sections/doc-layout.liquid")
    pt.add_argument("--in", dest="infile", required=True, help="file cục bộ chứa nội dung")
    pt.add_argument("--theme", dest="theme_id", help="theme id (mặc định active = 2565)")
    pt.add_argument("--no-publish", action="store_true", help="không clear cache sau khi ghi")
    a = ap.parse_args()
    e = Epod()

    if a.cmd == "context":
        print(json.dumps(e.tool("get_context", {}), ensure_ascii=False, indent=2))
    elif a.cmd == "list":
        print(json.dumps(e.tool("list_pages", {}), ensure_ascii=False, indent=2))
    elif a.cmd == "clear-cache":
        print(json.dumps(e.tool("clear_storefront_cache", {}), ensure_ascii=False))
    elif a.cmd == "get":
        sd = e.get_sections(a.page_id)
        s = json.dumps(sd, ensure_ascii=False, indent=2)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(s)
            print(f"đã lưu {a.out}")
        else:
            print(s)
    elif a.cmd == "put":
        sd = json.load(open(a.infile, encoding="utf-8"))
        print(json.dumps(e.put_sections(a.page_id, sd, publish=not a.no_publish), ensure_ascii=False, indent=2))
    elif a.cmd == "create":
        sd = json.load(open(a.infile, encoding="utf-8")) if a.infile else None
        print(json.dumps(e.create_page(a.title, a.slug, sd=sd, store_id=a.store_id,
                                        publish=not a.no_publish), ensure_ascii=False, indent=2))
    elif a.cmd == "list-blocks":
        sd = e.get_sections(a.page_id)
        for b in e.doc_blocks(sd):
            print(f'  num={b["settings"].get("num")!s:<4} {b["settings"].get("title","")}')
    elif a.cmd == "build-doc":
        import md2doc
        md = open(a.mdfile, encoding="utf-8").read()
        blocks = md2doc.md_to_doc_blocks(md, link_map=DOC_LINK_MAP)
        if not blocks:
            raise SystemExit("không tách được block nào từ .md (cần heading '## <num>. <title>').")
        # hero: derive doc_type from the '# ...' line and subtitle from the '### ...' line.
        # doc_type = the part before an em-dash/colon in the H1, uppercased and kept short
        # (e.g. "# Test Plan — AI-Assisted ..." -> "TEST PLAN").
        m_dt = re.search(r"^#\s+(.+)$", md, re.M)
        h1 = (m_dt.group(1).strip() if m_dt else a.slug)
        doc_type = re.split(r"\s+[—–:-]\s+", h1)[0].strip().upper()
        title = a.title or h1
        # subheading: only from --subheading. (Don't auto-grab a '### ' line — the
        # first one is usually a section header like "5.1 ...", not a description.)
        hero_settings = {
            "mark": a.mark, "doc_type": doc_type,
            "heading": a.heading,
            "subheading": a.subheading or "",
            "chip1": a.chip1 or "", "chip2": a.chip2 or "",
            "chip3": a.chip3 or "", "note": a.note or "", "logo": ""}
        sd = {"order": ["doc", "hero"],
              "sections": {
                  "doc": {"type": "doc-layout",
                          "settings": {"nav_title": a.nav_title, "toc_title": a.toc_title},
                          # nav is menu-driven at runtime (docs-nav); no navitem blocks injected
                          "blocks": blocks},
                  "hero": {"type": "brd-hero", "settings": hero_settings}}}
        if a.out:
            open(a.out, "w", encoding="utf-8").write(json.dumps(sd, ensure_ascii=False, indent=2))
            print(f"đã ghi {a.out} · doc={len(blocks)} (chưa đẩy epod)")
        else:
            pid = e.page_id_by_slug(a.slug)
            if pid:
                print(f"page slug={a.slug} đã tồn tại (id={pid}) → cập nhật")
                print(json.dumps(e.put_sections(pid, sd, publish=not a.no_publish), ensure_ascii=False, indent=2))
            else:
                print(f"tạo page mới slug={a.slug}")
                print(json.dumps(e.create_page(title, a.slug, sd=sd, publish=not a.no_publish), ensure_ascii=False, indent=2))
    elif a.cmd == "sync-md":
        import md2doc
        sd = e.get_sections(a.page_id)
        blocks = e.doc_blocks(sd)
        if not blocks:
            raise SystemExit("page không có doc block nào.")
        rev = {v: k for k, v in DOC_LINK_MAP.items()}  # slug -> file.md
        body = md2doc.blocks_to_md_body(blocks, rev_link_map=rev)
        if a.stdout:
            print(body)
        else:
            existing = open(a.mdfile, encoding="utf-8").read() if os.path.isfile(a.mdfile) else ""
            merged = md2doc.splice_md_body(existing, body)
            open(a.mdfile, "w", encoding="utf-8").write(merged)
            print(f"đã đồng bộ {len(blocks)} block từ page {a.page_id} → {a.mdfile} (giữ header cũ)")
    elif a.cmd == "anchors":
        sd = e.get_sections(a.page_id)
        page_slug = None
        if a.url:
            pages = e.tool("list_pages", {})
            for p in (pages.get("storePages", pages) if isinstance(pages, dict) else pages):
                if str(p.get("id")) == str(a.page_id):
                    page_slug = p.get("slug"); break
        for b in e.doc_blocks(sd):
            title = b["settings"].get("title", "")
            anchor = slugify(title)
            if a.url:
                base = f"/pages/{page_slug}" if page_slug else "/pages/<slug>"
                print(f'  num={b["settings"].get("num")!s:<4} {base}#{anchor}')
            else:
                print(f'  num={b["settings"].get("num")!s:<4} #{anchor:<40} {title}')
    elif a.cmd == "get-block":
        sd = e.get_sections(a.page_id)
        b = e.find_block(sd, a.num)
        if not b:
            raise SystemExit(f"không có block num={a.num}")
        body = b["settings"].get("body", "")
        if a.out:
            open(a.out, "w", encoding="utf-8").write(body)
            print(f'đã lưu body block num={a.num} ("{b["settings"].get("title","")}") -> {a.out}')
        else:
            print(body)
    elif a.cmd == "put-block":
        sd = e.get_sections(a.page_id)
        b = e.find_block(sd, a.num)
        if not b:
            raise SystemExit(f"không có block num={a.num}")
        b["settings"]["body"] = open(a.infile, encoding="utf-8").read()
        if a.title:
            b["settings"]["title"] = a.title
        print(json.dumps(e.put_sections(a.page_id, sd, publish=not a.no_publish), ensure_ascii=False, indent=2))
    elif a.cmd == "get-theme":
        content = e.get_theme_file(a.path, theme_id=a.theme_id)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(content or "")
            print(f"đã lưu {a.path} -> {a.out} ({len(content or '')} bytes)")
        else:
            print(content)
    elif a.cmd == "put-theme":
        content = open(a.infile, encoding="utf-8").read()
        print(json.dumps(e.put_theme_file(a.path, content, theme_id=a.theme_id,
                                           publish=not a.no_publish), ensure_ascii=False, indent=2))
    elif a.cmd == "publish":
        print(json.dumps(e.tool("publish_page", {"id": str(a.page_id)}), ensure_ascii=False))
    elif a.cmd == "query":
        print(json.dumps(e.tool("graphql_query", {"query": a.graphql}), ensure_ascii=False, indent=2))
    elif a.cmd == "fix-mojibake":
        sd = e.get_sections(a.page_id)
        found = []
        def scan(x):
            if isinstance(x, str) and MOJIBAKE_RE.search(x):
                found.append(x[:60])
            return x
        walk(sd, scan)
        fixed = walk(sd, demojibake)
        print(f"chuỗi nghi hỏng: {len(found)}")
        for s in found[:5]:
            print("  -", s, "->", demojibake(s)[:60])
        if a.dry:
            print("(dry-run, chưa ghi)")
            return
        if not found:
            print("không có gì để sửa."); return
        print(json.dumps(e.put_sections(a.page_id, fixed), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
