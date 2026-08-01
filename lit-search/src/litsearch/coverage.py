"""召回率证据。

红线：**每一项都是测出来的，没有一项是声称的**——这条同样管着"没做成的事"。

这个模块存在的直接原因是一次事故：覆盖率报告里有一句无条件拼进去的
"捕获-再捕获需 PubMed 与 OpenAlex 同时在场；OpenAlex 受配额限制未纳入"。
而那次运行 OpenAlex 明明跑了 3,944 条，真正缺席的是被协议主动关掉的 PubMed。
证据文件里的硬编码叙述是最坏的一种：它和算出来的长得一模一样，
读者没有任何办法从报告本身发现这一点。

同一份报告还漏掉了另外两个源——它们写在 manifest 的 ``sources`` 里，
却一次都没被访问过。"跑了没成功"有 partial 告警管着，"压根没跑"
在整套产物里没有任何表示形式。所以这里把它补成第一等公民：
``find_gaps`` 的产出会原样进报告，缺口为空也要写出"无"。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from litsearch.dedupe import CanonicalRecord
from litsearch.metrics import (
    capture_recapture,
    gold_set_recall,
    out_of_window_leakage,
    overlap_between,
    source_contribution,
)
from litsearch.normalize import WindowStatus

#: 捕获-再捕获要求两个索引策略近似独立的源。PubMed 与 OpenAlex 是本工具里唯一
#: 满足这一点的一对；非生物医学主题关掉 PubMed 后，这项证据**结构性不可得**，
#: 此时召回证据只剩金标准一个点——这件事必须说出来，不能留一句含糊的"未纳入"。
CAPTURE_PAIR = ("pubmed", "openalex")

#: 金标准少于这个数时，"命中率 100%" 的证据强度不足以支撑"检索是全面的"。
#: 3/3 和 9/9 印出来一模一样，读者分辨不出，所以由报告自己标注。
MIN_GOLD_SET = 5


@dataclass(frozen=True)
class Gap:
    """流水线里没被执行的一环，以及**为什么**。

    ``why`` 必须来自查出来的事实（档位、注册表、manifest 对不上），
    不能是猜的——编一个理由比不给理由更糟。
    """

    what: str
    why: str


def find_gaps(
    *,
    declared: Sequence[str],
    executed: Sequence[str],
    enabled: Sequence[str],
    available: Iterable[str],
    depth: str | None,
    ran_snowball: bool,
) -> list[Gap]:
    """本次运行声明了、但实际没做的事。

    三类，按严重程度排：声明了却没访问的源、协议启用但尚未实现的源、跳过的滚雪球。
    """
    gaps: list[Gap] = []
    done = set(executed)

    gaps += [
        Gap(
            what=f"源 {name}",
            why="写在 manifest 的 sources 里，但没有任何一条检索式的执行结局——"
            "本次一条记录都没从它那里取过",
        )
        for name in declared
        if name not in done
    ]

    ready = set(available)
    gaps += [
        Gap(
            what=f"源 {name}",
            why="协议里 enabled，但本版本尚未实现该源，已在源清单处丢弃",
        )
        for name in enabled
        if name not in ready
    ]

    if not ran_snowball:
        reason = (
            f"深度档位 {depth} 不跑引文闭包"
            if depth
            else "没有滚雪球轮次记录，且该 run 未记录深度档位"
        )
        gaps.append(
            Gap(
                what="引文滚雪球",
                why=f"{reason}。实测滚雪球的独有贡献占 92%，跳过它的召回边界说不清",
            )
        )

    return gaps


def _capture_section(corpus: list[CanonicalRecord]) -> list[str]:
    """两源重叠诊断。它不代表多源流水线的相关文献召回率。"""
    source_a, source_b = CAPTURE_PAIR
    in_a, in_b, both = overlap_between(corpus, source_a, source_b)

    header = ["## 两源重叠诊断（非流水线召回率）", ""]
    missing = [name for name, count in ((source_a, in_a), (source_b, in_b)) if count == 0]
    if missing:
        return header + [
            f"语料中没有 {'、'.join(missing)} 的记录，Chapman 估计不成立"
            f"（需 {source_a} × {source_b} 两个索引策略近似独立的源同时在场）。",
            "",
            "此时召回证据只剩金标准一个点位——这不是「证据不足以下结论」，"
            "而是**这一项根本没有测**。",
            "",
        ]

    estimate = capture_recapture(captured_a=in_a, captured_b=in_b, overlap=both)
    lines = header + [
        f"{source_a} {in_a:,} 条，{source_b} {in_b:,} 条，重叠 {both:,} 条。",
        "",
        estimate.note,
        "",
    ]
    if estimate.recall is not None:
        lines += [
            f"两源并集覆盖度估计 **{estimate.recall:.0%}**（并集观测 {estimate.observed:,}）。",
            "",
            "这只描述 PubMed∪OpenAlex 对其 Chapman 估计总体的覆盖度。它没有纳入其他源，"
            "也没有验证主题相关性，**不能写成整条检索流水线的召回率**。",
            "两源并不真正独立（OpenAlex 收录 PubMed），正相关还会使该覆盖度偏乐观。",
            "",
        ]
    return lines


def _gold_section(gold_set: Sequence, corpus: list[CanonicalRecord]) -> list[str]:
    gold = gold_set_recall(gold_set, corpus)
    recall = f"{gold.recall:.0%}" if gold.recall is not None else "无金标准"
    lines = [
        "## 金标准召回",
        "",
        f"**{gold.found_count}/{gold.total} = {recall}**",
        "",
    ]

    if gold.total == 0:
        lines += ["协议没有提名金标准——这一项**没有证据**，不是「通过了」。", ""]
    elif gold.total < MIN_GOLD_SET:
        lines += [
            f"⚠️ 金标准只有 {gold.total} 条（建议 {MIN_GOLD_SET}–10 条），**证据偏弱**："
            f"{gold.total}/{gold.total} 与 9/9 印出来一样，但前者能证伪的检索缺陷少得多。",
            "",
        ]

    if gold.missing:
        lines += ["漏检（每一条都必须回溯到具体的检索式或源缺陷并修复后重跑）：", ""]
        lines += [
            f"- `{item.doi or item.arxiv or item.pmid}` {item.note or ''}" for item in gold.missing
        ]
        lines.append("")
    if gold.found_out_of_window:
        lines += ["命中但被判为窗口外（需核对日期证据）：", ""]
        lines += [
            f"- `{item.doi or item.arxiv}` {item.note or ''}" for item in gold.found_out_of_window
        ]
        lines.append("")
    if gold.found_pending_date:
        lines += ["命中但日期尚待人工裁定（不计入严格窗口召回）：", ""]
        lines += [
            f"- `{item.doi or item.arxiv or item.pmid}` {item.note or ''}"
            for item in gold.found_pending_date
        ]
        lines.append("")
    return lines


def _gaps_section(gaps: Sequence[Gap]) -> list[str]:
    """缺口为空也要写出来——「无缺口」必须是结论，不能靠空白段落暗示。"""
    lines = ["## 本次运行未执行的部分", ""]
    if not gaps:
        return lines + ["无——协议声明的每一步都执行了。", ""]
    return lines + [
        "以下内容**没有被执行**，因此本报告的召回数字不覆盖它们：",
        "",
        "| 未执行 | 原因 |",
        "|---|---|",
        *(f"| {gap.what} | {gap.why} |" for gap in gaps),
        "",
    ]


def coverage_markdown(
    *,
    title: str,
    corpus: list[CanonicalRecord],
    gold_set: Sequence,
    controls: Sequence,
    gaps: Sequence[Gap],
    snowball_rounds: Sequence[dict],
) -> str:
    """召回率证据。每一项都是测出来的，没有一项是声称的。"""
    leak = out_of_window_leakage(controls, corpus)
    strict = [item for item in corpus if item.window_status is WindowStatus.IN_WINDOW]

    lines = [
        f"# 覆盖率证据 — {title}",
        "",
        f"宽采集语料 **{len(corpus):,}** 条规范记录；严格窗口语料 **{len(strict):,}** 条。",
        "",
        "除「窗口外对照泄漏」外，下列命中、来源贡献和两源重叠统计均只使用严格窗口语料。",
        "",
        *_gaps_section(gaps),
        *_gold_section(gold_set, corpus),
        "## 窗口外对照泄漏",
        "",
        f"对照 {leak.checked} 条，泄漏 **{len(leak.leaked)}** 条"
        f"{'（日期过滤有效）' if leak.clean else '——日期过滤存在缺陷'}",
        "",
        "## 来源独有贡献",
        "",
        "独有贡献为 0 的源说明它完全被其他源覆盖；很高则说明少了它就会漏。"
        "**没跑过的源不在此表**——见上面的「未执行的部分」。",
        "",
        "| 源 | 总贡献 | 独有 | 独有占比 |",
        "|---|---:|---:|---:|",
        *(
            f"| {row.source} | {row.total:,} | {row.unique:,} | {row.unique_share:.0%} |"
            for row in source_contribution(strict)
        ),
        "",
        *_capture_section(strict),
    ]

    if snowball_rounds:
        lines += [
            "## 引文滚雪球饱和曲线",
            "",
            "| 轮次 | 种子 | 新增（窗口内） | 占轮前 |",
            "|---|---:|---:|---:|",
            *(
                f"| {item['number']} | {item['seeds']:,} | {item['new_in_window']:,} | "
                f"{item['new_in_window'] / item['corpus_before']:.1%} |"
                for item in snowball_rounds
            ),
            "",
        ]

    lines += [
        "## 本工具不覆盖的验证",
        "",
        "这两项**本工具做不了**，需要人工执行后才能声称检索是全面的：",
        "",
        "- Google Scholar 抽查 20 条（其 ToS 不允许批量抓取，只能手工核对）",
        "- 人工复核 30 条筛选判定，与 LLM 判定的一致率",
        "",
    ]
    return "\n".join(lines)
