"""Unit + integration tests for PDF ingestion."""
import os
import ingest_pdf as ing
import pytest

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "attention.pdf")


class TestArxivId:
    def test_modern_id_with_version(self):
        assert ing.detect_arxiv_id("Published as arXiv:1706.03762v5 [cs.CL]") == "1706.03762"

    def test_modern_id_no_version(self):
        assert ing.detect_arxiv_id("see arXiv:2307.08691 for details") == "2307.08691"

    def test_with_space_after_label(self):
        assert ing.detect_arxiv_id("arXiv: 1234.56789") == "1234.56789"

    def test_none_when_absent(self):
        assert ing.detect_arxiv_id("no identifier here") is None

    def test_stamp_only_ignores_reference_list_ids(self):
        # A journal paper with no arXiv version of its OWN, but whose reference list cites arXiv
        # preprints, must NOT adopt a cited id as its own (was: cross-contamination bug).
        refs = "[24] X. Y, 'Some method,' 2016, arXiv:1611.06391. [25] Z. W, 2019, arXiv:1905.04753."
        assert ing.detect_arxiv_id(refs, stamp_only=True) is None

    def test_stamp_only_accepts_first_page_watermark(self):
        # The paper's own id appears as the official first-page stamp: id + [category].
        stamp = "GLM-5: from Vibe Coding\narXiv:2602.15763v1  [cs.LG]  17 Feb 2026"
        assert ing.detect_arxiv_id(stamp, stamp_only=True) == "2602.15763"


@pytest.mark.integration
class TestExtract:
    def test_extract_structure(self):
        d = ing.extract(FIX)
        assert d["n_pages"] >= 10
        assert "Attention Is All You Need" in d["full_text"]
        assert any(len(p["blocks"]) > 0 for p in d["pages"])

    def test_blocks_have_bbox(self):
        d = ing.extract(FIX)
        first_page_blocks = d["pages"][0]["blocks"]
        b = first_page_blocks[0]
        assert "text" in b and "bbox" in b and len(b["bbox"]) == 4
        assert all(isinstance(v, (int, float)) for v in b["bbox"])

    def test_pages_are_one_indexed(self):
        d = ing.extract(FIX)
        assert d["pages"][0]["page"] == 1
