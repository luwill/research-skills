"""TypeSafe Jev（System One）判定 API 客户端。

Jev 不生成文本：给它一个 ``state`` 和一组 typed question，它按并行、互相隔离的方式
逐条作答，返回校准过的概率。这里只做三件事——鉴权、组请求体、校验应答——
重试、限速、配额、体积上限全部复用 ``HttpClient``，因为那些规则是被实测逼出来的，
再写一份就会漏。

不引 ``typesafe-sdk``：它会同时改动根仓库与 skill 副本两份 lockfile，且它自带的
重试策略绕开 ``sources.base._sleep`` 这个测试注入缝，会让测试真的睡。API 只有一个
端点，httpx 足够。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from litsearch.sources.base import (
    HttpClient,
    QuotaExhausted,
    RateLimiter,
    SourceError,
)

JEV_URL = "https://api.typesafe.ai/v1/systemone"

#: 钉住带版本的模型 id。``jev-latest`` 会随新版漂移，而阈值是在某个具体版本上
#: 调出来的——别名一动，同一套阈值就悄悄换了含义。
JEV_PINNED = "jev-1.13.0"

#: 这些状态码说明请求本身有问题（key 错、模型名错、请求体不合法）。
#: 它们对每一条记录都会一样地错，所以必须整轮中止；逐条标失败只会产出
#: 一份"全部待人工"的假结果，看起来像跑完了。
FATAL_STATUS = frozenset({400, 401, 403, 404, 422})

#: 判定调用实测 p50 约 0.25 s。给足余量，但不像采集那样需要长超时。
JEV_TIMEOUT_SECONDS = 60.0

#: 文档给的上限是 1200 req/min（20 req/s）。实测 6 并发裸跑约 23 req/s 已经超了，
#: 所以卡在 16 req/s——宁可慢一点，也不要在跑到一半时撞 429 雪崩。
DEFAULT_RATE_PER_SECOND = 16.0

_SOURCE = "jev"


class JevError(RuntimeError):
    """一次判定调用失败。调用方应把受影响的记录记为失败，让它们进人工队列。"""


class JevFatalError(JevError):
    """请求本身就不合法，重试和换记录都没用。整轮中止。"""


@dataclass(frozen=True, slots=True)
class JevResponse:
    """一次判定的应答。

    ``model`` 是服务端回报的**带版本** id，不是我们请求时写的那个别名——
    轮次要记录到底是哪个版本判的，否则审计链在模型升级那天就断了。
    """

    model: str
    answers: Mapping[str, Mapping[str, Any]]
    input_tokens: int
    output_tokens: int

    def noul(self, question_id: str) -> float:
        answer = self.answers[question_id]
        if answer.get("type") != "noul" or "noul" not in answer:
            raise JevError(f"问题 {question_id} 的答案不是 noul：{answer.get('type')!r}")
        return float(answer["noul"])

    def nouls(self) -> dict[str, float]:
        return {
            key: float(value["noul"])
            for key, value in self.answers.items()
            if value.get("type") == "noul" and "noul" in value
        }


def _validate(payload: Any, questions: Mapping[str, Any]) -> JevResponse:
    if not isinstance(payload, dict):
        raise JevError(f"应答不是 JSON 对象：{type(payload).__name__}")
    model = payload.get("model")
    if not model:
        raise JevError("应答缺少 model 字段——记不下是哪个版本判的，审计链会断")

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise JevError("应答缺少 answers 字典")
    missing = [key for key in questions if key not in answers]
    if missing:
        # 漏答当成 0 会把该纳入的论文静默排掉，而排除是不可逆的。
        raise JevError(f"以下问题未作答：{sorted(missing)}")

    for key, answer in answers.items():
        if not isinstance(answer, dict):
            raise JevError(f"问题 {key} 的答案不是对象：{answer!r}")
        if answer.get("type") == "noul":
            value = answer.get("noul")
            if not isinstance(value, int | float) or not 0.0 <= float(value) <= 1.0:
                raise JevError(f"问题 {key} 的 noul 超出 [0,1]：{value!r}")

    usage = payload.get("usage") or {}
    return JevResponse(
        model=str(model),
        answers=answers,
        input_tokens=int(usage.get("input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
    )


class JevClient:
    """判定 API 的薄封装。密钥只由调用方传入，这里从不读环境变量。"""

    def __init__(self, http: HttpClient, api_key: str, *, model: str = JEV_PINNED) -> None:
        self._http = http
        self._api_key = api_key
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def ask(
        self, state: Any, questions: Mapping[str, Mapping[str, Any]]
    ) -> JevResponse:
        if not questions:
            raise ValueError("至少要问一个问题")
        body = {"state": state, "model": self._model, "questions": dict(questions)}
        try:
            payload = await self._http.post_json(
                JEV_URL,
                body,
                source=_SOURCE,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
        except QuotaExhausted:
            # 配额耗尽是独立信号：降速无用，必须原样上抛让调用方停下来。
            raise
        except SourceError as error:
            if error.status in FATAL_STATUS:
                raise JevFatalError(str(error)) from error
            raise JevError(str(error)) from error
        return _validate(payload, questions)


def build_jev_client(
    api_key: str,
    *,
    model: str = JEV_PINNED,
    rate_per_second: float = DEFAULT_RATE_PER_SECOND,
    max_attempts: int = 4,
) -> tuple[JevClient, httpx.AsyncClient]:
    """建一个限速的判定客户端。调用方负责关闭返回的 ``httpx.AsyncClient``。

    与 ``sources.registry.build_client`` 同样的约定：谁建谁关。
    """
    if not api_key:
        raise ValueError(
            "缺少 Jev API key。设 TYPESAFE_API_KEY（或 LITSEARCH_TYPESAFE_API_KEY）后重试。"
        )
    if rate_per_second <= 0:
        raise ValueError(f"限速必须为正，收到 {rate_per_second}")
    raw = httpx.AsyncClient(timeout=JEV_TIMEOUT_SECONDS)
    http = HttpClient(
        raw,
        rate_limiter=RateLimiter(min_interval=1.0 / rate_per_second),
        max_attempts=max_attempts,
    )
    return JevClient(http, api_key, model=model), raw


@dataclass(frozen=True, slots=True)
class Judged:
    """一条记录的判定结果。``state`` 留着以便调用方算 state 哈希。"""

    key: str
    state: Any
    reply: JevResponse


async def ask_each(
    client: JevClient,
    items: Sequence[tuple[str, Any]],
    questions: Mapping[str, Mapping[str, Any]],
    *,
    concurrency: int = 16,
    on_error: Callable[[str, Exception], None] | None = None,
    checkpoint: Callable[[Judged], None] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[list[Judged], int]:
    """对一批 ``(key, state)`` 各问一次，返回成功的结果与输入 token 总数。

    失败策略是这里唯一值得共用的东西，也是最容易在第二份实现里写漏的：
    ``JevFatalError`` 与配额耗尽**原样上抛**（那类错误对每条记录都会一样地错，
    逐条记失败只会产出一份"全部失败"的假结果），其余按条记下并继续。
    失败的记录**不产出结果**——绝不用占位值冒充判过。
    """
    semaphore = asyncio.Semaphore(concurrency)
    done = 0

    async def one(key: str, state: Any) -> Judged | None:
        nonlocal done
        async with semaphore:
            try:
                reply = await client.ask(state, questions)
            except JevFatalError:
                raise
            except JevError as error:
                if on_error:
                    on_error(key, error)
                return None
        judged = Judged(key=key, state=state, reply=reply)
        if checkpoint:
            checkpoint(judged)
        done += 1
        if progress:
            progress(done, len(items))
        return judged

    results = await asyncio.gather(*(one(key, state) for key, state in items))
    kept = [item for item in results if item is not None]
    return kept, sum(item.reply.input_tokens for item in kept)
