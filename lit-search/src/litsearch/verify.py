"""Integrity and staleness checks for a run directory."""

from __future__ import annotations

import json
from dataclasses import dataclass

from litsearch.normalize import WindowStatus
from litsearch.run import ARTIFACTS_NAME, Run, file_sha256

KNOWN_DERIVED = frozenset(
    {
        "PRISMA.md",
        "evidence_table.md",
        "included.csv",
        "coverage_report.md",
        "zotero_dois.txt",
        "tier_report.md",
        "ranked.csv",
        "ranked.jsonl",
        "dois.md",
        "references.md",
        "references.bib",
    }
)


@dataclass(frozen=True)
class VerificationIssue:
    severity: str  # error | warning
    code: str
    message: str


def _issue(severity: str, code: str, message: str) -> VerificationIssue:
    return VerificationIssue(severity=severity, code=code, message=message)


def verify_run(run: Run) -> list[VerificationIssue]:
    """Return all detectable integrity failures; never repair or delete artifacts."""
    issues: list[VerificationIssue] = []
    try:
        manifest = run.load_manifest()
    except (OSError, json.JSONDecodeError) as error:
        return [_issue("error", "manifest-invalid", f"manifest.json 无法解析：{error}")]

    try:
        corpus = run.read_jsonl("corpus.jsonl")
    except (OSError, json.JSONDecodeError) as error:
        return [_issue("error", "corpus-invalid", f"corpus.jsonl 无法解析：{error}")]

    counts = manifest.get("counts") or {}
    if "canonical_records" in counts and counts["canonical_records"] != len(corpus):
        issues.append(
            _issue(
                "error",
                "corpus-count",
                f"manifest 记录 {counts['canonical_records']} 条规范记录，"
                f"corpus.jsonl 实有 {len(corpus)} 条",
            )
        )
    for status in WindowStatus:
        if status.value not in counts:
            continue
        actual = sum(1 for item in corpus if item.get("window_status") == status.value)
        if counts[status.value] != actual:
            issues.append(
                _issue(
                    "error",
                    "window-count",
                    f"manifest 的 {status.value}={counts[status.value]}，语料实有 {actual}",
                )
            )

    snapshot = run.root / "topic.yaml"
    if snapshot.exists():
        recorded = manifest.get("topic_sha256")
        if recorded and file_sha256(snapshot) != recorded:
            issues.append(
                _issue(
                    "error",
                    "topic-snapshot",
                    "run/topic.yaml 与 manifest 记录的协议字节哈希不一致",
                )
            )
    else:
        issues.append(
            _issue(
                "warning",
                "topic-snapshot-missing",
                "该 run 没有协议快照（旧格式）；仅凭哈希无法恢复原协议文本",
            )
        )

    phases = manifest.get("phases") or {}
    if int(manifest.get("schema_version", 1)) >= 2:
        for path in sorted(run.root.glob("records*.jsonl")):
            phase = (
                "initial" if path.name == "records.jsonl" else path.stem.removeprefix("records_")
            )
            if phases.get(phase, {}).get("status") != "complete":
                issues.append(
                    _issue(
                        "error",
                        "phase-uncommitted",
                        f"{path.name} 已存在，但阶段 {phase!r} 没有 complete 提交记录",
                    )
                )

    rounds = sorted(
        run.root.glob("screening_round_*.json"),
        key=lambda item: int(item.stem.rsplit("_", 1)[-1]),
    )
    if rounds:
        try:
            latest = json.loads(rounds[-1].read_text(encoding="utf-8"))
            decisions = latest.get("decisions") or {}
            expected = latest.get("expected_records")
            if expected is not None and expected != len(decisions):
                issues.append(
                    _issue(
                        "error",
                        "screening-incomplete",
                        f"最新筛选轮次期望 {expected} 条，实际只有 {len(decisions)} 条",
                    )
                )
            strict = sum(
                1 for item in corpus if item.get("window_status") == WindowStatus.IN_WINDOW.value
            )
            if len(decisions) != strict:
                issues.append(
                    _issue(
                        "error",
                        "screening-corpus-mismatch",
                        f"严格窗口有 {strict} 条，最新筛选轮次有 {len(decisions)} 条；需重新筛选",
                    )
                )
        except (OSError, json.JSONDecodeError) as error:
            issues.append(_issue("error", "screening-invalid", f"最新筛选轮次无法解析：{error}"))

    registry_path = run.root / ARTIFACTS_NAME
    tracked: set[str] = set()
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            for name, metadata in (registry.get("artifacts") or {}).items():
                tracked.add(name)
                target = run.root / name
                if not target.exists():
                    # 交付物动辄几 MB，为腾空间删掉它是**正当操作**，不是完整性损坏。
                    # 报成 error 会让真正的损坏（内容被改、输入变了）淹没在同级噪声里。
                    issues.append(
                        _issue(
                            "warning",
                            "artifact-deleted",
                            f"登记的派生产物 {name} 已不在——若是主动清理可忽略，"
                            f"需要时用对应命令重建",
                        )
                    )
                    continue
                if file_sha256(target) != metadata.get("sha256"):
                    issues.append(
                        _issue("error", "artifact-modified", f"{name} 生成后被修改，内容哈希不符")
                    )
                for dependency, expected_hash in (metadata.get("inputs") or {}).items():
                    source = run.root / dependency
                    if not source.exists():
                        issues.append(
                            _issue(
                                "error",
                                "artifact-input-missing",
                                f"{name} 的输入 {dependency} 已不存在",
                            )
                        )
                    elif file_sha256(source) != expected_hash:
                        issues.append(
                            _issue(
                                "error",
                                "artifact-stale",
                                f"{name} 已过期：输入 {dependency} 在生成后发生变化",
                            )
                        )
        except (OSError, json.JSONDecodeError) as error:
            issues.append(_issue("error", "artifacts-invalid", f"artifacts.json 无法解析：{error}"))

    for name in sorted(KNOWN_DERIVED - tracked):
        if (run.root / name).exists():
            issues.append(
                _issue(
                    "warning",
                    "artifact-untracked",
                    f"{name} 是旧格式产物，没有依赖哈希，无法证明它仍与当前语料一致",
                )
            )
    return issues
