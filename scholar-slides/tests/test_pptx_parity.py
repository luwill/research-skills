"""Unit + integration tests for PPTX content parity (scripts/verify_pptx_parity.py)."""
import json
import os

import pytest

import verify_pptx_parity as vp

ROOT = os.path.dirname(os.path.dirname(__file__))


class TestNorm:
    def test_strip_math_keeps_inner(self):
        assert vp.strip_math("scaled by $1/\\sqrt{d_k}$ here") == "scaled by 1/\\sqrt{d_k} here"

    def test_norm_collapses_and_lowercases(self):
        assert vp.norm("  PANDA  wins\nboth ") == "panda wins both"


class TestExpectedTexts:
    def test_assertion_evidence(self):
        s = {"layout": "assertion-evidence", "action_title": "PANDA wins",
             "figure": {"src": "figures/f.png", "caption": "Fig 1"}, "annotation": "the takeaway"}
        fields = dict(vp.expected_texts(s))
        assert fields["title"] == "PANDA wins"
        assert fields["figure.caption"] == "Fig 1"
        assert fields["annotation"] == "the takeaway"

    def test_results_table_expects_every_cell(self):
        s = {"layout": "results-table", "action_title": "T",
             "table": {"caption": "Deploy", "columns": [{"label": "M"}, {"label": "V"}],
                       "rows": [["Sensitivity", {"v": "92.9%"}]], "footnote": "note"}}
        texts = [t for _, t in vp.expected_texts(s)]
        assert "92.9%" in texts and "Sensitivity" in texts and "Deploy" in texts and "note" in texts

    def test_paper_title_joins_author_list(self):
        s = {"layout": "paper-title", "title": "X", "authors": ["A", "B"], "venue": "Nature"}
        fields = dict(vp.expected_texts(s))
        assert fields["authors"] == "A, B" and fields["venue"] == "Nature"

    def test_section_has_num_and_title(self):
        assert dict(vp.expected_texts({"layout": "section", "num": "01", "title": "Problem"})) == \
            {"num": "01", "title": "Problem"}


class TestCheckParity:
    def _extracted(self, text, notes="", pic=False, tbl=False):
        return {"text": text, "notes": notes, "has_picture": pic, "has_table": tbl}

    def test_clean_deck_has_no_findings(self):
        deck = {"slides": [
            {"layout": "section", "num": "01", "title": "The problem"},
            {"layout": "assertion-evidence", "action_title": "PANDA wins",
             "figure": {"src": "f.png", "caption": "Fig 1"}, "annotation": "beats readers",
             "speaker_notes": "here is why"},
        ]}
        extracted = [
            self._extracted("01 The problem"),
            self._extracted("PANDA wins Fig 1 beats readers", notes="here is why", pic=True),
        ]
        assert vp.check_parity(deck, extracted) == []

    def test_flags_dropped_annotation(self):
        deck = {"slides": [{"layout": "assertion-evidence", "action_title": "T",
                            "figure": {"src": "f.png"}, "annotation": "the crucial takeaway"}]}
        extracted = [self._extracted("T", pic=True)]  # annotation text missing
        kinds = {(f["kind"], f.get("field")) for f in vp.check_parity(deck, extracted)}
        assert ("missing-text", "annotation") in kinds

    def test_flags_missing_notes(self):
        deck = {"slides": [{"layout": "bullets", "action_title": "T", "points": ["a"],
                            "speaker_notes": "spoken script"}]}
        extracted = [self._extracted("T a", notes="")]
        assert any(f["kind"] == "missing-notes" for f in vp.check_parity(deck, extracted))

    def test_flags_missing_figure_and_table(self):
        deck = {"slides": [
            {"layout": "assertion-evidence", "action_title": "T", "figure": {"src": "f.png"}},
            {"layout": "results-table", "action_title": "U",
             "table": {"columns": [{"label": "M"}], "rows": [["x"]]}},
        ]}
        extracted = [self._extracted("T", pic=False), self._extracted("U x", tbl=False)]
        kinds = {f["kind"] for f in vp.check_parity(deck, extracted)}
        assert "missing-figure" in kinds and "missing-table" in kinds

    def test_superstring_number_does_not_satisfy_dropped_cells(self):
        # Regression: substring matching let an unrelated "59" in the slide text satisfy the
        # dropped table cells "5" and "9" — a false PASS on exactly the load-bearing numbers.
        deck = {"slides": [{"layout": "results-table", "action_title": "T",
                            "table": {"columns": [{"label": "M"}], "rows": [["5", "9"]]}}]}
        extracted = [self._extracted("T 59", tbl=True)]
        fields = {f.get("field") for f in vp.check_parity(deck, extracted)}
        assert "table.cell[0]" in fields and "table.cell[1]" in fields

    def test_word_boundary_still_matches_normal_prose(self):
        deck = {"slides": [{"layout": "bullets", "action_title": "Top-k wins",
                            "points": ["achieves 92.9% at top-k selection."]}]}
        extracted = [self._extracted("Top-k wins \n achieves 92.9% at top-k selection.")]
        assert vp.check_parity(deck, extracted) == []

    def test_native_cells_are_consumed_as_a_multiset(self):
        # Two expected "5" cells need two native "5" cells — one cannot vouch twice.
        deck = {"slides": [{"layout": "results-table", "action_title": "T",
                            "table": {"columns": [{"label": "M"}], "rows": [["5", "5"]]}}]}
        one_cell = {"text": "T 5 5", "notes": "", "has_picture": False,
                    "has_table": True, "cells": ["5"]}
        fields = {f.get("field") for f in vp.check_parity(deck, [one_cell])}
        assert "table.cell[1]" in fields and "table.cell[0]" not in fields

    def test_flags_slide_count_mismatch(self):
        deck = {"slides": [{"layout": "section", "title": "A"}, {"layout": "section", "title": "B"}]}
        extracted = [self._extracted("A")]
        assert any(f["kind"] == "slide-count" for f in vp.check_parity(deck, extracted))


@pytest.mark.integration
@pytest.mark.parametrize("deck_dir", ["out/attention", "out/deepseek_v32", "out/deepseek_conf"])
def test_real_exported_decks_are_faithful(deck_dir):
    deck_json = os.path.join(ROOT, deck_dir, "deck.json")
    pptx = os.path.join(ROOT, deck_dir, "deck", "deck.pptx")
    if not (os.path.exists(deck_json) and os.path.exists(pptx)):
        pytest.skip(f"{deck_dir} not built")
    deck = json.load(open(deck_json, encoding="utf-8"))
    findings = vp.check_parity(deck, vp.extract_from_pptx(pptx))
    assert findings == [], f"parity issues: {findings}"
