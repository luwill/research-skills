#!/usr/bin/env python3
"""PDF ingestion: extract text + layout blocks into a normalized structure.

This is the first step of the scholar-slides pipeline. It produces the raw text
material (with per-block bounding boxes) that the LLM turns into the typed *paper
digest* (see references/ingestion.md), and detects an arXiv id so the caller can
prefer the arXiv LaTeX source (equations + .bib come for free).

Ported from ppt-master's PyMuPDF source-to-markdown step, narrowed to what Stage 1
needs. `detect_arxiv_id` is pure/unit-tested; `extract` is the PyMuPDF integration.
"""
from __future__ import annotations

import json
import re
import sys

_ARXIV_RE = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)
# The paper's OWN id shows up as the first-page stamp: "arXiv:2602.15763v1  [cs.LG]  17 Feb 2026"
# — the id is immediately followed by a [category] tag. A cited preprint in the reference list is
# followed by a period/comma, so requiring the [category] tag rejects reference-list ids.
_ARXIV_STAMP = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})(?:v\d+)?\s*\[", re.IGNORECASE)


def detect_arxiv_id(text, stamp_only: bool = False):
    """Return a bare arXiv id like '1706.03762' (version stripped), or None.

    stamp_only=True requires the official first-page stamp form (id followed by a [category] tag),
    so a journal paper cannot adopt an arXiv id that only appears in its reference list.
    """
    t = text or ""
    m = _ARXIV_STAMP.search(t)
    if m:
        return m.group(1)
    if stamp_only:
        return None
    m = _ARXIV_RE.search(t)
    return m.group(1) if m else None


def _page_blocks(page):
    out = []
    for b in page.get_text("dict").get("blocks", []):
        if b.get("type", 0) != 0:  # 0 = text block
            continue
        text = " ".join(
            span["text"] for line in b.get("lines", []) for span in line.get("spans", [])
        )
        if text.strip():
            out.append({"text": text, "bbox": tuple(b["bbox"])})
    return out


def extract(pdf_path):
    """Return {path, n_pages, meta:{title, arxiv_id}, pages:[{page, blocks, text}], full_text}."""
    import fitz

    doc = fitz.open(pdf_path)
    pages = []
    parts = []
    for i, page in enumerate(doc):
        ptext = page.get_text("text")
        parts.append(ptext)
        pages.append({"page": i + 1, "blocks": _page_blocks(page), "text": ptext})
    full_text = "\n".join(parts)
    # The paper's own arXiv id is the first-page stamp only — scanning full_text would pick up an
    # id cited in the reference list (a different paper) on a journal PDF with no arXiv version.
    meta = {
        "title": (doc.metadata or {}).get("title") or None,
        "arxiv_id": detect_arxiv_id(parts[0] if parts else "", stamp_only=True),
    }
    n_pages = doc.page_count
    doc.close()
    return {
        "path": pdf_path,
        "n_pages": n_pages,
        "meta": meta,
        "pages": pages,
        "full_text": full_text,
    }


def main(argv):
    import argparse

    ap = argparse.ArgumentParser(description="Ingest a PDF into normalized text+layout JSON.")
    ap.add_argument("pdf")
    ap.add_argument("--out", help="write JSON here (default: stdout summary)")
    ap.add_argument("--full", action="store_true", help="include per-block layout in --out")
    args = ap.parse_args(argv)

    d = extract(args.pdf)
    if args.out:
        payload = d if args.full else {k: v for k, v in d.items() if k != "pages"}
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
        print(f"{d['n_pages']} pages ingested (arXiv: {d['meta']['arxiv_id']}) -> {args.out}")
    else:
        print(f"pages={d['n_pages']} arxiv_id={d['meta']['arxiv_id']} title={d['meta']['title']!r}")
        print(f"chars={len(d['full_text'])}")


if __name__ == "__main__":
    main(sys.argv[1:])
