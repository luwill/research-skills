"""筛选判定的评估基座。

项目原本只有**检索**召回指标（metrics.py），没有任何**筛选**精度指标。
换判定器（换模型、换后端、改阈值）时，"这次是变好还是变坏"无从回答。

这一层的纪律：
- 金标（真人裁决）与银标（模型判定）分开报。实测银标纳入约 21% 是错的，
  拿它当真值算出来的精度是天花板，不是真相。
- 每个比率带 Wilson 区间。44 条纳入即使 100% 敏感，下界也只有约 92%——
  不带区间就会把"没测出问题"说成"证明了没问题"。
- 错误排除不可逆，错误纳入只是多读一篇全文。两者绝不能混进同一个 F1 里。
"""

from __future__ import annotations

import pytest

from litsearch.dedupe import CanonicalRecord
from litsearch.screen import Decision, MergedDecision, Verdict
from litsearch.screen_eval import (
    Prediction,
    Reference,
    auc,
    confusion,
    disagreements_csv,
    predictions_from_round,
    predictions_from_scores,
    reference_from_round,
    reliability,
    render_markdown,
    sweep,
    wilson,
)


def merged(
    key: str,
    decision: str,
    *,
    needs_human: bool = False,
    by: str | None = None,
) -> MergedDecision:
    return MergedDecision(
        record_key=key,
        decision=Decision(decision),
        needs_human=needs_human,
        reason="",
        channel_verdicts=[
            Verdict(record_key=key, decision=Decision(decision), confidence=0.9, channel=0)
        ],
        adjudicated_by=by,
    )


def record(key: str, title: str = "A paper", doi: str = "") -> CanonicalRecord:
    return CanonicalRecord(
        key=key, title=title, identifiers={"doi": doi} if doi else {}, sources=("openalex",)
    )


class TestWilson:
    def test_a_perfect_rate_still_has_a_lower_bound_below_one(self):
        lo, hi = wilson(44, 44)

        assert hi == pytest.approx(1.0)
        assert 0.90 < lo < 0.95, f"44/44 的下界应在 0.92 附近，得到 {lo}"

    def test_a_small_sample_is_wider_than_a_large_one(self):
        narrow = wilson(90, 100)
        wide = wilson(9, 10)

        assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])

    def test_no_observations_spans_the_whole_interval(self):
        assert wilson(0, 0) == (0.0, 1.0)

    def test_bounds_stay_inside_zero_and_one(self):
        for k, n in ((0, 5), (5, 5), (1, 3)):
            lo, hi = wilson(k, n)
            assert 0.0 <= lo <= hi <= 1.0


class TestAuc:
    def test_perfect_separation_is_one(self):
        assert auc([0.9, 0.8], [0.2, 0.1]) == 1.0

    def test_reversed_separation_is_zero(self):
        assert auc([0.1, 0.2], [0.8, 0.9]) == 0.0

    def test_ties_count_as_half(self):
        assert auc([0.5], [0.5]) == 0.5

    def test_an_empty_side_has_no_auc(self):
        assert auc([], [0.1]) is None
        assert auc([0.1], []) is None


class TestReference:
    def test_human_adjudicated_records_are_gold_the_rest_silver(self):
        ref = reference_from_round(
            {
                "a": merged("a", "include", by="louwill"),
                "b": merged("b", "exclude"),
            },
            gold_keys=frozenset(),
        )

        assert ref.tier == {"a": "gold", "b": "silver"}
        assert ref.labels == {"a": Decision.INCLUDE, "b": Decision.EXCLUDE}

    def test_records_still_queued_carry_no_label(self):
        """还在人工队列里的记录没有结论，不能当真值用。"""
        ref = reference_from_round(
            {"a": merged("a", "unclear", needs_human=True)}, gold_keys=frozenset()
        )

        assert ref.labels == {}

    def test_gold_set_keys_become_must_keep(self):
        ref = reference_from_round(
            {"a": merged("a", "include")}, gold_keys=frozenset({"a"})
        )

        assert ref.must_keep == frozenset({"a"})


