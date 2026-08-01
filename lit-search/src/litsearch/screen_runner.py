"""筛选的 DeepSeek API 驱动层。

DeepSeek 兼容 OpenAI 的接口形态，但有三处与 Anthropic 不同，且都影响架构：

**1. 结构化输出走 strict 工具调用，不走 JSON 模式。**
``response_format={"type":"json_object"}`` 只保证"是一段合法 JSON"，
不保证形状——判定少一个字段、confidence 变成字符串都不会被拦下；
官方文档还明确说这个模式"偶尔返回空内容"。而 strict 工具调用在**服务端**
按 JSON Schema 校验参数，这才是真正的结构化输出。代价是必须走 ``/beta`` 端点，
且 schema 要满足 strict 的三条硬要求：不能有 ``$ref``、每层
``additionalProperties: false``、``required`` 列全所有属性。

**2. 没有 Message Batches API**，所以没有"批处理半价"这条路，只能实时调用 + 并发。

**3. 上下文缓存是自动的**，不需要也无法声明。命中与否只能从
``usage.prompt_cache_hit_tokens`` 读回。纳排标准在整轮筛选中逐字不变，
是天然的缓存前缀——命中价 $0.003625/M 对未命中价 $0.435/M，差 120 倍，
所以把标准放 system 块、并让每个通道的批次共用同一段前缀，是成本的主要来源。

成本必须在跑之前算清楚（``estimate``），这和 ``lit plan`` 是同一个原则。
但 DeepSeek **没有 count_tokens 端点**，估算只能按字符数近似——
因此 ``precise`` 恒为 False，必须如实标注；真实用量在跑完后由 API 回报。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass

from litsearch import providers
from litsearch.dedupe import CanonicalRecord
from litsearch.protocol import Topic
from litsearch.screen import (
    MergedDecision,
    Verdict,
    build_batches,
    build_channel_prompt,
    format_records,
)

#: 兼容旧调用点。真正的默认值与端点由 litsearch.providers 解析——
#: 这一层不再知道任何厂商的名字。
DEFAULT_MODEL = providers.DEFAULT_MODEL
BASE_URL = providers.BUILTIN[providers.DEFAULT_MODEL].base_url
DEFAULT_MAX_TOKENS = 8000
TOOL_NAME = "record_verdicts"

#: DeepSeek 官方经验值：1 个英文字符约 0.3 token。这是**近似**，
#: 没有 count_tokens 端点可以校准，所以估算结果必须标注为粗估。
CHARS_PER_TOKEN = 3.3
#: 每条记录的判定输出约占多少 token
OUTPUT_TOKENS_PER_RECORD = 70


def build_tool() -> dict:
    """判定的 JSON Schema，手写而非从 pydantic 导出。

    ``model_json_schema()`` 会产生 ``$defs``/``$ref``，而 strict 模式不接受引用；
    手写还能保证每层都带 ``additionalProperties: false``、``required`` 列全属性——
    少一条服务端就会直接拒绝请求。
    """
    verdict = {
        "type": "object",
        "properties": {
            "record_key": {"type": "string", "description": "记录的 key，原样照抄"},
            "decision": {
                "type": "string",
                "enum": ["include", "exclude", "unclear"],
                "description": "信息不足以判定时必须选 unclear，不要猜",
            },
            "matched_criteria": {
                "type": "array",
                "items": {"type": "string"},
                "description": '命中的标准编号，如 ["I1","I2"] 或 ["X2"]',
            },
            "reason": {"type": "string", "description": "一句话依据，引用记录中的具体内容"},
            "confidence": {"type": "number", "description": "0 到 1 的置信度"},
        },
        "required": ["record_key", "decision", "matched_criteria", "reason", "confidence"],
        "additionalProperties": False,
    }
    return {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": "为本批**每一条**记录记录一个判定，不得遗漏、不得增补。",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"verdicts": {"type": "array", "items": verdict}},
                "required": ["verdicts"],
                "additionalProperties": False,
            },
        },
    }


@dataclass(frozen=True)
class ScreeningRequest:
    """一次待发送的筛选请求。"""

    custom_id: str
    channel: int
    batch_index: int
    system: str
    user_content: str
    record_keys: tuple[str, ...]


def build_requests(
    topic: Topic,
    records: list[CanonicalRecord],
    *,
    per_channel: dict[int, list[CanonicalRecord]] | None = None,
    batch_size: int | None = None,
) -> list[ScreeningRequest]:
    """把记录切批、交叉通道，展开成全部待发请求。

    ``per_channel`` 用于续跑：只为**各通道各自缺判定**的记录建请求。
    通道 0 整批连接失败、通道 1 正常，是实测中真实发生过的情形
    （1,234 个请求里 359 个 APIConnectionError），此时重跑全部等于白烧一遍钱。
    """
    plan = per_channel or {channel: records for channel in range(topic.screening.channels)}
    requests: list[ScreeningRequest] = []
    for channel, subset in sorted(plan.items()):
        if not subset:
            continue
        system = build_channel_prompt(topic.criteria, channel)
        size = batch_size or topic.screening.batch_size
        for index, batch in enumerate(build_batches(subset, size)):
            requests.append(
                ScreeningRequest(
                    custom_id=f"c{channel}-b{index:05d}",
                    channel=channel,
                    batch_index=index,
                    system=system,
                    user_content=format_records(batch),
                    record_keys=tuple(item.key for item in batch),
                )
            )
    return requests


def regroup_by_channel(decisions: dict[str, MergedDecision], channels: int) -> list[list[Verdict]]:
    """把已有判定按通道拆回去，供续跑时与新判定合并。

    早于 ``channel`` 字段的判定按**位置**归位：``merge_verdicts`` 是按通道顺序
    追加的，所以数量齐了时第 i 个就是通道 i。数量不齐时无从判断，整条丢弃——
    这些记录本来就会被 ``pending_by_channel`` 判为全通道待补。
    """
    grouped: list[list[Verdict]] = [[] for _ in range(channels)]
    for merged in decisions.values():
        stamped = [item for item in merged.channel_verdicts if item.channel is not None]
        if stamped:
            for verdict in stamped:
                if 0 <= verdict.channel < channels:
                    grouped[verdict.channel].append(verdict)
        elif len(merged.channel_verdicts) >= channels:
            for index in range(channels):
                grouped[index].append(
                    merged.channel_verdicts[index].model_copy(update={"channel": index})
                )
    return grouped


def pending_by_channel(
    topic: Topic,
    records: list[CanonicalRecord],
    decisions: dict[str, MergedDecision] | None,
) -> dict[int, list[CanonicalRecord]]:
    """每个通道还缺哪些记录的判定。

    判据是"这条记录在这个通道有没有判定"，而不是"这条记录进没进人工队列"——
    通道分歧和低置信度是**已经判过**的结论，重跑它们既浪费钱，
    也会把一个本该由人裁定的分歧变成掷第二次骰子。
    """
    if not decisions:
        return {channel: list(records) for channel in range(topic.screening.channels)}

    total = topic.screening.channels
    judged: dict[int, set[str]] = {channel: set() for channel in range(total)}
    for key, merged in decisions.items():
        stamped = [item for item in merged.channel_verdicts if item.channel is not None]
        if stamped:
            for verdict in stamped:
                if verdict.channel in judged:
                    judged[verdict.channel].add(key)
        elif len(merged.channel_verdicts) >= total:
            # 早于 channel 字段的旧判定：数量齐了就说明每个通道都判过。
            # 不齐则分不清缺的是哪个通道，只能整条重判——宁可多花钱，
            # 也不能把"通道 1 判过"错记成"通道 0 判过"，那会让一条记录
            # 拿着两份来自同一视角的判定，双通道就名存实亡了。
            for channel in judged:
                judged[channel].add(key)

    return {
        channel: [item for item in records if item.key not in done]
        for channel, done in judged.items()
    }


@dataclass
class Usage:
    """token 用量。缓存命中与未命中必须分开——两者差 120 倍。"""

    cache_hit: int = 0
    cache_miss: int = 0
    output: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            cache_hit=self.cache_hit + other.cache_hit,
            cache_miss=self.cache_miss + other.cache_miss,
            output=self.output + other.output,
        )

    def cost(self, pricing: providers.Pricing | None) -> float | None:
        """按给定价目算钱。**价目未知时返回 None，不返回 0。**

        一个说 $0.00 的 dry-run 比一个说"算不出来"的危险得多——
        人是照着那个数字决定跑不跑的。
        """
        if pricing is None:
            return None
        return (
            self.cache_hit / 1_000_000 * pricing.input_hit
            + self.cache_miss / 1_000_000 * pricing.input_miss
            + self.output / 1_000_000 * pricing.output
        )

    @property
    def cost_usd(self) -> float:
        """按内置默认价目估算，供旧调用点使用。"""
        return self.cost(providers.BUILTIN[providers.DEFAULT_MODEL].pricing) or 0.0


@dataclass
class CostEstimate:
    requests: int
    records: int
    usage: Usage
    #: 冷启动请求数（system 前缀尚未进缓存）
    cold_requests: int = 0
    #: DeepSeek 没有 count_tokens 端点，估算恒为近似
    precise: bool = False


def _tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN)


def estimate(
    topic: Topic,
    records: list[CanonicalRecord],
    *,
    per_channel: dict[int, list[CanonicalRecord]] | None = None,
    batch_size: int | None = None,
) -> CostEstimate:
    """按字符数近似估算成本，并把**自动缓存**建模进去。

    每个通道的 system 前缀完全相同，因此只有该通道的第一次请求算未命中，
    其余都算命中。不建模这一点会把成本高估一个数量级——而高估会让人
    误以为跑不起，和低估同样有害。

    ``per_channel`` 让续跑时估的是**待补部分**。续跑却报全量价钱，
    等于让人按一个不会发生的数字做决定。
    """
    requests = build_requests(topic, records, per_channel=per_channel, batch_size=batch_size)
    if not requests:
        return CostEstimate(0, 0, Usage())

    channels = {item.channel for item in requests}
    system_tokens = _tokens(requests[0].system)
    user_tokens = sum(_tokens(item.user_content) for item in requests)
    judged = (
        sum(len(item) for item in per_channel.values())
        if per_channel
        else len(records) * len(channels)
    )

    cold = len(channels)
    return CostEstimate(
        requests=len(requests),
        records=judged,
        cold_requests=cold,
        usage=Usage(
            cache_hit=system_tokens * (len(requests) - cold),
            cache_miss=system_tokens * cold + user_tokens,
            output=OUTPUT_TOKENS_PER_RECORD * judged,
        ),
    )


def _params(request: ScreeningRequest, model: str, *, thinking: bool = False) -> dict:
    """构造一次请求。

    **思考模式与强制工具调用互斥。** v4 默认开思考，而思考模式同时拒绝
    ``tool_choice="required"`` 与指定函数两种形式，返回
    ``400 Thinking mode does not support this tool_choice``。

    默认关思考、强制工具调用：标题摘要初筛是照着 8 条明确标准做的分类，
    思考带来的判断力提升有限，而**每一批都能拿到可解析的结构化判定**是刚需——
    拿不到就得进人工队列，等于让人去看模型本来判得了的记录。
    开思考时必须放弃强制，那个取舍留给调用方显式做。
    """
    params: dict = {
        "model": model,
        "max_tokens": DEFAULT_MAX_TOKENS,
        "messages": [
            # system 块在整轮筛选中逐字不变，是自动缓存的前缀
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.user_content},
        ],
        "tools": [build_tool()],
        "extra_body": {"thinking": {"type": "enabled" if thinking else "disabled"}},
    }
    if not thinking:
        # 不强制的话，模型可以直接用散文作答，判定就无法解析
        params["tool_choice"] = {"type": "function", "function": {"name": TOOL_NAME}}
    return params


def _usage_of(response) -> Usage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return Usage()
    return Usage(
        cache_hit=getattr(usage, "prompt_cache_hit_tokens", 0) or 0,
        cache_miss=getattr(usage, "prompt_cache_miss_tokens", 0) or 0,
        output=getattr(usage, "completion_tokens", 0) or 0,
    )


def _parse(response, request: ScreeningRequest) -> list[Verdict]:
    """从工具调用里取出判定，并丢弃不属于本批次的 record_key。

    模型偶尔会编造或串批 key；静默接受会让判定挂到错误的记录上。
    丢弃后该记录在合并阶段会因"通道缺少判定"进人工队列——这正是我们要的。
    """
    calls = getattr(response.choices[0].message, "tool_calls", None)
    if not calls:
        raise ValueError("回复里没有工具调用（模型直接用散文作答）")

    payload = json.loads(calls[0].function.arguments)
    allowed = set(request.record_keys)
    return [
        # 通道号由请求决定，在这里盖上——模型不该也不需要知道它
        Verdict.model_validate({**item, "channel": request.channel})
        for item in payload.get("verdicts", [])
        if item.get("record_key") in allowed
    ]


async def run_screening(
    topic: Topic,
    records: list[CanonicalRecord],
    client,
    *,
    model: str = DEFAULT_MODEL,
    concurrency: int = 8,
    thinking: bool = False,
    per_channel: dict[int, list[CanonicalRecord]] | None = None,
    batch_size: int | None = None,
    progress: Callable[[str], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> tuple[list[list[Verdict]], Usage]:
    """逐批实时调用，返回（按通道分组的判定, 实际用量）。

    单个批次失败**不中止整轮**，但一定会被记录：那一批的记录会因
    "通道缺少判定"进人工队列，绝不会被静默当作"这批没有相关文献"。
    """
    requests = build_requests(topic, records, per_channel=per_channel, batch_size=batch_size)
    channels: list[list[Verdict]] = [[] for _ in range(topic.screening.channels)]
    semaphore = asyncio.Semaphore(concurrency)
    totals: list[Usage] = []
    done = 0

    async def one(request: ScreeningRequest) -> None:
        nonlocal done
        async with semaphore:
            try:
                response = await client.chat.completions.create(
                    **_params(request, model, thinking=thinking)
                )
            except Exception as error:  # 网络/限流/服务端错误都不该中止整轮
                if on_error:
                    on_error(f"{request.custom_id}: 请求失败 {error!r}")
                return
            totals.append(_usage_of(response))
            try:
                channels[request.channel].extend(_parse(response, request))
            except (ValueError, json.JSONDecodeError) as error:
                if on_error:
                    on_error(f"{request.custom_id}: 解析失败 {error}")
            finally:
                done += 1
                if progress and done % 20 == 0:
                    progress(f"  已完成 {done}/{len(requests)} 批")

    await asyncio.gather(*(one(request) for request in requests))
    return channels, sum(totals, Usage())


def build_client(api_key: str, *, base_url: str = BASE_URL):
    """构造 OpenAI 兼容的异步客户端。密钥只从调用方传入，绝不在此读环境。"""
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=180.0, max_retries=3)
