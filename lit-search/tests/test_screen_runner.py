"""筛选的 DeepSeek API 驱动层。用假客户端，不打网络。

三个由 API 形态决定的设计点，都在这里被测住：

- **走 strict 工具调用，不走 JSON 模式。** DeepSeek 的 `response_format=json_object`
  只保证"是合法 JSON"，不保证形状，且官方文档承认"偶尔返回空内容"。
  strict 工具调用在服务端按 JSON Schema 校验参数——这才是结构化输出。
  代价是必须走 beta 端点。
- **没有 Batches API**，所以没有批处理半价那条路，只能实时调用 + 并发。
- **缓存是自动的**，命中与否只能从 `usage.prompt_cache_hit_tokens` 读回。
  纳排标准在整轮筛选中逐字不变，是天然的缓存前缀。
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from litsearch.dedupe import CanonicalRecord
from litsearch.protocol import Topic
from litsearch.screen import Verdict
from litsearch.screen_runner import (
    BASE_URL,
    DEFAULT_MODEL,
    TOOL_NAME,
    Usage,
    build_requests,
    build_tool,
    estimate,
    pending_by_channel,
    regroup_by_channel,
    run_screening,
)


@pytest.fixture
def topic() -> Topic:
    return Topic.model_validate(
        {
            "id": "t",
            "title": "T",
            "window": {"start": "2021-07-01", "end": "2026-07-27"},
            "concepts": {"a": {"required": True, "terms": ["stroke"]}},
            "query_plan": {"combinations": [["a"]]},
            "criteria": {
                "include": [{"id": "I1", "text": "人类缺血性卒中影像"}],
                "exclude": [{"id": "X1", "text": "仅出血性卒中"}],
            },
            "screening": {"channels": 2, "confidence_threshold": 0.7, "batch_size": 2},
        }
    )


@pytest.fixture
def records() -> list[CanonicalRecord]:
    return [
        CanonicalRecord(key=f"k{i}", title=f"Paper {i}", abstract="Abstract text") for i in range(5)
    ]


def tool_reply(keys, decision="include"):
    payload = json.dumps(
        {
            "verdicts": [
                {
                    "record_key": key,
                    "decision": decision,
                    "matched_criteria": ["I1"],
                    "reason": "ok",
                    "confidence": 0.9,
                }
                for key in keys
            ]
        }
    )
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=[
                        SimpleNamespace(function=SimpleNamespace(name=TOOL_NAME, arguments=payload))
                    ]
                )
            )
        ],
        usage=SimpleNamespace(
            prompt_cache_hit_tokens=100,
            prompt_cache_miss_tokens=200,
            completion_tokens=50,
        ),
    )


class FakeClient:
    """最小的 OpenAI 兼容客户端替身。"""

    def __init__(self, responder):
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._responder = responder

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responder(kwargs)


def _keys_from(kwargs) -> list[str]:
    user = kwargs["messages"][-1]["content"]
    return [line.split("key: ")[1] for line in user.splitlines() if "key: " in line]


class TestToolSchema:
    def test_the_schema_is_strict_mode_compatible(self, topic):
        """strict 模式要求：不能有 $ref，每层 additionalProperties=false，
        且 required 必须列全所有属性。任何一条不满足，服务端会直接拒绝。"""
        tool = build_tool()
        raw = json.dumps(tool)

        assert "$ref" not in raw and "$defs" not in raw
        assert tool["function"]["strict"] is True

        def walk(node):
            if not isinstance(node, dict):
                return
            if node.get("type") == "object":
                assert node.get("additionalProperties") is False
                assert set(node.get("required", [])) == set(node.get("properties", {}))
            for value in node.values():
                if isinstance(value, dict):
                    walk(value)
                elif isinstance(value, list):
                    for item in value:
                        walk(item)

        walk(tool["function"]["parameters"])

    def test_decision_is_constrained_to_the_three_allowed_values(self):
        schema = build_tool()["function"]["parameters"]
        item = schema["properties"]["verdicts"]["items"]

        assert item["properties"]["decision"]["enum"] == ["include", "exclude", "unclear"]

    def test_the_beta_endpoint_is_used_because_strict_requires_it(self):
        assert BASE_URL.endswith("/beta")


class TestBuildRequests:
    def test_covers_every_batch_in_every_channel(self, topic, records):
        requests = build_requests(topic, records)

        assert len(requests) == 6  # 5 条 / 每批 2 条 = 3 批 × 2 通道
        assert {item.channel for item in requests} == {0, 1}

    def test_channels_use_different_system_prompts(self, topic, records):
        requests = build_requests(topic, records)

        first = next(item for item in requests if item.channel == 0)
        second = next(item for item in requests if item.channel == 1)
        assert first.system != second.system

    def test_criteria_appear_verbatim(self, topic, records):
        request = build_requests(topic, records)[0]

        assert "人类缺血性卒中影像" in request.system
        assert "仅出血性卒中" in request.system


class TestResume:
    """续跑：只补**各通道各自缺判定**的记录。

    实测背景：1,234 个请求里 359 个 APIConnectionError，且几乎全在通道 0，
    导致 8,915 条记录只拿到一个通道的判定。重跑全部等于白烧一遍钱和两小时。
    """

    def _decisions(self, topic, records, judged: dict[int, list[str]]):
        from litsearch.screen import merge_verdicts

        channels = [
            [
                Verdict(record_key=key, decision="include", confidence=0.9, channel=channel)
                for key in keys
            ]
            for channel, keys in sorted(judged.items())
        ]
        return merge_verdicts(channels, topic.screening)

    def test_no_decisions_means_everything_is_pending(self, topic, records):
        pending = pending_by_channel(topic, records, None)

        assert {c: len(v) for c, v in pending.items()} == {0: 5, 1: 5}

    def test_only_the_channel_that_failed_is_rerun(self, topic, records):
        """通道 1 判完了、通道 0 整批连接失败——只该补通道 0。"""
        keys = [item.key for item in records]
        decisions = self._decisions(topic, records, {0: [], 1: keys})

        pending = pending_by_channel(topic, records, decisions)

        assert [item.key for item in pending[0]] == keys
        assert pending[1] == []

    def test_records_already_judged_by_both_channels_are_not_rerun(self, topic, records):
        keys = [item.key for item in records]
        decisions = self._decisions(topic, records, {0: keys, 1: keys})

        pending = pending_by_channel(topic, records, decisions)

        assert pending == {0: [], 1: []}

    def test_disagreements_are_not_rerun(self, topic, records):
        """通道分歧是**已经判过**的结论。重跑它既浪费钱，
        也会把一个本该由人裁定的分歧变成掷第二次骰子。"""
        keys = [item.key for item in records]
        decisions = self._decisions(topic, records, {0: keys, 1: keys})
        for item in decisions.values():
            item.needs_human = True
            item.reason = "通道间分歧"

        assert pending_by_channel(topic, records, decisions) == {0: [], 1: []}

    def test_legacy_verdicts_with_a_full_house_count_as_done(self, topic, records):
        """早于 channel 字段的旧判定：数量齐了就说明每个通道都判过。
        不这样认，一次字段升级就会让上一轮的钱全部白花。"""
        from litsearch.screen import merge_verdicts

        legacy = [
            [Verdict(record_key=item.key, decision="include", confidence=0.9) for item in records]
            for _ in range(2)
        ]
        decisions = merge_verdicts(legacy, topic.screening)

        assert pending_by_channel(topic, records, decisions) == {0: [], 1: []}

    def test_legacy_verdicts_that_are_short_rerun_every_channel(self, topic, records):
        """只有一份旧判定时分不清缺的是哪个通道——只能整条重判。
        猜错会让一条记录拿着两份来自同一视角的判定，双通道就名存实亡。"""
        from litsearch.screen import merge_verdicts

        legacy = [
            [Verdict(record_key=item.key, decision="include", confidence=0.9) for item in records],
            [],
        ]
        decisions = merge_verdicts(legacy, topic.screening)

        pending = pending_by_channel(topic, records, decisions)

        assert len(pending[0]) == len(records) and len(pending[1]) == len(records)

    def test_legacy_verdicts_are_regrouped_by_position(self, topic, records):
        """续跑时旧判定必须能并回来。并不回来 = 新一轮只有新判定，
        写下去就会遮蔽上一轮——实测这让一轮 15,375 条判定变成 0 条。"""
        from litsearch.screen import merge_verdicts

        legacy = [
            [Verdict(record_key=item.key, decision="include", confidence=0.9) for item in records]
            for _ in range(2)
        ]
        decisions = merge_verdicts(legacy, topic.screening)

        grouped = regroup_by_channel(decisions, 2)

        assert [len(item) for item in grouped] == [5, 5]
        assert all(item.channel == 0 for item in grouped[0])
        assert all(item.channel == 1 for item in grouped[1])

    def test_regroup_drops_records_whose_channel_cannot_be_known(self, topic, records):
        """只有一份无通道号的旧判定——归到哪个通道都是猜。
        丢弃即可：这些记录本来就会被判为全通道待补。"""
        from litsearch.screen import merge_verdicts

        legacy = [
            [Verdict(record_key=item.key, decision="include", confidence=0.9) for item in records],
            [],
        ]
        decisions = merge_verdicts(legacy, topic.screening)

        assert regroup_by_channel(decisions, 2) == [[], []]

    def test_requests_are_built_only_for_pending_channels(self, topic, records):
        requests = build_requests(topic, records, per_channel={0: records, 1: []})

        assert {item.channel for item in requests} == {0}

    async def test_run_screening_honours_the_pending_plan(self, topic, records):
        client = FakeClient(lambda kwargs: tool_reply(_keys_from(kwargs)))

        channels, _ = await run_screening(
            topic, records, client, per_channel={0: records[:2], 1: []}
        )

        assert len(channels[0]) == 2
        assert channels[1] == []

    async def test_the_channel_is_stamped_by_the_driver_not_the_model(self, topic, records):
        client = FakeClient(lambda kwargs: tool_reply(_keys_from(kwargs)))

        channels, _ = await run_screening(topic, records, client)

        assert all(item.channel == 0 for item in channels[0])
        assert all(item.channel == 1 for item in channels[1])


class TestUsageAndCost:
    def test_cache_hits_are_priced_two_orders_of_magnitude_lower(self):
        from litsearch import providers

        pricing = providers.BUILTIN[providers.DEFAULT_MODEL].pricing
        hit = Usage(cache_hit=1_000_000).cost(pricing)
        miss = Usage(cache_miss=1_000_000).cost(pricing)

        assert hit == pytest.approx(pricing.input_hit)
        assert miss == pytest.approx(pricing.input_miss)
        assert miss > hit * 50

    def test_unknown_pricing_yields_none_not_zero(self):
        """说 $0.00 比说"算不出来"危险得多——人是照着那个数字决定跑不跑的。"""
        assert Usage(cache_miss=1_000_000).cost(None) is None

    def test_usages_add_up(self):
        total = Usage(cache_hit=1, cache_miss=2, output=3) + Usage(
            cache_hit=10, cache_miss=20, output=30
        )

        assert (total.cache_hit, total.cache_miss, total.output) == (11, 22, 33)


class TestEstimate:
    def test_the_stable_system_prefix_is_counted_as_cached_after_the_first_call(
        self, topic, records
    ):
        """纳排标准逐字不变，是天然的缓存前缀——不把它算成缓存命中会高估成本。"""
        report = estimate(topic, records)

        assert report.requests == 6
        assert report.usage.cache_hit > 0
        assert report.usage.cache_miss > 0

    def test_每个通道的第一次请求算未命中(self, topic, records):
        report = estimate(topic, records)

        # 2 个通道各有一次冷启动
        assert report.cold_requests == 2

    def test_a_resume_estimates_only_the_pending_part(self, topic, records):
        """续跑却报全量价钱，等于让人按一个不会发生的数字做决定。"""
        full = estimate(topic, records)
        partial = estimate(topic, records, per_channel={0: records[:2], 1: []})

        assert partial.requests < full.requests
        assert partial.usage.cost_usd < full.usage.cost_usd
        assert partial.records == 2

    def test_empty_corpus_costs_nothing(self, topic):
        report = estimate(topic, [])

        assert report.requests == 0
        assert report.usage.cost_usd == 0.0

    def test_estimates_are_flagged_as_approximate(self, topic, records):
        """DeepSeek 没有 count_tokens 端点，估算永远是近似——必须如实标注。"""
        assert estimate(topic, records).precise is False


class TestRunScreening:
    async def test_collects_verdicts_per_channel(self, topic, records):
        client = FakeClient(lambda kwargs: tool_reply(_keys_from(kwargs)))

        channels, usage = await run_screening(topic, records, client)

        assert len(channels) == 2
        assert sorted(item.record_key for item in channels[0]) == sorted(
            item.key for item in records
        )
        assert usage.output > 0

    async def test_the_tool_is_forced_so_the_model_cannot_reply_in_prose(self, topic, records):
        client = FakeClient(lambda kwargs: tool_reply(_keys_from(kwargs)))

        await run_screening(topic, records, client)

        assert client.calls[0]["tool_choice"]["function"]["name"] == TOOL_NAME

    async def test_hallucinated_record_keys_are_dropped(self, topic, records):
        """编造或串批的 key 必须丢弃——判定挂到错误记录上比漏判更糟。
        丢弃后该记录会因"通道缺少判定"进人工队列，正是想要的。"""
        client = FakeClient(lambda kwargs: tool_reply(["not-in-this-batch"]))

        channels, _ = await run_screening(topic, records, client)

        assert channels[0] == [] and channels[1] == []

    async def test_a_reply_without_a_tool_call_is_recorded_as_failed(self, topic, records):
        """模型偶尔会直接说话而不调工具。静默当成"这批没有相关文献"是最坏的结果。"""
        empty = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None))],
            usage=SimpleNamespace(
                prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=1, completion_tokens=0
            ),
        )
        client = FakeClient(lambda kwargs: empty)

        channels, _ = await run_screening(topic, records, client)

        assert all(channel == [] for channel in channels)

    async def test_unparseable_arguments_do_not_abort_the_whole_run(self, topic, records):
        bad = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        tool_calls=[
                            SimpleNamespace(
                                function=SimpleNamespace(name=TOOL_NAME, arguments="{oops")
                            )
                        ]
                    )
                )
            ],
            usage=SimpleNamespace(
                prompt_cache_hit_tokens=0, prompt_cache_miss_tokens=1, completion_tokens=1
            ),
        )
        client = FakeClient(lambda kwargs: bad)
        failures: list[str] = []

        channels, _ = await run_screening(topic, records, client, on_error=failures.append)

        assert all(channel == [] for channel in channels)
        assert failures

    async def test_actual_usage_is_summed_across_requests(self, topic, records):
        client = FakeClient(lambda kwargs: tool_reply(_keys_from(kwargs)))

        _, usage = await run_screening(topic, records, client)

        assert usage.cache_hit == 100 * 6
        assert usage.cache_miss == 200 * 6
        assert usage.output == 50 * 6

    async def test_thinking_is_disabled_so_forced_tool_choice_is_accepted(self, topic, records):
        """v4 默认开思考模式，而思考模式**同时拒绝** `tool_choice="required"`
        与指定函数两种形式，返回 400。实测错误原文：
        `Thinking mode does not support this tool_choice`。
        不显式关掉，整轮筛选会一条判定都拿不到。"""
        client = FakeClient(lambda kwargs: tool_reply(_keys_from(kwargs)))

        await run_screening(topic, records, client)

        assert client.calls[0]["extra_body"]["thinking"] == {"type": "disabled"}

    async def test_thinking_can_be_turned_back_on_at_the_cost_of_forcing(self, topic, records):
        """开思考就必须放弃强制工具调用——模型可能改用散文作答，
        那一批会进人工队列。这个取舍要让调用方显式做，不能藏在默认值里。"""
        client = FakeClient(lambda kwargs: tool_reply(_keys_from(kwargs)))

        await run_screening(topic, records, client, thinking=True)

        assert client.calls[0]["extra_body"]["thinking"] == {"type": "enabled"}
        assert "tool_choice" not in client.calls[0]

    async def test_the_model_defaults_to_the_configured_one(self, topic, records):
        client = FakeClient(lambda kwargs: tool_reply(_keys_from(kwargs)))

        await run_screening(topic, records, client)

        assert client.calls[0]["model"] == DEFAULT_MODEL
