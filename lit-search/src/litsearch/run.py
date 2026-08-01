"""Run 目录与清单管理。

一次 run = 一个不可变的目录。协议哈希、检索式、每个源每条检索式的状态与页数
都冻结在 manifest.json 里，使"这批文献是怎么来的"永远可回答。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from litsearch import ARTIFACT_SCHEMA_VERSION, __version__
from litsearch.protocol import Topic, freeze_topic, protocol_fingerprint

MANIFEST_NAME = "manifest.json"
ARTIFACTS_NAME = "artifacts.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def jsonl_text(rows: list[Any]) -> str:
    """JSONL 序列化。抽出来是为了让 ``write_artifact`` 也能登记 jsonl 产物——
    两条写盘路径必须产出**逐字节相同**的内容，否则登记的哈希对不上文件。"""
    payload = "\n".join(json.dumps(row, ensure_ascii=False, default=str) for row in rows)
    return payload + ("\n" if rows else "")


@dataclass
class QueryOutcome:
    """单个源 × 单条检索式的采集结局。partial/failed 必须显形。"""

    source: str
    query_hash: str
    kind: str
    label: str
    query: str
    reported_total: int | None
    fetched: int
    status: str
    error: str | None = None
    truncated: bool = False


def latest_degraded(outcomes) -> set[str]:
    """按 (源, 检索式) 取最新结局，返回仍未取全的源。

    ``outcomes`` 可以是 ``QueryOutcome`` 也可以是从 manifest.json 读回的字典——
    报告层拿到的是后者。
    """

    def field(item, name):
        return item[name] if isinstance(item, dict) else getattr(item, name)

    final: dict[tuple[str, str], str] = {}
    for item in outcomes:
        final[(field(item, "source"), field(item, "query_hash"))] = field(item, "status")
    return {source for (source, _), status in final.items() if status != "complete"}


def unrun_sources(declared, outcomes) -> list[str]:
    """声明了、但一条检索式都没执行过的源。

    这是与 partial/failed **不同**的一类失败：跑了没成功有 ``degraded_sources``
    管着，压根没跑却什么都不会触发——它在产物里唯一的痕迹，就是 ``sources``
    和 ``outcomes`` 对不上，而没有人会去比对这两个字段。

    ``outcomes`` 可以是 ``QueryOutcome`` 也可以是从 manifest.json 读回的字典。
    """

    def source_of(item):
        return item["source"] if isinstance(item, dict) else item.source

    executed = {source_of(item) for item in outcomes}
    return [name for name in declared if name not in executed]


@dataclass
class RunManifest:
    run_id: str
    topic_id: str
    #: 协议文件字节的哈希——精确到文件版本，用于溯源
    topic_sha256: str
    #: 协议**语义内容**的哈希——用于判断两批采集是否属于同一次系统检索。
    #: 加注释不会改变它，改术语会。
    topic_fingerprint: str
    created_at: str
    window_start: str
    window_end: str
    harvest_start: str
    harvest_end: str
    date_priority: list[str]
    sources: list[str]
    #: 采集深度档位。决定了跑几个源、滚几轮雪球——不记下来，这次 run 的
    #: 覆盖面就无法复现，而产物本身看不出它是摸底还是全量。
    #: ``None`` 表示早于该字段的旧 run，不是"没有档位"。
    depth: str | None = None
    outcomes: list[QueryOutcome] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    #: 分阶段采集的提交记录。只有 manifest 中 status=complete 的阶段才算完成；
    #: records 文件存在但没有提交记录，表示上次运行在提交前中断，可以安全重试。
    phases: dict[str, dict[str, Any]] = field(default_factory=dict)
    schema_version: int = ARTIFACT_SCHEMA_VERSION
    tool_version: str = __version__

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, sort_keys=False)

    @property
    def unrun_sources(self) -> list[str]:
        """声明了但一次都没访问过的源。见模块级同名函数。"""
        return unrun_sources(self.sources, self.outcomes)

    @property
    def degraded_sources(self) -> list[str]:
        """仍有检索式未取全的源——其召回数字不可当作完整值使用。

        只看每条检索式的**最新**结局。同一条检索式先失败、后补跑成功是常态
        （改限速、修解析缺陷之后就会这样），把历史失败一直算进来，会让报告
        永远挂着一个已经解决的告警——而告警一旦变成噪声，真出问题时就没人看了。
        """
        return sorted(latest_degraded(self.outcomes))


class Run:
    """一次采集运行的目录布局。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.raw = root / "raw"
        self.raw.mkdir(parents=True, exist_ok=True)

    @classmethod
    def create(cls, runs_root: Path, topic_id: str, run_id: str | None = None) -> Run:
        run_id = run_id or utc_stamp()
        return cls(Path(runs_root) / topic_id / run_id)

    @classmethod
    def open(cls, path: Path) -> Run:
        if not (Path(path) / MANIFEST_NAME).exists():
            raise FileNotFoundError(f"{path} 不是一个 run 目录（缺少 {MANIFEST_NAME}）")
        return cls(Path(path))

    @property
    def run_id(self) -> str:
        return self.root.name

    def write_text(self, name: str, content: str) -> Path:
        """Atomically replace a run artifact.

        Readers must see either the previous complete artifact or the new complete artifact,
        never a half-written JSON/JSONL file after interruption.
        """
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return path

    def write_jsonl(self, name: str, rows: list[Any]) -> Path:
        return self.write_text(name, jsonl_text(rows))

    def read_jsonl(self, name: str) -> list[Any]:
        path = self.root / name
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def save_manifest(self, manifest: RunManifest) -> Path:
        return self.write_text(MANIFEST_NAME, manifest.to_json())

    def load_manifest(self) -> dict[str, Any]:
        return json.loads((self.root / MANIFEST_NAME).read_text(encoding="utf-8"))

    def save_topic_snapshot(self, topic_path: Path) -> Path:
        """Persist the exact protocol bytes used by the run, without overwriting history."""
        target = self.root / "topic.yaml"
        content = Path(topic_path).read_text(encoding="utf-8")
        if target.exists():
            if target.read_text(encoding="utf-8") != content:
                raise ValueError("run 内的 topic.yaml 快照与当前协议不同，拒绝覆盖历史协议")
            return target
        return self.write_text("topic.yaml", content)

    def write_artifact(self, name: str, content: str, *, inputs: list[str]) -> Path:
        """Write a derived artifact and commit hashes of every dependency used."""
        missing = [item for item in inputs if not (self.root / item).exists()]
        if missing:
            raise FileNotFoundError(f"派生产物 {name} 的输入不存在：{missing}")
        path = self.write_text(name, content)
        registry_path = self.root / ARTIFACTS_NAME
        registry = (
            json.loads(registry_path.read_text(encoding="utf-8"))
            if registry_path.exists()
            else {"schema_version": ARTIFACT_SCHEMA_VERSION, "artifacts": {}}
        )
        registry.setdefault("artifacts", {})[name] = {
            "sha256": file_sha256(path),
            "generated_at": datetime.now(UTC).isoformat(),
            "tool_version": __version__,
            "inputs": {item: file_sha256(self.root / item) for item in sorted(set(inputs))},
        }
        self.write_text(ARTIFACTS_NAME, json.dumps(registry, ensure_ascii=False, indent=2))
        return path


