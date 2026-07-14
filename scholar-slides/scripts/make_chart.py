#!/usr/bin/env python3
"""Data-bound charts from EXTRACTED numbers — never an image model's painted guess.

A chart is bound to the exact values in its spec (which the model fills from the digest's
extracted metrics). The plotted heights equal the input values verbatim; nothing is smoothed,
rounded, or invented. Uses the Okabe-Ito color-blind-safe palette and a restrained academic style.

`chart_data` (pure: returns exactly what will be plotted) is unit-tested; `render` saves the PNG.
"""
from __future__ import annotations

import json
import sys

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt

OKABE_ITO = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#000000"]


def chart_data(spec):
    """Normalize a chart spec into exactly what will be plotted (values preserved verbatim)."""
    if not spec or "series" not in spec or "categories" not in spec:
        raise ValueError("chart spec needs {categories, series}")
    cats = list(spec["categories"])
    series = []
    for i, s in enumerate(spec["series"]):
        vals = list(s["values"])
        if len(vals) != len(cats):
            raise ValueError(f"series '{s.get('name')}' has {len(vals)} values for {len(cats)} categories")
        series.append({"name": s.get("name", f"series{i+1}"), "values": vals, "color": s.get("color") or OKABE_ITO[i % len(OKABE_ITO)]})
    return {"type": spec.get("type", "bar"), "categories": cats, "series": series,
            "title": spec.get("title"), "x_label": spec.get("x_label"), "y_label": spec.get("y_label"),
            "highlight_max": bool(spec.get("highlight_max"))}


def tick_rotation(categories) -> int:
    """0 (upright, on-register with the deck's type) unless the axis is genuinely crowded:
    >8 categories or a label too long to sit horizontally. Rotation is the fallback, not the default."""
    cats = [str(c) for c in categories]
    if len(cats) > 8 or (cats and max(len(c) for c in cats) > 14):
        return 15
    return 0


def should_label_bars(n_series: int, n_cats: int) -> bool:
    """Every data point gets a visible value label — unless the chart is too dense for the
    labels to stay legible (>12 bars: they collide and lie worse than they inform)."""
    return n_series * n_cats <= 12


def _style(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#d7dbe0", linewidth=0.6)
    ax.set_axisbelow(True)


def render(spec, out_path, dpi=200):
    d = chart_data(spec)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    cats, series = d["categories"], d["series"]
    n = len(series)
    import numpy as np
    x = np.arange(len(cats))

    if d["type"] == "line":
        for s in series:
            ax.plot(x, s["values"], marker="o", color=s["color"], label=s["name"], linewidth=2)
            ax.set_xticks(x); ax.set_xticklabels(cats)
    else:  # bar / grouped_bar
        width = 0.8 / n
        label_bars = should_label_bars(n, len(cats))
        for j, s in enumerate(series):
            offs = (j - (n - 1) / 2) * width
            bars = ax.bar(x + offs, s["values"], width, color=s["color"], label=s["name"])
            if d["highlight_max"] and n == 1:
                mi = max(range(len(s["values"])), key=lambda k: s["values"][k])
                bars[mi].set_edgecolor("#15497a"); bars[mi].set_linewidth(2)
            if label_bars:
                # value OUTSIDE the bar (padding above), never inside where a short bar clips it;
                # %g renders the spec value verbatim (no invented precision)
                ax.bar_label(bars, padding=3, fontsize=9, color="#1a1d21", fmt="%g")
        if label_bars:
            ax.margins(y=0.12)  # headroom so the tallest bar's label never clips
        rot = tick_rotation(cats)
        ax.set_xticks(x)
        ax.set_xticklabels(cats, rotation=rot, ha="right" if rot else "center")

    if d["title"]: ax.set_title(d["title"], fontsize=13, loc="left", color="#1a1d21")
    if d["x_label"]: ax.set_xlabel(d["x_label"], fontsize=11)
    if d["y_label"]: ax.set_ylabel(d["y_label"], fontsize=11)
    if n > 1: ax.legend(frameon=False, fontsize=10)
    _style(ax)
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", transparent=False)
    plt.close(fig)
    return out_path


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="Render a data-bound chart from a spec JSON.")
    ap.add_argument("spec", help="chart spec JSON file")
    ap.add_argument("out", help="output PNG path")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args(argv)
    spec = json.load(open(args.spec, encoding="utf-8"))
    render(spec, args.out, dpi=args.dpi)
    print(f"chart -> {args.out}")


if __name__ == "__main__":
    main(sys.argv[1:])
