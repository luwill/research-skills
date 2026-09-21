"""筛选轮次的提交尾段：审计元数据、退步守卫、产物落盘。

这段逻辑原本长在 `cli.py` 的 screen 命令里，没有任何测试覆盖，而它管着三件
出错就很难发现的事：

1. 轮次的审计字段齐不齐（缺了 `lit verify` 会判轮次不可审计）；
2. 跑砸的一轮会不会盖掉上一轮好结果（下游只认轮次号最大的那一轮）；
3. 试跑会不会占掉正式轮次号。

三个后端（OpenAI 兼容、宿主、判定 API）都要走同一份，否则它们产出的轮次
在审计上就不是同一种东西。
"""

from __future__ import annotations

import json

import pytest

from litsearch.dedupe import CanonicalRecord
from litsearch.protocol import Topic
from litsearch.run import Run
from litsearch.screen import Decision, MergedDecision, ScreeningRound
from litsearch.screen_commit import (
    BackendResult,
    Regression,
    commit_round,
    find_regression,
    round_metadata,
)

TOPIC_YAML = """
id: t
title: T
window: {start: 2021-07-01, end: 2026-07-27}
concepts: {a: {required: true, terms: [stroke]}}
query_plan: {combinations: [[a]]}
criteria: {include: [{id: I1, text: x}]}
"""


@pytest.fixture
def topic_path(tmp_path):
    path = tmp_path / "topic.yaml"
    path.write_text(TOPIC_YAML, encoding="utf-8")
    return path


@pytest.fixture
def topic(topic_path) -> Topic:
    import yaml

    return Topic.model_validate(yaml.safe_load(topic_path.read_text(encoding="utf-8")))


@pytest.fixture
def run(tmp_path) -> Run:
    return Run.create(tmp_path / "runs", "t", "20200101T000000Z")


def record(key: str) -> CanonicalRecord:
    return CanonicalRecord(key=key, title=f"Paper {key}", sources=("openalex",))


def decision(key: str, value: str, *, queued: bool = False) -> MergedDecision:
    return MergedDecision(
        record_key=key,
        decision=Decision(value),
        needs_human=queued,
        reason="缺少判定" if queued else "",
    )


def result(decisions: dict[str, MergedDecision], **overrides) -> BackendResult:
    payload = {
        "decisions": decisions,
        "usage": {"cache_hit": 0, "cache_miss": 10, "output": 5},
        "failures": (),
        "provider": "api.deepseek.com",
        "model": "deepseek-v4-flash",
        "endpoint_host": "api.deepseek.com",
        "parameters": {"channels": 2, "batch_size": 25},
        "prompt_sha256": "a" * 64,
    }
    payload.update(overrides)
    return BackendResult(**payload)


class TestRoundMetadata:
    def test_carries_every_field_lit_verify_expects(self, topic):
        meta = round_metadata(result({"k": decision("k", "include")}), topic, expected=7)

        assert meta["provider"] == "api.deepseek.com"
        assert meta["model"] == "deepseek-v4-flash"
        assert meta["endpoint_host"] == "api.deepseek.com"
        assert meta["parameters"] == {"channels": 2, "batch_size": 25}
        assert meta["system_prompt_sha256"] == "a" * 64
        assert meta["expected_records"] == 7
        assert meta["failures"] == []
        assert meta["usage"] == {"cache_hit": 0, "cache_miss": 10, "output": 5}
        assert len(meta["topic_fingerprint"]) == 64

    def test_the_metadata_is_accepted_by_the_frozen_round_model(self, topic):
        """元数据字段一旦与 ScreeningRound 对不上，轮次就根本写不出来。"""
        meta = round_metadata(result({}), topic, expected=0)

        round_ = ScreeningRound(number=1, topic_sha256="b" * 64, decisions={}, **meta)

        assert round_.model == "deepseek-v4-flash"

    def test_failures_survive_into_the_round(self, topic):
        meta = round_metadata(result({}, failures=("batch 3 超时",)), topic, expected=0)

        assert meta["failures"] == ["batch 3 超时"]


