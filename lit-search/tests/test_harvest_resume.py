"""续跑：一个源被限流，不该让整批已成功的采集结果作废。"""

from __future__ import annotations

import httpx
import pytest
import respx

from litsearch.harvest import harvest
from litsearch.protocol import Topic, load_topic
from litsearch.run import Run
from litsearch.sources.registry import Credentials
from tests.test_sources import fixture


@pytest.fixture
def topic_path(tmp_path):
    path = tmp_path / "topic.yaml"
    path.write_text(
        """
id: demo
title: Demo
window:
  start: 2021-07-01
  end: 2026-07-27
  harvest_margin_days: 0
concepts:
  condition:
    required: true
    terms: [stroke]
  task:
    required: true
    terms: [segmentation]
query_plan:
  combinations: [[condition, task]]
criteria:
  include:
    - id: I1
      text: x
known_items: [ISLES 2022]
sources:
  openalex:
    enabled: true
  europepmc:
    enabled: true
""".strip(),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def topic(topic_path) -> Topic:
    return load_topic(topic_path)


def _openalex_ok():
    return httpx.Response(200, text=fixture("openalex_page1.json"))


def _empty_openalex():
    return httpx.Response(200, json={"results": [], "meta": {"next_cursor": None}})


def _europepmc_ok():
    return httpx.Response(200, text=fixture("europepmc_page1.json"))


def _empty_europepmc():
    return httpx.Response(200, json={"resultList": {"result": []}, "nextCursorMark": None})


@respx.mock
async def _first_run(topic, topic_path, tmp_path) -> Run:
    """OpenAlex 两条检索式都成功，Europe PMC 全部失败。"""
    respx.get("https://api.openalex.org/works").mock(
        side_effect=[_openalex_ok(), _empty_openalex(), _openalex_ok(), _empty_openalex()]
    )
    respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
        return_value=httpx.Response(400, text="bad request")
    )

    run = Run.create(tmp_path / "runs", topic.id, run_id="first")
    await harvest(topic, topic_path, run, Credentials(contact_email="t@example.com"))
    return run


class TestResume:
    async def test_first_run_records_the_failures(self, topic, topic_path, tmp_path):
        run = await _first_run(topic, topic_path, tmp_path)
        manifest = run.load_manifest()

        statuses = {item["source"]: item["status"] for item in manifest["outcomes"]}
        assert statuses["openalex"] == "complete"
        assert statuses["europepmc"] == "failed"
        assert run.read_jsonl("records.jsonl")

    @respx.mock
    async def test_resume_reruns_only_failures_and_carries_the_rest(
        self, topic, topic_path, tmp_path
    ):
        first = await _first_run(topic, topic_path, tmp_path)
        carried = len(first.read_jsonl("records.jsonl"))
        assert carried > 0

        # 续跑时只有 Europe PMC 会被请求；OpenAlex 一次都不该被打
        openalex = respx.get("https://api.openalex.org/works").mock(return_value=_empty_openalex())
        respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            side_effect=[
                _europepmc_ok(),
                _empty_europepmc(),
                _europepmc_ok(),
                _empty_europepmc(),
            ]
        )

        second = Run.create(tmp_path / "runs", topic.id, run_id="second")
        report = await harvest(
            topic,
            topic_path,
            second,
            Credentials(contact_email="t@example.com"),
            resume_from=first,
        )

        assert openalex.call_count == 0, "已完成的检索式不该重跑"
        assert report.raw_count > carried, "续跑结果应当在沿用记录之上有增量"
        assert any("续跑自 first" in note for note in report.manifest.notes)

        statuses = {item.status for item in report.manifest.outcomes}
        assert statuses == {"complete"}

    @respx.mock
    async def test_resume_cannot_widen_the_source_list(self, topic, topic_path, tmp_path):
        """实测事故：一次 `--depth quick` 的采集被续跑后，manifest 凭空多出两个源。

        续跑**按定义**只重跑上一轮未完成的检索式，它没有能力覆盖一个从没跑过的源。
        此时把当前算出的源清单写进 manifest，等于声称采集了从未访问过的地方——
        而这份 manifest 正是"这批文献是怎么来的"的唯一答案。
        """
        respx.get("https://api.openalex.org/works").mock(
            side_effect=[_openalex_ok(), _empty_openalex(), _openalex_ok(), _empty_openalex()]
        )
        first = Run.create(tmp_path / "runs", topic.id, run_id="narrow")
        await harvest(
            topic,
            topic_path,
            first,
            Credentials(contact_email="t@example.com"),
            only=["openalex"],
        )
        assert first.load_manifest()["sources"] == ["openalex"]

        # 续跑时不再限制 --sources：europepmc 绝不能凭空出现在清单里
        respx.get("https://api.openalex.org/works").mock(return_value=_empty_openalex())
        second = Run.create(tmp_path / "runs", topic.id, run_id="widened")
        report = await harvest(
            topic,
            topic_path,
            second,
            Credentials(contact_email="t@example.com"),
            resume_from=first,
        )

        assert "europepmc" not in report.manifest.sources
        assert any("europepmc" in note for note in report.manifest.notes), (
            "被挡下来这件事本身要说出来，否则用户以为自己扩了源"
        )

    @respx.mock
    async def test_resume_refuses_when_the_protocol_changed(self, topic, topic_path, tmp_path):
        first = await _first_run(topic, topic_path, tmp_path)
        topic_path.write_text(
            topic_path.read_text(encoding="utf-8").replace("title: Demo", "title: Changed"),
            encoding="utf-8",
        )
        changed = load_topic(topic_path)

        # 协议变了就不能续跑——否则一批结果会对应两个不同的协议版本，无法追溯
        with pytest.raises(ValueError, match="协议已变更"):
            await harvest(
                changed,
                topic_path,
                Run.create(tmp_path / "runs", topic.id, run_id="third"),
                Credentials(),
                resume_from=first,
            )
