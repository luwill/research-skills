"""Protocol loading, validation and freezing."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from litsearch.protocol import (
    ProtocolError,
    Topic,
    freeze_topic,
    load_topic,
    protocol_fingerprint,
)
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


class TestFingerprintStability:
    """协议指纹钉桩。

    ``protocol_fingerprint`` 哈希的是 ``model_dump(mode="json")``——**含默认值**。
    给 ``Topic`` 或其任一子模型加一个可选字段，哪怕默认是 ``None``，也会让所有
    历史 run 的指纹对不上，被 ``assert_topic_compatible`` 挡死，
    ``screen``/``adjudicate``/``report``/``validate``/``snowball`` 全部失效。

    这个测试让那类改动**响亮地失败**，而不是等到用户的 run 跑不动才发现。
    真要改协议语义时，同步更新下面的哈希，并明确告知已有 run 需要重新采集。
    """

    #: 2026-09-20 实测值。改动协议 schema 会让这些值全部变化。
    PINNED = {
        "context-engineering-2026.yaml": (
            "47695e453be1caeb2bd048284326ef55df28b2d18ae27452987373fa5f20ee0f"
        ),
        "isles-2026.yaml": (
            "a9a2e221c80ba406479687712754497adef779deda11e43968edcaec136e5a82"
        ),
        "pediatric-intestinal-obstruction-ai.yaml": (
            "9ce217c335d7dd5c99bec85fd7e48da235a6cf996c362b87bcb3503d387dc3c0"
        ),
        "pulmonary-fibrosis-ai.yaml": (
            "63c159311204b9414c2c9b3116fa358d4571e5715482e837ff2ab0fd82fe2d6e"
        ),
    }

    @pytest.mark.parametrize("name", sorted(PINNED))
    def test_sample_topic_fingerprints_are_pinned(self, name: str):
        # 打包成 skill 时只随附部分样例协议。没随附的跳过；
        # **随附了的一个都不能漏检**——否则这层护栏在副本里就是空的。
        try:
            path = sample_topic(name)
        except FileNotFoundError:
            pytest.skip(f"{name} 不在本布局中（skill 包只随附部分样例协议）")
        topic = load_topic(path)

        assert protocol_fingerprint(topic) == self.PINNED[name], (
            f"{name} 的协议指纹变了。若这是有意的协议语义变更，请更新钉桩值，"
            f"并告知已有 run 需要重新采集；若只是给 schema 加了字段，请撤销——"
            f"加字段会让所有历史 run 被兼容性检查挡死。"
        )
