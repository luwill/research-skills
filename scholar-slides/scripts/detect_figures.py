#!/usr/bin/env python3
"""Figure / table inventory + bounding-box localization from a PDF.

Ports the caption-regex *idea* from luwill/paper-slide-deck's `detect-figures.ts`
and EXTENDS it: where that detector only matched caption text (and therefore had to
rasterize whole pages), this one also localizes the figure region via PyMuPDF's
raster-image rects and vector-drawing clusters, so `crop_figure.py` can emit a clean,
single-figure crop instead of a full page.

Output (`figures.json`): one record per detected Figure/Table:
    {id, kind, number, label, caption, page, caption_bbox,
     figure_bbox|null, bbox_source, factual, confidence}

Pure functions (`parse_captions`, `associate_caption_with_figure`) are unit-tested;
`detect()` is the PyMuPDF-bound integration entry point.
"""
from __future__ import annotations

import json
import re
import sys

# Keyword is case-insensitive (scoped flag); the NUMBER stays case-sensitive so a
# roman numeral must be uppercase ("Table III") and we don't match stray lowercase
# letters as romans.
_CAPTION_RE = re.compile(r"^\s*(?i:(?P<kw>Figure|Fig\.?|Table|Tab\.?))\s+(?P<num>\d+|[IVXLCDM]+)\b")


def _kind_of(kw: str) -> str:
    return "figure" if kw.lower().startswith("fig") else "table"


def _caption_score(text: str, end: int) -> int:
    """Rank how caption-like a "Figure N ..."/"Table N ..." block is.

    A real caption uses a separator ("Figure 1:" / "Figure 1.") or a capitalized
    caption word ("Fig. 2 Attention"); an inline body sentence ("Table 2 summarizes
    our results") has a lowercase verb next. Used to beat false positives in dedup.
    """
    rest = text[end:].lstrip()
    if rest[:1] in (":", "."):
        return 2
    first = rest.split()[0] if rest.split() else ""
    if first and (first[0].isupper() or not first[0].isalpha()):
        return 1
    return 0


def parse_captions(blocks):
    """Find caption blocks whose text *starts* with a Figure/Table label.

    `blocks` = [{"text", "bbox": (x0,y0,x1,y1), "page"?}]. Inline references like
    "as shown in Figure 1" do not start with the label and are ignored. Deduped by
    (kind, number), keeping the most caption-like block (separator/capitalized over a
    body sentence), breaking ties by length.
    """
    found = []
    for b in blocks:
        text = b.get("text", "") or ""
        m = _CAPTION_RE.match(text)
        if not m:
            continue
        kind = _kind_of(m.group("kw"))
        num = m.group("num")
        found.append((_caption_score(text, m.end()), {
            "kind": kind,
            "number": num,
            "label": f"{'Figure' if kind == 'figure' else 'Table'} {num}",
            "caption": " ".join(text.split()).strip(),
            "caption_bbox": tuple(b["bbox"]),
            "page": b.get("page"),
        }))

    best = {}
    for score, c in found:
        key = (c["kind"], c["number"])
        rank = (score, len(c["caption"]))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, c)
    return [c for _, c in best.values()]


def _overlap_x(a, b) -> float:
    return min(a[2], b[2]) - max(a[0], b[0])


