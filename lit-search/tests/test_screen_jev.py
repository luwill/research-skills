"""Jev 筛选后端：编译问题、打分、路由成判定。

**它不是第三个通道，是打分器。** 把 Jev 映射成现有的两个通道会坏事：一条明显
离题的记录 p_inc=0.03、p_exc=0.02，纳入视角判 exclude、排除视角"找不到排除
理由"判 include，``merge_verdicts`` 会判成分歧送进人工队列。要避免就得让第二个
通道也读 p_inc，那两个通道就成了同一向量的函数——正是 screen.py 明令禁止的
"同一个偏差重复两次"。所以每条记录出一个 Verdict，由纯函数 ``route`` 直接
构造 ``MergedDecision``，``merge_verdicts`` 完全不参与。
"""

from __future__ import annotations

import pytest

from litsearch.dedupe import CanonicalRecord
from litsearch.jev_client import JevError
from litsearch.jev_profile import JevProfile
from litsearch.protocol import Topic
from litsearch.screen import Decision
from litsearch.screen_jev import (
    ScoreRow,
    build_state,
    compile_questions,
    estimate_jev,
    gold_set_violations,
    pending_records,
    questions_sha256,
    route,
    route_all,
    score_records,
)

TOPIC = Topic.model_validate(
    {
        "id": "t",
        "title": "T",
        "window": {"start": "2021-07-01", "end": "2026-07-27"},
        "concepts": {"a": {"required": True, "terms": ["stroke"]}},
        "query_plan": {"combinations": [["a"]]},
        "criteria": {
            "include": [
                {"id": "I1", "text": "研究对象为人类缺血性卒中的脑影像。"},
                {"id": "I2", "text": "存在病灶级别的分割或体积量化任务。"},
                {"id": "I3", "text": "报告了 Dice/HD95 等定量结果。"},
            ],
            "exclude": [
                {"id": "X1", "text": "仅做出血性卒中，且无缺血性卒中数据。"},
                {"id": "X2", "text": "仅做分类/检出，不涉及分割。"},
            ],
        },
        "gold_set": [{"doi": "10.1000/gold"}],
    }
)
PROFILE = JevProfile(topic_id="t", skip=["I3"])


def record(key: str, *, abstract: str | None = "摘要正文", doi: str = "") -> CanonicalRecord:
    return CanonicalRecord(
        key=key,
        title=f"Paper {key}",
        abstract=abstract,
        venue="Medical Image Analysis",
        identifiers={"doi": doi} if doi else {},
        sources=("openalex",),
    )


def row(key: str, answers: dict[str, float], *, qsha: str = "q" * 64) -> ScoreRow:
    return ScoreRow(
        record_key=key,
        model="jev-1.13.0",
        questions_sha256=qsha,
        state_sha256="s" * 64,
        answers=answers,
        input_tokens=1200,
    )


class TestCompileQuestions:
    def test_one_noul_per_active_criterion_keyed_by_its_id(self):
        questions = compile_questions(TOPIC, PROFILE)

        assert set(questions) == {"I1", "I2", "X1", "X2"}
        assert all(item["type"] == "noul" for item in questions.values())

    def test_the_criterion_text_is_copied_verbatim(self):
        """标准原文就是协议。改写或概括一下，判定依据就与协议脱钩了。

        实测也支持照抄：中文标准原文 AUC 0.989，手写英文原子问题 0.982。
        """
        questions = compile_questions(TOPIC, PROFILE)

        assert TOPIC.criteria.include[0].text in str(questions["I1"]["instructions"])

    def test_a_skipped_criterion_is_not_asked(self):
        assert "I3" not in compile_questions(TOPIC, PROFILE)

    def test_ignore_mode_drops_the_exclusion_questions(self):
        profile = JevProfile(topic_id="t", skip=["I3"], exclusions="ignore")

        assert set(compile_questions(TOPIC, profile)) == {"I1", "I2"}

    def test_the_hash_changes_when_the_question_set_changes(self):
        """问题集变了，旧打分就不再可比——续跑必须重新打分而不是沿用。"""
        base = questions_sha256(compile_questions(TOPIC, PROFILE))
        fewer = questions_sha256(
            compile_questions(TOPIC, JevProfile(topic_id="t", skip=["I3", "X1"]))
        )

        assert base != fewer

    def test_the_hash_is_stable_across_calls(self):
        first = questions_sha256(compile_questions(TOPIC, PROFILE))
        second = questions_sha256(compile_questions(TOPIC, PROFILE))

        assert first == second and len(first) == 64


