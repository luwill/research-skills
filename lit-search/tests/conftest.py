"""阶段 3 各源共用的夹具。"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from litsearch.protocol import Topic
from litsearch.sources.base import HttpClient, PageStore, RateLimiter, SourceContext

FIXTURES = Path(__file__).parent / "fixtures"

#: 样例协议在开发仓库里放 topics/，打包成 skill 后放 examples/。
#: 两个布局都要能跑——这些测试验的是"真实协议仍然合法且检索式可复现"，
#: 换个目录名就让它们静默跳过，等于把一层回归护栏关掉了。
SAMPLE_TOPIC_DIRS = ("topics", "examples")


def sample_topic(name: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    for folder in SAMPLE_TOPIC_DIRS:
        candidate = root / folder / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"样例协议 {name} 不在 {' / '.join(SAMPLE_TOPIC_DIRS)} 任一目录下"
    )


@pytest.fixture(autouse=True)
def disable_real_source_rate_waits(monkeypatch):
    """Recorded-response tests exercise ordering, not providers' wall-clock courtesy waits."""

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(
        "litsearch.sources.registry.rate_limit_for", lambda _name, _credentials: 0.0
    )
    monkeypatch.setattr("litsearch.sources.base._sleep", no_wait)


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def make_topic(**overrides) -> Topic:
    payload = {
        "id": "t",
        "title": "T",
        "window": {"start": "2021-07-01", "end": "2026-07-27", "harvest_margin_days": 365},
        "concepts": {
            "condition": {
                "required": True,
                "terms": ["ischemic stroke", "stroke lesion"],
                "wildcards": ["infarct*"],
            },
            "task": {"required": True, "terms": ["segmentation"]},
        },
        "known_items": ["ISLES challenge"],
        "query_plan": {"combinations": [["condition", "task"]]},
        "criteria": {"include": [{"id": "I1", "text": "x"}]},
        "sources": {
            "cvf": {"enabled": True, "venues": ["CVPR", "ICCV", "WACV"]},
            "openreview": {"enabled": True, "venues": ["ICLR", "NeurIPS"]},
            "grey": {"enabled": True},
            "crossref": {"enabled": True, "role": "enrich"},
        },
    }
    payload.update(overrides)
    return Topic.model_validate(payload)


@pytest.fixture
def stage3_topic() -> Topic:
    return make_topic()


@pytest.fixture
def stage3_context(stage3_topic, tmp_path) -> SourceContext:
    client = HttpClient(
        httpx.AsyncClient(timeout=5.0),
        rate_limiter=RateLimiter(min_interval=0.0),
        max_attempts=2,
        backoff_base=0.0,  # 测试里不真等指数退避
    )
    return SourceContext(
        client=client,
        store=PageStore(tmp_path / "raw"),
        topic=stage3_topic,
        contact_email="probe@example.com",
    )