def associate_caption_with_figure(caption_bbox, candidate_rects, page_rect, kind,
                                  seed_max_gap_frac: float = 0.5,
                                  merge_gap_frac: float = 0.10):
    """Localize the figure/table region a caption belongs to.

    Convention: a *figure* caption sits BELOW its figure; a *table* caption sits ABOVE
    its table. We pick the nearest same-side candidate rect that horizontally overlaps
    the caption (the "seed"), then grow a cluster of vertically contiguous, overlapping
    rects (handles multi-panel figures and vector drawings split into many paths), and
    return the union. Returns None when nothing plausible is on the expected side.
    """
    cx0, cy0, cx1, cy1 = caption_bbox
    page_h = page_rect[3] - page_rect[1]
    seed_max_gap = seed_max_gap_frac * page_h
    merge_gap = merge_gap_frac * page_h

    side = []
    for r in candidate_rects:
        if _overlap_x(caption_bbox, r) <= 0:
            continue
        if kind == "figure":
            if r[3] <= cy0 + 2:                 # rect ends above the caption
                side.append((cy0 - r[3], r))    # gap = caption-top minus rect-bottom
        else:                                   # table: caption above, table below
            if r[1] >= cy1 - 2:
                side.append((r[1] - cy1, r))
    if not side:
        return None

    side.sort(key=lambda t: t[0])
    seed_gap, seed = side[0]
    if seed_gap > seed_max_gap:
        return None

    cluster = [seed]
    changed = True
    while changed:
        changed = False
        cspan = (min(r[0] for r in cluster), min(r[1] for r in cluster),
                 max(r[2] for r in cluster), max(r[3] for r in cluster))
        for _, r in side:
            if any(r is cr or r == cr for cr in cluster):
                continue
            if _overlap_x(cspan, r) <= 0:
                continue
            vgap = max(cspan[1], r[1]) - min(cspan[3], r[3])  # >0 if disjoint vertically
            if vgap <= merge_gap:
                cluster.append(r)
                changed = True

    x0 = min(r[0] for r in cluster)
    y0 = min(r[1] for r in cluster)
    x1 = max(r[2] for r in cluster)
    y1 = max(r[3] for r in cluster)
    return (x0, y0, x1, y1)


def strip_margin_bands(rects, page_rect,
                       header_frac: float = 0.06, footer_frac: float = 0.06):
    """Drop page furniture (running head / running foot) before region-growing.

    A journal page's running head ("Article  https://doi.org/...") and running foot
    (page number / journal name) live in the top/bottom margin and are NOT part of any
    figure — but they x-overlap the figure and sit close enough that the region-grower
    would otherwise absorb them, so every crop carries the paper's own header/DOI band.

    Geometric and journal-agnostic: remove any rect lying *entirely* inside the top
    `header_frac` or bottom `footer_frac` of the page. "Entirely inside" is deliberate —
    a real figure that dips into the margin band straddles the edge and is kept, never
    clipped. Real figure content essentially never sits wholly within the page margin.
    """
    page_h = page_rect[3] - page_rect[1]
    header_bottom = page_rect[1] + header_frac * page_h
    footer_top = page_rect[3] - footer_frac * page_h
    out = []
    for r in rects:
        in_header = r[3] <= header_bottom      # whole rect above the header cutoff
        in_footer = r[1] >= footer_top         # whole rect below the footer cutoff
        if in_header or in_footer:
            continue
        out.append(r)
    return out


_PANEL_LETTERS = "abcdefgh"


def _contiguous_run(letters) -> int:
    """Length of the a,b,c,... prefix present in `letters` (stops at the first gap)."""
    n = 0
    for ch in _PANEL_LETTERS:
        if ch in letters:
            n += 1
        else:
            break
    return n


def detect_panels(label_spans, figure_bbox, tol_frac: float = 0.045, min_panels: int = 3):
    """Localize sub-panels of a multi-panel figure so the spec can show ONE panel enlarged.

    `label_spans` = single-letter text spans [{"text","bbox","font","size"}]. Real panel labels
    are one bold display-font family placed at each panel's top-left; caption sub-labels
    ("a, ... b, ...") are a *different, smaller* font. We keep only spans inside the figure region,
    pick the style group (font, size) whose letters form the longest contiguous a,b,c… run, and
    require >= `min_panels` — otherwise return [] (not a multi-panel figure, or detection is
    unreliable, so the caller shows the whole figure).

    Each panel's bbox is derived from its label anchor by nearest-neighbour boundaries: the panel
    extends right to the next label in the same row and down to the next label in the same column,
    else to the figure edge. Anchors are reliable; the bbox is a good-enough sub-crop (crop padding
    absorbs small slack). Returns [{label, bbox}] ordered by label.
    """
    fx0, fy0, fx1, fy1 = figure_bbox
    # keep only single-letter labels whose center sits inside the figure region
    inside = []
    for s in label_spans:
        t = (s.get("text") or "").strip()
        if len(t) != 1 or t not in _PANEL_LETTERS:
            continue
        b = s["bbox"]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if fx0 - 2 <= cx <= fx1 + 2 and fy0 - 2 <= cy <= fy1 + 2:
            inside.append(s)

    # group by (font, rounded size); within a group keep the top-left-most span per letter
    groups: dict = {}
    for s in inside:
        key = (s.get("font", ""), round(s.get("size", 0)))
        letters = groups.setdefault(key, {})
        t = s["text"].strip()
        prev = letters.get(t)
        if prev is None or (s["bbox"][1], s["bbox"][0]) < (prev["bbox"][1], prev["bbox"][0]):
            letters[t] = s

    # choose the style group with the longest a,b,c… run (tie-break: larger font)
    best = None
    for (font, size), letters in groups.items():
        run = _contiguous_run(letters)
        score = (run, size)
        if best is None or score > best[0]:
            best = (score, letters, run)
    if best is None or best[2] < min_panels:
        return []

    _, letters, run = best
    chosen = {ch: letters[ch] for ch in _PANEL_LETTERS[:run]}
    anchors = {ch: (sp["bbox"][0], sp["bbox"][1]) for ch, sp in chosen.items()}
    rtol = tol_frac * (fy1 - fy0)
    ctol = tol_frac * (fx1 - fx0)

    panels = []
    for ch in _PANEL_LETTERS[:run]:
        x, y = anchors[ch]
        rights = [ox for (ox, oy) in anchors.values() if ox > x + ctol and abs(oy - y) <= rtol]
        bottoms = [oy for (ox, oy) in anchors.values() if oy > y + rtol and abs(ox - x) <= ctol]
        right = min(rights) if rights else fx1
        bottom = min(bottoms) if bottoms else fy1
        panels.append({"label": ch,
                       "bbox": (round(x, 1), round(y, 1), round(right, 1), round(bottom, 1))})
    return panels