class TestBuildState:
    def test_carries_only_what_the_questions_need(self):
        state = build_state(record("k"), PROFILE)

        assert set(state) == {"title", "venue", "abstract"}

    def test_a_missing_abstract_is_stated_not_left_blank(self):
        """留空会让模型以为"摘要说了但没提到"，而不是"根本没有摘要"。"""
        state = build_state(record("k", abstract=None), PROFILE)

        assert "无摘要" in state["abstract"]

    def test_a_long_abstract_is_truncated_and_says_so(self):
        """state 越大判别力越差。截断必须可见，否则看不出结论是基于半篇摘要。"""
        profile = JevProfile(topic_id="t", max_abstract_chars=200)

        state = build_state(record("k", abstract="长" * 5000), profile)

        assert len(state["abstract"]) < 400
        assert "截断" in state["abstract"]


class TestRoute:
    def test_the_score_is_the_weakest_active_inclusion_criterion(self):
        """纳入标准要同时满足，合取取最小；求平均会让一条严重不满足的被掩盖。"""
        decision = route(
            "k", row("k", {"I1": 0.99, "I2": 0.34, "X1": 0.0, "X2": 0.0}), TOPIC, PROFILE
        )

        assert decision.channel_verdicts[0].confidence == pytest.approx(0.66)
        assert decision.decision is Decision.UNCLEAR

    def test_above_the_include_band_it_is_settled_as_include(self):
        decision = route(
            "k", row("k", {"I1": 0.99, "I2": 0.95, "X1": 0.0, "X2": 0.0}), TOPIC, PROFILE
        )

        assert decision.decision is Decision.INCLUDE
        assert decision.needs_human is False

    def test_below_the_exclude_band_it_is_settled_as_exclude(self):
        decision = route(
            "k", row("k", {"I1": 0.02, "I2": 0.9, "X1": 0.0, "X2": 0.0}), TOPIC, PROFILE
        )

        assert decision.decision is Decision.EXCLUDE
        assert decision.needs_human is False

    def test_between_the_bands_it_goes_to_a_human(self):
        decision = route(
            "k", row("k", {"I1": 0.5, "I2": 0.5, "X1": 0.0, "X2": 0.0}), TOPIC, PROFILE
        )

        assert decision.decision is Decision.UNCLEAR
        assert decision.needs_human is True

    def test_the_reason_names_the_weakest_criterion_and_every_probability(self):
        decision = route(
            "k", row("k", {"I1": 0.99, "I2": 0.34, "X1": 0.8, "X2": 0.0}), TOPIC, PROFILE
        )

        assert "I2" in decision.reason
        assert "0.99" in decision.reason and "0.34" in decision.reason
        assert "X1" in decision.reason, "排除标准的概率要给人看，即使不参与打分"

    def test_exclusion_probabilities_do_not_move_the_score(self):
        """实测：乘上 (1 - max 排除概率) 反而更差（AUC 0.989 → 0.981）。

        官方文档也说，一个问题与其否定式的概率不满足互补关系。
        """
        high_exclusion = route(
            "k", row("k", {"I1": 0.99, "I2": 0.95, "X1": 0.99, "X2": 0.99}), TOPIC, PROFILE
        )

        assert high_exclusion.decision is Decision.INCLUDE

    def test_a_missing_score_becomes_a_queue_item_that_says_so(self):
        """打分缺失不能当成 0——那会把一篇没判过的论文直接排掉。"""
        decision = route("k", None, TOPIC, PROFILE)

        assert decision.needs_human is True
        assert "缺少" in decision.reason, "cli.py 靠这两个字统计漏判数"

    def test_it_emits_one_verdict_not_a_channel_pair(self):
        decision = route(
            "k", row("k", {"I1": 0.9, "I2": 0.9, "X1": 0.0, "X2": 0.0}), TOPIC, PROFILE
        )

        assert len(decision.channel_verdicts) == 1
        assert decision.channel_verdicts[0].channel == 0

    def test_the_matched_criteria_are_the_ones_that_actually_fired(self):
        decision = route(
            "k", row("k", {"I1": 0.99, "I2": 0.95, "X1": 0.9, "X2": 0.0}), TOPIC, PROFILE
        )

        assert "I1" in decision.matched_criteria and "I2" in decision.matched_criteria

    def test_an_answer_missing_an_active_criterion_is_refused(self):
        """少问了一条标准却照常路由，等于悄悄放开它。"""
        with pytest.raises(JevError):
            route("k", row("k", {"I1": 0.9}), TOPIC, PROFILE)


