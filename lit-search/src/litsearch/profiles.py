"""检索深度分档。

为什么需要：全量流水线实测跑了 21,712 条、3 小时、$12。**没有人会容忍第一次
试用就是这个代价**，而且他多半会中途 Ctrl-C，然后觉得这工具没用。

三档的差别只在**跑多少源、滚几轮雪球**——判定规则、去重、窗口、
召回率证据在三档里完全一致。降档降的是覆盖面，不是严谨度。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class Depth(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    SYSTEMATIC = "systematic"


#: 主干源：有布尔检索、有完整翻页、覆盖面最广
TRUNK_SOURCES = ("openalex", "pubmed", "europepmc", "arxiv")
#: 顶会与灰色文献：无布尔检索，走"锚点短语 + 本地 AND"
VENUE_SOURCES = ("cvf", "openreview", "grey")


@dataclass(frozen=True, slots=True)
class DepthProfile:
    """一档的配置与**代价预期**。

    代价必须和配置写在一起——用户选档时要看到的是时间和钱，不是源清单。
    """

    depth: Depth
    sources: tuple[str, ...]
    #: 滚雪球轮数上限；0 表示不滚。``None`` 表示用协议里的 max_rounds
    snowball_rounds: int | None
    label: str
    scale: str
    wall_clock: str
    #: API 后端（deepseek-v4-flash）的实测外推成本
    api_cost: str
    #: 宿主后端（claude -p · haiku）的 **API 等价成本**。
    #: 订阅用户不额外付费，但会消耗额度——写 "$0" 是误导。
    host_cost: str

    @property
    def runs_snowball(self) -> bool:
        return self.snowball_rounds != 0


PROFILES: dict[Depth, DepthProfile] = {
    Depth.QUICK: DepthProfile(
        depth=Depth.QUICK,
        sources=TRUNK_SOURCES,
        snowball_rounds=0,
        label="快速摸底",
        scale="数百 – 2,000 条",
        wall_clock="约 10 分钟",
        api_cost="$0.1 – $0.3",
        host_cost="约 $10 等价（订阅额度内不额外付费）",
    ),
    Depth.STANDARD: DepthProfile(
        depth=Depth.STANDARD,
        sources=TRUNK_SOURCES + VENUE_SOURCES,
        snowball_rounds=1,
        label="常规调研",
        scale="2,000 – 8,000 条",
        wall_clock="约 40 分钟",
        api_cost="$0.3 – $1.2",
        host_cost="约 $40 等价——**建议改用 API 后端**",
    ),
    Depth.SYSTEMATIC: DepthProfile(
        depth=Depth.SYSTEMATIC,
        sources=TRUNK_SOURCES + VENUE_SOURCES,
        snowball_rounds=None,  # 滚到饱和
        label="系统综述级",
        scale="10,000 条以上",
        wall_clock="2 – 4 小时",
        api_cost="$3.4（flash）– $10.4（pro）",
        host_cost="不适用——请用 API 后端",
    ),
}

DEFAULT_DEPTH = Depth.STANDARD


def profile_for(depth: Depth | str) -> DepthProfile:
    try:
        return PROFILES[Depth(depth)]
    except ValueError as error:
        raise ValueError(
            f"不认识的深度 {depth!r}，可选：{', '.join(item.value for item in Depth)}"
        ) from error


def sources_for(depth: Depth | str, *, enabled: Sequence[str]) -> list[str]:
    """本档要跑的源，与协议里启用的取交集。

    档位**只做减法**：协议里没启用的源，任何档位都不会把它打开——
    否则用户会拿到一份自己没声明过的检索策略。
    """
    allowed = set(profile_for(depth).sources)
    return [name for name in enabled if name in allowed]


def summary_table() -> str:
    """三档对照，供 CLI 在开跑前打印。

    两个后端的成本分开列——宿主后端不需要任何 key，但它**不是免费的**：
    实测 60 条记录两次 ``claude -p`` 调用是 $0.295 的 API 等价成本
    （haiku；用 opus 是 $1.44）。订阅用户不额外付费，但会消耗额度。
    """
    lines = [
        f"{'档位':<22}{'规模':<20}{'耗时':<12}{'API 后端':<26}{'滚雪球'}",
        "-" * 92,
    ]
    for depth in Depth:
        item = PROFILES[depth]
        rounds = "至饱和" if item.snowball_rounds is None else f"{item.snowball_rounds} 轮"
        lines.append(
            f"{item.depth.value + '｜' + item.label:<22}{item.scale:<20}"
            f"{item.wall_clock:<12}{item.api_cost:<26}{rounds}"
        )
    lines += ["", "宿主后端（--model host，零配置、不需要 key）的 API 等价成本："]
    for depth in Depth:
        item = PROFILES[depth]
        lines.append(f"  {item.depth.value:<14}{item.host_cost}")
    return "\n".join(lines)
