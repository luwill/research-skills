"""Import explicit human decisions without erasing model or date evidence."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from litsearch.dedupe import CanonicalRecord
from litsearch.normalize import WindowStatus
from litsearch.screen import Decision, MergedDecision


class AdjudicationError(ValueError):
    """The adjudication file is incomplete, ambiguous, or targets unknown records."""


def load_rows(path: Path) -> list[dict[str, str]]:
    """Read a shared CSV contract: record_key, decision, reviewer, reason."""
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"record_key", "decision", "reviewer", "reason"}
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise AdjudicationError(f"裁定 CSV 缺少列：{', '.join(sorted(missing))}")
            rows = [
                {key: (value or "").strip() for key, value in row.items()}
                for row in reader
                if any((value or "").strip() for value in row.values())
            ]
    except OSError as error:
        raise AdjudicationError(f"无法读取裁定 CSV {path}：{error}") from error

    if not rows:
        raise AdjudicationError("裁定 CSV 没有数据行")
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        key = row["record_key"]
        if not key or not row["reviewer"] or not row["reason"]:
            raise AdjudicationError(
                f"裁定 CSV 第 {index} 行必须填写 record_key、reviewer 和 reason"
            )
        if key in seen:
            raise AdjudicationError(f"裁定 CSV 重复 record_key：{key}")
        seen.add(key)
    return rows


def apply_screening(
    decisions: dict[str, MergedDecision], rows: list[dict[str, str]]
) -> tuple[dict[str, MergedDecision], list[dict[str, str]]]:
    """Apply include/exclude decisions while retaining the original channel verdicts."""
    updated = dict(decisions)
    audit: list[dict[str, str]] = []
    timestamp = datetime.now(UTC).isoformat()
    for row in rows:
        key = row["record_key"]
        if key not in decisions:
            raise AdjudicationError(f"筛选轮次中不存在 record_key：{key}")
        try:
            decision = Decision(row["decision"])
        except ValueError as error:
            raise AdjudicationError(
                f"筛选裁定 {key} 的 decision 必须是 include 或 exclude"
            ) from error
        if decision is Decision.UNCLEAR:
            raise AdjudicationError(f"筛选裁定 {key} 不能仍为 unclear")
        previous = decisions[key]
        updated[key] = previous.model_copy(
            update={
                "decision": decision,
                "needs_human": False,
                "reason": f"人工裁定：{row['reason']}",
                "adjudicated_by": row["reviewer"],
                "adjudicated_at": timestamp,
                "adjudication_reason": row["reason"],
                "previous_decision": previous.decision,
            }
        )
        audit.append(
            {
                **row,
                "kind": "screening",
                "previous_decision": previous.decision.value,
                "adjudicated_at": timestamp,
            }
        )
    return updated, audit


def apply_dates(
    records: list[CanonicalRecord], rows: list[dict[str, str]]
) -> tuple[list[CanonicalRecord], list[dict[str, str]]]:
    """Resolve boundary/undated records to an explicit strict-window status."""
    by_key = {item.key: item for item in records}
    replacements: dict[str, CanonicalRecord] = {}
    audit: list[dict[str, str]] = []
    timestamp = datetime.now(UTC).isoformat()
    allowed = {WindowStatus.IN_WINDOW, WindowStatus.OUT_OF_WINDOW}
    # 裁定只解决**不确定**，不覆盖已有证据。放开的话，一条已筛选的 in_window 记录
    # 可以被改成 out_of_window，此时严格窗口条数减 1 而筛选轮次条数不变，
    # `lit verify` 会报 screening-corpus-mismatch 并建议「需重新筛选」——
    # 而重新筛选消除不了这个偏差。日期真判错了，该修的是日期证据与 date_priority。
    adjudicable = {WindowStatus.BOUNDARY, WindowStatus.UNDATED}
    for row in rows:
        key = row["record_key"]
        record = by_key.get(key)
        if record is None:
            raise AdjudicationError(f"语料中不存在 record_key：{key}")
        if record.window_status not in adjudicable:
            raise AdjudicationError(
                f"{key} 已有明确日期判定"
                f"（{record.window_status.value if record.window_status else 'unknown'}）；"
                f"日期裁定只受理 boundary / undated 的记录。"
                f"若判定本身有误，请修正日期证据或 date_priority 后重跑 lit reclassify"
            )
        try:
            status = WindowStatus(row["decision"])
        except ValueError as error:
            raise AdjudicationError(
                f"日期裁定 {key} 的 decision 必须是 in_window 或 out_of_window"
            ) from error
        if status not in allowed:
            raise AdjudicationError(f"日期裁定 {key} 的 decision 必须是 in_window 或 out_of_window")
        previous = record.window_status
        evidence = {
            "reviewer": row["reviewer"],
            "reason": row["reason"],
            "adjudicated_at": timestamp,
            "previous_status": previous.value if previous else "unknown",
            "decision": status.value,
        }
        replacements[key] = record.model_copy(
            update={"window_status": status, "date_adjudication": evidence}
        )
        audit.append({**row, "kind": "date", **evidence})
    return [replacements.get(item.key, item) for item in records], audit
