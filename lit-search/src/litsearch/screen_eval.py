"""筛选判定的评估基座：换判定器时，回答"这次是变好还是变坏"。

``metrics.py`` 量的是**检索**召回（该找到的论文找到没有）。这一层量的是**筛选**
精度（找到之后判对没有）——项目此前完全没有这类指标，于是换模型、换后端、改阈值
都只能凭感觉。

三条纪律，都是被数据逼出来的：

1. **金标与银标分开报。** 金标 = 真人裁决；银标 = 模型判定。实测某课题银标纳入
   约 21% 是错的，拿它当真值算出的精度是天花板，不是真相。
2. **每个比率带 Wilson 区间。** 44 条纳入即使 100% 敏感，95% 下界也只有约 92%。
   不带区间就会把"没测出问题"讲成"证明了没问题"。
3. **错误排除与进队列分开数。** 错误排除不可逆（那篇论文再也不会被看到），
   错误纳入只是多读一篇全文。把两者平均进一个 F1 里等于抹掉唯一重要的区别。
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from litsearch.dedupe import CanonicalRecord
from litsearch.screen import Decision, MergedDecision

#: 95% 双侧正态分位数。
Z95 = 1.959963984540054

GOLD = "gold"
SILVER = "silver"


def wilson(k: int, n: int, *, z: float = Z95) -> tuple[float, float]:
    """比例的 Wilson 得分区间。

    比 Wald 区间好在两头：``k == n`` 时下界仍然小于 1，``k == 0`` 时上界仍然大于 0。
    正态近似在这两种情形下会给出宽度为零的区间，也就是"100% 准确"这种谎话。
    """
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denominator = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return (max(0.0, center - half), min(1.0, center + half))


def auc(pos: Sequence[float], neg: Sequence[float]) -> float | None:
    """ROC 曲线下面积，按秩计算（Mann-Whitney U），并列记 0.5。

    任一侧为空时返回 ``None`` 而不是 0.5——"无法计算"和"毫无判别力"是两回事。
    """
    if not pos or not neg:
        return None
    wins = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


@dataclass(frozen=True, slots=True)
class Reference:
    """参考标签。``tier`` 记录每条标签的来源，因为两种来源的可信度差一个量级。"""

    labels: Mapping[str, Decision]
    tier: Mapping[str, str]
    #: 金标种子：被自动排除即为检索/筛选缺陷，必须单独喊出来。
    must_keep: frozenset[str]


@dataclass(frozen=True, slots=True)
class Prediction:
    record_key: str
    decision: Decision
    queued: bool
    score: float | None = None


@dataclass(frozen=True, slots=True)
class Confusion:
    total: int
    tp: int
    fp: int
    tn: int
    fn: int
    queued: int
    queued_include: int
    queued_exclude: int
    missed_keys: tuple[str, ...] = ()
    must_keep_violations: tuple[str, ...] = ()

    @property
    def missed(self) -> int:
        """被**自动排除**的参考纳入记录。不可逆错误，这是头号指标。"""
        return self.fn

    @property
    def auto_include_precision(self) -> float | None:
        decided = self.tp + self.fp
        return self.tp / decided if decided else None

    @property
    def auto_exclude_npv(self) -> float | None:
        decided = self.tn + self.fn
        return self.tn / decided if decided else None

    @property
    def queue_rate(self) -> float | None:
        return self.queued / self.total if self.total else None

    @property
    def n_reference_include(self) -> int:
        return self.tp + self.fn + self.queued_include


def reference_from_round(
    decisions: Mapping[str, MergedDecision], gold_keys: frozenset[str]
) -> Reference:
    """把一轮筛选结果当作参考标签。

    还挂在人工队列里的记录**没有结论**，不进标签集——把"还没定"当成"判定为 unclear"
    会凭空造出一类真值。
    """
    labels: dict[str, Decision] = {}
    tier: dict[str, str] = {}
    for key, decision in decisions.items():
        if decision.needs_human:
            continue
        labels[key] = decision.decision
        tier[key] = GOLD if decision.adjudicated_by else SILVER
    return Reference(labels=labels, tier=tier, must_keep=gold_keys)


def predictions_from_round(decisions: Mapping[str, MergedDecision]) -> list[Prediction]:
    return [
        Prediction(
            record_key=key,
            decision=item.decision,
            queued=item.needs_human,
            score=None,
        )
        for key, item in decisions.items()
    ]


def predictions_from_scores(
    scores: Mapping[str, float], *, include_at: float, exclude_below: float
) -> list[Prediction]:
    """把连续分数路由成三档：纳入、排除、进队列。

    判定器无关——传进来的可以是 Jev 的概率，也可以是任何别的打分。
    """
    if not exclude_below < include_at:
        raise ValueError(
            f"排除带上界必须低于纳入带下界，收到 exclude_below={exclude_below} "
            f">= include_at={include_at}"
        )
    out: list[Prediction] = []
    for key, score in scores.items():
        if score >= include_at:
            out.append(Prediction(key, Decision.INCLUDE, queued=False, score=score))
        elif score < exclude_below:
            out.append(Prediction(key, Decision.EXCLUDE, queued=False, score=score))
        else:
            out.append(Prediction(key, Decision.UNCLEAR, queued=True, score=score))
    return out


def confusion(
    preds: Iterable[Prediction], ref: Reference, *, tier: str | None = None
) -> Confusion:
    """对照参考标签计数。没有参考标签的预测直接跳过——无从评判。"""
    tp = fp = tn = fn = queued = queued_include = queued_exclude = 0
    missed: list[str] = []
    violations: list[str] = []
    total = 0
    for item in preds:
        label = ref.labels.get(item.record_key)
        if label is None:
            continue
        if tier is not None and ref.tier.get(item.record_key) != tier:
            continue
        total += 1
        if item.queued:
            queued += 1
            if label is Decision.INCLUDE:
                queued_include += 1
            else:
                queued_exclude += 1
            continue
        if item.decision is Decision.INCLUDE:
            if label is Decision.INCLUDE:
                tp += 1
            else:
                fp += 1
        else:
            if label is Decision.INCLUDE:
                fn += 1
                missed.append(item.record_key)
            else:
                tn += 1
            if item.record_key in ref.must_keep:
                violations.append(item.record_key)
    return Confusion(
        total=total,
        tp=tp,
        fp=fp,
        tn=tn,
        fn=fn,
        queued=queued,
        queued_include=queued_include,
        queued_exclude=queued_exclude,
        missed_keys=tuple(missed),
        must_keep_violations=tuple(violations),
    )


@dataclass(frozen=True, slots=True)
class SweepRow:
    exclude_below: float
    include_at: float
    missed: int
    queued: int
    auto_include_precision: float | None
    auto_exclude_npv: float | None


def sweep(
    scores: Mapping[str, float],
    ref: Reference,
    *,
    grid: Sequence[float],
    include_at: float = 0.7,
    tier: str | None = None,
) -> list[SweepRow]:
    """扫排除带阈值。让"少漏一篇要多付多少队列"这笔账显式可见。"""
    rows: list[SweepRow] = []
    for lo in grid:
        preds = predictions_from_scores(scores, include_at=include_at, exclude_below=lo)
        c = confusion(preds, ref, tier=tier)
        rows.append(
            SweepRow(
                exclude_below=lo,
                include_at=include_at,
                missed=c.missed,
                queued=c.queued,
                auto_include_precision=c.auto_include_precision,
                auto_exclude_npv=c.auto_exclude_npv,
            )
        )
    return rows


@dataclass(frozen=True, slots=True)
class Bin:
    lo: float
    hi: float
    n: int
    observed: float | None
    ci: tuple[float, float] = field(default=(0.0, 1.0))


def reliability(scores: Mapping[str, float], ref: Reference, *, bins: int = 5) -> list[Bin]:
    """校准表：某个分数区间里的记录，实际有多大比例是纳入的。

    空桶照样留着——分数从不落在某个区间本身就是信息，删掉就看不见了。
    """
    width = 1.0 / bins
    buckets: list[list[bool]] = [[] for _ in range(bins)]
    for key, score in scores.items():
        label = ref.labels.get(key)
        if label is None:
            continue
        index = min(bins - 1, max(0, int(score / width)))
        buckets[index].append(label is Decision.INCLUDE)
    out: list[Bin] = []
    for index, bucket in enumerate(buckets):
        n = len(bucket)
        hits = sum(bucket)
        out.append(
            Bin(
                lo=round(index * width, 6),
                hi=round((index + 1) * width, 6),
                n=n,
                observed=(hits / n) if n else None,
                ci=wilson(hits, n),
            )
        )
    return out


#: 与 ``render_human_queue`` 同构：前四列留空给人填，诊断信息放后面。
_DISAGREEMENT_HEADER = "record_key,decision,reviewer,reason,disagreement,score,doi,title"


def disagreements_csv(
    preds: Iterable[Prediction],
    ref: Reference,
    records: Mapping[str, CanonicalRecord],
) -> str:
    """判定器与参考标签不一致的记录，导成可直接回填的裁定 CSV。

    这是评估报告的主产物。汇总指标告诉你差多少，这张表告诉你差在哪——
    而且填完就能被 ``lit adjudicate`` 直接吃回去。
    """
    lines = [_DISAGREEMENT_HEADER]
    for item in preds:
        label = ref.labels.get(item.record_key)
        if label is None or item.queued or item.decision is label:
            continue
        record = records.get(item.record_key)
        title = (record.title if record else "").replace('"', "'")
        doi = record.identifiers.get("doi", "") if record else ""
        score = f"{item.score:.3f}" if item.score is not None else ""
        source = ref.tier.get(item.record_key, "")
        note = f"判定 {item.decision.value} vs 参考 {label.value}（{source}）"
        lines.append(f'{item.record_key},,,,"{note}",{score},{doi},"{title}"')
    return "\n".join(lines) + "\n"


def _rate_line(label: str, k: int, n: int) -> str:
    if not n:
        return f"| {label} | — | 无样本 |"
    lo, hi = wilson(k, n)
    return f"| {label} | {k}/{n} = {k / n:.1%} | [{lo:.1%}, {hi:.1%}] |"


def _confusion_section(name: str, c: Confusion, *, caveat: str = "") -> list[str]:
    if not c.total:
        return [f"### {name}", "", "无样本。", ""]
    lines = [f"### {name}（n={c.total}）", ""]
    if caveat:
        lines += [caveat, ""]
    lines += ["| 指标 | 值 | 95% Wilson 区间 |", "| --- | --- | --- |"]
    lines.append(_rate_line("**被自动排除的纳入记录**（不可逆）", c.fn, c.n_reference_include))
    lines.append(_rate_line("自动纳入精度", c.tp, c.tp + c.fp))
    lines.append(_rate_line("自动排除 NPV", c.tn, c.tn + c.fn))
    lines.append(_rate_line("人工队列率", c.queued, c.total))
    lines += ["", f"混淆矩阵：TP={c.tp} FP={c.fp} TN={c.tn} FN={c.fn}，队列 {c.queued}", ""]
    return lines


def render_markdown(
    *,
    title: str,
    preds: Sequence[Prediction],
    ref: Reference,
    scores: Mapping[str, float] | None = None,
) -> str:
    """评估报告。金标在前，银标在后且明确标注为天花板。"""
    overall = confusion(preds, ref)
    lines = [f"# 筛选评估：{title}", ""]

    if overall.must_keep_violations:
        lines += [
            "> **金标种子被自动排除**："
            + "、".join(overall.must_keep_violations)
            + "。金标是「必须被检出并保留」的种子，出现在这里说明判定器或阈值有缺陷，"
            "不是可以接受的误差。",
            "",
        ]

    lines += _confusion_section("金标（真人裁决）", confusion(preds, ref, tier=GOLD))
    lines += _confusion_section(
        "银标（模型判定）",
        confusion(preds, ref, tier=SILVER),
        caveat="> 银标本身含错。实测某课题银标纳入约 21% 被真人推翻，"
        "所以这一节的数字是**天花板**，不是真实精度。",
    )
    lines += _confusion_section("合计", overall)

    if scores:
        pos = [scores[k] for k, v in ref.labels.items() if v is Decision.INCLUDE and k in scores]
        neg = [scores[k] for k, v in ref.labels.items() if v is Decision.EXCLUDE and k in scores]
        value = auc(pos, neg)
        lines += ["### 判别力与校准", ""]
        lines.append(
            f"AUC = {value:.3f}（纳入 {len(pos)} / 排除 {len(neg)}）"
            if value is not None
            else "AUC 无法计算（某一侧没有样本）。"
        )
        lines += [
            "",
            "| 分数区间 | 记录数 | 实际纳入率 | 95% Wilson 区间 |",
            "| --- | --- | --- | --- |",
        ]
        for item in reliability(scores, ref):
            observed = "—" if item.observed is None else f"{item.observed:.1%}"
            span = "—" if not item.n else f"[{item.ci[0]:.1%}, {item.ci[1]:.1%}]"
            lines.append(f"| [{item.lo:.1f}, {item.hi:.1f}) | {item.n} | {observed} | {span} |")
        lines.append("")

    return "\n".join(lines)
