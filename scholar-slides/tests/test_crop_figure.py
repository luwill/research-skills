"""Unit + integration tests for figure region cropping."""
import os
import crop_figure as cf
import pytest

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "attention.pdf")


class TestPadAndClamp:
    PAGE = (0, 0, 500, 500)

    def test_absolute_padding(self):
        assert cf.pad_and_clamp((100, 100, 200, 200), self.PAGE, pad_abs=10, pad_frac=0) == (90, 90, 210, 210)

    def test_clamps_to_top_left(self):
        r = cf.pad_and_clamp((0, 0, 100, 100), self.PAGE, pad_abs=20)
        assert r[0] == 0 and r[1] == 0

    def test_clamps_to_bottom_right(self):
        r = cf.pad_and_clamp((400, 400, 500, 500), self.PAGE, pad_abs=20)
        assert r[2] == 500 and r[3] == 500

    def test_fractional_padding(self):
        # 100x100 box, frac 0.1 -> 10px each side
        r = cf.pad_and_clamp((100, 100, 200, 200), (0, 0, 1000, 1000), pad_abs=0, pad_frac=0.1)
        assert r == (90, 90, 210, 210)


class TestFigureClip:
    PAGE = (0, 0, 612, 792)

    def test_bottom_pad_stops_above_caption(self):
        # Caption sits flush under the figure (the common case) — the padded clip must NOT
        # swallow the caption band, which produced double captions on slides.
        rec = {"figure_bbox": [100, 100, 500, 300], "caption_bbox": [120, 300, 480, 312]}
        clip = cf.figure_clip(rec, self.PAGE, pad_abs=4.0, pad_frac=0.02)
        assert clip[3] < 300, "clip bottom must stay above the caption top"
        assert clip[1] < 100 and clip[0] < 100 and clip[2] > 500  # other sides still padded

    def test_caption_above_figure_keeps_bottom_pad(self):
        # Tables often carry the caption ON TOP — bottom padding must be unaffected then.
        rec = {"figure_bbox": [100, 100, 500, 300], "caption_bbox": [120, 80, 480, 96]}
        clip = cf.figure_clip(rec, self.PAGE, pad_abs=4.0, pad_frac=0.02)
        assert clip[3] > 300

    def test_no_caption_bbox_pads_normally(self):
        rec = {"figure_bbox": [100, 100, 500, 300]}
        clip = cf.figure_clip(rec, self.PAGE, pad_abs=4.0, pad_frac=0.02)
        assert clip == cf.pad_and_clamp([100, 100, 500, 300], self.PAGE, 4.0, 0.02)


class TestPanelBbox:
    REC = {"id": "figure-3", "page": 5, "figure_bbox": [38, 54, 560, 660],
           "panels": [{"label": "a", "bbox": [40, 54, 228, 170]},
                      {"label": "f", "bbox": [40, 402, 560, 660]}]}

    def test_looks_up_panel_by_label(self):
        assert cf.panel_bbox(self.REC, "a") == [40, 54, 228, 170]
        assert cf.panel_bbox(self.REC, "f") == [40, 402, 560, 660]

    def test_unknown_panel_returns_none(self):
        assert cf.panel_bbox(self.REC, "z") is None

    def test_no_panels_returns_none(self):
        assert cf.panel_bbox({"id": "x", "panels": []}, "a") is None


@pytest.mark.integration
class TestCrop:
    def test_crop_creates_nonempty_png(self, tmp_path):
        out = str(tmp_path / "crop.png")
        cf.crop(FIX, 1, (100, 100, 400, 300), out, dpi=120)
        assert os.path.exists(out)
        from PIL import Image
        im = Image.open(out)
        assert im.width > 0 and im.height > 0
        # 300x200 pt at 120dpi (zoom ~1.667) -> ~500x333 px
        assert im.width > 300
