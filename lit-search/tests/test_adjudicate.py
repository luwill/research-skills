from __future__ import annotations

import pytest

from litsearch.adjudicate import (
    AdjudicationError,
    apply_dates,
    apply_machine,
    apply_screening,
    load_rows,
)
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


class TestMachineAdjudication:
    """机器裁决走和人工裁决一样的审计轨迹，但必须**看得出来是机器判的**。

    把它记成人工裁定，等于让审计链说谎：事后没人分得清哪些结论有人真的看过。
    """

    @staticmethod
    def machine_row(key="k1", decision="include", reason="与通道 0 一致（0.92）"):
        return {"record_key": key, "decision": decision, "reason": reason}

    def test_it_stamps_the_judge_not_a_person(self):
        updated, _ = apply_machine(
            {"k1": queued()}, [self.machine_row()], judge="jev:jev-1.13.0"
        )

        assert updated["k1"].adjudicated_by == "jev:jev-1.13.0"
        assert updated["k1"].decision is Decision.INCLUDE
        assert updated["k1"].needs_human is False

    def test_the_reason_says_a_machine_decided_it(self):
        updated, _ = apply_machine(
            {"k1": queued()}, [self.machine_row()], judge="jev:jev-1.13.0"
        )

        assert "机器裁定" in updated["k1"].reason
        assert "人工裁定" not in updated["k1"].reason

    def test_the_original_channel_verdicts_and_previous_decision_survive(self):
        updated, _ = apply_machine(
            {"k1": queued()}, [self.machine_row()], judge="jev:jev-1.13.0"
        )

        assert updated["k1"].previous_decision is Decision.UNCLEAR
        assert updated["k1"].adjudication_reason == "与通道 0 一致（0.92）"

    def test_the_audit_rows_carry_the_judge_and_a_timestamp(self):
        _, audit = apply_machine(
            {"k1": queued()}, [self.machine_row()], judge="jev:jev-1.13.0"
        )

        assert audit[0]["reviewer"] == "jev:jev-1.13.0"
        assert audit[0]["kind"] == "screening"
        assert audit[0]["previous_decision"] == "unclear"
        assert audit[0]["adjudicated_at"]

    def test_it_refuses_to_machine_resolve_toward_exclude(self):
        """只向可逆方向自动化。错误纳入只是多读一篇全文，错误排除不可逆。"""
        with pytest.raises(AdjudicationError, match="exclude"):
            apply_machine(
                {"k1": queued()},
                [self.machine_row(decision="exclude")],
                judge="jev:jev-1.13.0",
            )

    def test_an_unknown_record_is_refused(self):
        with pytest.raises(AdjudicationError):
            apply_machine({}, [self.machine_row()], judge="jev:jev-1.13.0")

    def test_it_will_not_overwrite_a_human_decision(self):
        """人工裁决是终审。机器不能把人已经定过的结论再翻一遍。"""
        human = MergedDecision(
            record_key="k1",
            decision=Decision.EXCLUDE,
            needs_human=False,
            reason="人工裁定：不符合 I1",
            adjudicated_by="louwill",
        )

        with pytest.raises(AdjudicationError, match="人工"):
            apply_machine({"k1": human}, [self.machine_row()], judge="jev:jev-1.13.0")

    def test_it_does_not_mutate_the_input(self):
        decisions = {"k1": queued()}

        apply_machine(decisions, [self.machine_row()], judge="jev:jev-1.13.0")

        assert decisions["k1"].needs_human is True
