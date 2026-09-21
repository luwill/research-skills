"""双通道筛选的纯逻辑：批次构造、判定合并、人工队列。

设计原则：模型不能单方面拍板。两个通道独立判定，分歧或低置信度一律进人工队列；
判定按轮次不可变追加，修正记为新一轮，绝不改写上一轮。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from litsearch.dedupe import CanonicalRecord
from litsearch.protocol import Criteria, ScreeningConfig
from litsearch.screen import (
    CHANNEL_PROMPTS,
    Decision,
    MergedDecision,
    ScreeningRound,
    Verdict,
    build_batches,
    build_channel_prompt,
    carry_adjudications,
    format_records,
    merge_verdicts,
    render_human_queue,
)

CRITERIA = Criteria.model_validate(
    {
        "include": [
            {"id": "I1", "text": "人类缺血性卒中脑影像"},
            {"id": "I2", "text": "存在病灶级别分割或体积量化"},
        ],
        "exclude": [
            {"id": "X1", "text": "仅出血性卒中或非缺血性病变"},
            {"id": "X2", "text": "仅分类/检出，无分割输出"},
        ],
    }
)
CONFIG = ScreeningConfig(channels=2, confidence_threshold=0.7, batch_size=3)


def record(key: str, title: str = "A paper", abstract: str | None = "An abstract"):
    return CanonicalRecord(key=key, title=title, abstract=abstract)


def verdict(key: str, decision: str, confidence: float = 0.95, criteria=None):
    return Verdict(
        record_key=key,
        decision=decision,
        matched_criteria=criteria or [],
        reason="because",
        confidence=confidence,
    )


class TestBatching:
    def test_splits_by_batch_size(self):
        records = [record(f"k{i}") for i in range(7)]

        batches = build_batches(records, batch_size=3)

        assert [len(item) for item in batches] == [3, 3, 1]

    def test_empty_input(self):
        assert build_batches([], batch_size=25) == []

    def test_records_without_abstract_are_still_screened(self):
        """没有摘要不等于不相关——只凭标题判定，并让模型知道摘要缺失。"""
        batches = build_batches([record("k1", abstract=None)], batch_size=25)

        rendered = format_records(batches[0])

        assert "k1" in rendered
        assert "（无摘要）" in rendered


class TestPrompts:
    def test_two_channels_use_different_framings(self):
        assert len(CHANNEL_PROMPTS) >= 2
        assert CHANNEL_PROMPTS[0] != CHANNEL_PROMPTS[1]

    def test_prompt_contains_every_criterion_verbatim(self):
        prompt = build_channel_prompt(CRITERIA, channel=0)

        for item in (*CRITERIA.include, *CRITERIA.exclude):
            assert item.id in prompt
            assert item.text in prompt

    def test_prompt_requires_unclear_option(self):
        """必须允许模型说"判不了"——逼它二选一会把不确定伪装成确定。"""
        prompt = build_channel_prompt(CRITERIA, channel=0)

        assert "unclear" in prompt

    def test_both_channels_state_that_this_is_the_title_abstract_stage(self):
        """初筛必须从宽：错误排除不可逆，错误纳入只是多读一篇全文。
        不写这条，模型会为"摘要没给 Dice"而判 unclear，人工队列直接爆掉
        （实测 13% → 见 IMPLEMENTATION_PLAN 的实测记录）。"""
        for channel in range(len(CHANNEL_PROMPTS)):
            prompt = build_channel_prompt(CRITERIA, channel)

            assert "标题摘要初筛" in prompt
            assert "错误排除不可逆" in prompt
            assert "待全文确认" in prompt

    def test_a_missing_abstract_is_not_by_itself_a_reason_for_unclear(self):
        """整卷补齐的会议录里大部分条目在 Crossref 上**没有摘要**，而 Springer
        也没把它们存进 OpenAlex / PubMed / Europe PMC（实测 12 条抽样，三个源全 0）。

        不写这条，模型会对每一条无摘要记录回「信息不足」：实测一次 100 条的
        代表性抽样里队列率 18%，其中 15/18 是无摘要记录，而它们的标题多数
        一眼就是另一个课题（"Decoder Conditioning with Tabular Data"）。
        把这些全送人工等于没有筛。

        纪律的边界在于**排除的依据是标题里的正面反证，不是摘要的缺席**——
        标题本身判不出主题时仍然要判 unclear，不可逆的那一侧不能靠猜。
        """
        for channel in range(len(CHANNEL_PROMPTS)):
            prompt = build_channel_prompt(CRITERIA, channel)

            assert "没有摘要" in prompt
            assert "不是判 unclear 的理由" in prompt

    def test_unclear_is_reserved_for_topic_level_ambiguity(self):
        prompt = build_channel_prompt(CRITERIA, channel=0)

        assert "主题本身" in prompt

    def test_channel_index_out_of_range_is_rejected(self):
        with pytest.raises(IndexError):
            build_channel_prompt(CRITERIA, channel=99)


class TestMergeVerdicts:
    def _merge(self, channels, config=CONFIG):
        return merge_verdicts(channels, config)

    def test_both_include_confidently(self):
        merged = self._merge([[verdict("k1", "include")], [verdict("k1", "include")]])

        assert merged["k1"].decision is Decision.INCLUDE
        assert merged["k1"].needs_human is False

    def test_both_exclude_confidently(self):
        merged = self._merge([[verdict("k1", "exclude")], [verdict("k1", "exclude")]])

        assert merged["k1"].decision is Decision.EXCLUDE
        assert merged["k1"].needs_human is False

    def test_disagreement_goes_to_human(self):
        merged = self._merge([[verdict("k1", "include")], [verdict("k1", "exclude")]])

        assert merged["k1"].needs_human is True
        assert "分歧" in merged["k1"].reason

    def test_low_confidence_in_either_channel_goes_to_human(self):
        merged = self._merge(
            [[verdict("k1", "include", confidence=0.4)], [verdict("k1", "include")]]
        )

        assert merged["k1"].needs_human is True
        assert "置信度" in merged["k1"].reason

    def test_unclear_goes_to_human_even_if_the_other_channel_is_sure(self):
        merged = self._merge([[verdict("k1", "unclear")], [verdict("k1", "include")]])

        assert merged["k1"].needs_human is True

    def test_missing_verdict_from_a_channel_goes_to_human_not_silently_dropped(self):
        """某个通道漏判一条记录，绝不能当作它不存在。"""
        merged = self._merge([[verdict("k1", "include")], []])

        assert merged["k1"].needs_human is True
        assert "缺少" in merged["k1"].reason

    def test_a_record_missing_from_every_channel_still_enters_the_queue(self):
        """两条请求都失败时，记录也不能从合并结果里消失。"""
        merged = merge_verdicts([[], []], CONFIG, expected_keys=["k1"])

        assert set(merged) == {"k1"}
        assert merged["k1"].needs_human is True
        assert "2 个通道缺少" in merged["k1"].reason

    def test_model_cannot_invent_an_unknown_decision(self):
        with pytest.raises(ValidationError):
            verdict("k1", "maybe")

    def test_single_channel_config_still_flags_low_confidence(self):
        config = ScreeningConfig(channels=1, confidence_threshold=0.7)

        merged = merge_verdicts([[verdict("k1", "include", confidence=0.5)]], config)

        assert merged["k1"].needs_human is True

    def test_channel_verdicts_are_retained_for_audit(self):
        merged = self._merge([[verdict("k1", "include")], [verdict("k1", "exclude")]])

        assert len(merged["k1"].channel_verdicts) == 2
        assert {item.decision for item in merged["k1"].channel_verdicts} == {
            "include",
            "exclude",
        }


class TestScreeningRound:
    def test_round_is_immutable_and_numbered(self):
        first = ScreeningRound(number=1, topic_sha256="abc", decisions={})

        assert first.number == 1
        with pytest.raises(ValidationError):
            first.number = 2

    def test_next_round_carries_forward_the_protocol_hash(self):
        first = ScreeningRound(number=1, topic_sha256="abc", decisions={})

        second = first.next_round()

        assert second.number == 2
        assert second.topic_sha256 == "abc"
        assert second.decisions == {}


class TestHumanQueue:
    def test_only_flagged_records_appear(self):
        merged = merge_verdicts(
            [
                [verdict("keep", "include"), verdict("split", "include")],
                [verdict("keep", "include"), verdict("split", "exclude")],
            ],
            CONFIG,
        )
        records = {"keep": record("keep", "Agreed"), "split": record("split", "Disputed")}

        csv = render_human_queue(merged, records)

        assert "Disputed" in csv
        assert "Agreed" not in csv

    def test_queue_states_why_each_record_is_there(self):
        merged = merge_verdicts(
            [[verdict("k1", "include", confidence=0.3)], [verdict("k1", "include")]], CONFIG
        )

        csv = render_human_queue(merged, {"k1": record("k1")})

        assert "置信度" in csv


class TestDecisionRendering:
    """判定值进入审计文本时必须是协议里的字面量，不是 Python 枚举的 repr。

    实测污染：已归档的 ``adjudications.jsonl`` 里存着
    ``"通道间分歧：[<Decision.EXCLUDE: 'exclude'>, <Decision.INCLUDE: 'include'>]"``
    和 ``"Decision.INCLUDE@0.90"``。这些字符串是给人读、也会被下游解析的，
    泄漏实现细节等于把审计记录和 Python 版本绑死
    （3.11 起 ``Enum.__format__`` 改用 ``__str__``，同一行代码换个版本输出就变了）。
    """

    def test_disagreement_reason_uses_protocol_values(self):
        merged = merge_verdicts(
            [[verdict("k1", "include")], [verdict("k1", "exclude")]], CONFIG
        )

        reason = merged["k1"].reason

        assert "通道间分歧" in reason
        assert "exclude" in reason and "include" in reason
        assert "Decision." not in reason, f"枚举 repr 泄漏进审计文本：{reason}"

    def test_human_queue_channel_column_uses_protocol_values(self):
        merged = merge_verdicts(
            [
                [verdict("k1", "include", confidence=0.9)],
                [verdict("k1", "exclude", confidence=0.7)],
            ],
            CONFIG,
        )

        csv = render_human_queue(merged, {"k1": record("k1")})

        assert "include@0.90" in csv
        assert "Decision." not in csv, f"枚举 repr 泄漏进人工队列 CSV：{csv}"


class TestCarryAdjudications:
    """续跑不得抹掉人工裁决。

    ``lit screen --resume`` 会把上一轮的判定按通道拆回去、重新 ``merge_verdicts``。
    合并函数构造的是全新的 ``MergedDecision``，于是 ``adjudicated_by`` /
    ``adjudicated_at`` / ``adjudication_reason`` / ``previous_decision`` 全部丢失——
    人工花时间裁定过的记录，续跑一次就退回模型判定，且没有任何提示。

    人工裁决是终审。续跑补的是"缺的那个通道"，不是推翻已经定谳的结论。
    """

    @staticmethod
    def _adjudicated(key: str = "k1") -> MergedDecision:
        return MergedDecision(
            record_key=key,
            decision=Decision.INCLUDE,
            needs_human=False,
            reason="人工裁定：确为儿科肠梗阻 AI 研究",
            channel_verdicts=[verdict(key, "unclear", confidence=0.5)],
            adjudicated_by="louwill",
            adjudicated_at="2026-08-03T14:09:08.201269+00:00",
            adjudication_reason="确为儿科肠梗阻 AI 研究",
            previous_decision=Decision.UNCLEAR,
        )

    def test_resume_without_carry_loses_the_human_decision(self):
        """先钉住缺陷本身：裸 merge_verdicts 确实会丢裁决。"""
        remerged = merge_verdicts(
            [[verdict("k1", "exclude")], [verdict("k1", "exclude")]], CONFIG
        )

        assert remerged["k1"].adjudicated_by is None
        assert remerged["k1"].decision is Decision.EXCLUDE

    def test_human_decision_survives_a_resume_remerge(self):
        remerged = merge_verdicts(
            [[verdict("k1", "exclude")], [verdict("k1", "exclude")]], CONFIG
        )

        carried = carry_adjudications(remerged, {"k1": self._adjudicated()})

        assert carried["k1"].decision is Decision.INCLUDE
        assert carried["k1"].needs_human is False
        assert carried["k1"].adjudicated_by == "louwill"
        assert carried["k1"].adjudication_reason == "确为儿科肠梗阻 AI 研究"
        assert carried["k1"].previous_decision is Decision.UNCLEAR

    def test_fresh_channel_verdicts_are_kept_for_audit(self):
        remerged = merge_verdicts(
            [[verdict("k1", "exclude")], [verdict("k1", "exclude")]], CONFIG
        )

        carried = carry_adjudications(remerged, {"k1": self._adjudicated()})

        assert [item.decision for item in carried["k1"].channel_verdicts] == [
            Decision.EXCLUDE,
            Decision.EXCLUDE,
        ]

    def test_records_without_adjudication_are_untouched(self):
        remerged = merge_verdicts(
            [[verdict("k2", "include")], [verdict("k2", "include")]], CONFIG
        )
        previous = {"k2": MergedDecision(
            record_key="k2", decision=Decision.EXCLUDE, needs_human=False, reason="模型判定"
        )}

        carried = carry_adjudications(remerged, previous)

        assert carried["k2"].decision is Decision.INCLUDE
        assert carried["k2"].adjudicated_by is None

    def test_does_not_mutate_its_inputs(self):
        remerged = merge_verdicts(
            [[verdict("k1", "exclude")], [verdict("k1", "exclude")]], CONFIG
        )
        previous = {"k1": self._adjudicated()}

        carry_adjudications(remerged, previous)

        assert remerged["k1"].decision is Decision.EXCLUDE
        assert remerged["k1"].adjudicated_by is None

    def test_an_adjudicated_record_missing_from_this_round_is_reported(self):
        """裁决过的记录这轮不见了，说明语料变了——静默丢掉比报错危险得多。"""
        with pytest.raises(KeyError):
            carry_adjudications({}, {"k1": self._adjudicated()})
