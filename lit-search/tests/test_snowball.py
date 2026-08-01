"""引文滚雪球的纯逻辑：种子选择、候选提取、批量切分、饱和判据。

**种子集是这一步的全部。** 关键词检索必然漏掉用词不同的论文
（"core infarct estimation"、"tissue-at-risk mapping"），滚雪球正是为此存在。
但它从哪些论文出发，决定了它是"补齐遗漏"还是"把噪声放大一个数量级"：

实测本课题——从 13,920 条**未筛选**的窗口内记录出发，后向候选是 **134,317** 条；
而这 13,920 条里最终会被纳入的大约只有几百条。也就是说绝大部分候选来自
"本来就该被排除"的论文的参考文献列表。系统综述的规范做法是
**从已纳入研究出发**，本模块把这一点做成默认值而不是建议。
"""

from __future__ import annotations

import pytest

from litsearch.dedupe import CanonicalRecord
from litsearch.normalize import WindowStatus
from litsearch.protocol import SnowballConfig, Topic
from litsearch.screen import Decision, MergedDecision
from litsearch.snowball import (
    RoundStat,
    SeedMode,
    backward_candidates,
    batch_terms,
    build_snowball_queries,
    forward_seed_ids,
    is_saturated,
    select_seeds,
)

TOPIC = Topic.model_validate(
    {
        "id": "t",
        "title": "T",
        "window": {"start": "2021-07-01", "end": "2026-07-27"},
        "concepts": {
            "condition": {"required": True, "terms": ["ischemic stroke"]},
            "task": {"required": True, "terms": ["segmentation"]},
        },
        "query_plan": {"combinations": [["condition", "task"]]},
        "criteria": {"include": [{"id": "I1", "text": "x"}]},
        "gold_set": [{"doi": "10.1000/gold"}],
    }
)


def record(
    key,
    *,
    title="Ischemic stroke segmentation",
    abstract="lesion segmentation",
    doi=None,
    pmid=None,
    refs=(),
    status=WindowStatus.IN_WINDOW,
):
    identifiers = {}
    if doi:
        identifiers["doi"] = doi
    if pmid:
        identifiers["pmid"] = pmid
    return CanonicalRecord(
        key=key,
        title=title,
        abstract=abstract,
        identifiers=identifiers,
        referenced_works=list(refs),
        window_status=status,
    )


def verdict(key, decision):
    return MergedDecision(
        record_key=key, decision=Decision(decision), needs_human=False, reason="r"
    )


class TestSelectSeeds:
    def test_included_mode_requires_a_screening_round(self):
        """默认从**已纳入研究**出发。没筛选就滚雪球，等于把噪声放大一个数量级。"""
        with pytest.raises(ValueError, match="筛选"):
            select_seeds([record("a")], TOPIC, SeedMode.INCLUDED, decisions=None)

    def test_included_mode_takes_only_included_records(self):
        records = [record("a"), record("b"), record("c")]
        decisions = {
            "a": verdict("a", "include"),
            "b": verdict("b", "exclude"),
            "c": verdict("c", "include"),
        }

        seeds = select_seeds(records, TOPIC, SeedMode.INCLUDED, decisions=decisions)

        assert [item.key for item in seeds] == ["a", "c"]

    def test_records_awaiting_human_review_are_not_seeds(self):
        """待人工裁定的还不是"已纳入"，不能拿来滚。"""
        pending = MergedDecision(
            record_key="a", decision=Decision.UNCLEAR, needs_human=True, reason="分歧"
        )

        seeds = select_seeds([record("a")], TOPIC, SeedMode.INCLUDED, decisions={"a": pending})

        assert seeds == []

    def test_gold_mode_matches_by_identifier(self):
        records = [record("a", doi="10.1000/gold"), record("b", doi="10.1000/other")]

        seeds = select_seeds(records, TOPIC, SeedMode.GOLD)

        assert [item.key for item in seeds] == ["a"]

    def test_matched_mode_applies_the_local_concept_filter(self):
        records = [
            record("a"),
            record("b", title="Cardiac infarction outcome", abstract="no imaging task"),
        ]

        seeds = select_seeds(records, TOPIC, SeedMode.MATCHED)

        assert [item.key for item in seeds] == ["a"]

    def test_every_mode_drops_out_of_window_records(self):
        """窗口外的论文不是本次综述的纳入对象，不能当作滚雪球起点。"""
        records = [record("a"), record("b", status=WindowStatus.OUT_OF_WINDOW)]

        seeds = select_seeds(records, TOPIC, SeedMode.IN_WINDOW)

        assert [item.key for item in seeds] == ["a"]


