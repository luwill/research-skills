"""Tests for data-bound charts: the plotted values must equal the spec values exactly."""
import os
import make_chart as mc
import pytest


def test_chart_data_preserves_values_verbatim():
    spec = {"type": "bar", "categories": ["A", "B", "C"], "series": [{"name": "BLEU", "values": [24.6, 25.16, 28.4]}]}
    d = mc.chart_data(spec)
    assert d["categories"] == ["A", "B", "C"]
    assert d["series"][0]["values"] == [24.6, 25.16, 28.4]  # never smoothed/rounded
    assert d["series"][0]["color"]  # an Okabe-Ito color assigned


def test_chart_data_assigns_colorblind_palette():
    d = mc.chart_data({"categories": ["A"], "series": [{"name": "x", "values": [1]}, {"name": "y", "values": [2]}]})
    assert d["series"][0]["color"] != d["series"][1]["color"]
    assert d["series"][0]["color"] in mc.OKABE_ITO


def test_chart_data_rejects_length_mismatch():
    with pytest.raises(ValueError):
        mc.chart_data({"categories": ["A", "B"], "series": [{"name": "x", "values": [1]}]})


def test_chart_data_rejects_malformed():
    with pytest.raises(ValueError):
        mc.chart_data({"categories": ["A"]})


def test_render_creates_nonempty_png(tmp_path):
    out = str(tmp_path / "chart.png")
    mc.render({"type": "bar", "title": "t", "categories": ["A", "B"], "series": [{"name": "v", "values": [1, 2]}], "highlight_max": True}, out)
    assert os.path.exists(out) and os.path.getsize(out) > 1000


# Chart discipline (open-design craft rules): <=8 short category labels stay horizontal —
# rotated ticks read off-register next to the deck's upright type; rotation is the fallback
# for crowded axes, not the default.
def test_tick_rotation_horizontal_for_few_short_labels():
    assert mc.tick_rotation(["Llama", "Mamba", "RWKV-4", "xLSTM[1:1]"]) == 0
    assert mc.tick_rotation([f"M{i}" for i in range(8)]) == 0


def test_tick_rotation_rotates_when_crowded_or_long():
    assert mc.tick_rotation([f"M{i}" for i in range(9)]) > 0          # >8 categories
    assert mc.tick_rotation(["short", "a very long model name here"]) > 0  # long label


# Every data point gets a visible value label (outside the bar, never clipped) — unless the
# chart is too dense for labels to stay legible.
def test_should_label_bars_by_density():
    assert mc.should_label_bars(n_series=1, n_cats=8) is True
    assert mc.should_label_bars(n_series=2, n_cats=6) is True
    assert mc.should_label_bars(n_series=3, n_cats=8) is False  # 24 bars: labels would collide


def test_render_labeled_bars_png(tmp_path):
    out = str(tmp_path / "labeled.png")
    mc.render({"type": "bar", "categories": ["A", "B", "C"], "series": [{"name": "ppl", "values": [13.43, 13.7, 14.25]}]}, out)
    assert os.path.exists(out) and os.path.getsize(out) > 1000