class TestRouteAll:
    def test_every_record_gets_a_decision_even_without_a_score(self):
        records = [record("a"), record("b")]
        rows = {"a": row("a", {"I1": 0.9, "I2": 0.9, "X1": 0.0, "X2": 0.0})}

        decisions = route_all(records, rows, TOPIC, PROFILE)

        assert set(decisions) == {"a", "b"}
        assert decisions["b"].needs_human is True


class TestPendingRecords:
    QSHA = "q" * 64

    def test_a_record_with_a_matching_score_is_done(self):
        rows = {"a": row("a", {"I1": 0.9}, qsha=self.QSHA)}

        assert pending_records([record("a")], rows, self.QSHA) == []

    def test_a_record_scored_under_a_different_question_set_is_pending(self):
        """问题集变了，旧打分不再可比。沿用它等于拿旧标准判新协议。"""
        rows = {"a": row("a", {"I1": 0.9}, qsha="other" + "0" * 59)}

        assert [item.key for item in pending_records([record("a")], rows, self.QSHA)] == ["a"]

    def test_an_unscored_record_is_pending(self):
        assert [item.key for item in pending_records([record("a")], {}, self.QSHA)] == ["a"]


class TestGoldSetViolations:
    def test_a_gold_seed_settled_as_exclude_is_named(self):
        records = [record("g", doi="10.1000/gold")]
        decisions = route_all(
            records, {"g": row("g", {"I1": 0.01, "I2": 0.9, "X1": 0.0, "X2": 0.0})}, TOPIC, PROFILE
        )

        assert gold_set_violations(decisions, records, TOPIC) == ["g"]

    def test_a_gold_seed_merely_queued_is_not_a_violation(self):
        """进人工队列不是排除——人还会看它。"""
        records = [record("g", doi="10.1000/gold")]
        decisions = route_all(
            records, {"g": row("g", {"I1": 0.5, "I2": 0.5, "X1": 0.0, "X2": 0.0})}, TOPIC, PROFILE
        )

        assert gold_set_violations(decisions, records, TOPIC) == []

    def test_a_non_gold_record_excluded_is_fine(self):
        records = [record("x")]
        decisions = route_all(
            records, {"x": row("x", {"I1": 0.01, "I2": 0.9, "X1": 0.0, "X2": 0.0})}, TOPIC, PROFILE
        )

        assert gold_set_violations(decisions, records, TOPIC) == []


class FakeJev:
    """按 record 标题决定答什么的判定客户端替身。"""

    def __init__(self, answers, *, fail_on: set[str] | None = None) -> None:
        self.answers = answers
        self.fail_on = fail_on or set()
        self.asked: list[dict] = []
        self.model = "jev-1.13.0"

    async def ask(self, state, questions):
        self.asked.append(state)
        title = state["title"]
        if title in self.fail_on:
            raise JevError(f"模拟失败：{title}")
        from litsearch.jev_client import JevResponse

        return JevResponse(
            model="jev-1.13.0",
            answers={key: {"type": "noul", "noul": self.answers[key]} for key in questions},
            input_tokens=1200,
            output_tokens=40,
        )


class TestScoreRecords:
    ANSWERS = {"I1": 0.9, "I2": 0.8, "X1": 0.1, "X2": 0.05}

    async def test_one_request_per_record_carrying_every_question(self):
        client = FakeJev(self.ANSWERS)

        rows, usage = await score_records(client, TOPIC, PROFILE, [record("a"), record("b")])

        assert len(client.asked) == 2
        assert len(rows) == 2
        assert usage.cache_miss == 2400

    async def test_every_input_token_is_charged_as_a_miss(self):
        """Jev 没有前缀缓存，每次都吃完整 state。算成命中会低估成本。"""
        client = FakeJev(self.ANSWERS)

        _, usage = await score_records(client, TOPIC, PROFILE, [record("a")])

        assert usage.cache_hit == 0
        assert usage.cache_miss == 1200

    async def test_rows_carry_the_question_hash_so_resume_can_tell_them_apart(self):
        client = FakeJev(self.ANSWERS)

        rows, _ = await score_records(client, TOPIC, PROFILE, [record("a")])

        assert rows[0].questions_sha256 == questions_sha256(compile_questions(TOPIC, PROFILE))
        assert rows[0].model == "jev-1.13.0"

    async def test_a_failed_record_is_reported_and_simply_has_no_row(self):
        """有行就是判过，没行就是没判过。用一个假分数占位是最危险的做法。"""
        seen: list[str] = []
        client = FakeJev(self.ANSWERS, fail_on={"Paper b"})

        rows, _ = await score_records(
            client,
            TOPIC,
            PROFILE,
            [record("a"), record("b")],
            on_error=lambda key, err: seen.append(key),
        )

        assert [item.record_key for item in rows] == ["a"]
        assert seen == ["b"]

    async def test_a_checkpoint_sees_each_row_as_it_lands(self):
        """上万条规模跑到一半断掉，没有断点就要全部重跑。"""
        saved: list[ScoreRow] = []
        client = FakeJev(self.ANSWERS)

        await score_records(
            client, TOPIC, PROFILE, [record("a"), record("b")], checkpoint=saved.append
        )

        assert len(saved) == 2


