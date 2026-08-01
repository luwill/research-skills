"""本地概念过滤器：给没有布尔检索能力的源兜底。

CVF 只给标题列表、OpenReview 的多词查询是 OR 语义、Zenodo 只有单框检索——
这些源的"AND 概念块"必须在本地做，否则召回边界就完全失控。
"""

from __future__ import annotations

import pytest

from litsearch.localfilter import ConceptMatcher, build_matcher
from litsearch.protocol import Topic

TOPIC = Topic.model_validate(
    {
        "id": "t",
        "title": "T",
        "window": {"start": "2021-07-01", "end": "2026-07-27"},
        "concepts": {
            "condition": {
                "required": True,
                "terms": ["ischemic stroke", "infarct core", "non-contrast CT"],
                "wildcards": ["infarct*"],
            },
            "task": {"required": True, "terms": ["segment"], "wildcards": ["segment*"]},
            "method": {"required": False, "terms": ["nnU-Net", "U-Net"]},
        },
        "query_plan": {"combinations": [["condition", "task"]]},
        "criteria": {"include": [{"id": "I1", "text": "x"}]},
    }
)


@pytest.fixture
def matcher() -> ConceptMatcher:
    return build_matcher(TOPIC)


class TestTermMatching:
    def test_matches_multiword_phrase_case_insensitively(self, matcher):
        assert matcher.hits("Ischemic Stroke lesion analysis")["condition"] == ["ischemic stroke"]

    def test_term_does_not_match_a_longer_word(self, matcher):
        """`segment` 不能命中 `segmentation`——否则通配符与精确词就没有区别了。"""
        assert "segment" not in matcher.hits("Segmentation of the brain")["task"]

    def test_wildcard_matches_the_longer_word(self, matcher):
        assert "segment*" in matcher.hits("Segmentation of the brain")["task"]

    def test_wildcard_expands_only_within_a_word(self, matcher):
        """`infarct*` 命中 infarction，但不能跨词命中 `infarct core` 之外的东西。"""
        assert "infarct*" in matcher.hits("cerebral infarction volume")["condition"]
        assert matcher.hits("the infant is well")["condition"] == []

    def test_regex_metacharacters_in_terms_are_literal(self, matcher):
        """`nnU-Net` 里的 `-` 不能被当成正则字符类。"""
        assert "nnU-Net" in matcher.hits("we train a nnU-Net baseline")["method"]

    def test_hyphen_and_space_are_interchangeable(self, matcher):
        """各源对连字符的写法不一致，`non-contrast CT` 与 `non contrast CT` 必须都能命中。"""
        assert matcher.hits("non contrast CT of the head")["condition"] == ["non-contrast CT"]

    def test_empty_text_matches_nothing(self, matcher):
        assert matcher.hits("")["condition"] == []


class TestRequiredBlocks:
    def test_all_required_blocks_present(self, matcher):
        assert matcher.matches_all_required("ischemic stroke lesion segmentation") is True

    def test_missing_one_required_block_fails(self, matcher):
        assert matcher.matches_all_required("ischemic stroke outcome prediction") is False

    def test_missing_blocks_are_named_for_audit(self, matcher):
        assert matcher.missing_required("ischemic stroke outcome prediction") == ["task"]

    def test_optional_block_absence_does_not_fail(self, matcher):
        assert matcher.matches_all_required("infarct segmentation") is True

    def test_any_required_is_the_looser_gate(self, matcher):
        """只有标题可用时（CVF），命中任一必需块就值得去取摘要——宁可多取也不能漏。"""
        assert matcher.matches_any_required("Video Object Segmentation") is True
        assert matcher.matches_any_required("Neural Radiance Fields") is False


class TestEvidence:
    def test_matched_terms_are_reported_per_block(self, matcher):
        hits = matcher.hits("nnU-Net for ischemic stroke segmentation")

        assert hits["condition"] == ["ischemic stroke"]
        assert hits["method"] == ["nnU-Net"]
        assert "segment*" in hits["task"]

    def test_reason_string_explains_a_rejection(self, matcher):
        assert "task" in matcher.reason("ischemic stroke outcome prediction")

    def test_reason_is_empty_when_accepted(self, matcher):
        assert matcher.reason("ischemic stroke segmentation") == ""


class TestConstruction:
    def test_matcher_requires_at_least_one_required_block(self):
        topic = Topic.model_validate(
            {
                "id": "t",
                "title": "T",
                "window": {"start": "2021-07-01", "end": "2026-07-27"},
                "concepts": {"a": {"required": False, "terms": ["x"]}},
                "query_plan": {"combinations": [["a"]]},
                "criteria": {"include": [{"id": "I1", "text": "x"}]},
            }
        )

        with pytest.raises(ValueError, match="required"):
            build_matcher(topic)

    def test_anchor_block_defaults_to_the_first_required_block(self, matcher):
        assert matcher.anchor == "condition"

    def test_anchor_phrases_are_the_anchor_blocks_terms(self, matcher):
        """锚点检索式只用锚点块的短语——实测 OpenReview 上 `"segmentation"`
        单独一个词就撞上 10,000 条的返回上限，任务块不能当锚点。"""
        assert matcher.anchor_phrases() == [
            "ischemic stroke",
            "infarct core",
            "non-contrast CT",
        ]
