"""双通道标题摘要筛选的纯逻辑。

模型不能单方面拍板。两个通道用**不同的思路框架**独立判定同一批记录：
一个从纳入标准出发，一个主动找排除理由。两者一致且都有把握才算定论；
分歧、低置信度、"判不了"、任一通道漏判——一律进人工队列。

判定按轮次不可变追加。要改判就开新一轮，绝不改写上一轮——否则
"这批文献是怎么筛出来的"这个问题就永远答不上来了。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from litsearch import ARTIFACT_SCHEMA_VERSION, __version__
from litsearch.dedupe import CanonicalRecord
from litsearch.protocol import Criteria, ScreeningConfig

MAX_ABSTRACT_CHARS = 2000


class Decision(str, Enum):
    INCLUDE = "include"
    EXCLUDE = "exclude"
    #: 模型明确表示判不了。必须保留这个选项——逼它二选一只会把不确定伪装成确定。
    UNCLEAR = "unclear"


class Verdict(BaseModel):
    """单个通道对单条记录的判定。这是模型返回的结构化输出。

    ``channel`` **不在**模型的输出 schema 里，由驱动层在解析后盖上——
    通道号是请求的属性，不是模型该回答的东西，让它填只会多一个出错的地方。
    没有这个字段就分不清"通道 0 缺判"和"通道 1 缺判"，续跑也就无从谈起。
    """

    record_key: str
    decision: Decision
    matched_criteria: list[str] = Field(default_factory=list)
    reason: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    channel: int | None = None


class MergedDecision(BaseModel):
    """双通道合并后的结论，保留每个通道的原始判定以备审计。"""

    record_key: str
    decision: Decision
    needs_human: bool
    reason: str
    channel_verdicts: list[Verdict] = Field(default_factory=list)
    adjudicated_by: str | None = None
    adjudicated_at: str | None = None
    adjudication_reason: str | None = None
    previous_decision: Decision | None = None

    @property
    def matched_criteria(self) -> list[str]:
        seen: list[str] = []
        for item in self.channel_verdicts:
            for criterion in item.matched_criteria:
                if criterion not in seen:
                    seen.append(criterion)
        return seen


class ScreeningRound(BaseModel):
    """一轮筛选。冻结后不可修改——改判请开新一轮。"""

    model_config = ConfigDict(frozen=True)

    number: int = Field(ge=1)
    #: 这一轮所依据的协议版本，使判定能追溯到确切的纳排标准
    topic_sha256: str
    topic_fingerprint: str | None = None
    schema_version: int = ARTIFACT_SCHEMA_VERSION
    tool_version: str = __version__
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    provider: str | None = None
    model: str | None = None
    endpoint_host: str | None = None
    parameters: dict[str, object] = Field(default_factory=dict)
    system_prompt_sha256: str | None = None
    expected_records: int | None = None
    failures: list[str] = Field(default_factory=list)
    usage: dict[str, object] = Field(default_factory=dict)
    decisions: dict[str, MergedDecision] = Field(default_factory=dict)

    def next_round(self) -> ScreeningRound:
        return ScreeningRound(number=self.number + 1, topic_sha256=self.topic_sha256, decisions={})


#: 两个通道用不同的思路框架，而不是同一段提示词跑两遍——
#: 后者只是把同一个偏差重复两次，看起来像"双重确认"，实际毫无独立性。
#: 标题摘要阶段的通用规则。两个通道共用，因为它约束的是**阶段**而非视角。
#:
#: 初筛必须从宽：错误排除**不可逆**（那篇论文再也不会被看到），
#: 错误纳入只是多读一篇全文。所以"这条标准要读全文才能确认"绝不能触发 unclear——
#: 否则每一篇正经论文都会进人工队列（实测：不写这段时，13% 的记录被送去人工，
#: 其中绝大多数是模型在等摘要给出 Dice/HD95，而那本来就只在全文里）。
_STAGE_RULE = (
    "这是**标题摘要初筛**，不是全文评估。两条纪律：\n"
    "1. 错误排除不可逆，错误纳入只是多读一篇全文——拿不准就倾向 include。\n"
    "2. 只有当**主题本身**判不清（这项研究到底做没做该疾病、该任务）才判 unclear。\n"
    "   若某条标准按其性质只能读全文确认（如具体评价指标、样本量、实现细节），\n"
    "   而其余标准已明确满足，就判 include 并在 reason 里注明「待全文确认」，\n"
    "   **不要**因此判 unclear。"
)

CHANNEL_PROMPTS = (
    (
        "你在做系统综述的标题摘要初筛。逐条记录**先看纳入标准**：\n"
        "只要它满足全部纳入标准，就判 include；明确违反任一排除标准则判 exclude。\n"
        f"\n{_STAGE_RULE}"
    ),
    (
        "你在做系统综述的标题摘要初筛，职责是**把不该纳入的挑出来**。\n"
        "逐条记录主动寻找排除理由：命中任一排除标准即判 exclude。\n"
        "确实找不到排除理由、且满足全部纳入标准时才判 include。\n"
        "不要为了给出结论而放宽排除标准。\n"
        f"\n{_STAGE_RULE}"
    ),
)

_OUTPUT_CONTRACT = (
    "对**每一条**记录输出一个判定对象，字段：\n"
    "  record_key: 记录的 key，原样照抄\n"
    "  decision: include | exclude | unclear\n"
    '  matched_criteria: 命中的标准编号列表，如 ["I1","I2"] 或 ["X2"]\n'
    "  reason: 一句话说明依据，引用记录中的具体内容\n"
    "  confidence: 0 到 1 的置信度\n\n"
    "不得遗漏任何一条记录，也不得输出输入中没有的 record_key。"
)


def build_channel_prompt(criteria: Criteria, channel: int) -> str:
    """构造某个通道的系统提示词。

    标准逐条原样写入——不做改写或概括，否则判定依据就与协议脱钩了。
    这段内容在整轮筛选中完全稳定，作为 prompt cache 的前缀。
    """
    if not 0 <= channel < len(CHANNEL_PROMPTS):
        raise IndexError(f"通道编号 {channel} 超出范围；已定义 {len(CHANNEL_PROMPTS)} 个通道")

    lines = [CHANNEL_PROMPTS[channel], "", "## 纳入标准（须全部满足）"]
    lines += [f"- {item.id}: {item.text}" for item in criteria.include]
    if criteria.exclude:
        lines += ["", "## 排除标准（命中任一即排除）"]
        lines += [f"- {item.id}: {item.text}" for item in criteria.exclude]
    lines += ["", "## 输出要求", _OUTPUT_CONTRACT]
    return "\n".join(lines)


def build_batches(records: list[CanonicalRecord], batch_size: int) -> list[list[CanonicalRecord]]:
    if batch_size < 1:
        raise ValueError("batch_size 必须 >= 1")
    return [records[index : index + batch_size] for index in range(0, len(records), batch_size)]


def format_records(records: list[CanonicalRecord]) -> str:
    """把一批记录渲染成提示词正文。缺摘要要显式说明，不能静默留空。"""
    blocks = []
    for record in records:
        abstract = (record.abstract or "").strip()
        if not abstract:
            abstract = "（无摘要）"
        elif len(abstract) > MAX_ABSTRACT_CHARS:
            abstract = abstract[:MAX_ABSTRACT_CHARS] + "…（摘要已截断）"
        venue = record.venue or "（未知来源）"
        blocks.append(
            f"### key: {record.key}\n标题：{record.title}\n来源：{venue}\n摘要：{abstract}"
        )
    return "\n\n".join(blocks)


def _flag(record_key: str, reason: str, verdicts: list[Verdict]) -> MergedDecision:
    return MergedDecision(
        record_key=record_key,
        decision=Decision.UNCLEAR,
        needs_human=True,
        reason=reason,
        channel_verdicts=verdicts,
    )


def merge_verdicts(
    channels: list[list[Verdict]],
    config: ScreeningConfig,
    *,
    expected_keys: Iterable[str] | None = None,
) -> dict[str, MergedDecision]:
    """合并各通道判定。任何不一致都向上暴露，不向下压平。"""
    by_channel: list[dict[str, Verdict]] = [
        {item.record_key: item for item in channel} for channel in channels
    ]
    keys: list[str] = list(dict.fromkeys(expected_keys or ()))
    for channel in by_channel:
        for key in channel:
            if key not in keys:
                keys.append(key)

    merged: dict[str, MergedDecision] = {}
    for key in keys:
        verdicts = [channel[key] for channel in by_channel if key in channel]

        if len(verdicts) < len(by_channel):
            missing = len(by_channel) - len(verdicts)
            merged[key] = _flag(key, f"有 {missing} 个通道缺少对该记录的判定", verdicts)
            continue

        if any(item.decision == Decision.UNCLEAR.value for item in verdicts):
            merged[key] = _flag(key, "有通道判定为 unclear（信息不足）", verdicts)
            continue

        low = [item for item in verdicts if item.confidence < config.confidence_threshold]
        if low:
            lowest = min(item.confidence for item in low)
            merged[key] = _flag(
                key,
                f"置信度不足（最低 {lowest:.2f} < 阈值 {config.confidence_threshold}）",
                verdicts,
            )
            continue

        decisions = {item.decision for item in verdicts}
        if len(decisions) > 1:
            merged[key] = _flag(key, f"通道间分歧：{sorted(decisions)}", verdicts)
            continue

        merged[key] = MergedDecision(
            record_key=key,
            decision=Decision(decisions.pop()),
            needs_human=False,
            reason=verdicts[0].reason,
            channel_verdicts=verdicts,
        )

    return merged


def render_human_queue(
    decisions: dict[str, MergedDecision], records: dict[str, CanonicalRecord]
) -> str:
    """待人工裁定清单。每一行都说明它为什么在这里。"""
    lines = ["record_key,decision,reviewer,reason,queue_reason,doi,channel_decisions,title"]
    for key, decision in decisions.items():
        if not decision.needs_human:
            continue
        record = records.get(key)
        title = (record.title if record else "").replace('"', "'")
        doi = record.identifiers.get("doi", "") if record else ""
        channels = "|".join(
            f"{item.decision}@{item.confidence:.2f}" for item in decision.channel_verdicts
        )
        lines.append(f'{key},,,,"{decision.reason}",{doi},{channels},"{title}"')
    return "\n".join(lines) + "\n"


def summarize(decisions: dict[str, MergedDecision]) -> dict[str, int]:
    counts = {"include": 0, "exclude": 0, "human_queue": 0}
    for decision in decisions.values():
        if decision.needs_human:
            counts["human_queue"] += 1
        else:
            counts[decision.decision.value] += 1
    return counts