class TestEstimate:
    def test_one_request_per_record(self):
        estimate = estimate_jev(TOPIC, PROFILE, [record("a"), record("b")])

        assert estimate.requests == 2
        assert estimate.records == 2

    def test_input_only_and_never_counted_as_a_cache_hit(self):
        estimate = estimate_jev(TOPIC, PROFILE, [record("a")])

        assert estimate.usage.cache_hit == 0
        assert estimate.usage.cache_miss > 0
        assert estimate.usage.output == 0

    def test_asking_more_questions_costs_only_a_little_more(self):
        """实测 token 随问题数亚线性增长：1 问 630、16 问 966，state 占大头。"""
        few = estimate_jev(TOPIC, JevProfile(topic_id="t", exclusions="ignore"), [record("a")])
        many = estimate_jev(TOPIC, PROFILE, [record("a")])

        assert many.usage.cache_miss > few.usage.cache_miss
        assert many.usage.cache_miss < few.usage.cache_miss * 2


class TestTriageQueue:
    """人工队列分诊：把「随机顺序的一千多行」变成「有优先级的工作队列」。

    排序按**分数降序**，最可能纳入的排最前。理由是这个项目一以贯之的不对称：
    错误排除不可逆，错误纳入只是多读一篇全文。队列往往没人看得完（实测两个 run
    合计 2,541 行至今空着），所以看得越靠前，越该是「漏掉代价最大」的那些。
    """

    RECORDS = [record("hi"), record("mid"), record("lo"), record("none")]
    ROWS = {
        "hi": row("hi", {"I1": 0.88, "I2": 0.9, "X1": 0.0, "X2": 0.0}),
        "mid": row("mid", {"I1": 0.5, "I2": 0.6, "X1": 0.0, "X2": 0.0}),
        "lo": row("lo", {"I1": 0.12, "I2": 0.9, "X1": 0.7, "X2": 0.0}),
    }

    def _queued(self) -> dict:
        from litsearch.screen import Decision as D
        from litsearch.screen import MergedDecision

        return {
            item.key: MergedDecision(
                record_key=item.key, decision=D.UNCLEAR, needs_human=True, reason="通道间分歧"
            )
            for item in self.RECORDS
        }

    def test_the_header_keeps_the_adjudicate_contract(self):
        from litsearch.screen_jev import render_triage_queue

        csv = render_triage_queue(self._queued(), self.RECORDS, self.ROWS, TOPIC, PROFILE)

        assert csv.splitlines()[0].startswith("record_key,decision,reviewer,reason")

    def test_rows_are_ordered_most_likely_include_first(self):
        from litsearch.screen_jev import render_triage_queue

        csv = render_triage_queue(self._queued(), self.RECORDS, self.ROWS, TOPIC, PROFILE)

        keys = [line.split(",")[0] for line in csv.splitlines()[1:]]
        assert keys[:3] == ["hi", "mid", "lo"]

    def test_an_unscored_record_sorts_last_and_says_so(self):
        """没打上分的不能排在前面假装最不相关——它只是没判过。"""
        from litsearch.screen_jev import render_triage_queue

        csv = render_triage_queue(self._queued(), self.RECORDS, self.ROWS, TOPIC, PROFILE)

        lines = csv.splitlines()[1:]
        assert lines[-1].split(",")[0] == "none"
        assert "未打分" in lines[-1]

    def test_each_row_names_the_weakest_criterion_and_any_fired_exclusion(self):
        from litsearch.screen_jev import render_triage_queue

        csv = render_triage_queue(self._queued(), self.RECORDS, self.ROWS, TOPIC, PROFILE)

        lo_line = next(line for line in csv.splitlines() if line.startswith("lo,"))
        assert "I1" in lo_line, "最弱的纳入标准要写出来"
        assert "X1" in lo_line, "命中的排除标准也要写出来"

    def test_only_queued_records_appear(self):
        from litsearch.screen import Decision as D
        from litsearch.screen import MergedDecision
        from litsearch.screen_jev import render_triage_queue

        decisions = self._queued()
        decisions["hi"] = MergedDecision(
            record_key="hi", decision=D.INCLUDE, needs_human=False, reason=""
        )

        csv = render_triage_queue(decisions, self.RECORDS, self.ROWS, TOPIC, PROFILE)

        assert "hi," not in csv