class TestBackwardCandidates:
    def test_strips_the_doi_prefix_pubmed_writes(self):
        """PubMed 的参考文献存成 ``doi:10.1007/...``，前缀不剥掉就永远匹配不上语料。"""
        records = [record("a", refs=["doi:10.1007/X"])]

        assert backward_candidates(records, known=set()) == ["10.1007/x"]

    def test_candidates_already_in_the_corpus_are_dropped(self):
        records = [record("a", refs=["doi:10.1/known", "doi:10.1/new"])]

        assert backward_candidates(records, known={"10.1/known"}) == ["10.1/new"]

    def test_duplicates_across_seeds_are_collapsed(self):
        records = [record("a", refs=["doi:10.1/x"]), record("b", refs=["doi:10.1/X"])]

        assert backward_candidates(records, known=set()) == ["10.1/x"]

    def test_non_doi_references_are_ignored(self):
        """只有 DOI 能拿去批量查元数据；其余形态原样丢弃并不影响正确性。"""
        records = [record("a", refs=["PMID12345", "doi:10.1/x"])]

        assert backward_candidates(records, known=set()) == ["10.1/x"]


class TestForwardSeeds:
    def test_only_records_with_a_pmid_can_be_cited_forward(self):
        """Europe PMC 的 ``CITES:`` 语法要求 ``<pmid>_MED``。"""
        records = [record("a", pmid="111"), record("b", doi="10.1/x")]

        assert forward_seed_ids(records) == ["111"]


class TestBatching:
    def test_splits_by_character_budget_not_just_count(self):
        """查询串是 GET 的一部分，超长会 414。实测 200 个 DOI（6,907 字符）即失败。"""
        terms = [f"10.1000/{'x' * 40}{index}" for index in range(50)]

        batches = batch_terms(terms, 'DOI:"{}"', max_chars=600, max_items=100)

        assert len(batches) > 1
        for batch in batches:
            rendered = " OR ".join(f'DOI:"{item}"' for item in batch)
            assert len(rendered) <= 600

    def test_item_cap_applies_even_when_terms_are_short(self):
        batches = batch_terms(
            [str(index) for index in range(250)], "CITES:{}_MED", max_chars=100_000, max_items=100
        )

        assert [len(batch) for batch in batches] == [100, 100, 50]

    def test_a_single_oversized_term_still_gets_its_own_batch(self):
        """宁可发一个注定超长的请求并如实失败，也不能把它悄悄丢掉。"""
        batches = batch_terms(["x" * 500], 'DOI:"{}"', max_chars=100, max_items=100)

        assert batches == [["x" * 500]]

    def test_empty_input_yields_no_batches(self):
        assert batch_terms([], "{}", max_chars=100, max_items=10) == []


class TestBuildQueries:
    def test_forward_and_backward_queries_are_labelled_by_round(self):
        seeds = [record("a", pmid="111", refs=["doi:10.1/new"])]

        queries = build_snowball_queries(seeds, known={"10.1/x"}, round_number=2)

        labels = {item.label for item in queries}
        assert any("r2" in label and "forward" in label for label in labels)
        assert any("r2" in label and "backward" in label for label in labels)

    def test_query_syntax_matches_europe_pmc(self):
        seeds = [record("a", pmid="111", refs=["doi:10.1/new"])]

        queries = build_snowball_queries(seeds, known=set(), round_number=1)
        rendered = {item.query for item in queries}

        assert "CITES:111_MED" in rendered
        assert 'DOI:"10.1/new"' in rendered

    def test_no_seeds_means_no_queries(self):
        assert build_snowball_queries([], known=set(), round_number=1) == []


class TestSaturation:
    CONFIG = SnowballConfig(saturation_consecutive_rounds=2, saturation_new_inclusion_rate=0.05)

    def _stat(self, number, new, base):
        return RoundStat(
            number=number,
            seeds=base,
            candidates=0,
            new_records=new,
            new_in_window=new,
            corpus_before=base,
        )

    def test_not_saturated_while_rounds_keep_producing(self):
        history = [self._stat(1, 500, 1000), self._stat(2, 400, 1500)]

        assert is_saturated(history, self.CONFIG) is False

    def test_saturated_after_enough_consecutive_lean_rounds(self):
        history = [self._stat(1, 500, 1000), self._stat(2, 10, 1500), self._stat(3, 10, 1510)]

        assert is_saturated(history, self.CONFIG) is True

    def test_one_lean_round_is_not_enough(self):
        history = [self._stat(1, 500, 1000), self._stat(2, 10, 1500)]

        assert is_saturated(history, self.CONFIG) is False

    def test_a_productive_round_resets_the_streak(self):
        history = [self._stat(1, 10, 1000), self._stat(2, 500, 1010), self._stat(3, 10, 1510)]

        assert is_saturated(history, self.CONFIG) is False

    def test_no_history_is_never_saturated(self):
        assert is_saturated([], self.CONFIG) is False

    def test_a_round_that_finds_nothing_counts_as_lean(self):
        history = [self._stat(1, 0, 1000), self._stat(2, 0, 1000)]

        assert is_saturated(history, self.CONFIG) is True

    def test_rate_is_relative_to_the_corpus_before_the_round(self):
        stat = self._stat(1, 50, 1000)

        assert stat.new_rate == pytest.approx(0.05)
