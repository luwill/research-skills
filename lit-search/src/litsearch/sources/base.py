"""源采集的公共设施：限速、重试、体积上限、原始响应落盘。

设计要点：
- **每一页原始响应都落盘**（`raw/<source>/<query_hash>/page_NNNN.<ext>.gz`），永不覆盖。
  这是"检索可审计"的物理基础——任何一条最终纳入的文献都能回溯到它来自哪一页原始响应。
- **失败必须显形**。一个源翻页中途失败会标记为 partial 并记录已抓页数，
  绝不静默当作"这个源就这么多"。
"""

from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import os
import tempfile
import time
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx

from litsearch.normalize import Record
from litsearch.protocol import Topic, Window
from litsearch.query import SourceQuery

DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_MAX_BYTES = 32 * 1024 * 1024
DEFAULT_MAX_ATTEMPTS = 4
RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
#: Retry-After 超过这个值就不再等待，直接判定为配额耗尽
MAX_RETRY_AFTER_SECONDS = 120.0


async def _sleep(seconds: float) -> None:
    """Injection seam: production really waits; recorded-response tests replace this."""
    await asyncio.sleep(seconds)


def _retry_after_seconds(response: httpx.Response) -> float | None:
    raw = response.headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


class SourceError(RuntimeError):
    """某个源的采集失败。调用方必须把它记为 partial/failed，不能吞掉。

    ``status`` 保留 HTTP 状态码，让源能区分"这个资源本来就不存在"（如 CVF 的
    ICCV2024——ICCV 只在奇数年办）与"采集失败"。靠匹配错误消息里的字符串来做
    这个区分迟早会错。
    """

    def __init__(
        self, source: str, message: str, *, pages_fetched: int = 0, status: int | None = None
    ) -> None:
        super().__init__(f"[{source}] {message}")
        self.source = source
        self.pages_fetched = pages_fetched
        self.status = status


class QuotaExhausted(SourceError):
    """配额耗尽（不是瞬时限流）。等待毫无意义，必须立刻失败并告诉用户何时恢复。"""

    def __init__(
        self, source: str, retry_after: float, *, pages_fetched: int = 0, detail: str = ""
    ) -> None:
        hours = retry_after / 3600
        super().__init__(
            source,
            f"配额已耗尽，服务端要求等待 {retry_after:,.0f} 秒（约 {hours:.1f} 小时）"
            f"{'；' + detail if detail else ''}。这是配额而非速率问题，降速无效——"
            f"请配置 API key、减少检索式数量，或等待配额重置。",
            pages_fetched=pages_fetched,
        )
        self.retry_after = retry_after


def _quota_detail(response: httpx.Response) -> str:
    fields = [
        (key, value)
        for key, value in response.headers.items()
        if key.lower().startswith("x-ratelimit")
    ]
    return " ".join(f"{key}={value}" for key, value in sorted(fields))


@dataclass
class RateLimiter:
    """最简单的间隔限速器。各源按其官方指引配置。"""

    min_interval: float
    _last: float = field(default=0.0, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    async def wait(self) -> None:
        async with self._lock:
            elapsed = time.monotonic() - self._last
            if (remaining := self.min_interval - elapsed) > 0:
                await _sleep(remaining)
            self._last = time.monotonic()


class PageStore:
    """把每一页原始响应写到磁盘。已存在的页不覆盖，使重跑幂等。"""

    def __init__(self, root: Path | None) -> None:
        self.root = root

    def write(self, source: str, query_hash: str, page: int, body: str, suffix: str) -> Path | None:
        if self.root is None:
            return None
        directory = self.root / source / query_hash
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"page_{page:04d}.{suffix}.gz"
        if not path.exists():
            descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=directory)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    # mtime=0 让同一响应产生确定性字节，便于哈希与跨 run 对比。
                    handle.write(gzip.compress(body.encode("utf-8"), mtime=0))
                    handle.flush()
                    os.fsync(handle.fileno())
                # 每次采集 attempt 使用独立目录；replace 只用于恢复同一 attempt
                # 的半写临时页，不会覆盖历史 attempt。
                os.replace(temporary, path)
            except BaseException:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise
        return path