class TestTiebreakCandidates:
    """自动裁决只解开一类：两个 LLM 通道**互相矛盾**、而 Jev 明确站在纳入一侧。

    这不是让模型单方面拍板——是两个不同模型族达成一致。而且只往可逆方向走。
    """

    @staticmethod
    def _disagreement(key: str) -> object:
        from litsearch.screen import Decision as D
        from litsearch.screen import MergedDecision, Verdict

        return MergedDecision(
            record_key=key,
            decision=D.UNCLEAR,
            needs_human=True,
            reason="通道间分歧：['exclude', 'include']",
            channel_verdicts=[
                Verdict(record_key=key, decision=D.INCLUDE, confidence=0.9, channel=0),
                Verdict(record_key=key, decision=D.EXCLUDE, confidence=0.8, channel=1),
            ],
        )

    @staticmethod
    def _low_confidence(key: str) -> object:
        from litsearch.screen import Decision as D
        from litsearch.screen import MergedDecision, Verdict

        return MergedDecision(
            record_key=key,
            decision=D.UNCLEAR,
            needs_human=True,
            reason="置信度不足（最低 0.55 < 阈值 0.7）",
            channel_verdicts=[
                Verdict(record_key=key, decision=D.INCLUDE, confidence=0.55, channel=0),
                Verdict(record_key=key, decision=D.INCLUDE, confidence=0.9, channel=1),
            ],
        )

    def test_a_disagreement_that_jev_settles_toward_include_qualifies(self):
        from litsearch.screen_jev import tiebreak_candidates

        rows = {"k": row("k", {"I1": 0.92, "I2": 0.9, "X1": 0.0, "X2": 0.0})}

        picked = tiebreak_candidates({"k": self._disagreement("k")}, rows, TOPIC, PROFILE)

        assert [item["record_key"] for item in picked] == ["k"]
        assert picked[0]["decision"] == "include"
        assert "0.90" in picked[0]["reason"]

    def test_jev_below_the_include_band_does_not_qualify(self):
        from litsearch.screen_jev import tiebreak_candidates

        rows = {"k": row("k", {"I1": 0.5, "I2": 0.9, "X1": 0.0, "X2": 0.0})}

        assert tiebreak_candidates({"k": self._disagreement("k")}, rows, TOPIC, PROFILE) == []

    def test_a_low_confidence_queue_item_is_left_to_a_human(self):
        """低置信度不是分歧。两个通道本就一致，没有僵局可打破。"""
        from litsearch.screen_jev import tiebreak_candidates

        rows = {"k": row("k", {"I1": 0.95, "I2": 0.95, "X1": 0.0, "X2": 0.0})}

        assert tiebreak_candidates({"k": self._low_confidence("k")}, rows, TOPIC, PROFILE) == []

    def test_a_disagreement_where_no_channel_said_include_does_not_qualify(self):
        """没有通道主张纳入，Jev 就是在单方面拍板，不是打破僵局。"""
        from litsearch.screen import Decision as D
        from litsearch.screen import MergedDecision, Verdict
        from litsearch.screen_jev import tiebreak_candidates

        both_unclear = MergedDecision(
            record_key="k",
            decision=D.UNCLEAR,
            needs_human=True,
            reason="有通道判定为 unclear（信息不足）",
            channel_verdicts=[
                Verdict(record_key="k", decision=D.UNCLEAR, confidence=0.5, channel=0),
                Verdict(record_key="k", decision=D.EXCLUDE, confidence=0.9, channel=1),
            ],
        )
        rows = {"k": row("k", {"I1": 0.95, "I2": 0.95, "X1": 0.0, "X2": 0.0})}

        assert tiebreak_candidates({"k": both_unclear}, rows, TOPIC, PROFILE) == []

    def test_an_unscored_record_never_qualifies(self):
        from litsearch.screen_jev import tiebreak_candidates

        assert tiebreak_candidates({"k": self._disagreement("k")}, {}, TOPIC, PROFILE) == []