class TestFindRegression:
    """判据是**已定谳集合的丢失**，不是判定总数。

    总数测不到它要防的那种失败：``merge_verdicts(expected_keys=by_key)`` 保证每条
    记录都有一个判定，所以一轮全灭表现为「每条都有判定，但全是待人工」——
    数量分毫不变。当年那次事故能表现成「0 条判定」，是因为当时还没有 expected_keys。

    定谳 = ``not needs_human``。它才是下游真正消费的东西：``included.jsonl``
    只收已定谳的纳入。
    """

    @staticmethod
    def settled(key: str, value: str = "include") -> MergedDecision:
        return decision(key, value)

    @staticmethod
    def queued(key: str) -> MergedDecision:
        return decision(key, "unclear", queued=True)

    def test_a_first_round_is_never_a_regression(self):
        assert find_regression({"a": self.settled("a")}, None) is None

    def test_keeping_every_settled_record_is_fine(self):
        previous = {"a": self.settled("a"), "q": self.queued("q")}
        now = {"a": self.settled("a", "exclude"), "q": self.queued("q")}

        assert find_regression(now, previous) is None

    def test_settling_a_previously_queued_record_is_progress_not_regression(self):
        previous = {"a": self.settled("a"), "q": self.queued("q")}
        now = {"a": self.settled("a"), "q": self.settled("q")}

        assert find_regression(now, previous) is None

    def test_growing_the_corpus_is_not_a_regression(self):
        previous = {"a": self.settled("a")}
        now = {"a": self.settled("a"), "new": self.settled("new")}

        assert find_regression(now, previous) is None

    def test_a_settled_record_falling_back_into_the_queue_is_caught(self):
        """同样的判定条数，但内容退步了——这正是总数判据漏掉的那一类。"""
        previous = {"a": self.settled("a"), "b": self.settled("b")}
        now = {"a": self.settled("a"), "b": self.queued("b")}

        found = find_regression(now, previous)

        assert found is not None
        assert len(now) == len(previous)
        assert found.lost_keys == ("b",)
        assert (found.settled_before, found.settled_now) == (2, 1)

    def test_a_wholesale_failure_is_caught_even_though_the_count_is_unchanged(self):
        previous = {f"k{i}": self.settled(f"k{i}") for i in range(15375)}
        now = {f"k{i}": self.queued(f"k{i}") for i in range(15375)}

        found = find_regression(now, previous)

        assert found is not None
        assert found.lost == 15375
        assert found.settled_now == 0

    def test_a_settled_record_vanishing_entirely_is_caught(self):
        previous = {"a": self.settled("a"), "gone": self.settled("gone")}
        now = {"a": self.settled("a")}

        found = find_regression(now, previous)

        assert found is not None
        assert found.lost_keys == ("gone",)

    def test_a_human_adjudication_counts_as_settled_and_must_not_be_lost(self):
        adjudicated = MergedDecision(
            record_key="h",
            decision=Decision.INCLUDE,
            needs_human=False,
            reason="人工裁定：符合 I1",
            adjudicated_by="louwill",
        )

        found = find_regression({"h": self.queued("h")}, {"h": adjudicated})

        assert found is not None
        assert found.lost_keys == ("h",)

    def test_the_message_states_the_counts_and_names_examples(self):
        previous = {f"k{i}": self.settled(f"k{i}") for i in range(200)}
        now = {f"k{i}": self.queued(f"k{i}") for i in range(200)}

        text = find_regression(now, previous).message()

        assert "200" in text
        assert "k0" in text
        assert "--allow-regression" in text

    def test_the_message_lists_at_most_a_handful_of_keys(self):
        previous = {f"k{i}": self.settled(f"k{i}") for i in range(200)}
        now = {f"k{i}": self.queued(f"k{i}") for i in range(200)}

        text = find_regression(now, previous).message()

        assert text.count("k1") < 20, "举例而已，不要把 200 个 key 全倒出来"

    def test_it_is_a_plain_value_not_an_exception(self):
        """判定是否退步是纯计算；要不要因此中止是调用方的策略。"""
        found = find_regression({"a": self.queued("a")}, {"a": self.settled("a")})

        assert isinstance(found, Regression)


class TestCommitRound:
    DECISIONS = {
        "a": decision("a", "include"),
        "b": decision("b", "exclude"),
        "q": decision("q", "unclear", queued=True),
    }
    RECORDS = {key: record(key) for key in ("a", "b", "q")}

    def test_writes_the_round_queue_and_included_set(self, run, topic, topic_path):
        path = commit_round(
            run, topic_path, result(self.DECISIONS), self.RECORDS, topic=topic, trial=False
        )

        assert path.name == "screening_round_1.json"
        assert (run.root / "human_queue.csv").exists()
        included = run.read_jsonl("included.jsonl")
        assert [item["key"] for item in included] == ["a"]

    def test_queued_records_never_reach_the_included_set(self, run, topic, topic_path):
        """待人工裁定的记录还没有结论，混进 included.jsonl 就是凭空纳入。"""
        queued_include = {"q": decision("q", "include", queued=True)}

        commit_round(
            run, topic_path, result(queued_include), {"q": record("q")}, topic=topic, trial=False
        )

        assert run.read_jsonl("included.jsonl") == []

    def test_the_round_number_continues_from_what_is_already_there(
        self, run, topic, topic_path
    ):
        run.write_text("screening_round_1.json", "{}")
        run.write_text("screening_round_4.json", "{}")

        path = commit_round(
            run, topic_path, result(self.DECISIONS), self.RECORDS, topic=topic, trial=False
        )

        assert path.name == "screening_round_5.json"

    def test_a_trial_does_not_occupy_a_round(self, run, topic, topic_path):
        """一次 --limit 100 的试跑若占掉轮次号，就会盖住正式全量结果。"""
        path = commit_round(
            run, topic_path, result(self.DECISIONS), self.RECORDS, topic=topic, trial=True
        )

        assert path.name == "screening_trial.json"
        assert (run.root / "human_queue_trial.csv").exists()
        assert not list(run.root.glob("screening_round_*.json"))
        assert run.read_jsonl("included.jsonl") == []

    def test_the_written_round_is_valid_and_auditable(self, run, topic, topic_path):
        path = commit_round(
            run, topic_path, result(self.DECISIONS), self.RECORDS, topic=topic, trial=False
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        parsed = ScreeningRound.model_validate(payload)
        assert parsed.number == 1
        assert parsed.expected_records == 3
        assert len(parsed.topic_sha256) == 64
        assert parsed.model == "deepseek-v4-flash"
        assert set(parsed.decisions) == {"a", "b", "q"}
