"""A published page → the body of its .md, the other direction.

The .md header above the first '## <num>.' is preserved; only the body is
replaced. See the epod-docs skill for why the .md diff is the check that matters.
"""
import os

from ...resources import pages
from . import link_map
from . import blocks as blocks_mod
from . import md2doc


def run(e, page_id, mdfile, to_stdout=False):
    sd = pages.get_sections(e, page_id)
    blocks = blocks_mod.doc_blocks(sd)
    if not blocks:
        raise SystemExit(f"page {page_id} has no doc blocks.")
    rev = {v: k for k, v in link_map().items()}  # slug -> file.md
    body = md2doc.blocks_to_md_body(blocks, rev_link_map=rev)
    if to_stdout:
        return body, None
    existing = open(mdfile, encoding="utf-8").read() if os.path.isfile(mdfile) else ""
    open(mdfile, "w", encoding="utf-8").write(md2doc.splice_md_body(existing, body))
    return None, {"page": str(page_id), "blocks": len(blocks), "wrote": mdfile}
