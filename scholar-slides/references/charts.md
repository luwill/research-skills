# Charts — data-bound plotting from extracted numbers

**Status: live (Stage 5).** A chart is **bound to the exact extracted values**, never an image
model's painted approximation and never a redrawn guess. Use it when you want to *plot* numbers
from the digest (e.g., a baseline comparison) rather than reuse the paper's figure image.

```
node ... # build a spec, then:
./.venv/bin/python scripts/make_chart.py spec.json out/<stem>/figures/chart-1.png
```

## Spec
```jsonc
{
  "type": "bar" | "grouped_bar" | "line",
  "title": "WMT'14 EN-DE BLEU (Table 2)", "x_label": "", "y_label": "BLEU",
  "categories": ["GNMT+RL", "ConvS2S", "MoE", "Transformer (big)"],
  "series": [{ "name": "BLEU EN-DE", "values": [24.6, 25.16, 26.03, 28.4] }],  // verbatim from the digest
  "highlight_max": true
}
```
- Values are plotted **verbatim** — `chart_data` never smooths, rounds, or interpolates them.
- Colors default to the **Okabe–Ito** color-blind-safe palette; multiple series get distinct
  colors; keep a method→color mapping consistent across charts.
- A series whose length ≠ categories is a hard error (you mis-bound the data).

## Integrity
- Fill `values` **only** from the digest's extracted metrics/table cells, each with a
  `source_ref`. If a value isn't in the source, you may not plot it — flag `[UNVERIFIED]`.
- The rendered chart is a normal figure: drop it into an `assertion-evidence` slide as
  `figure.src`, with a caption noting it's a re-plot of the paper's reported numbers (not a
  reproduction of the paper's own figure).

The QA gate's number-grounding still applies to any values you also state in text. Grounding is
robust to PDF line-breaks that split a decimal in the source ("34.\n1" still matches "34.1"), so a
correctly-transcribed chart value is not false-flagged. Echo the plotted values in the caption or
annotation so the gate can verify them — the chart image itself is pixels the gate can't read.

CJK note: `make_chart.py` uses matplotlib, whose default fonts don't render CJK. For a 中文 deck,
either keep axis labels/legend in English (common in practice — the slide title/caption/annotation
carry the Chinese) or configure a CJK font before plotting.
