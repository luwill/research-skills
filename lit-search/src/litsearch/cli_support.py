"""CLI 各命令共用的加载与开仓助手。

抽出来是因为判定相关的命令（``screen-eval``、``triage``）住在 ``cli_judge.py``，
而它们需要和 ``cli.py`` 完全一致的错误退出行为——协议读不了退 2、run 找不到退 2、
协议与 run 不匹配退 2。复制一份迟早会漂移，而漂移出来的是"同一个错误在不同命令里
表现不一样"，排查成本很高。
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import typer

from litsearch.dedupe import CanonicalRecord
from litsearch.protocol import ProtocolError, Topic, load_topic
from litsearch.run import Run, assert_topic_compatible, resolve_run
from litsearch.screen import MergedDecision, carry_adjudications, summarize
from litsearch.screen_commit import BackendResult, commit_round, find_regression

DEFAULT_RUNS_ROOT = Path("runs")


def load_topic_or_exit(topic_path: Path) -> Topic:
    try:
        return load_topic(topic_path)
    except ProtocolError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error


def open_run_or_exit(runs_root: Path, reference: str) -> Run:
    try:
        return Run.open(resolve_run(runs_root, reference))
    except FileNotFoundError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error


def open_compatible_run_or_exit(
    runs_root: Path, reference: str, topic: Topic, topic_path: Path
) -> Run:
    """Open a run and reject commands that supply an unrelated protocol."""
    run = open_run_or_exit(runs_root, reference)
    try:
        assert_topic_compatible(run, topic, topic_path)
    except ValueError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error
    return run


def load_latest_decisions(run_dir: Run) -> dict[str, MergedDecision] | None:
    """读回**最近一轮**筛选判定；没有就返回 None。

    判定按轮次不可变追加（`screening_round_N.json`），改判开新一轮。
    这里取轮次号最大的那一轮——它才是当前结论。
    """
    rounds = sorted(
        run_dir.root.glob("screening_round_*.json"),
        key=lambda item: int(item.stem.rsplit("_", 1)[-1]),
    )
    if not rounds:
        return None
    payload = json.loads(rounds[-1].read_text(encoding="utf-8"))
    return {
        key: MergedDecision.model_validate(value)
        for key, value in (payload.get("decisions") or {}).items()
    }


def load_round(run_dir: Run, number: int) -> dict[str, MergedDecision]:
    """读回**指定**轮次。评估要对比任意两轮，不能只拿得到最后一轮。"""
    path = run_dir.root / f"screening_round_{number}.json"
    if not path.exists():
        available = sorted(
            int(item.stem.rsplit("_", 1)[-1])
            for item in run_dir.root.glob("screening_round_*.json")
        )
        typer.secho(
            f"{path.name} 不存在。该 run 现有轮次：{available or '（无）'}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        key: MergedDecision.model_validate(value)
        for key, value in (payload.get("decisions") or {}).items()
    }


def carry_or_exit(
    decisions: dict[str, MergedDecision],
    previous: Mapping[str, MergedDecision] | None,
) -> dict[str, MergedDecision]:
    """把人工裁决盖回新一轮。裁决过的记录若这轮不见了，报干净的错而不是栈回溯。"""
    if not previous:
        return decisions
    try:
        return carry_adjudications(decisions, previous)
    except KeyError as error:
        typer.secho(str(error.args[0]), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error


def _echo_counts(decisions: Mapping[str, MergedDecision]) -> dict[str, int]:
    counts = summarize(decisions)
    typer.echo(f"\n{'判定':<16}{'数量':>10}")
    typer.echo("-" * 26)
    for label, key in (("纳入", "include"), ("排除", "exclude"), ("待人工裁定", "human_queue")):
        typer.echo(f"{label:<16}{counts[key]:>10,}")

    missing = sum(1 for item in decisions.values() if item.needs_human and "缺少" in item.reason)
    if missing:
        typer.secho(
            f"其中 {missing:,} 条**没拿到判定**（请求失败或模型漏答），"
            f"占 {missing / len(decisions):.1%}",
            fg=typer.colors.YELLOW,
        )
    return counts


def finish_screening_round(
    *,
    run_dir: Run,
    topic_path: Path,
    topic: Topic,
    result: BackendResult,
    records: Mapping[str, CanonicalRecord],
    previous: Mapping[str, MergedDecision] | None,
    trial: bool,
    allow_regression: bool,
) -> Path:
    """三个后端共用的收尾：盖回裁决 → 退步守卫 → 报数 → 落盘。

    安全逻辑只此一份。复制第二份的代价是：某一天只有一条路径被修好，而两条路径
    写出的轮次看起来一模一样。
    """
    carried = carry_or_exit(dict(result.decisions), previous)
    result = replace(result, decisions=carried)

    # 试跑写的是 screening_trial.json，不占轮次号也遮蔽不了任何东西，无需守卫。
    regression = None if trial else find_regression(carried, previous)
    if regression and not allow_regression:
        typer.secho(f"\n{regression.message()}", fg=typer.colors.RED, err=True)
        if result.failures:
            typer.secho(f"失败样例：{result.failures[0]}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    if regression:
        typer.secho(
            f"\n--allow-regression：明知丢失 {regression.lost:,} 条已有结论仍然写入。",
            fg=typer.colors.YELLOW,
        )

    counts = _echo_counts(carried)
    written = commit_round(run_dir, topic_path, result, records, topic=topic, trial=trial)
    if trial:
        typer.secho(
            f"\n试跑结果 → {written}（不计入轮次，下游读不到它）", fg=typer.colors.YELLOW
        )
        return written

    typer.echo(f"\n判定 → {written}")
    typer.secho(
        f"待人工裁定 {counts['human_queue']:,} 条 → {run_dir.root / 'human_queue.csv'}",
        fg=typer.colors.YELLOW,
    )
    return written


def latest_round_judge(run_dir: Run) -> str | None:
    """最近一轮是哪种判定器打的。``None`` 表示双通道 LLM（API 或宿主）。

    用来拦跨后端续跑：LLM 对 Jev 轮次续跑时，会看到"每条记录的通道 1 都缺判定"
    （Jev 轮次只有通道 0），于是静默重判全部记录，并把 Jev 的通道 0 与 LLM 的
    通道 1 合并成一条"双通道"判定——两个通道来自完全不同的判定器，
    而它看起来和真的双通道判定一模一样。
    """
    rounds = sorted(
        run_dir.root.glob("screening_round_*.json"),
        key=lambda item: int(item.stem.rsplit("_", 1)[-1]),
    )
    for path in reversed(rounds):
        payload = json.loads(path.read_text(encoding="utf-8"))
        parameters = payload.get("parameters") or {}
        # 裁定类轮次（人工裁定、日期裁定、机器分诊）是加在模型轮次之上的一层，
        # 它们只改动个别记录的结论，不重判整批，因此不改变"这批是谁判的"。
        # 它们一律带 kind 标记；真正跑模型的轮次不带。
        if parameters.get("kind") or payload.get("provider") == "human":
            continue
        return parameters.get("judge")
    return None


def refuse_cross_backend_resume(run_dir: Run, *, judge: str | None) -> None:
    previous_judge = latest_round_judge(run_dir)
    if previous_judge == judge:
        return
    names = {None: "双通道 LLM", "jev": "判定 API（jev）"}
    typer.secho(
        f"上一轮是{names.get(previous_judge, previous_judge)}判的，这次要用"
        f"{names.get(judge, judge)}——**不能跨后端续跑**。\n"
        f"两者的判定单元不同（双通道 vs 单打分），混起来会产出一条看起来像"
        f"双通道、实际来自两个不同判定器的判定。要换后端请跑完整的一轮，不加 --resume。",
        fg=typer.colors.RED,
        err=True,
    )
    raise typer.Exit(code=2)
