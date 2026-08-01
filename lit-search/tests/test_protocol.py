"""Protocol loading, validation and freezing."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from litsearch.protocol import ProtocolError, Topic, freeze_topic, load_topic
from tests.conftest import sample_topic

ISLES_TOPIC = sample_topic("isles-2026.yaml")


def _write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "topic.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture
def minimal_payload() -> dict:
    return {
        "id": "demo",
        "title": "Demo",
        "window": {"start": "2021-07-01", "end": "2026-07-27"},
        "concepts": {
            "condition": {"required": True, "terms": ["stroke"]},
            "task": {"required": True, "terms": ["segmentation"]},
        },
        "query_plan": {"combinations": [["condition", "task"]]},
        "criteria": {"include": [{"id": "I1", "text": "human stroke imaging"}]},
    }


class TestWindow:
    def test_harvest_window_is_widened_by_margin(self, tmp_path, minimal_payload):
        minimal_payload["window"]["harvest_margin_days"] = 365
        topic = load_topic(_write(tmp_path, minimal_payload))

        assert topic.window.start == date(2021, 7, 1)
        assert topic.window.end == date(2026, 7, 27)
        # 宽进：采集窗口向两端各外扩一年
        assert topic.window.harvest_start == date(2020, 7, 1)
        assert topic.window.harvest_end == date(2027, 7, 27)

    def test_zero_margin_keeps_strict_window(self, tmp_path, minimal_payload):
        minimal_payload["window"]["harvest_margin_days"] = 0
        topic = load_topic(_write(tmp_path, minimal_payload))

        assert topic.window.harvest_start == topic.window.start
        assert topic.window.harvest_end == topic.window.end

    def test_end_before_start_is_rejected(self, tmp_path, minimal_payload):
        minimal_payload["window"] = {"start": "2026-01-01", "end": "2021-01-01"}

        with pytest.raises(ProtocolError, match="window.end"):
            load_topic(_write(tmp_path, minimal_payload))

    def test_contains_uses_inclusive_bounds(self, tmp_path, minimal_payload):
        window = load_topic(_write(tmp_path, minimal_payload)).window

        assert window.contains(date(2021, 7, 1)) is True
        assert window.contains(date(2026, 7, 27)) is True
        assert window.contains(date(2021, 6, 30)) is False
        assert window.contains(date(2026, 7, 28)) is False

    def test_is_near_edge_flags_records_close_to_either_edge(self, tmp_path, minimal_payload):
        minimal_payload["window"]["near_edge_days"] = 180
        window = load_topic(_write(tmp_path, minimal_payload)).window

        assert window.is_near_edge(date(2021, 8, 1)) is True  # 窗口内但贴近下沿
        assert window.is_near_edge(date(2021, 3, 1)) is True  # 窗口外但贴近下沿
        assert window.is_near_edge(date(2026, 6, 1)) is True  # 贴近上沿
        assert window.is_near_edge(date(2023, 1, 1)) is False  # 窗口正中


class TestConceptsAndQueryPlan:
    def test_unknown_block_in_combination_is_rejected(self, tmp_path, minimal_payload):
        minimal_payload["query_plan"]["combinations"] = [["condition", "nonexistent"]]

        with pytest.raises(ProtocolError, match="nonexistent"):
            load_topic(_write(tmp_path, minimal_payload))

    def test_combination_missing_required_block_is_rejected(self, tmp_path, minimal_payload):
        # task 是 required，组合里却漏了它
        minimal_payload["concepts"]["modality"] = {"required": False, "terms": ["MRI"]}
        minimal_payload["query_plan"]["combinations"] = [["condition", "modality"]]

        with pytest.raises(ProtocolError, match="task"):
            load_topic(_write(tmp_path, minimal_payload))

    def test_empty_concept_block_is_rejected(self, tmp_path, minimal_payload):
        minimal_payload["concepts"]["task"] = {"required": True, "terms": []}

        with pytest.raises(ProtocolError, match="task"):
            load_topic(_write(tmp_path, minimal_payload))

    def test_terms_are_deduplicated_case_insensitively(self, tmp_path, minimal_payload):
        minimal_payload["concepts"]["condition"]["terms"] = ["Stroke", "stroke", "STROKE ", "AIS"]
        topic = load_topic(_write(tmp_path, minimal_payload))

        assert topic.concepts["condition"].terms == ["Stroke", "AIS"]

    def test_max_terms_per_block_truncates(self, tmp_path, minimal_payload):
        minimal_payload["concepts"]["condition"]["terms"] = [f"t{i}" for i in range(20)]
        minimal_payload["query_plan"]["max_terms_per_block"] = 5
        topic = load_topic(_write(tmp_path, minimal_payload))

        assert len(topic.effective_terms("condition")) == 5


class TestGoldSet:
    def test_gold_item_without_identifier_is_rejected(self, tmp_path, minimal_payload):
        minimal_payload["gold_set"] = [{"note": "no identifier at all"}]

        with pytest.raises(ProtocolError, match="identifier"):
            load_topic(_write(tmp_path, minimal_payload))

    def test_doi_is_normalized(self, tmp_path, minimal_payload):
        minimal_payload["gold_set"] = [{"doi": "https://doi.org/10.1038/S41597-022-01875-5"}]
        topic = load_topic(_write(tmp_path, minimal_payload))

        assert topic.gold_set[0].doi == "10.1038/s41597-022-01875-5"


class TestFreeze:
    def test_freeze_is_stable_and_content_addressed(self, tmp_path, minimal_payload):
        path = _write(tmp_path, minimal_payload)

        first = freeze_topic(path)
        second = freeze_topic(path)
        assert first == second
        assert len(first) == 64

        minimal_payload["title"] = "Changed"
        assert freeze_topic(_write(tmp_path, minimal_payload)) != first


class TestRealTopic:
    def test_isles_topic_loads(self):
        topic = load_topic(ISLES_TOPIC)

        assert isinstance(topic, Topic)
        assert topic.id == "isles-2026"
        assert topic.window.start == date(2021, 7, 1)
        assert topic.window.end == date(2026, 7, 27)
        assert topic.window.harvest_start == date(2020, 7, 1)
        assert {"condition", "task", "modality", "method"} <= set(topic.concepts)
        assert len(topic.gold_set) >= 9
        assert topic.enabled_sources() >= {"openalex", "pubmed", "europepmc", "arxiv"}

    def test_isles_out_of_window_controls_are_outside_the_window(self):
        topic = load_topic(ISLES_TOPIC)

        assert topic.out_of_window_controls
        for control in topic.out_of_window_controls:
            assert control.doi