def grow_figure_region(caption_bbox, content_rects, page_rect, kind,
                       gap_thresh_frac: float = 0.038):
    """Localize a figure/table by region-growing over ALL content rects.

    Unlike `associate_caption_with_figure` (which only unions image/vector rects),
    this also absorbs TEXT rects, so it captures attention-style figures made of page
    text tokens + faint lines, and text-grid tables. It floods outward from the caption
    edge, absorbing any rect that x-overlaps the running region and is within
    `gap_thresh_frac * page_height` vertically — stopping at the paragraph gap that
    separates the figure from surrounding body text. Returns None if nothing absorbed.
    """
    cx0, cy0, cx1, cy1 = caption_bbox
    gap = gap_thresh_frac * (page_rect[3] - page_rect[1])
    above = kind == "figure"

    if above:
        pool = [r for r in content_rects if r[3] <= cy0 + 2]   # strictly above caption
        region = [cx0, cy0, cx1, cy0]                          # zero-height seed at caption top
    else:
        pool = [r for r in content_rects if r[1] >= cy1 - 2]   # strictly below caption
        region = [cx0, cy1, cx1, cy1]

    changed = True
    while changed:
        changed = False
        for r in list(pool):
            if min(region[2], r[2]) - max(region[0], r[0]) <= 0:      # no x overlap
                continue
            vgap = max(region[1], r[1]) - min(region[3], r[3])        # >0 if disjoint
            if vgap <= gap:
                region = [min(region[0], r[0]), min(region[1], r[1]),
                          max(region[2], r[2]), max(region[3], r[3])]
                pool.remove(r)
                changed = True

    if above:
        if region[1] >= cy0 - 1:          # nothing absorbed above
            return None
        region[3] = min(region[3], cy0)   # never include the caption itself
    else:
        if region[3] <= cy1 + 1:
            return None
        region[1] = max(region[1], cy1)
    return tuple(region)


# --------------------------------------------------------------------------- #
# PyMuPDF-bound integration
# --------------------------------------------------------------------------- #
def _page_text_blocks(page):
    blocks = []
    for b in page.get_text("dict").get("blocks", []):
        if b.get("type", 0) != 0:
            continue
        text = " ".join(
            span["text"] for line in b.get("lines", []) for span in line.get("spans", [])
        )
        if text.strip():
            blocks.append({"text": text, "bbox": tuple(b["bbox"])})
    return blocks


def _page_letter_spans(page):
    """Single-letter text spans on a page with font + size (panel-label candidates)."""
    spans = []
    for b in page.get_text("dict").get("blocks", []):
        if b.get("type", 0) != 0:
            continue
        for line in b.get("lines", []):
            for s in line.get("spans", []):
                t = (s.get("text") or "").strip()
                if len(t) == 1:
                    spans.append({"text": t, "bbox": tuple(s["bbox"]),
                                  "font": s.get("font", ""), "size": s.get("size", 0)})
    return spans


