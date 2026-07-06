"""Unit tests for figure/table caption detection + bbox association (pure logic).

These cover the caption-regex and geometric-association cores; PyMuPDF-bound
end-to-end detection is exercised by the integration test on the real paper.
"""
import detect_figures as df


def block(text, bbox, page=1):
    return {"text": text, "bbox": bbox, "page": page}


class TestParseCaptions:
    def test_basic_figure_caption(self):
        caps = df.parse_captions(
            [block("Figure 1: The Transformer - model architecture.", (50, 600, 500, 620))]
        )
        assert len(caps) == 1
        c = caps[0]
        assert c["kind"] == "figure"
        assert c["number"] == "1"
        assert c["label"] == "Figure 1"
        assert c["caption"].startswith("Figure 1:")
        assert c["page"] == 1
        assert c["caption_bbox"] == (50, 600, 500, 620)

    def test_abbreviated_fig(self):
        caps = df.parse_captions([block("Fig. 2 Attention visualization", (50, 600, 500, 620))])
        assert len(caps) == 1 and caps[0]["kind"] == "figure" and caps[0]["number"] == "2"

    def test_table_roman_numeral(self):
        caps = df.parse_captions([block("Table III: Results on WMT 2014.", (50, 100, 500, 120))])
        assert len(caps) == 1 and caps[0]["kind"] == "table" and caps[0]["number"] == "III"

    def test_uppercase(self):
        caps = df.parse_captions([block("FIGURE 4. Latency vs sequence length.", (0, 0, 100, 10))])
        assert caps[0]["kind"] == "figure" and caps[0]["number"] == "4"

    def test_inline_reference_not_matched(self):
        caps = df.parse_captions(
            [block("As shown in Figure 1, the model attends to distant tokens.", (50, 300, 500, 320))]
        )
        assert caps == []

    def test_dedupe_keeps_longest_caption(self):
        # a short list-of-figures entry plus the real caption -> keep the real one
        caps = df.parse_captions([
            block("Figure 1", (0, 0, 50, 10)),
            block("Figure 1: The Transformer - model architecture.", (50, 600, 500, 620)),
        ])
        assert len(caps) == 1
        assert caps[0]["caption"].startswith("Figure 1:")

    def test_prefers_colon_caption_over_inline_sentence(self):
        # both blocks start with "Table 2"; the real caption has a ':' separator,
        # the other is a body sentence ("Table 2 summarizes ...") and is longer.
        caps = df.parse_captions([
            block("Table 2 summarizes our results and compares our translation quality and costs.", (0, 0, 1, 1)),
            block("Table 2: The Transformer achieves better BLEU scores than prior models.", (0, 0, 1, 1)),
        ])
        assert len(caps) == 1
        assert caps[0]["caption"].startswith("Table 2:")

    def test_multiple_distinct(self):
        caps = df.parse_captions([
            block("Figure 1: a", (0, 0, 1, 1)),
            block("Figure 2: b", (0, 0, 1, 1)),
            block("Table 1: c", (0, 0, 1, 1)),
        ])
        got = sorted((c["kind"], c["number"]) for c in caps)
        assert got == [("figure", "1"), ("figure", "2"), ("table", "1")]


class TestAssociate:
    PAGE = (0, 0, 560, 720)

    def test_figure_above_caption(self):
        cap = (50, 600, 500, 620)
        rects = [(60, 100, 480, 590)]
        bbox = df.associate_caption_with_figure(cap, rects, self.PAGE, "figure")
        assert bbox is not None
        assert bbox[1] < cap[1]  # figure sits above its caption

    def test_figure_ignores_rect_below(self):
        cap = (50, 300, 500, 320)
        rects = [(60, 400, 480, 500)]  # below the caption -> not this figure
        assert df.associate_caption_with_figure(cap, rects, self.PAGE, "figure") is None

    def test_no_candidates_returns_none(self):
        assert df.associate_caption_with_figure((0, 0, 1, 1), [], self.PAGE, "figure") is None

    def test_requires_horizontal_overlap(self):
        cap = (50, 600, 200, 620)
        rects = [(400, 100, 500, 590)]  # far to the right, no x overlap
        assert df.associate_caption_with_figure(cap, rects, self.PAGE, "figure") is None

    def test_table_below_caption(self):
        cap = (50, 100, 500, 120)
        rects = [(60, 130, 480, 300)]
        bbox = df.associate_caption_with_figure(cap, rects, self.PAGE, "table")
        assert bbox is not None and bbox[1] >= cap[3] - 1

    def test_unions_adjacent_rects(self):
        cap = (50, 600, 500, 620)
        rects = [(60, 100, 480, 300), (60, 310, 480, 590)]  # two stacked panels
        bbox = df.associate_caption_with_figure(cap, rects, self.PAGE, "figure")
        assert bbox is not None
        # union should span both panels
        assert bbox[1] <= 100 + 1 and bbox[3] >= 590 - 1


class TestGrowRegion:
    """Region-growing localizer over ALL content (text+vector+image)."""
    PAGE = (0, 0, 560, 720)

    def test_grows_figure_over_text_tokens(self):
        # narrow centered caption, but a WIDE field of token rows above it
        cap = (200, 600, 360, 615)
        content = [(150, 580, 360, 595), (60, 555, 500, 578), (60, 530, 500, 553)]
        bbox = df.grow_figure_region(cap, content, self.PAGE, "figure")
        assert bbox is not None
        assert bbox[0] <= 70 and bbox[2] >= 490   # widened to the full token field
        assert bbox[3] <= cap[1]                  # does not bleed into the caption

    def test_stops_at_paragraph_gap(self):
        cap = (60, 600, 500, 615)
        content = [(60, 560, 500, 590),   # figure row, 10pt above caption
                   (60, 300, 500, 330)]   # body text far above -> boundary
        bbox = df.grow_figure_region(cap, content, self.PAGE, "figure", gap_thresh_frac=0.06)
        assert bbox is not None and bbox[1] >= 559   # did not grab the far body text

    def test_table_grows_downward(self):
        cap = (60, 100, 500, 115)
        content = [(60, 120, 500, 140), (60, 142, 500, 162)]  # table rows below caption
        bbox = df.grow_figure_region(cap, content, self.PAGE, "table")
        assert bbox is not None and bbox[3] >= 160 and bbox[1] >= cap[3] - 1

    def test_returns_none_when_no_content(self):
        assert df.grow_figure_region((60, 600, 500, 615), [], self.PAGE, "figure") is None