class TestConfusion:
    REF = Reference(
        labels={
            "i1": Decision.INCLUDE,
            "i2": Decision.INCLUDE,
            "i3": Decision.INCLUDE,
            "e1": Decision.EXCLUDE,
            "e2": Decision.EXCLUDE,
        },
        tier={"i1": "gold", "i2": "silver", "i3": "silver", "e1": "silver", "e2": "gold"},
        must_keep=frozenset({"i1"}),
    )

    @staticmethod
    def preds(**mapping: str) -> list[Prediction]:
        out = []
        for key, state in mapping.items():
            out.append(
                Prediction(
                    record_key=key,
                    decision=Decision.UNCLEAR if state == "queue" else Decision(state),
                    queued=state == "queue",
                    score=None,
                )
            )
        return out

    def test_counts_split_auto_decisions_from_the_queue(self):
        c = confusion(
            self.preds(i1="include", i2="queue", i3="exclude", e1="exclude", e2="include"),
            self.REF,
        )

        assert (c.tp, c.fp, c.tn, c.fn) == (1, 1, 1, 1)
        assert c.queued == 1
        assert c.queued_include == 1

    def test_the_irreversible_error_is_reported_separately(self):
        """被自动排除的纳入记录，和被送进队列的纳入记录，代价完全不同。"""
        c = confusion(
            self.preds(i1="include", i2="queue", i3="exclude", e1="exclude", e2="exclude"),
            self.REF,
        )

        assert c.missed == 1
        assert c.missed_keys == ("i3",)

    def test_must_keep_violations_are_named(self):
        c = confusion(
            self.preds(i1="exclude", i2="include", i3="include", e1="exclude", e2="exclude"),
            self.REF,
        )

        assert c.must_keep_violations == ("i1",)

    def test_a_tier_filter_restricts_the_population(self):
        c = confusion(
            self.preds(i1="include", i2="exclude", i3="exclude", e1="exclude", e2="exclude"),
            self.REF,
            tier="gold",
        )

        assert c.total == 2
        assert (c.tp, c.tn) == (1, 1)
        assert c.missed == 0

    def test_rates_are_none_when_the_denominator_is_empty(self):
        c = confusion(self.preds(e1="exclude", e2="exclude"), self.REF, tier="gold")

        assert c.auto_include_precision is None
        assert c.auto_exclude_npv is not None

    def test_predictions_without_a_reference_label_are_ignored(self):
        c = confusion(self.preds(unknown="include"), self.REF)

        assert c.total == 0


class TestPredictions:
    def test_a_round_maps_to_predictions(self):
        preds = predictions_from_round(
            {
                "a": merged("a", "include"),
                "q": merged("q", "unclear", needs_human=True),
            }
        )

        by_key = {item.record_key: item for item in preds}
        assert by_key["a"].queued is False
        assert by_key["q"].queued is True

    def test_scores_route_into_three_bands(self):
        preds = predictions_from_scores(
            {"hi": 0.9, "mid": 0.4, "lo": 0.02}, include_at=0.7, exclude_below=0.1
        )

        by_key = {item.record_key: item for item in preds}
        assert by_key["hi"].decision is Decision.INCLUDE and not by_key["hi"].queued
        assert by_key["mid"].queued is True
        assert by_key["lo"].decision is Decision.EXCLUDE and not by_key["lo"].queued
        assert by_key["hi"].score == 0.9

    def test_the_bands_must_not_overlap(self):
        with pytest.raises(ValueError):
            predictions_from_scores({}, include_at=0.3, exclude_below=0.5)


class TestSweep:
    def test_a_lower_exclude_band_never_misses_more(self):
        scores = {"i1": 0.5, "i2": 0.08, "e1": 0.01}
        ref = Reference(
            labels={
                "i1": Decision.INCLUDE,
                "i2": Decision.INCLUDE,
                "e1": Decision.EXCLUDE,
            },
            tier={k: "silver" for k in ("i1", "i2", "e1")},
            must_keep=frozenset(),
        )

        rows = sweep(scores, ref, grid=(0.02, 0.1))

        missed = {row.exclude_below: row.missed for row in rows}
        assert missed[0.02] == 0
        assert missed[0.1] == 1


