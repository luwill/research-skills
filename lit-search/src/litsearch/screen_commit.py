"""筛选轮次的提交尾段：三个后端共用。

判定**怎么来的**各后端不同（OpenAI 兼容的强制工具调用、宿主的自由文本解析、
判定 API 的概率打分），但判定**怎么落盘**必须完全一样：同样的审计字段、同样的
退步守卫、同样的产物集合。否则三种后端产出的轮次在审计上就不是同一种东西，
``lit verify`` 和 PRISMA 也就没法一视同仁地检查它们。

这段逻辑原本长在 ``cli.py`` 的 screen 命令尾部，没有任何测试覆盖。
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from litsearch.dedupe import CanonicalRecord
from litsearch.protocol import Topic, freeze_topic, protocol_fingerprint
from litsearch.run import Run
from litsearch.screen import MergedDecision, ScreeningRound, render_human_queue

TRIAL_ROUND = "screening_trial.json"
TRIAL_QUEUE = "human_queue_trial.csv"
QUEUE = "human_queue.csv"
INCLUDED = "included.jsonl"


@dataclass(frozen=True, slots=True)
class BackendResult:
    """一个筛选后端跑完一轮的全部产出。

    审计字段之所以由后端填而不是在这里推断：只有后端知道自己实际连的是哪个端点、
    用的是哪个版本的模型。推断出来的审计信息不是审计信息。
    """

    decisions: Mapping[str, MergedDecision]
    usage: Mapping[str, object]
    #: 失败批次的说明。这些记录会因"通道缺少判定"进人工队列，**不是**"没有相关文献"。
    failures: Sequence[str] = field(default_factory=tuple)
    provider: str | None = None
    model: str | None = None
    endpoint_host: str | None = None
    parameters: Mapping[str, object] = field(default_factory=dict)
    #: 判定依据的哈希。OpenAI/宿主后端是系统提示词，判定 API 是编译出的问题集。
    prompt_sha256: str | None = None


def round_metadata(result: BackendResult, topic: Topic, expected: int) -> dict[str, object]:
    """组装 ``ScreeningRound`` 的审计头。

    字段缺一不可：``lit verify`` 靠它们判断一轮筛选是否可追溯到确切的协议、
    端点与模型版本。
    """
    return {
        "topic_fingerprint": protocol_fingerprint(topic),
        "provider": result.provider,
        "model": result.model,
        "endpoint_host": result.endpoint_host,
        "parameters": dict(result.parameters),
        "system_prompt_sha256": result.prompt_sha256,
        "expected_records": expected,
        "failures": list(result.failures),
        "usage": dict(result.usage),
    }


#: 报错时最多举几个例子。全倒出来只会把真正该看的那句话冲掉。
_EXAMPLE_KEYS = 5


def settled_keys(decisions: Mapping[str, MergedDecision]) -> set[str]:
    """已定谳的记录。

    定谳 = ``not needs_human``。这才是下游真正消费的东西：``included.jsonl``
    只收已定谳的纳入，PRISMA 也只数这些。还挂在人工队列里的记录没有结论。
    """
    return {key for key, item in decisions.items() if not item.needs_human}


@dataclass(frozen=True, slots=True)
class Regression:
    """一次退步写入的证据。是个值，不是异常——要不要因此中止是调用方的策略。"""

    settled_before: int
    settled_now: int
    lost_keys: tuple[str, ...]

    @property
    def lost(self) -> int:
        return len(self.lost_keys)

    def message(self) -> str:
        examples = "、".join(self.lost_keys[:_EXAMPLE_KEYS])
        more = f" 等 {self.lost:,} 条" if self.lost > _EXAMPLE_KEYS else ""
        return (
            f"上一轮已定谳 {self.settled_before:,} 条，这一轮只剩 {self.settled_now:,} 条，"
            f"其中 {self.lost:,} 条**丢失了已有结论**（{examples}{more}）。\n"
            f"下游只认轮次号最大的那一轮，写下去等于把上一轮的好结果遮蔽掉，"
            f"所以**不写入新轮次**，上一轮保持不变。\n"
            f"若这是有意的（例如窗口收窄后语料本就变少），加 --allow-regression "
            f"显式覆盖——该标记会记进轮次的 parameters，审计时看得见。"
        )


def find_regression(
    decisions: Mapping[str, MergedDecision],
    previous: Mapping[str, MergedDecision] | None,
) -> Regression | None:
    """比对上一轮，找出丢失的已定谳结论。没有退步返回 ``None``。

    判据是**已定谳集合的丢失**，不是判定总数。总数测不到它要防的那种失败：
    ``merge_verdicts(expected_keys=by_key)`` 保证每条记录都有一个判定，
    所以一轮全灭表现为「每条都有判定，但全是待人工」，数量分毫不变。
    当年那次事故之所以表现成「0 条判定」，是因为当时还没有 ``expected_keys``。

    反过来，把待人工的记录判出结论、或者语料变大，都不是退步。
    """
    if not previous:
        return None
    before = settled_keys(previous)
    now = settled_keys(decisions)
    lost = before - now
    if not lost:
        return None
    return Regression(
        settled_before=len(before),
        settled_now=len(now),
        # 按上一轮的顺序列举，让同一次退步每次报出的例子一致
        lost_keys=tuple(key for key in previous if key in lost),
    )


def next_round_number(run: Run) -> int:
    existing = [
        int(item.stem.rsplit("_", 1)[-1]) for item in run.root.glob("screening_round_*.json")
    ]
    return max(existing, default=0) + 1


def included_rows(
    decisions: Mapping[str, MergedDecision], records: Mapping[str, CanonicalRecord]
) -> list[dict]:
    """已定谳为纳入的记录。

    ``needs_human`` 的一律不算——它们还没有结论，写进 ``included.jsonl``
    就是凭空纳入。
    """
    return [
        records[key].model_dump(mode="json")
        for key, item in decisions.items()
        if not item.needs_human and item.decision.value == "include" and key in records
    ]


def commit_round(
    run: Run,
    topic_path: Path,
    result: BackendResult,
    records: Mapping[str, CanonicalRecord],
    *,
    topic: Topic,
    trial: bool,
) -> Path:
    """把一轮判定落盘，返回轮次文件路径。

    ``trial=True`` 写 ``screening_trial.json`` 且**不占轮次号**：否则一次
    ``--limit 100`` 的试跑会盖住正式全量结果，而下游只认轮次号最大的那一轮。
    试跑也不写 ``included.jsonl``，因为它只覆盖了语料的一小部分。
    """
    decisions = dict(result.decisions)
    meta = round_metadata(result, topic, expected=len(records))
    number = 1 if trial else next_round_number(run)
    payload = ScreeningRound(
        number=number,
        topic_sha256=freeze_topic(topic_path),
        decisions=decisions,
        **meta,
    ).model_dump_json(indent=2)

    if trial:
        path = run.write_text(TRIAL_ROUND, payload)
        run.write_text(TRIAL_QUEUE, render_human_queue(decisions, dict(records)))
        return path

    path = run.write_text(f"screening_round_{number}.json", payload)
    run.write_text(QUEUE, render_human_queue(decisions, dict(records)))
    run.write_jsonl(INCLUDED, included_rows(decisions, records))
    return path
