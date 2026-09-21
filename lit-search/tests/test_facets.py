"""已纳入记录的类型化标注。

**只标注，不过滤，也不进证据表。** report.py 明令禁止猜测只有全文才知道的字段，
所以这一层的产物是独立文件，供人筛选和排序，不参与任何自动判定。

措辞纪律：每个问题都问「摘要**明确陈述**了 X 吗」，答案只有 stated / not_stated，
**永远没有 no**。摘要没提外部验证，不等于这篇研究没做外部验证——它只是没在
摘要里说。把"没说"记成"没有"，是这一层最容易犯也最难发现的错。
"""

from __future__ import annotations

import pytest

from litsearch.dedupe import CanonicalRecord
from litsearch.facets import (
    DEFAULT_FACETS,
    NOT_STATED,
    STATED,
    FacetRow,
    compile_facet_questions,
    facet_label,
    facets_csv,
    facets_for,
)
from litsearch.jev_profile import JevProfile, load_profile
from litsearch.protocol import ProtocolError, Topic

TOPIC = Topic.model_validate(
    {
        "id": "t",
        "title": "T",
        "window": {"start": "2021-07-01", "end": "2026-07-27"},
        "concepts": {"a": {"required": True, "terms": ["stroke"]}},
        "query_plan": {"combinations": [["a"]]},
        "criteria": {"include": [{"id": "I1", "text": "x"}]},
    }
)


def _write_profile(tmp_path, payload: dict):
    import yaml

    path = tmp_path / "t.jev.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def record(key: str, title: str = "A paper") -> CanonicalRecord:
    return CanonicalRecord(key=key, title=title, abstract="摘要", sources=("openalex",))


def facet_row(key: str, answers: dict[str, float]) -> FacetRow:
    return FacetRow(
        record_key=key,
        model="jev-1.13.0",
        questions_sha256="f" * 64,
        answers=answers,
        input_tokens=900,
    )


class TestPhrasingDiscipline:
    def test_every_shipped_facet_asks_what_the_abstract_states(self):
        """问「这项研究做了外部验证吗」会得到一个关于世界的猜测；
        问「摘要明确陈述了外部验证吗」才是摘要真能回答的问题。"""
        for facet in DEFAULT_FACETS:
            assert "明确" in facet.ask and "摘要" in facet.ask, facet.id

    def test_the_two_labels_never_say_no(self):
        assert {STATED, NOT_STATED} == {"stated", "not_stated"}
        assert "no" not in {STATED, NOT_STATED}

    def test_a_low_probability_means_not_stated_not_absent(self):
        assert facet_label(0.02, threshold=0.7) == NOT_STATED
        assert facet_label(0.95, threshold=0.7) == STATED

    def test_the_boundary_counts_as_stated(self):
        assert facet_label(0.7, threshold=0.7) == STATED


class TestCompileFacetQuestions:
    def test_the_profile_facets_win_over_the_defaults(self):
        profile = JevProfile(
            topic_id="t", facets=[{"id": "custom", "ask": "摘要是否明确陈述了自定义内容？"}]
        )

        questions = compile_facet_questions(profile)

        assert set(questions) == {"custom"}

    def test_an_empty_profile_falls_back_to_the_shipped_set(self):
        questions = compile_facet_questions(JevProfile(topic_id="t"))

        assert set(questions) == {facet.id for facet in DEFAULT_FACETS}

    def test_every_question_is_a_noul(self):
        questions = compile_facet_questions(JevProfile(topic_id="t"))

        assert all(item["type"] == "noul" for item in questions.values())

    def test_a_facet_phrased_as_a_claim_about_the_world_is_refused(self, tmp_path):
        """措辞纪律必须在加载时强制，不能靠写的人自觉。"""
        path = _write_profile(
            tmp_path,
            {"topic_id": "t", "facets": [{"id": "bad", "ask": "这项研究做了外部验证吗？"}]},
        )

        with pytest.raises(ProtocolError, match="明确"):
            load_profile(path, TOPIC)

    def test_duplicate_facet_ids_are_refused(self, tmp_path):
        path = _write_profile(
            tmp_path,
            {
                "topic_id": "t",
                "facets": [
                    {"id": "dup", "ask": "摘要是否明确陈述了 A？"},
                    {"id": "dup", "ask": "摘要是否明确陈述了 B？"},
                ],
            },
        )

        with pytest.raises(ProtocolError, match="重复"):
            load_profile(path, TOPIC)


class TestFacetsFor:
    def test_it_maps_probabilities_to_labels(self):
        profile = JevProfile(topic_id="t")
        ids = [facet.id for facet in DEFAULT_FACETS]
        row = facet_row("k", {ids[0]: 0.9, **{i: 0.1 for i in ids[1:]}})

        labels = facets_for(row, profile)

        assert labels[ids[0]] == STATED
        assert labels[ids[1]] == NOT_STATED

    def test_a_facet_the_model_did_not_answer_is_absent_not_guessed(self):
        profile = JevProfile(topic_id="t")
        row = facet_row("k", {})

        assert facets_for(row, profile) == {}


class TestFacetsCsv:
    def test_one_column_per_facet_plus_the_raw_probability(self):
        profile = JevProfile(topic_id="t")
        ids = [facet.id for facet in DEFAULT_FACETS]
        rows = {"k": facet_row("k", {i: 0.9 for i in ids})}

        csv = facets_csv(rows, [record("k")], profile)

        header = csv.splitlines()[0]
        for name in ids:
            assert name in header
            assert f"{name}_p" in header, "原始概率也要留着，标签是阈值切出来的"

    def test_an_unscored_record_still_gets_a_row(self):
        """已纳入却没标注上的记录不能从表里消失——那会让人以为它不存在。"""
        profile = JevProfile(topic_id="t")

        csv = facets_csv({}, [record("k")], profile)

        assert len(csv.splitlines()) == 2
        assert "未标注" in csv

    def test_the_title_is_quoted_and_commas_do_not_break_the_row(self):
        profile = JevProfile(topic_id="t")
        ids = [facet.id for facet in DEFAULT_FACETS]
        rows = {"k": facet_row("k", {i: 0.9 for i in ids})}

        csv = facets_csv(rows, [record("k", "Title, with comma")], profile)

        assert '"Title, with comma"' in csv
