"""Jev 判定配置。

**为什么不放进 topic.yaml**：``protocol_fingerprint`` 哈希的是含默认值的
``model_dump``，给协议加任何一个可选字段都会让所有历史 run 的指纹对不上、被
``assert_topic_compatible`` 挡死，``screen`` / ``adjudicate`` / ``report`` /
``validate`` / ``snowball`` 全部失效。阈值还需要反复调，每调一次就废掉一次 run
更不可接受。所以判定配置单独成文件，只把它的内容记进轮次的 parameters。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from litsearch.jev_client import JEV_PINNED
from litsearch.jev_profile import load_profile
from litsearch.protocol import ProtocolError, Topic

TOPIC = Topic.model_validate(
    {
        "id": "t",
        "title": "T",
        "window": {"start": "2021-07-01", "end": "2026-07-27"},
        "concepts": {"a": {"required": True, "terms": ["stroke"]}},
        "query_plan": {"combinations": [["a"]]},
        "criteria": {
            "include": [
                {"id": "I1", "text": "人类缺血性卒中影像"},
                {"id": "I2", "text": "存在病灶级别分割"},
                {"id": "I3", "text": "报告了 Dice/HD95 等定量结果"},
            ],
            "exclude": [{"id": "X1", "text": "仅出血性卒中"}],
        },
    }
)


def write(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "t.jev.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


MINIMAL = {"topic_id": "t"}


class TestDefaults:
    def test_a_minimal_profile_pins_the_model_and_the_bands(self, tmp_path):
        profile = load_profile(write(tmp_path, MINIMAL), TOPIC)

        assert profile.model == JEV_PINNED
        assert profile.include_at == 0.7
        assert profile.exclude_below == 0.1

    def test_exclusion_criteria_are_annotated_not_scored_by_default(self, tmp_path):
        """实测：把分数乘上 (1 - max 排除概率) 反而更差。

        官方文档也说了，一个问题与其否定式的概率不满足互补关系。所以排除标准
        默认只记进 reason 供人看，不参与打分。
        """
        profile = load_profile(write(tmp_path, MINIMAL), TOPIC)

        assert profile.exclusions == "annotate"

    def test_nothing_is_skipped_unless_asked(self, tmp_path):
        assert load_profile(write(tmp_path, MINIMAL), TOPIC).skip == []


class TestValidation:
    def test_a_profile_for_another_topic_is_refused(self, tmp_path):
        path = write(tmp_path, {"topic_id": "other"})

        with pytest.raises(ProtocolError, match="topic_id"):
            load_profile(path, TOPIC)

    def test_skipping_a_criterion_that_does_not_exist_is_refused(self, tmp_path):
        """写错标准编号就等于悄悄放开一条标准，必须当场拦下。"""
        path = write(tmp_path, {**MINIMAL, "skip": ["I9"]})

        with pytest.raises(ProtocolError, match="I9"):
            load_profile(path, TOPIC)

    def test_an_exclusion_criterion_can_be_skipped_too(self, tmp_path):
        profile = load_profile(write(tmp_path, {**MINIMAL, "skip": ["X1"]}), TOPIC)

        assert profile.skip == ["X1"]

    def test_skipping_every_inclusion_criterion_is_refused(self, tmp_path):
        """一条纳入标准都不问，分数就无从谈起，只会得到一个恒定值。"""
        path = write(tmp_path, {**MINIMAL, "skip": ["I1", "I2", "I3"]})

        with pytest.raises(ProtocolError, match="纳入标准"):
            load_profile(path, TOPIC)

    def test_overlapping_bands_are_refused(self, tmp_path):
        path = write(tmp_path, {**MINIMAL, "include_at": 0.3, "exclude_below": 0.5})

        with pytest.raises(ProtocolError):
            load_profile(path, TOPIC)

    def test_equal_bands_are_refused_because_nothing_could_be_queued(self, tmp_path):
        path = write(tmp_path, {**MINIMAL, "include_at": 0.5, "exclude_below": 0.5})

        with pytest.raises(ProtocolError):
            load_profile(path, TOPIC)

    def test_an_unknown_key_is_refused_rather_than_ignored(self, tmp_path):
        """拼错的键名被静默忽略，等于让整套阈值无声失效。"""
        path = write(tmp_path, {**MINIMAL, "include_ad": 0.9})

        with pytest.raises(ProtocolError):
            load_profile(path, TOPIC)

    def test_a_missing_file_says_so(self, tmp_path):
        with pytest.raises(ProtocolError, match="读取"):
            load_profile(tmp_path / "nope.yaml", TOPIC)

    def test_a_probability_outside_zero_to_one_is_refused(self, tmp_path):
        with pytest.raises(ProtocolError):
            load_profile(write(tmp_path, {**MINIMAL, "include_at": 1.4}), TOPIC)


class TestAudit:
    def test_the_profile_serialises_into_the_round_parameters(self, tmp_path):
        """阈值必须随轮次存档：否则事后没人知道这批判定是按什么标准分的档。"""
        profile = load_profile(
            write(tmp_path, {**MINIMAL, "include_at": 0.8, "skip": ["I3"]}), TOPIC
        )

        payload = profile.model_dump(mode="json")

        assert payload["include_at"] == 0.8
        assert payload["skip"] == ["I3"]
        assert payload["model"] == JEV_PINNED

    def test_two_identical_profiles_hash_the_same(self, tmp_path):
        first = load_profile(write(tmp_path, MINIMAL), TOPIC)
        second = load_profile(write(tmp_path, dict(MINIMAL)), TOPIC)

        assert first.sha256() == second.sha256()

    def test_changing_a_threshold_changes_the_hash(self, tmp_path):
        first = load_profile(write(tmp_path, MINIMAL), TOPIC)
        second = load_profile(write(tmp_path, {**MINIMAL, "include_at": 0.8}), TOPIC)

        assert first.sha256() != second.sha256()


class TestActiveCriteria:
    def test_active_inclusions_drop_the_skipped_ones(self, tmp_path):
        profile = load_profile(write(tmp_path, {**MINIMAL, "skip": ["I3"]}), TOPIC)

        assert [item.id for item in profile.active_inclusions(TOPIC)] == ["I1", "I2"]

    def test_active_exclusions_respect_both_skip_and_the_mode(self, tmp_path):
        annotated = load_profile(write(tmp_path, MINIMAL), TOPIC)
        ignored = load_profile(write(tmp_path, {**MINIMAL, "exclusions": "ignore"}), TOPIC)

        assert [item.id for item in annotated.active_exclusions(TOPIC)] == ["X1"]
        assert ignored.active_exclusions(TOPIC) == []