class TestStripMarginBands:
    """Running head / running foot (page furniture) must be dropped before growing, so a
    figure crop never carries the journal's 'Article' header or DOI band. Geometric and
    journal-agnostic: real figure content does not live in the top/bottom page margin."""
    PAGE = (0, 0, 595, 791)  # Nature page: h=791

    def test_removes_full_width_running_head(self):
        header = (40, 20, 561, 34)      # "Article  https://doi.org/..." at the top margin
        figpanel = (50, 51, 500, 300)   # real figure starts just below the band
        kept = df.strip_margin_bands([header, figpanel], self.PAGE)
        assert header not in kept
        assert figpanel in kept

    def test_removes_running_foot(self):
        footer = (40, 772, 200, 786)    # page number / journal foot
        body = (50, 100, 500, 400)
        kept = df.strip_margin_bands([footer, body], self.PAGE)
        assert footer not in kept and body in kept

    def test_keeps_rect_straddling_band_edge(self):
        # a figure that dips slightly into the top band must NOT be clipped away
        straddler = (50, 30, 500, 300)  # y0 inside band, y1 well into the body
        assert df.strip_margin_bands([straddler], self.PAGE) == [straddler]

    def test_keeps_body_rects_untouched(self):
        body = [(60, 100, 500, 200), (60, 210, 500, 300)]
        assert df.strip_margin_bands(body, self.PAGE) == body

    def test_grown_figure_excludes_running_head(self):
        # PANDA regression: header 17pt above the first panel would be bridged by the
        # 30pt grow gap -> without the strip the crop swallows "Article"+DOI. With it,
        # the region top lands below the header band.
        cap = (40, 343, 296, 402)
        header = (40, 20, 561, 34)
        panels = [(50, 51, 500, 120), (50, 125, 500, 343)]
        content = df.strip_margin_bands([header] + panels, self.PAGE)
        bbox = df.grow_figure_region(cap, content, self.PAGE, "figure", gap_thresh_frac=0.06)
        assert bbox is not None
        assert bbox[1] >= 47   # top is below the ~6% header band; header not included


class TestDetectPanels:
    """Sub-panel localization for multi-panel figures, so the spec can show ONE panel enlarged
    instead of an illegible a–f grid. Panel labels are a distinct bold display font at each
    panel's top-left; caption sub-labels ('a, ... b, ...') are a smaller font and are rejected."""
    FIG = (38, 53, 560, 660)  # PANDA figure-3 region

    def span(self, t, x, y, font="GraphikNaturel-Black", size=9.3):
        return {"text": t, "bbox": (x, y, x + 6, y + 9), "font": font, "size": size}

    def test_detects_panel_grid(self):
        # figure-3 real anchors: a top-left; d,e top-right; b,c,f stacked down the left column
        labels = [self.span("a", 39.9, 53.7), self.span("d", 227.8, 76.5), self.span("e", 397.9, 76.5),
                  self.span("b", 39.9, 169.8), self.span("c", 39.9, 285.4), self.span("f", 39.9, 402.1)]
        panels = df.detect_panels(labels, self.FIG)
        assert {p["label"] for p in panels} == set("abcdef")
        a = next(p for p in panels if p["label"] == "a")
        assert a["bbox"][2] <= 228 and a["bbox"][3] <= 170   # bounded right by d, below by b
        f = next(p for p in panels if p["label"] == "f")
        assert f["bbox"][2] >= 500 and f["bbox"][3] >= 655   # spans the full bottom band

    def test_rejects_caption_sublabels_by_style(self):
        # big Black panel labels a,b,c PLUS small Bold caption sub-labels a,b inside the region
        labels = [self.span("a", 39.9, 53.7), self.span("b", 39.9, 169.8), self.span("c", 39.9, 285.4),
                  self.span("a", 113, 600, font="HardingText-Bold", size=7.0),
                  self.span("b", 253, 605, font="HardingText-Bold", size=7.0)]
        panels = df.detect_panels(labels, self.FIG)
        assert {p["label"] for p in panels} == set("abc")   # chose the Black/9.3 style group

    def test_returns_empty_when_not_multipanel(self):
        labels = [self.span("a", 39.9, 53.7), self.span("b", 39.9, 169.8)]  # < min_panels
        assert df.detect_panels(labels, self.FIG) == []

    def test_ignores_labels_outside_figure(self):
        labels = [self.span("a", 39.9, 53.7), self.span("b", 39.9, 169.8), self.span("c", 39.9, 285.4),
                  self.span("d", 39.9, 900)]  # d below the figure region -> excluded
        assert {p["label"] for p in df.detect_panels(labels, self.FIG)} == set("abc")

    def test_requires_contiguous_run_from_a(self):
        # a,b present but the third labelled letter is 'e' (c,d missing) -> run stops at b -> not multipanel
        labels = [self.span("a", 39.9, 53.7), self.span("b", 39.9, 169.8), self.span("e", 39.9, 285.4)]
        assert df.detect_panels(labels, self.FIG) == []