class TestReliability:
    def test_bins_report_observed_rate_against_predicted(self):
        scores = {f"k{i}": 0.05 for i in range(4)} | {f"h{i}": 0.95 for i in range(4)}
        labels = {f"k{i}": Decision.EXCLUDE for i in range(4)} | {
            f"h{i}": Decision.INCLUDE for i in range(4)
        }
        ref = Reference(labels=labels, tier={k: "silver" for k in labels}, must_keep=frozenset())

        bins = reliability(scores, ref, bins=5)

        low = next(b for b in bins if b.lo == 0.0)
        high = next(b for b in bins if b.hi == 1.0)
        assert low.observed == 0.0 and low.n == 4
        assert high.observed == 1.0 and high.n == 4

    def test_empty_bins_are_kept_so_the_gap_is_visible(self):
        ref = Reference(
            labels={"a": Decision.INCLUDE},
            tier={"a": "silver"},
            must_keep=frozenset(),
        )

        bins = reliability({"a": 0.9}, ref, bins=5)

        assert len(bins) == 5
        assert any(b.n == 0 for b in bins)


class TestDisagreementsCsv:
    def test_only_disagreements_appear_and_the_header_matches_adjudicate(self):
        ref = Reference(
            labels={"same": Decision.INCLUDE, "diff": Decision.EXCLUDE},
            tier={"same": "gold", "diff": "gold"},
            must_keep=frozenset(),
        )
        preds = [
            Prediction("same", Decision.INCLUDE, queued=False, score=0.9),
            Prediction("diff", Decision.INCLUDE, queued=False, score=0.8),
        ]

        csv = disagreements_csv(preds, ref, {"diff": record("diff", "Disputed", "10.1/x")})

        header = csv.splitlines()[0]
        assert header.startswith("record_key,decision,reviewer,reason")
        assert "Disputed" in csv
        assert "same" not in csv

    def test_the_csv_round_trips_through_adjudicate(self):
        from litsearch.adjudicate import load_rows

        ref = Reference(
            labels={"diff": Decision.EXCLUDE}, tier={"diff": "gold"}, must_keep=frozenset()
        )
        preds = [Prediction("diff", Decision.INCLUDE, queued=False, score=0.8)]

        csv = disagreements_csv(preds, ref, {"diff": record("diff")})
        filled = csv.replace("diff,,,", "diff,exclude,louwill,核对后维持排除")

        rows = load_rows_from_text(load_rows, filled)

        assert rows[0]["record_key"] == "diff"
        assert rows[0]["decision"] == "exclude"


def load_rows_from_text(load_rows, text: str):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "q.csv"
        path.write_text(text, encoding="utf-8")
        return load_rows(path)


class TestRenderMarkdown:
    def test_silver_metrics_are_labelled_as_a_ceiling(self):
        ref = Reference(
            labels={"a": Decision.INCLUDE, "b": Decision.EXCLUDE},
            tier={"a": "gold", "b": "silver"},
            must_keep=frozenset(),
        )
        preds = [
            Prediction("a", Decision.INCLUDE, queued=False, score=0.9),
            Prediction("b", Decision.EXCLUDE, queued=False, score=0.1),
        ]

        text = render_markdown(
            title="demo", preds=preds, ref=ref, scores={"a": 0.9, "b": 0.1}
        )

        assert "银标" in text and "天花板" in text
        assert "金标" in text

    def test_a_must_keep_violation_is_impossible_to_miss(self):
        ref = Reference(
            labels={"g": Decision.INCLUDE},
            tier={"g": "gold"},
            must_keep=frozenset({"g"}),
        )
        preds = [Prediction("g", Decision.EXCLUDE, queued=False, score=0.01)]

        text = render_markdown(title="demo", preds=preds, ref=ref, scores={"g": 0.01})

        assert "金标种子被自动排除" in text
        assert "g" in text
