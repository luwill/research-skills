#!/usr/bin/env python3
"""Crop a localized figure/table region from a PDF page to a clean PNG.

This is the fix for luwill/paper-slide-deck's biggest fidelity gap: it rasterizes a
*bounding box* (from detect_figures.py), not the whole page, so the extracted figure
carries no neighboring columns/text. Vector figures stay crisp because we render at a
configurable DPI rather than copying an embedded raster.

`pad_and_clamp` is pure/unit-tested; `crop` is the PyMuPDF integration.
"""
from __future__ import annotations

import json
import sys


def pad_and_clamp(rect, page_rect, pad_abs: float = 4.0, pad_frac: float = 0.0):
    """Expand `rect` by padding, clamped to `page_rect`. pad = pad_abs + pad_frac*size."""
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    px = pad_abs + pad_frac * w
    py = pad_abs + pad_frac * h
    return (
        max(page_rect[0], x0 - px),
        max(page_rect[1], y0 - py),
        min(page_rect[2], x1 + px),
        min(page_rect[3], y1 + py),
    )


def figure_clip(figure_record, page_rect, pad_abs: float = 4.0, pad_frac: float = 0.02):
    """Padded crop rect for a figure that never swallows its own caption band.

    The paper's caption usually sits flush under `figure_bbox`; symmetric padding used to pull
    that text line into the crop, so the slide showed the caption twice (in-image + figcaption).
    When the caption lies below the figure, the clip's bottom is clamped just above it.
    """
    clip = pad_and_clamp(figure_record["figure_bbox"], page_rect, pad_abs, pad_frac)
    cap = figure_record.get("caption_bbox")
    if cap and cap[1] >= figure_record["figure_bbox"][3] - 2:  # caption starts below the figure
        clip = (clip[0], clip[1], clip[2], min(clip[3], cap[1] - 1.5))
    return clip


def panel_bbox(figure_record, label):
    """Return the bbox of the named sub-panel in a figures.json record, or None."""
    for p in figure_record.get("panels") or []:
        if p.get("label") == label:
            return p.get("bbox")
    return None


def crop(pdf_path, page_number, rect, out_path, dpi: int = 200,
         page_rect=None, pad_abs: float = 4.0, pad_frac: float = 0.02):
    """Render `rect` on 1-indexed `page_number` to a PNG at `out_path`. Returns out_path."""
    import fitz

    doc = fitz.open(pdf_path)
    try:
        page = doc[page_number - 1]
        pr = page_rect or (page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1)
        clip = pad_and_clamp(rect, pr, pad_abs=pad_abs, pad_frac=pad_frac)
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=fitz.Rect(*clip))
        pix.save(out_path)
    finally:
        doc.close()
    return out_path


def crop_panel(pdf_path, figure_record, label, out_path, dpi: int = 300):
    """Crop one sub-panel of a multi-panel figure to a legible standalone PNG.

    Panels are cropped tight (no fractional expansion) so the crop does not bleed into the
    neighbouring panel's label. Higher default DPI than a full-figure crop because a single panel
    is enlarged to fill the slide. Raises if the panel label is unknown.
    """
    bbox = panel_bbox(figure_record, label)
    if bbox is None:
        raise ValueError(f"{figure_record.get('id')}: no panel '{label}'")
    return crop(pdf_path, figure_record["page"], bbox, out_path, dpi=dpi,
                pad_abs=1.0, pad_frac=0.0)


def crop_from_inventory(pdf_path, figures, out_dir, dpi: int = 300):
    """Crop every localized figure in a figures.json list. Returns list of results.

    Uses `figure_clip` (caption-safe padding); 300 dpi default so a crop displayed at the
    layout's protagonist height (~560-640 px) stays crisp on a projector.
    """
    import os

    import fitz

    os.makedirs(out_dir, exist_ok=True)
    results = []
    doc = fitz.open(pdf_path)
    try:
        for f in figures:
            bbox = f.get("figure_bbox")
            if not bbox:
                results.append({"id": f["id"], "status": "skipped-no-bbox"})
                continue
            page = doc[f["page"] - 1]
            pr = (page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1)
            clip = figure_clip(f, pr)
            out = os.path.join(out_dir, f"{f['id']}.png")
            crop(pdf_path, f["page"], clip, out, dpi=dpi, pad_abs=0.0, pad_frac=0.0)
            results.append({"id": f["id"], "status": "ok", "path": out})
    finally:
        doc.close()
    return results


def main(argv):
    import argparse

    ap = argparse.ArgumentParser(description="Crop figure regions from a PDF.")
    ap.add_argument("pdf")
    ap.add_argument("figures_json", help="figures.json from detect_figures.py")
    ap.add_argument("--out-dir", default="out/figures")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args(argv)

    with open(args.figures_json, encoding="utf-8") as fh:
        figures = json.load(fh)
    res = crop_from_inventory(args.pdf, figures, args.out_dir, dpi=args.dpi)
    ok = sum(1 for r in res if r["status"] == "ok")
    print(f"cropped {ok}/{len(res)} figures -> {args.out_dir}")
    for r in res:
        if r["status"] != "ok":
            print(f"  [skip] {r['id']}: {r['status']}")


if __name__ == "__main__":
    main(sys.argv[1:])
