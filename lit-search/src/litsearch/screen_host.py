"""宿主模型筛选后端：不用任何 API key，由 Claude Code 本身判定。

调 ``claude -p`` 子进程。这条路的价值是**零配置**——clone 完就能跑，
不用注册、不用充值；订阅用户走的是自己的额度，不额外计费。

代价必须讲清楚：**每次调用有约 20,000 token 的框架开销**
（system prompt + 工具定义，实测禁用全部工具后仍有 9,410 创建 + 10,589 读取，
单次约 $0.02 的 API 等价成本）。所以这里的批次比 API 后端大得多——
开销是**按次**算的，批次翻倍开销就减半。

批次大到什么程度是有上限的：批越大，模型漏写记录的概率越高。
漏写不会静默——续跑判据是"这条记录在这个通道有没有判定"，漏的会被重判。
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from litsearch.screen import Verdict
from litsearch.screen_runner import ScreeningRequest

#: 宿主后端的批大小。远大于 API 后端的 25——框架开销按次计，批大就摊薄。
#: 60 是权衡：再大漏写风险明显上升，而摊薄收益已经不明显。
HOST_BATCH_SIZE = 60

#: 实测的每次调用框架开销（禁用全部工具后）。用于估算，不是精确值。
OVERHEAD_TOKENS_PER_CALL = 20_000

CLAUDE_BIN = "claude"
#: 宿主后端的默认模型。标题摘要初筛是照着明确标准做的分类任务，
#: 不需要最强的模型；而 claude -p 不指定时会用会话默认（通常是 Opus），
#: 实测 60 条记录两次调用就要 $1.44 的 API 等价成本。
HOST_DEFAULT_MODEL = "haiku"
#: 判定不需要任何工具。禁掉能把 system prompt 压掉约三分之一。
_DISALLOWED = (
    "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Task,TodoWrite,"
    "NotebookEdit,BashOutput,KillShell,SlashCommand,Skill"
)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class HostBackendError(RuntimeError):
    """宿主后端不可用。"""


def ensure_available() -> None:
    """确认 claude CLI 在 PATH 上。缺了要立刻说清楚，不要跑到一半才炸。"""
    if shutil.which(CLAUDE_BIN) is None:
        raise HostBackendError(
            "找不到 claude 命令。宿主模型后端需要已安装的 Claude Code CLI；"
            "或改用 API 后端（设 LITSEARCH_LLM_API_KEY）。"
        )


def build_prompt(request: ScreeningRequest) -> str:
    """把一次筛选请求拼成给 ``claude -p`` 的提示词。

    没有工具调用可用，所以把 schema 直接写进提示词，并**要求只输出 JSON**。
    """
    return (
        f"{request.system}\n\n"
        "---\n\n"
        f"{request.user_content}\n\n"
        "---\n\n"
        "只输出一个 JSON 对象，不要任何解释、前言或 markdown 代码块。格式：\n"
        '{"verdicts": [{"record_key": "<记录的 key，原样照抄>", '
        '"decision": "include|exclude|unclear", '
        '"matched_criteria": ["I1", "X2"], '
        '"reason": "<一句话依据，引用记录中的具体内容>", '
        '"confidence": 0.0-1.0}]}\n\n'
        "信息不足以判定时必须选 unclear，不要猜。"
        "**每条记录都要有一条判定，一条都不能少。**"
    )


def parse_output(text: str, request: ScreeningRequest) -> list[Verdict]:
    """解析模型输出。

    字段名与 API 后端的工具 schema 保持一致（``record_key``），
    两条路必须产出**结构相同**的判定——否则同一个 run 里会出现两种格式的判定文件。

    只保留 ``record_keys`` 里真实存在的 key——模型偶尔会改写或臆造 key，
    而一条挂在不存在 key 上的判定会**永远匹配不上任何记录**，
    表现为"筛完了但计数对不上"，比直接漏判更难查。
    """
    payload = _extract_json(text)
    allowed = set(request.record_keys)
    verdicts: list[Verdict] = []
    seen: set[str] = set()
    for row in payload.get("verdicts") or []:
        key = str(row.get("record_key") or row.get("key") or "").strip()
        if key not in allowed or key in seen:
            continue
        seen.add(key)
        verdicts.append(
            Verdict(
                record_key=key,
                decision=row.get("decision", "unclear"),
                matched_criteria=[str(item) for item in (row.get("matched_criteria") or [])],
                reason=str(row.get("reason", ""))[:500],
                confidence=_confidence(row.get("confidence")),
                channel=request.channel,
            )
        )
    return verdicts


def _confidence(value) -> float:
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        # 读不出置信度时给 0，让它落进人工队列——
        # 给 1.0 会让一条来路不明的判定绕过所有安全网。
        return 0.0


def _extract_json(text: str) -> dict:
    stripped = _FENCE_RE.sub("", (text or "").strip()).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    # 模型偶尔会在 JSON 前后加话；退而求其次，取最外层的一对花括号
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        raise HostBackendError(f"输出不是 JSON：{stripped[:160]}")
    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError as error:
        raise HostBackendError(f"输出不是合法 JSON：{error}") from error


@dataclass
class HostUsage:
    """宿主后端的用量。``cost_usd`` 是 **API 等价成本**——
    订阅用户实际走的是自己的额度，不会被这样计费。"""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_creation: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: HostUsage) -> HostUsage:
        return HostUsage(
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read=self.cache_read + other.cache_read,
            cache_creation=self.cache_creation + other.cache_creation,
            cost_usd=self.cost_usd + other.cost_usd,
        )


def _usage_of(payload: dict) -> HostUsage:
    usage = payload.get("usage") or {}
    return HostUsage(
        calls=1,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cache_read=usage.get("cache_read_input_tokens", 0),
        cache_creation=usage.get("cache_creation_input_tokens", 0),
        cost_usd=payload.get("total_cost_usd", 0.0) or 0.0,
    )


async def _one(request: ScreeningRequest, *, model: str | None) -> tuple[list[Verdict], HostUsage]:
    argv = [
        CLAUDE_BIN,
        "-p",
        build_prompt(request),
        "--output-format",
        "json",
        "--disallowed-tools",
        _DISALLOWED,
    ]
    if model:
        argv += ["--model", model]

    process = await asyncio.create_subprocess_exec(
        *argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise HostBackendError(
            f"claude 退出码 {process.returncode}：{stderr.decode(errors='replace')[:200]}"
        )
    try:
        payload = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError as error:
        raise HostBackendError(f"claude 输出不是 JSON：{error}") from error
    if payload.get("is_error"):
        raise HostBackendError(f"claude 报错：{str(payload.get('result'))[:200]}")
    return parse_output(payload.get("result") or "", request), _usage_of(payload)


async def run_host_screening(
    requests: Sequence[ScreeningRequest],
    *,
    model: str | None = None,
    concurrency: int = 3,
    progress: Callable[[int, int], None] | None = None,
    on_error: Callable[[ScreeningRequest, Exception], None] | None = None,
) -> tuple[list[list[Verdict]], HostUsage]:
    """跑完全部请求，返回按通道分组的判定与总用量。

    并发默认 3：每个 ``claude -p`` 都是一个完整会话，开高了既压不出吞吐，
    也更容易撞到额度限制。单批失败不中断整体——漏掉的记录会进人工队列，
    或在下一次 ``--resume`` 时被补判。
    """
    ensure_available()
    semaphore = asyncio.Semaphore(concurrency)
    channels = max((item.channel for item in requests), default=-1) + 1
    grouped: list[list[Verdict]] = [[] for _ in range(channels)]
    total = HostUsage()
    done = 0

    async def worker(request: ScreeningRequest) -> None:
        nonlocal done, total
        async with semaphore:
            try:
                verdicts, usage = await _one(request, model=model)
                grouped[request.channel].extend(verdicts)
                total = total + usage
            except Exception as error:  # noqa: BLE001 - 单批失败降级，不中断整体
                if on_error:
                    on_error(request, error)
            done += 1
            if progress:
                progress(done, len(requests))

    await asyncio.gather(*(worker(item) for item in requests))
    return grouped, total


def estimate_calls(records: int, channels: int, *, batch_size: int = HOST_BATCH_SIZE) -> int:
    """本档要发多少次 ``claude -p``。开销按次算，所以这个数就是主要成本。"""
    per_channel = -(-records // batch_size)  # 向上取整
    return per_channel * channels
