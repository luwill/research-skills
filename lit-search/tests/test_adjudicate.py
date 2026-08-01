from __future__ import annotations

import pytest

from litsearch.adjudicate import AdjudicationError, apply_dates, apply_screening, load_rows
from litsearch.dedupe import CanonicalRecord
from litsearch.normalize import WindowStatus
from litsearch.screen import Decision, MergedDecision


def row(key="k1", decision="include"):
    return {
        "record_key": key,
        "decision": decision,
        "reviewer": "reviewer-a",
        "reason": "checked against protocol",
    }


def queued(key="k1"):
    return MergedDecision(
        record_key=key,
        decision=Decision.UNCLEAR,
        needs_human=True,
        reason="channel disagreement",
    )


class TestCsvContract:
    def test_reviewer_and_reason_are_required(self, tmp_path):
        path = tmp_path / "decisions.csv"
        path.write_text("record_key,decision,reviewer,reason\nk1,include,,\n", encoding="utf-8")

        with pytest.raises(AdjudicationError, match="reviewer"):
            load_rows(path)

    def test_duplicate_keys_are_rejected(self, tmp_path):
        path = tmp_path / "decisions.csv"
        path.write_text(
            "record_key,decision,reviewer,reason\nk1,include,a,x\nk1,exclude,b,y\n",
            encoding="utf-8",
        )

        with pytest.raises(AdjudicationError, match="重复"):
            load_rows(path)


class TestScreeningAdjudication:
    def test_human_decision_retains_the_previous_state(self):
        decisions, audit = apply_screening({"k1": queued()}, [row()])

        decided = decisions["k1"]
        assert decided.decision is Decision.INCLUDE
        assert decided.needs_human is False
        assert decided.previous_decision is Decision.UNCLEAR
        assert decided.adjudicated_by == "reviewer-a"
        assert audit[0]["previous_decision"] == "unclear"

    def test_unclear_is_not_a_completed_human_decision(self):
        with pytest.raises(AdjudicationError, match="不能仍为 unclear"):
            apply_screening({"k1": queued()}, [row(decision="unclear")])


class TestDateAdjudication:
    def test_boundary_can_be_explicitly_resolved_without_erasing_evidence(self):
        record = CanonicalRecord(key="k1", title="Paper", window_status=WindowStatus.BOUNDARY)

        revised, audit = apply_dates([record], [row(decision="in_window")])

        assert revised[0].window_status is WindowStatus.IN_WINDOW
        assert revised[0].date_adjudication["previous_status"] == "boundary"
        assert revised[0].date_adjudication["reviewer"] == "reviewer-a"
        assert audit[0]["kind"] == "date"

    def test_date_decision_is_limited_to_strict_window_states(self):
        record = CanonicalRecord(key="k1", title="Paper", window_status=WindowStatus.BOUNDARY)

        with pytest.raises(AdjudicationError, match="in_window"):
            apply_dates([record], [row(decision="boundary")])


class TestDateAdjudicationScope:
    """日期裁定只解决**不确定**，不覆盖已有证据。

    放开的话，一条已经判定并筛选过的 in_window 记录可以被改成 out_of_window，
    此时严格窗口条数减 1 而筛选轮次条数不变，`lit verify` 会报
    screening-corpus-mismatch 并建议「需重新筛选」——而重新筛选并不能消除这个偏差。
    真的日期判错了，该修的是日期证据与 date_priority，不是在这里盖掉结论。
    """

    def _row(self, key, decision="out_of_window"):
        return [{"record_key": key, "decision": decision, "reviewer": "r", "reason": "x"}]

    def test_a_settled_in_window_record_cannot_be_overridden(self):
        record = CanonicalRecord(
            key="k1", title="A", window_status=WindowStatus.IN_WINDOW, sources=["openalex"]
        )

        with pytest.raises(AdjudicationError, match="已有明确日期判定"):
            apply_dates([record], self._row("k1"))

    def test_a_settled_out_of_window_record_cannot_be_overridden(self):
        record = CanonicalRecord(
            key="k1", title="A", window_status=WindowStatus.OUT_OF_WINDOW, sources=["openalex"]
        )

        with pytest.raises(AdjudicationError, match="已有明确日期判定"):
            apply_dates([record], self._row("k1", "in_window"))

    def test_boundary_records_are_still_adjudicable(self):
        record = CanonicalRecord(
            key="k1", title="A", window_status=WindowStatus.BOUNDARY, sources=["openalex"]
        )

        revised, _ = apply_dates([record], self._row("k1", "in_window"))

        assert revised[0].window_status is WindowStatus.IN_WINDOW

    def test_undated_records_are_still_adjudicable(self):
        record = CanonicalRecord(
            key="k1", title="A", window_status=WindowStatus.UNDATED, sources=["openalex"]
        )

        revised, _ = apply_dates([record], self._row("k1"))

        assert revised[0].window_status is WindowStatus.OUT_OF_WINDOW
