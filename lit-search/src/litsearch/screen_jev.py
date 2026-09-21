"""Jev 筛选后端：把纳排标准编译成 typed question，打分，再由纯函数路由成判定。

**它是打分器，不是第三个通道。** 把 Jev 映射成现有的纳入视角 / 排除视角两个
通道会坏事：一条明显离题的记录 p_inc=0.03、p_exc=0.02，纳入视角判 exclude，
排除视角"找不到排除理由"判 include，``merge_verdicts`` 判成分歧送进人工队列。
要避免就得让第二个通道也读 p_inc，那两个通道就成了同一向量的函数——正是
``screen.py`` 明令禁止的"同一个偏差重复两次，看起来像双重确认，实际毫无独立性"。

所以：每条记录一次请求、一个 ``Verdict``，由 ``route`` 直接构造
``MergedDecision``，``merge_verdicts`` 完全不参与。

**打分与路由分离。** 网络调用只发生在 ``score_records``，结果落成
``jev_scores.jsonl``；改阈值、扫阈值、分诊、评估全部是对同一批打分重新
``route``，零成本、零网络不确定性。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from litsearch.dedupe import CanonicalRecord
from litsearch.jev_client import JevError, ask_each
from litsearch.jev_profile import JevProfile
from litsearch.protocol import Topic
from litsearch.screen import Decision, MergedDecision, Verdict
from litsearch.screen_runner import CHARS_PER_TOKEN, CostEstimate, Usage

#: 问题的固定措辞。标准原文放进 ``criterion`` 字段，由这句话按名引用——
#: 官方建议：来自代码的数据单独成字段，不要拼进句子里。
_ASK = "Does this record satisfy `criterion`?"

#: 排除标准概率到多少才值得写进 reason 给人看。**只影响显示，不影响判定**——
#: 排除标准根本不参与打分。
EXCLUSION_FLAG_AT = 0.5

NO_ABSTRACT = "（无摘要）"
TRUNCATED = "…（摘要已截断）"


def compile_questions(topic: Topic, profile: JevProfile) -> dict[str, dict]:
    """每条生效的标准编译成一个 Noul，问题 id 就是标准编号。

    标准**原文照抄**，不改写也不概括——否则判定依据就与协议脱钩了。
    实测也支持照抄：中文标准原文 AUC 0.989，手写英文原子问题 0.982。
    """
    questions: dict[str, dict] = {}
    for item in profile.active_inclusions(topic) + profile.active_exclusions(topic):
        questions[item.id] = {
            "type": "noul",
            "instructions": {"question": _ASK, "criterion": item.text},
        }
    return questions


def questions_sha256(questions: Mapping[str, dict]) -> str:
    """问题集的哈希。变了就说明旧打分不再可比，续跑必须重打而不是沿用。"""
    payload = json.dumps(questions, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def build_state(record: CanonicalRecord, profile: JevProfile) -> dict[str, str]:
    """只装问题用得上的字段。

    无关内容会拉低判别力（官方称之为 context rot），所以不把整条记录倒进去。
    缺摘要要明说：留空会让模型以为"摘要提过但没细说"，而不是"根本没有摘要"。
    """
    abstract = (record.abstract or "").strip()
    if not abstract:
        abstract = NO_ABSTRACT
    elif len(abstract) > profile.max_abstract_chars:
        abstract = abstract[: profile.max_abstract_chars] + TRUNCATED
    return {
        "title": record.title,
        "venue": record.venue or "（未知来源）",
        "abstract": abstract,
    }


def state_sha256(state: Mapping[str, str]) -> str:
    payload = json.dumps(state, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ScoreRow:
    """一条记录的打分结果。有行就是判过，没行就是没判过。

    ``questions_sha256`` 让续跑分得清"这条判过了"和"这条是按旧问题集判的"。
    """

    record_key: str
    model: str
    questions_sha256: str
    state_sha256: str
    answers: Mapping[str, float]
    input_tokens: int

    def to_json(self) -> dict:
        return {
            "record_key": self.record_key,
            "model": self.model,
            "questions_sha256": self.questions_sha256,
            "state_sha256": self.state_sha256,
            "answers": dict(self.answers),
            "input_tokens": self.input_tokens,
        }

    @classmethod
    def from_json(cls, payload: Mapping) -> ScoreRow:
        return cls(
            record_key=payload["record_key"],
            model=payload.get("model", ""),
            questions_sha256=payload.get("questions_sha256", ""),
            state_sha256=payload.get("state_sha256", ""),
            answers={key: float(value) for key, value in (payload.get("answers") or {}).items()},
            input_tokens=int(payload.get("input_tokens") or 0),
        )


def pending_records(
    records: Sequence[CanonicalRecord],
    rows: Mapping[str, ScoreRow],
    questions_hash: str,
) -> list[CanonicalRecord]:
    """还没按**当前问题集**打过分的记录。

    问题集变了就得重打：拿旧标准打的分去套新协议，判定依据是错的。
    """
    return [
        item
        for item in records
        if (row := rows.get(item.key)) is None or row.questions_sha256 != questions_hash
    ]


async def score_records(
    client,
    topic: Topic,
    profile: JevProfile,
    records: Sequence[CanonicalRecord],
    *,
    concurrency: int = 16,
    on_error: Callable[[str, Exception], None] | None = None,
    checkpoint: Callable[[ScoreRow], None] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[list[ScoreRow], Usage]:
    """逐条打分。并发扇出与失败策略共用 ``ask_each``，这里只负责组装行。"""
    questions = compile_questions(topic, profile)
    digest = questions_sha256(questions)

    def to_row(judged) -> ScoreRow:
        return ScoreRow(
            record_key=judged.key,
            model=judged.reply.model,
            questions_sha256=digest,
            state_sha256=state_sha256(judged.state),
            answers=judged.reply.nouls(),
            input_tokens=judged.reply.input_tokens,
        )

    items = [(item.key, build_state(item, profile)) for item in records]
    judged, tokens = await ask_each(
        client,
        items,
        questions,
        concurrency=concurrency,
        on_error=on_error,
        checkpoint=(lambda item: checkpoint(to_row(item))) if checkpoint else None,
        progress=progress,
    )
    usage = Usage(
        cache_hit=0,  # Jev 没有前缀缓存，每次都吃完整 state
        cache_miss=tokens,
        output=0,  # 输出免费，不进成本
    )
    return [to_row(item) for item in judged], usage


def _verdict(
    key: str, decision: Decision, score: float, matched: list[str], reason: str
) -> Verdict:
    return Verdict(
        record_key=key,
        decision=decision,
        matched_criteria=matched,
        reason=reason,
        confidence=max(score, 1.0 - score),
        channel=0,
    )


def _reason(answers: Mapping[str, float], inclusions: list[str], exclusions: list[str]) -> str:
    weakest = min(inclusions, key=lambda cid: answers[cid])
    parts = [
        f"{cid}={answers[cid]:.2f}" + ("*" if cid == weakest else "") for cid in inclusions
    ]
    fired = [f"{cid}={answers[cid]:.2f}" for cid in exclusions if answers[cid] >= EXCLUSION_FLAG_AT]
    text = " ".join(parts)
    if fired:
        text += " | 排除标准命中：" + " ".join(fired)
    return text


def route(
    record_key: str, row: ScoreRow | None, topic: Topic, profile: JevProfile
) -> MergedDecision:
    """把一条打分路由成判定。纯函数——改阈值重跑它不花一分钱。

    分数 = 生效纳入标准的**最小值**：它们要同时满足，合取取最小；求平均会让
    一条严重不满足的标准被另一条高分掩盖。排除标准只写进 reason 供人看，
    **不参与打分**——实测乘上 ``(1 - max 排除概率)`` 反而更差（AUC 0.989→0.981），
    官方文档也说一个问题与其否定式的概率不满足互补关系。
    """
    if row is None:
        # "缺少"这两个字是 cli.py 统计漏判数的判据，别改。
        return MergedDecision(
            record_key=record_key,
            decision=Decision.UNCLEAR,
            needs_human=True,
            reason="缺少判定：该记录没有打分结果（请求失败或尚未打分）",
        )

    inclusions = [item.id for item in profile.active_inclusions(topic)]
    exclusions = [item.id for item in profile.active_exclusions(topic)]
    if missing := [cid for cid in inclusions + exclusions if cid not in row.answers]:
        raise JevError(
            f"记录 {record_key} 的打分缺少标准 {sorted(missing)}——"
            f"少问一条却照常路由，等于悄悄放开它"
        )

    score = min(row.answers[cid] for cid in inclusions)
    reason = _reason(row.answers, inclusions, exclusions)
    weakest = min(inclusions, key=lambda cid: row.answers[cid])
    fired = [cid for cid in exclusions if row.answers[cid] >= EXCLUSION_FLAG_AT]

    if score >= profile.include_at:
        decision = Decision.INCLUDE
        matched = [cid for cid in inclusions if row.answers[cid] >= profile.include_at] + fired
        needs_human = False
    elif score < profile.exclude_below:
        decision = Decision.EXCLUDE
        matched = [weakest, *fired]
        needs_human = False
    else:
        decision = Decision.UNCLEAR
        matched = [weakest, *fired]
        needs_human = True
        reason = f"落在待定带（{profile.exclude_below}–{profile.include_at}）：{reason}"

    return MergedDecision(
        record_key=record_key,
        decision=decision,
        needs_human=needs_human,
        reason=reason,
        channel_verdicts=[_verdict(record_key, decision, score, matched, reason)],
    )


def route_all(
    records: Sequence[CanonicalRecord],
    rows: Mapping[str, ScoreRow],
    topic: Topic,
    profile: JevProfile,
) -> dict[str, MergedDecision]:
    """每条记录都要有判定，没打上分的也要——否则它会从 PRISMA 里凭空消失。"""
    return {item.key: route(item.key, rows.get(item.key), topic, profile) for item in records}


def gold_set_violations(
    decisions: Mapping[str, MergedDecision],
    records: Iterable[CanonicalRecord],
    topic: Topic,
) -> list[str]:
    """被**自动排除**的金标种子。

    进人工队列不算——人还会看它。只有"机器直接判了排除"才是缺陷：
    金标是"必须被检出并保留"的定义，它被排掉说明阈值或判定器有问题。
    """
    wanted = {
        (kind, value) for seed in topic.gold_set for kind, value in seed.identifiers.items()
    }
    violations = []
    for item in records:
        if not any((kind, value) in wanted for kind, value in item.identifiers.items()):
            continue
        decision = decisions.get(item.key)
        if decision and not decision.needs_human and decision.decision is Decision.EXCLUDE:
            violations.append(item.key)
    return violations


def estimate_jev(
    topic: Topic, profile: JevProfile, records: Sequence[CanonicalRecord]
) -> CostEstimate:
    """按字符数近似估算。一条记录一个请求，输入计费、输出免费。

    实测 token 随问题数**亚线性**增长（1 问 630、3 问 674、8 问 784、16 问 966）：
    state 占大头，每多一个问题只加约 20 token。
    """
    questions = compile_questions(topic, profile)
    question_chars = len(json.dumps(questions, ensure_ascii=False))
    total = 0
    for item in records:
        state = build_state(item, profile)
        state_chars = len(json.dumps(state, ensure_ascii=False))
        total += int((state_chars + question_chars) / CHARS_PER_TOKEN)
    return CostEstimate(
        requests=len(records),
        records=len(records),
        usage=Usage(cache_hit=0, cache_miss=total, output=0),
        cold_requests=len(records),
        precise=False,
    )


#: 分诊队列的表头。前四列是 ``lit adjudicate`` 的固定契约（留空给人填），
#: 判定器给出的线索紧随其后——人打开 CSV 第一眼就该看到它们。
_TRIAGE_HEADER = (
    "record_key,decision,reviewer,reason,"
    "jev_score,jev_weakest,jev_exclusions,queue_reason,doi,channel_decisions,title"
)
UNSCORED = "未打分"


def _score_of(row: ScoreRow | None, inclusions: list[str]) -> float | None:
    if row is None or any(cid not in row.answers for cid in inclusions):
        return None
    return min(row.answers[cid] for cid in inclusions)


def render_triage_queue(
    decisions: Mapping[str, MergedDecision],
    records: Sequence[CanonicalRecord],
    rows: Mapping[str, ScoreRow],
    topic: Topic,
    profile: JevProfile,
) -> str:
    """把人工队列重排成有优先级的工作队列。

    **按分数降序**，最可能纳入的排最前。理由是这个项目一以贯之的不对称：错误排除
    不可逆，错误纳入只是多读一篇全文。队列往往没人看得完（实测两个 run 合计
    2,541 行至今空着），所以排在前面的应该是「漏掉代价最大」的那些。

    没打上分的排最后并注明——它不是"最不相关"，只是还没判过。
    """
    inclusions = [item.id for item in profile.active_inclusions(topic)]
    exclusions = [item.id for item in profile.active_exclusions(topic)]
    by_key = {item.key: item for item in records}

    queued = [key for key, item in decisions.items() if item.needs_human]
    scored = [(key, _score_of(rows.get(key), inclusions)) for key in queued]
    # 无分数排最后：-1 只用于排序，不会出现在输出里。
    scored.sort(key=lambda pair: (pair[1] is not None, pair[1] or -1.0), reverse=True)

    lines = [_TRIAGE_HEADER]
    for key, score in scored:
        row = rows.get(key)
        record = by_key.get(key)
        title = (record.title if record else "").replace('"', "'")
        doi = record.identifiers.get("doi", "") if record else ""
        channels = "|".join(
            f"{item.decision.value}@{item.confidence:.2f}"
            for item in decisions[key].channel_verdicts
        )
        if score is None or row is None:
            cells = f"{UNSCORED},,"
        else:
            weakest = min(inclusions, key=lambda cid: row.answers[cid])
            fired = " ".join(
                f"{cid}={row.answers[cid]:.2f}"
                for cid in exclusions
                if row.answers.get(cid, 0.0) >= EXCLUSION_FLAG_AT
            )
            cells = f"{score:.3f},{weakest}={row.answers[weakest]:.2f},{fired}"
        lines.append(
            f'{key},,,,{cells},"{decisions[key].reason}",{doi},{channels},"{title}"'
        )
    return "\n".join(lines) + "\n"


def tiebreak_candidates(
    decisions: Mapping[str, MergedDecision],
    rows: Mapping[str, ScoreRow],
    topic: Topic,
    profile: JevProfile,
) -> list[dict[str, str]]:
    """两个 LLM 通道互相矛盾、而判定器明确站在纳入一侧的那些记录。

    这不是让模型单方面拍板——是两个**不同模型族**达成一致，且只往可逆方向走。
    低置信度不算僵局（两个通道本就一致，没什么可打破的）；没有任何通道主张纳入
    也不算（那样 Jev 就是在独自拍板，不是打破僵局）。
    """
    inclusions = [item.id for item in profile.active_inclusions(topic)]
    picked: list[dict[str, str]] = []
    for key, decision in decisions.items():
        if not decision.needs_human:
            continue
        stances = {item.decision for item in decision.channel_verdicts}
        if len(stances) < 2 or Decision.INCLUDE not in stances:
            continue
        score = _score_of(rows.get(key), inclusions)
        if score is None or score < profile.include_at:
            continue
        agreeing = next(
            item.channel
            for item in decision.channel_verdicts
            if item.decision is Decision.INCLUDE
        )
        picked.append(
            {
                "record_key": key,
                "decision": Decision.INCLUDE.value,
                "reason": (
                    f"通道 {agreeing} 判 include，判定器打分 {score:.2f} "
                    f"≥ {profile.include_at}——两个模型族一致"
                ),
            }
        )
    return picked