def assert_topic_compatible(run: Run, topic: Topic, topic_path: Path) -> dict[str, Any]:
    """Reject a consumer command when its protocol does not belong to the run."""
    manifest = run.load_manifest()
    # 早期中断留下的占位 manifest 可能没有协议元数据，也没有任何记录。
    # 这时没有语料会被错用，让调用方给出更具体的“空 run”错误。
    has_records = (run.root / "corpus.jsonl").exists() or any(run.root.glob("records*.jsonl"))
    if not has_records and not manifest.get("topic_id"):
        return manifest

    if manifest.get("topic_id") and manifest.get("topic_id") != topic.id:
        raise ValueError(f"协议 topic id 为 {topic.id!r}，但 run 属于 {manifest.get('topic_id')!r}")

    recorded_fingerprint = manifest.get("topic_fingerprint")
    if recorded_fingerprint:
        compatible = recorded_fingerprint == protocol_fingerprint(topic)
    else:
        compatible = manifest.get("topic_sha256") == freeze_topic(topic_path)
    if not compatible:
        raise ValueError(
            "协议已变更，与 run 不兼容：不能用另一份检索/筛选标准解释这批结果。"
            "请改用 run 对应的 topic.yaml，或新开一次 run。"
        )
    return manifest


def new_manifest(
    topic: Topic,
    topic_path: Path,
    run_id: str,
    sources: list[str],
    *,
    depth: str | None = None,
) -> RunManifest:
    window = topic.window
    return RunManifest(
        run_id=run_id,
        topic_id=topic.id,
        topic_sha256=freeze_topic(topic_path),
        topic_fingerprint=protocol_fingerprint(topic),
        created_at=datetime.now(UTC).isoformat(),
        window_start=window.start.isoformat(),
        window_end=window.end.isoformat(),
        harvest_start=window.harvest_start.isoformat(),
        harvest_end=window.harvest_end.isoformat(),
        date_priority=list(window.date_priority),
        sources=list(sources),
        depth=depth,
    )


def find_latest_run(runs_root: Path, topic_id: str) -> Path | None:
    directory = Path(runs_root) / topic_id
    if not directory.exists():
        return None
    candidates = sorted(
        (item for item in directory.iterdir() if (item / MANIFEST_NAME).exists()),
        key=lambda item: item.name,
    )
    return candidates[-1] if candidates else None


def resolve_run(runs_root: Path, reference: str) -> Path:
    """把 `--run` 参数解析成目录：可以是路径、`<topic>/<run_id>`，或 `<topic>` 取最新。"""
    direct = Path(reference)
    if (direct / MANIFEST_NAME).exists():
        return direct

    candidate = Path(runs_root) / reference
    if (candidate / MANIFEST_NAME).exists():
        return candidate

    if latest := find_latest_run(runs_root, reference):
        return latest

    raise FileNotFoundError(f"找不到 run：{reference}")