class HttpClient:
    """带限速、指数退避与响应体积上限的 GET 客户端。"""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        rate_limiter: RateLimiter,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        backoff_base: float = 2.0,
    ) -> None:
        self._client = client
        self._rate_limiter = rate_limiter
        self._max_attempts = max_attempts
        self._max_bytes = max_bytes
        self._backoff_base = backoff_base

    async def get_text(
        self,
        url: str,
        params: Mapping[str, Any],
        *,
        source: str,
        pages_fetched: int = 0,
        headers: Mapping[str, str] | None = None,
    ) -> str:
        if not url.startswith("https://"):
            raise SourceError(source, f"仅允许 HTTPS 端点：{url}")

        cleaned = {key: value for key, value in params.items() if value is not None}
        last_error: str = "未知错误"

        for attempt in range(1, self._max_attempts + 1):
            await self._rate_limiter.wait()
            try:
                response = await self._client.get(url, params=cleaned, headers=headers)
            except httpx.HTTPError as error:
                last_error = f"请求失败：{error!r}"
            else:
                if response.status_code in RETRY_STATUS:
                    last_error = f"HTTP {response.status_code}"
                    retry_after = _retry_after_seconds(response)
                    # Retry-After 超过上限说明这是配额耗尽而非瞬时限流。
                    # 实测 OpenAlex 匿名配额用尽会返回 retry-after: 53780（约 15 小时），
                    # 老实照睡会让整条流水线静默挂死。
                    if retry_after is not None and retry_after > MAX_RETRY_AFTER_SECONDS:
                        raise QuotaExhausted(
                            source,
                            retry_after,
                            pages_fetched=pages_fetched,
                            detail=_quota_detail(response),
                        )
                    if retry_after is not None and attempt < self._max_attempts:
                        # 瞬时限流时优先听服务端的，而不是我们自己的退避曲线
                        await _sleep(retry_after)
                        continue
                elif response.status_code >= 400:
                    raise SourceError(
                        source,
                        f"HTTP {response.status_code}: {response.text[:200]}",
                        pages_fetched=pages_fetched,
                        status=response.status_code,
                    )
                else:
                    body = response.text
                    if len(body.encode()) > self._max_bytes:
                        raise SourceError(source, "响应体积超过上限", pages_fetched=pages_fetched)
                    return body

            if attempt < self._max_attempts:
                await _sleep(min(self._backoff_base**attempt, 30.0))

        raise SourceError(
            source,
            f"重试 {self._max_attempts} 次后仍失败：{last_error}",
            pages_fetched=pages_fetched,
        )

    async def get_json(
        self, url: str, params: Mapping[str, Any], *, source: str, pages_fetched: int = 0
    ) -> Any:
        body = await self.get_text(url, params, source=source, pages_fetched=pages_fetched)
        try:
            return json.loads(body)
        except json.JSONDecodeError as error:
            raise SourceError(
                source, f"响应不是合法 JSON：{error}", pages_fetched=pages_fetched
            ) from error


@dataclass
class SourceContext:
    """一次采集运行中所有源共享的上下文。"""

    client: HttpClient
    store: PageStore
    topic: Topic
    contact_email: str | None = None
    api_keys: dict[str, str] = field(default_factory=dict)
    #: 单个检索式最多抓取的记录数；None 表示翻到底
    max_records_per_query: int | None = None

    @property
    def window(self) -> Window:
        return self.topic.window


@dataclass
class HarvestResult:
    """一个检索式在一个源上的采集结果。"""

    source: str
    query_hash: str
    reported_total: int | None
    records: list[Record]
    pages_fetched: int
    status: str  # "complete" | "partial" | "failed"
    error: str | None = None
    truncated: bool = False


class Source(Protocol):
    """所有源的统一接口。

    注意：``last_total`` 由 ``fetch`` 在翻第一页时写入，因此同一个源实例的多条检索式
    必须**串行**执行（编排层正是这样做的，每个源一个实例、一个限速器）。
    """

    name: str
    #: fetch 期间服务端报告的命中总数，省去一次单独的 estimate 请求
    last_total: int | None

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        """干跑：返回该检索式的预计命中数，用于 `lit plan` 提前暴露筛选成本。"""
        ...

    def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        """翻页到底，逐条产出规范化记录。"""
        ...


async def collect(
    source: Source,
    query: SourceQuery,
    context: SourceContext,
    *,
    with_estimate: bool = False,
) -> HarvestResult:
    """驱动一个源跑完一个检索式，把失败显式转成 partial/failed 而不是空结果。

    默认**不**单独调用 estimate：各源翻第一页时本来就能拿到总数，
    多打一次请求纯属浪费配额（OpenAlex 匿名每天仅约 100 次请求）。
    """
    records: list[Record] = []
    reported: int | None = None
    if with_estimate:
        try:
            reported = await source.estimate(query, context)
        except SourceError:
            reported = None

    truncated = False
    try:
        async for record in source.fetch(query, context):
            record.found_by = [query.query_hash]
            records.append(record)
            limit = context.max_records_per_query
            if limit is not None and len(records) >= limit:
                truncated = True
                break
    except SourceError as error:
        return HarvestResult(
            source=source.name,
            query_hash=query.query_hash,
            reported_total=(
                reported if reported is not None else getattr(source, "last_total", None)
            ),
            records=records,
            pages_fetched=error.pages_fetched,
            status="partial" if records else "failed",
            error=str(error),
        )

    return HarvestResult(
        source=source.name,
        query_hash=query.query_hash,
        reported_total=(reported if reported is not None else getattr(source, "last_total", None)),
        records=records,
        pages_fetched=0,
        status="complete",
        truncated=truncated,
    )


def record_hash(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode()
    ).hexdigest()
