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
