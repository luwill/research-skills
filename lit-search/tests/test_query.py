"""Concept blocks -> per-source query strings."""

from __future__ import annotations

import pytest
import yaml

from litsearch.protocol import load_topic
from litsearch.query import build_queries, effective_combinations, render_block
from tests.conftest import sample_topic

ISLES_TOPIC = sample_topic("isles-2026.yaml")


@pytest.fixture
def topic(tmp_path):
    payload = {
        "id": "demo",
        "title": "Demo",
        "window": {"start": "2021-07-01", "end": "2026-07-27"},
        "concepts": {
            "condition": {
                "required": True,
                "terms": ["ischemic stroke", "infarct core"],
                "mesh": ["Stroke"],
                "wildcards": ["infarct*"],
            },
            "task": {"required": True, "terms": ["segmentation"]},
            "modality": {"required": False, "terms": ["DWI", "CT perfusion"]},
        },
        "query_plan": {"combinations": [["condition", "task"], ["condition", "task", "modality"]]},
        "criteria": {"include": [{"id": "I1", "text": "x"}]},
        "known_items": ["ISLES 2022"],
        "sources": {
            "openalex": {"enabled": True},
            "pubmed": {"enabled": True},
            "europepmc": {"enabled": True},
            "arxiv": {"enabled": True},
        },
    }
    path = tmp_path / "topic.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return load_topic(path)


class TestRenderBlock:
    def test_pubmed_uses_tiab_mesh_and_wildcards(self, topic):
        rendered = render_block(topic.concepts["condition"], "pubmed", limit=16)

        assert '"ischemic stroke"[tiab]' in rendered
        assert '"infarct core"[tiab]' in rendered
        assert '"Stroke"[Mesh]' in rendered
        assert "infarct*[tiab]" in rendered
        assert rendered.startswith("(") and rendered.endswith(")")
        assert " OR " in rendered

    def test_openalex_quotes_multiword_terms_and_drops_mesh(self, topic):
        rendered = render_block(topic.concepts["condition"], "openalex", limit=16)

        assert '"ischemic stroke"' in rendered
        assert "[tiab]" not in rendered
        assert "Mesh" not in rendered

    def test_europepmc_uses_title_abs_field(self, topic):
        rendered = render_block(topic.concepts["condition"], "europepmc", limit=16)

        assert 'TITLE_ABS:"ischemic stroke"' in rendered

    def test_arxiv_uses_abs_field_and_drops_wildcards(self, topic):
        rendered = render_block(topic.concepts["condition"], "arxiv", limit=16)

        assert 'abs:"ischemic stroke"' in rendered
        # arXiv 不支持通配符，必须剔除而不是原样传入
        assert "*" not in rendered

    def test_limit_truncates_terms(self, topic):
        rendered = render_block(topic.concepts["condition"], "openalex", limit=1)

        assert '"ischemic stroke"' in rendered
        assert '"infarct core"' not in rendered


class TestSubsumption:
    def test_narrower_combination_is_dropped(self, topic):
        """[condition,task,modality] 的结果是 [condition,task] 的真子集，跑它零增量。"""
        assert effective_combinations(topic) == [["condition", "task"]]

    def test_include_subsumed_keeps_everything(self, topic):
        assert len(effective_combinations(topic, include_subsumed=True)) == 2

    def test_disjoint_combinations_are_both_kept(self, tmp_path):
        payload = {
            "id": "d",
            "title": "D",
            "window": {"start": "2021-07-01", "end": "2026-07-27"},
            "concepts": {
                "condition": {"required": True, "terms": ["stroke"]},
                "task": {"terms": ["segmentation"]},
                "method": {"terms": ["deep learning"]},
            },
            "query_plan": {"combinations": [["condition", "task"], ["condition", "method"]]},
            "criteria": {"include": [{"id": "I1", "text": "x"}]},
            "sources": {"openalex": {"enabled": True}},
        }
        path = tmp_path / "d.yaml"
        path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")

        assert len(effective_combinations(load_topic(path))) == 2


class TestBuildQueries:
    def test_one_query_per_effective_combination_per_source(self, topic):
        queries = build_queries(topic)

        cross = [q for q in queries if q.kind == "crossproduct"]
        # 2 个组合中 1 个被subsume掉，剩 1 个 × 4 个启用源
        assert len(cross) == 1 * 4

    def test_known_items_produce_separate_queries(self, topic):
        queries = build_queries(topic)

        known = [q for q in queries if q.kind == "known_item"]
        assert len(known) == 1 * 4
        assert all("ISLES 2022" in q.query for q in known)

    def test_combination_is_joined_with_and(self, topic):
        query = next(
            q
            for q in build_queries(topic)
            if q.source == "pubmed" and q.blocks == ("condition", "task")
        )

        assert " AND " in query.query
        assert query.query.count("(") >= 2

    def test_query_hash_is_stable_and_distinguishes_queries(self, topic):
        first = build_queries(topic)
        second = build_queries(topic)

        assert [q.query_hash for q in first] == [q.query_hash for q in second]
        assert len({q.query_hash for q in first}) == len(first)
        assert all(len(q.query_hash) == 16 for q in first)

    def test_disabled_source_is_skipped(self, topic):
        topic.sources["arxiv"].enabled = False
        queries = build_queries(topic)

        assert all(q.source != "arxiv" for q in queries)

    def test_enrich_only_source_is_not_used_for_recall(self, tmp_path):
        payload = {
            "id": "demo",
            "title": "Demo",
            "window": {"start": "2021-07-01", "end": "2026-07-27"},
            "concepts": {
                "condition": {"required": True, "terms": ["stroke"]},
                "task": {"required": True, "terms": ["segmentation"]},
            },
            "query_plan": {"combinations": [["condition", "task"]]},
            "criteria": {"include": [{"id": "I1", "text": "x"}]},
            "sources": {
                "openalex": {"enabled": True},
                "crossref": {"enabled": True, "role": "enrich"},
            },
        }
        path = tmp_path / "t.yaml"
        path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
        queries = build_queries(load_topic(path))

        assert all(q.source != "crossref" for q in queries)


class TestRealTopicQueries:
    def test_isles_generates_a_reproducible_strategy_set(self):
        queries = build_queries(load_topic(ISLES_TOPIC))

        assert len(queries) > 20
        assert {q.source for q in queries} >= {"openalex", "pubmed", "europepmc", "arxiv"}
        # 每条查询都必须能被原样复现
        assert all(q.query.strip() for q in queries)
        assert len({q.query_hash for q in queries}) == len(queries)

    def test_pubmed_isles_query_contains_mesh_terms(self):
        queries = build_queries(load_topic(ISLES_TOPIC))
        pubmed = next(q for q in queries if q.source == "pubmed" and q.kind == "crossproduct")

        assert "[Mesh]" in pubmed.query