def _content_rects(page):
    """All localizable content on a page: text blocks + raster images + vector drawings.

    Page header/footer rules and hairlines are dropped; everything else is a candidate
    for the figure/table region grower.
    """
    rects = [b["bbox"] for b in _page_text_blocks(page)]
    try:
        for im in page.get_image_info(xrefs=False):
            bb = im.get("bbox")
            if bb:
                rects.append(tuple(bb))
    except Exception:
        pass
    pw = page.rect.width
    try:
        for dr in page.get_drawings():
            r = dr["rect"]
            w, h = r.width, r.height
            if w <= 1 or h <= 1:            # hairline or speck
                continue
            if w > 0.9 * pw and h < 3:      # full-width horizontal rule
                continue
            rects.append((r.x0, r.y0, r.x1, r.y1))
    except Exception:
        pass
    return rects


def detect(pdf_path):
    import fitz

    doc = fitz.open(pdf_path)
    records = []
    for i, page in enumerate(doc):
        pageno = i + 1
        tblocks = [{**b, "page": pageno} for b in _page_text_blocks(page)]
        caps = parse_captions(tblocks)
        prect = (page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1)
        # Drop running head/foot so a crop never carries the paper's "Article"/DOI band.
        cand = strip_margin_bands(_content_rects(page), prect)
        letter_spans = _page_letter_spans(page)
        page_h = prect[3] - prect[1]
        for c in caps:
            kind = c["kind"]
            bbox = grow_figure_region(c["caption_bbox"], cand, prect, kind)
            # Plausibility guard: an over-grown region (table rows merged into the body
            # paragraphs below, or a figure that swallowed the page) is unreliable. Drop
            # and flag it rather than emit a wrong crop — honesty over a silent bad bbox.
            max_h_frac = 0.85 if kind == "figure" else 0.5
            if bbox and (bbox[3] - bbox[1]) > max_h_frac * page_h:
                bbox = None
            # Multi-panel figures: emit sub-panel regions so the spec can show ONE panel
            # enlarged (fixes the illegible a–f grid). Only for localized figures.
            panels = []
            if bbox and kind == "figure":
                panels = detect_panels(letter_spans, bbox)
            records.append({
                "id": f"{kind}-{c['number']}".lower(),
                "kind": kind,
                "number": c["number"],
                "label": c["label"],
                "caption": c["caption"],
                "page": pageno,
                # tables are rebuilt as real data tables downstream; the crop (if any) is
                # only a reference snapshot. Figures are reused as the cropped image asset.
                "render_as": "data" if kind == "table" else "image",
                "caption_bbox": list(c["caption_bbox"]),
                "figure_bbox": list(bbox) if bbox else None,
                "panels": [{"label": p["label"], "bbox": list(p["bbox"])} for p in panels],
                "bbox_source": "region" if bbox else "none",
                "factual": True,  # figures/tables default factual: reuse, never redraw
                "confidence": "high" if bbox else "low",
            })
    doc.close()

    best = {}
    for f in records:
        k = f["id"]
        cur = best.get(k)
        if cur is None:
            best[k] = f
            continue
        better = (bool(f["figure_bbox"]) and not cur["figure_bbox"]) or (
            bool(f["figure_bbox"]) == bool(cur["figure_bbox"])
            and len(f["caption"]) > len(cur["caption"])
        )
        if better:
            best[k] = f
    # stable order: by page then label
    return sorted(best.values(), key=lambda f: (f["page"], f["kind"], f["number"]))


def main(argv):
    import argparse

    ap = argparse.ArgumentParser(description="Detect figures/tables + bboxes in a PDF.")
    ap.add_argument("pdf")
    ap.add_argument("--out", help="write figures.json here (default: stdout)")
    args = ap.parse_args(argv)
    figs = detect(args.pdf)
    payload = json.dumps(figs, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(payload)
        n_loc = sum(1 for f in figs if f["figure_bbox"])
        print(f"{len(figs)} figures/tables detected, {n_loc} localized -> {args.out}")
    else:
        print(payload)


if __name__ == "__main__":
    main(sys.argv[1:])
