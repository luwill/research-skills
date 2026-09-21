"""命令行层：参数校验、错误路径、产物落盘。

这一层的价值不在算法，而在**出错时说人话且退出码正确**——
协议写错、run 找不到、参数不成对，都必须当场拦下并指明怎么改，
而不是抛一个栈回溯或者静默跑出一份不完整的结果。

不打网络：需要采集的命令用录制的 fixture 打桩。
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from typer.testing import CliRunner

from litsearch.cli import app
from litsearch.facets import DEFAULT_FACETS
from litsearch.jev_client import JevResponse
from litsearch.protocol import protocol_fingerprint
from litsearch.run import Run
from litsearch.screen import Decision, MergedDecision, ScreeningRound

from .conftest import fixture_text

runner = CliRunner()

TOPIC_YAML = """
id: t
title: 测试课题
window: {start: 2021-07-01, end: 2026-07-27, harvest_margin_days: 365}
concepts:
  condition:
    required: true
    terms: [ischemic stroke, stroke lesion]
    wildcards: [infarct*]
  task:
    required: true
    terms: [segmentation]
known_items: [ISLES challenge]
query_plan: {combinations: [[condition, task]]}
criteria:
  include: [{id: I1, text: 人类缺血性卒中影像}]
  exclude: [{id: X1, text: 仅出血性卒中}]
gold_set:
  - doi: 10.1038/s41597-022-01875-5
sources:
  openalex: {enabled: true}
  grey: {enabled: true}
"""


@pytest.fixture
def topic_path(tmp_path):
    path = tmp_path / "topic.yaml"
    path.write_text(TOPIC_YAML, encoding="utf-8")
    return path


@pytest.fixture
def runs_root(tmp_path):
    return tmp_path / "runs"


@pytest.fixture
def seeded_run(tmp_path, topic_path, runs_root, respx_mock):
    """一次已完成的 openalex 采集，供后续命令使用。

    按 cursor 应答而不是排一串固定响应：这个课题有 2 条检索式，
    固定序列会在第二条上耗尽；按 cursor 应答才是真实翻页的样子。
    """
    empty = json.dumps({"meta": {"count": 369, "next_cursor": None}, "results": []})

    def responder(request: httpx.Request) -> httpx.Response:
        first = request.url.params.get("cursor") == "*"
        body = fixture_text("openalex_page1.json") if first else empty
        return httpx.Response(200, text=body)

    respx_mock.get("https://api.openalex.org/works").mock(side_effect=responder)
    result = runner.invoke(
        app,
        [
            "harvest",
            "--topic",
            str(topic_path),
            "--runs-root",
            str(runs_root),
            "--sources",
            "openalex",
        ],
    )
    assert result.exit_code == 0, result.output
    return Run.open(next((runs_root / "t").iterdir()))


class TestStrategies:
    def test_prints_every_query_without_touching_the_network(self, topic_path):
        result = runner.invoke(app, ["strategies", "--topic", str(topic_path)])

        assert result.exit_code == 0
        assert "condition+task" in result.output

    def test_an_invalid_protocol_exits_with_a_readable_message(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("id: x\ntitle: y\n", encoding="utf-8")

        result = runner.invoke(app, ["strategies", "--topic", str(bad)])

        assert result.exit_code == 2
        assert "校验失败" in result.output

    def test_an_unknown_key_is_rejected_rather_than_ignored(self, tmp_path):
        """配置驱动的工具里，拼错的键被静默忽略等于让整套设置无声失效。"""
        bad = tmp_path / "bad.yaml"
        bad.write_text(TOPIC_YAML.replace("known_items:", "known_item:"), encoding="utf-8")

        result = runner.invoke(app, ["strategies", "--topic", str(bad)])

        assert result.exit_code == 2
        assert "known_item" in result.output


class TestHarvestArguments:
    def test_into_without_phase_is_refused(self, topic_path, runs_root):
        result = runner.invoke(
            app,
            ["harvest", "--topic", str(topic_path), "--runs-root", str(runs_root), "--into", "t"],
        )

        assert result.exit_code == 2
        assert "--phase" in result.output

    def test_phase_without_into_is_refused(self, topic_path, runs_root):
        result = runner.invoke(
            app,
            [
                "harvest",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--phase",
                "stage3",
            ],
        )

        assert result.exit_code == 2

    def test_a_missing_run_exits_cleanly(self, topic_path, runs_root):
        result = runner.invoke(
            app,
            [
                "harvest",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--into",
                "nope",
                "--phase",
                "stage3",
            ],
        )

        assert result.exit_code == 2
        assert "找不到 run" in result.output


class TestHarvestInto:
    def test_merges_a_new_phase_and_rebuilds_the_corpus(
        self, seeded_run, topic_path, runs_root, respx_mock
    ):
        from litsearch.sources.grey import ENDPOINT as ZENODO

        before = len(seeded_run.read_jsonl("corpus.jsonl"))
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )

        result = runner.invoke(
            app,
            [
                "harvest",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--into",
                "t",
                "--phase",
                "stage3",
                "--sources",
                "grey",
            ],
        )

        assert result.exit_code == 0, result.output
        assert (seeded_run.root / "records_stage3.jsonl").exists()
        assert len(seeded_run.read_jsonl("corpus.jsonl")) > before

    def test_a_semantically_changed_protocol_is_refused(self, seeded_run, topic_path, runs_root):
        topic_path.write_text(
            TOPIC_YAML.replace("[segmentation]", "[segmentation, volumetry]"),
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "harvest",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--into",
                "t",
                "--phase",
                "stage3",
                "--sources",
                "grey",
            ],
        )

        assert result.exit_code == 2
        assert "协议已变更" in result.output

    def test_the_run_records_a_semantic_fingerprint(self, seeded_run, topic_path):
        from litsearch.protocol import load_topic

        manifest = seeded_run.load_manifest()

        assert manifest["topic_fingerprint"] == protocol_fingerprint(load_topic(topic_path))


class TestReclassify:
    def test_rebuilds_the_corpus_without_refetching(
        self, seeded_run, topic_path, runs_root, respx_mock
    ):
        before = len(respx_mock.calls)  # seeded_run 夹具自己发过请求，只看新增

        result = runner.invoke(
            app,
            ["reclassify", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)],
        )

        assert result.exit_code == 0, result.output
        assert "窗口内" in result.output
        assert len(respx_mock.calls) == before  # 重判不该发一次网络请求

    def test_a_run_without_records_is_reported_not_crashed(self, tmp_path, topic_path, runs_root):
        empty = Run.create(runs_root, "t", "20200101T000000Z")
        empty.write_text("manifest.json", json.dumps({"topic_sha256": "x", "counts": {}}))

        result = runner.invoke(
            app,
            ["reclassify", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)],
        )

        assert result.exit_code == 2
        assert "records.jsonl" in result.output


class TestProceedings:
    def test_dry_run_lists_volumes_without_requesting(
        self, seeded_run, topic_path, runs_root, respx_mock
    ):
        seeded_run.write_jsonl(
            "records_seed.jsonl",
            [
                {
                    "source": "s",
                    "source_id": "1",
                    "title": "MICCAI paper",
                    "identifiers": {"doi": "10.1007/978-3-031-16443-9_1"},
                }
            ],
        )

        before = len(respx_mock.calls)

        result = runner.invoke(
            app,
            [
                "proceedings",
                "t",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "9783031164439" in result.output
        assert len(respx_mock.calls) == before  # --dry-run 只列卷，不请求

    def test_a_corpus_without_lncs_papers_says_so(
        self, seeded_run, topic_path, runs_root, respx_mock
    ):
        result = runner.invoke(
            app,
            [
                "proceedings",
                "t",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "无卷可补" in result.output


class TestSnowball:
    def test_included_mode_refuses_without_screening(self, seeded_run, topic_path, runs_root):
        """没筛选就滚雪球会把噪声放大一个数量级——必须先拦下来并说清楚。"""
        result = runner.invoke(
            app,
            [
                "snowball",
                "t",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--dry-run",
            ],
        )

        assert result.exit_code == 2
        assert "lit screen" in result.output

    def test_dry_run_reports_batch_counts_without_requesting(
        self, seeded_run, topic_path, runs_root, respx_mock
    ):
        before = len(respx_mock.calls)

        result = runner.invoke(
            app,
            [
                "snowball",
                "t",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--seeds",
                "in_window",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0, result.output
        assert "前向" in result.output and "后向" in result.output
        assert len(respx_mock.calls) == before

    def test_an_empty_corpus_is_reported(self, tmp_path, topic_path, runs_root):
        empty = Run.create(runs_root, "t", "20200101T000000Z")
        empty.write_text("manifest.json", json.dumps({"topic_sha256": "x", "counts": {}}))

        result = runner.invoke(
            app,
            [
                "snowball",
                "t",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--seeds",
                "gold",
                "--dry-run",
            ],
        )

        assert result.exit_code == 2
        assert "lit harvest" in result.output


class TestScreen:
    def test_dry_run_reports_cost_without_credentials(
        self, seeded_run, topic_path, runs_root, monkeypatch
    ):
        """没有 key 也要能看到成本——决定跑不跑，本来就该在花钱之前。"""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        result = runner.invoke(
            app,
            ["screen", "t", "--topic", str(topic_path), "--runs-root", str(runs_root), "--dry-run"],
        )

        assert result.exit_code == 0, result.output
        assert "预计成本" in result.output
        assert "粗估" in result.output  # 估算的不确定性必须写在脸上

    def test_a_real_run_without_a_key_fails_loudly(
        self, seeded_run, topic_path, runs_root, monkeypatch
    ):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("LITSEARCH_LLM_API_KEY", raising=False)
        monkeypatch.chdir(runs_root)  # 避开仓库根目录里的真实 .env

        result = runner.invoke(
            app,
            ["screen", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)],
        )

        assert result.exit_code == 2
        assert "LITSEARCH_LLM_API_KEY" in result.output
        # 缺 key 不是死路——要把零配置的那条路指出来
        assert "--model host" in result.output

    def test_an_unknown_model_without_a_base_url_is_rejected(
        self, seeded_run, topic_path, runs_root
    ):
        """不猜端点。猜错会把请求发到不存在的地方，报错还毫无线索。"""
        result = runner.invoke(
            app,
            [
                "screen",
                "t",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--model",
                "some-unknown-model",
                "--dry-run",
            ],
        )

        assert result.exit_code == 2
        assert "LITSEARCH_LLM_BASE_URL" in result.output

    def test_host_backend_dry_run_reports_overhead_not_a_dollar_amount(
        self, seeded_run, topic_path, runs_root
    ):
        """宿主后端不按 token 计费，报框架开销而不是一个假的金额。"""
        result = runner.invoke(
            app,
            [
                "screen",
                "t",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--model",
                "host",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        assert "框架开销" in result.output
        assert "无需 API key" in result.output

    def test_an_empty_window_is_reported(self, tmp_path, topic_path, runs_root):
        empty = Run.create(runs_root, "t", "20200101T000000Z")
        empty.write_text("manifest.json", json.dumps({"topic_sha256": "x", "counts": {}}))

        result = runner.invoke(
            app,
            ["screen", "t", "--topic", str(topic_path), "--runs-root", str(runs_root), "--dry-run"],
        )

        assert result.exit_code == 2
        assert "lit harvest" in result.output


class TestFulltext:
    def test_included_without_screening_is_refused(
        self, seeded_run, topic_path, runs_root, monkeypatch
    ):
        """给会被排除的论文找 PDF 是纯浪费；没有筛选结果就无从判断该给谁找。"""
        monkeypatch.setenv("CONTACT_EMAIL", "probe@example.com")

        result = runner.invoke(
            app,
            ["fulltext", "t", "--runs-root", str(runs_root), "--included"],
        )

        assert result.exit_code == 2
        assert "lit screen" in result.output

    def test_missing_contact_email_is_refused(self, seeded_run, runs_root, monkeypatch, tmp_path):
        """Unpaywall 与 Crossref 都要求声明身份，匿名请求会被限流甚至封禁。"""
        for name in ("CONTACT_EMAIL", "LITSEARCH_CONTACT_EMAIL"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.chdir(tmp_path)  # 避开仓库根目录里的真实 .env

        result = runner.invoke(app, ["fulltext", "t", "--runs-root", str(runs_root)])

        assert result.exit_code == 2
        assert "CONTACT_EMAIL" in result.output


class TestReport:
    def test_writes_every_artifact(self, seeded_run, topic_path, runs_root):
        result = runner.invoke(
            app,
            ["report", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)],
        )

        assert result.exit_code == 0, result.output
        for name in (
            "PRISMA.md",
            "evidence_table.md",
            "included.csv",
            "coverage_report.md",
            "zotero_dois.txt",
        ):
            assert (seeded_run.root / name).exists(), name

    def test_without_screening_it_says_so_instead_of_inflating(
        self, seeded_run, topic_path, runs_root
    ):
        """把窗口内记录数当成纳入数，会严重高估证据量。"""
        runner.invoke(
            app, ["report", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)]
        )

        prisma = (seeded_run.root / "PRISMA.md").read_text()
        assert "尚未筛选" in prisma
        assert (seeded_run.root / "included.csv").read_text().strip().count("\n") == 0

    def test_identification_counts_come_from_the_record_files(
        self, seeded_run, topic_path, runs_root
    ):
        """识别数以实际落盘的逐源记录为准——某个阶段忘了写 manifest 结局时，
        按结局统计会静默少算（实测 crossref 整卷补全的 670 条就这样漏过）。"""
        seeded_run.write_jsonl(
            "records_extra.jsonl",
            [{"source": "crossref", "source_id": "x", "title": "A volume sibling"}],
        )

        runner.invoke(
            app, ["report", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)]
        )

        assert "crossref" in (seeded_run.root / "PRISMA.md").read_text()

    def test_an_empty_corpus_is_reported(self, tmp_path, topic_path, runs_root):
        empty = Run.create(runs_root, "t", "20200101T000000Z")
        empty.write_text("manifest.json", json.dumps({"topic_sha256": "x", "counts": {}}))

        result = runner.invoke(
            app, ["report", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)]
        )

        assert result.exit_code == 2
        assert "lit harvest" in result.output


class TestShow:
    def test_summarises_a_run(self, seeded_run, runs_root):
        result = runner.invoke(app, ["show", "t", "--runs-root", str(runs_root)])

        assert result.exit_code == 0
        assert "openalex" in result.output


class TestVerify:
    def test_report_artifacts_are_current_immediately_after_generation(
        self, seeded_run, topic_path, runs_root
    ):
        generated = runner.invoke(
            app, ["report", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)]
        )
        assert generated.exit_code == 0, generated.output

        result = runner.invoke(app, ["verify", "t", "--runs-root", str(runs_root)])

        assert result.exit_code == 0, result.output
        assert "验证通过" in result.output

    def test_changed_input_marks_a_report_stale(self, seeded_run, topic_path, runs_root):
        runner.invoke(
            app, ["report", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)]
        )
        rows = seeded_run.read_jsonl("corpus.jsonl")
        rows[0]["title"] = "changed after report"
        seeded_run.write_jsonl("corpus.jsonl", rows)

        result = runner.invoke(app, ["verify", "t", "--runs-root", str(runs_root)])

        assert result.exit_code == 1
        assert "artifact-stale" in result.output


class TestAdjudicate:
    def test_screening_csv_creates_a_new_auditable_round(
        self, seeded_run, topic_path, runs_root, tmp_path
    ):
        records = seeded_run.read_jsonl("corpus.jsonl")
        decisions = {
            item["key"]: MergedDecision(
                record_key=item["key"],
                decision=Decision.UNCLEAR,
                needs_human=True,
                reason="two channels failed",
            )
            for item in records
            if item["window_status"] == "in_window"
        }
        manifest = seeded_run.load_manifest()
        seeded_run.write_text(
            "screening_round_1.json",
            ScreeningRound(
                number=1,
                topic_sha256=manifest["topic_sha256"],
                expected_records=len(decisions),
                decisions=decisions,
            ).model_dump_json(indent=2),
        )
        key = next(iter(decisions))
        csv_path = tmp_path / "human.csv"
        csv_path.write_text(
            "record_key,decision,reviewer,reason\n"
            f"{key},include,reviewer-a,meets I1 after manual review\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "adjudicate",
                "t",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--input",
                str(csv_path),
            ],
        )

        assert result.exit_code == 0, result.output
        latest = json.loads((seeded_run.root / "screening_round_2.json").read_text())
        assert latest["provider"] == "human"
        assert latest["decisions"][key]["decision"] == "include"
        assert latest["decisions"][key]["adjudicated_by"] == "reviewer-a"


class TestNumericOptions:
    def test_zero_screen_concurrency_is_rejected_before_any_work(self):
        result = runner.invoke(app, ["screen", "missing", "--topic", "x", "--concurrency", "0"])

        assert result.exit_code == 2
        assert "x>=1" in result.output

    def test_zero_harvest_limit_is_rejected(self):
        result = runner.invoke(app, ["harvest", "--topic", "x", "--max-per-query", "0"])

        assert result.exit_code == 2
        assert "x>=1" in result.output


class TestValidate:
    def test_reports_gold_set_recall(self, seeded_run, topic_path, runs_root):
        result = runner.invoke(
            app,
            ["validate", "t", "--topic", str(topic_path), "--runs-root", str(runs_root)],
        )

        assert result.exit_code == 0, result.output
        assert "金标准" in result.output


class TestDepths:
    def test_depths_command_lists_every_tier_with_its_cost(self):
        result = runner.invoke(app, ["depths"])
        assert result.exit_code == 0
        for name in ("quick", "standard", "systematic"):
            assert name in result.output
        assert "$" in result.output

    def test_depths_says_rigour_is_unchanged(self):
        """降档降的是覆盖面，不是严谨度——这句必须让用户看到。"""
        assert "不是严谨度" in runner.invoke(app, ["depths"]).output

    def test_quick_depth_announces_its_cost_before_running(self, topic_path, runs_root):
        """选档时要先看到时间和钱，不是跑完才知道。"""
        result = runner.invoke(
            app,
            [
                "harvest",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--depth",
                "quick",
                "--max-per-query",
                "1",
            ],
        )
        assert "quick｜快速摸底" in result.output
        assert "本档不跑滚雪球" in result.output

    def test_unknown_depth_is_rejected(self, topic_path, runs_root):
        result = runner.invoke(
            app,
            [
                "harvest",
                "--topic",
                str(topic_path),
                "--runs-root",
                str(runs_root),
                "--depth",
                "deep",
            ],
        )
        assert result.exit_code == 2
        assert "不认识的深度" in result.output


class TestDeliverablesAreTracked:
    """交付物必须和报告一样进 artifacts.json。

    实测缺陷：`lit rank` / `lit deliver` 用的是普通 write_text，而 verify 的
    KNOWN_DERIVED 列着它们的名字——于是**刚生成**的 dois.md 会被标成
    "旧格式产物"，且这个警告永远清不掉，一条走完全流程的正确 run 必然
    过不了 verify --strict。工具说了一句关于自己产出的假话。
    """

    def test_rank_registers_its_outputs(self, seeded_run, runs_root):
        result = runner.invoke(app, ["rank", "t", "--runs-root", str(runs_root)])
        assert result.exit_code == 0, result.output

        tracked = json.loads((seeded_run.root / "artifacts.json").read_text(encoding="utf-8"))
        assert {"tier_report.md", "ranked.csv", "ranked.jsonl"} <= set(tracked["artifacts"])

    def test_a_freshly_ranked_run_passes_strict_verification(self, seeded_run, runs_root):
        runner.invoke(app, ["rank", "t", "--runs-root", str(runs_root)])

        result = runner.invoke(app, ["verify", "t", "--runs-root", str(runs_root), "--strict"])

        assert result.exit_code == 0, result.output
        assert "artifact-untracked" not in result.output

    def test_deliver_registers_the_doi_list_against_the_cache_it_just_wrote(
        self, seeded_run, runs_root
    ):
        """dois.md 依赖 ranked.jsonl，所以缓存必须先落盘再登记。

        反过来写的话记下的是上一次的哈希，产物刚生成就被判过期。
        """
        runner.invoke(app, ["rank", "t", "--runs-root", str(runs_root)])
        result = runner.invoke(
            app, ["deliver", "t", "--runs-root", str(runs_root), "--all", "--no-citations"]
        )
        assert result.exit_code == 0, result.output

        tracked = json.loads((seeded_run.root / "artifacts.json").read_text(encoding="utf-8"))
        assert "ranked.jsonl" in tracked["artifacts"]["dois.md"]["inputs"]

        verified = runner.invoke(app, ["verify", "t", "--runs-root", str(runs_root), "--strict"])
        assert verified.exit_code == 0, verified.output


def _write_round(run, number: int, decisions: dict, **extra) -> None:
    run.write_text(
        f"screening_round_{number}.json",
        ScreeningRound(
            number=number,
            topic_sha256=run.load_manifest()["topic_sha256"],
            expected_records=len(decisions),
            decisions=decisions,
            **extra,
        ).model_dump_json(indent=2),
    )


def _decision(key: str, decision: str, *, queued: bool = False, by: str | None = None):
    return MergedDecision(
        record_key=key,
        decision=Decision(decision),
        needs_human=queued,
        reason="",
        adjudicated_by=by,
    )


class TestScreenEval:
    """评估命令：对照参考轮次量化一个判定器，不打网络。"""

    @staticmethod
    def _keys(run) -> list[str]:
        return [
            item["key"]
            for item in run.read_jsonl("corpus.jsonl")
            if item["window_status"] == "in_window"
        ]

    def _base(self, seeded_run, topic_path, runs_root) -> list[str]:
        return [
            "screen-eval",
            "t",
            "--topic",
            str(topic_path),
            "--runs-root",
            str(runs_root),
            "--reference-round",
            "2",
        ]

    def test_requires_exactly_one_candidate(self, seeded_run, topic_path, runs_root):
        both = runner.invoke(
            app,
            self._base(seeded_run, topic_path, runs_root)
            + ["--candidate-round", "1", "--candidate-scores", "s.jsonl"],
        )
        neither = runner.invoke(app, self._base(seeded_run, topic_path, runs_root))

        assert both.exit_code == 2
        assert neither.exit_code == 2
        assert "只能给一个被评估对象" in neither.output

    def test_missing_round_says_which_rounds_exist(self, seeded_run, topic_path, runs_root):
        keys = self._keys(seeded_run)
        _write_round(seeded_run, 2, {k: _decision(k, "exclude") for k in keys})

        result = runner.invoke(
            app,
            self._base(seeded_run, topic_path, runs_root) + ["--candidate-round", "7"],
        )

        assert result.exit_code == 2
        assert "screening_round_7.json 不存在" in result.output
        assert "[2]" in result.output

    def test_writes_report_and_disagreements_with_hashed_inputs(
        self, seeded_run, topic_path, runs_root
    ):
        keys = self._keys(seeded_run)
        _write_round(seeded_run, 1, {k: _decision(k, "include") for k in keys})
        _write_round(
            seeded_run,
            2,
            {k: _decision(k, "exclude", by="louwill") for k in keys},
        )

        result = runner.invoke(
            app,
            self._base(seeded_run, topic_path, runs_root) + ["--candidate-round", "1"],
        )

        assert result.exit_code == 0, result.output
        report = seeded_run.root / "screen_eval_round1_vs_round2.md"
        csv_path = seeded_run.root / "screen_eval_round1_vs_round2_disagreements.csv"
        assert report.exists() and csv_path.exists()
        assert "金标（真人裁决）" in report.read_text(encoding="utf-8")
        registry = json.loads((seeded_run.root / "artifacts.json").read_text())["artifacts"]
        assert set(registry[report.name]["inputs"]) == {
            "screening_round_1.json",
            "screening_round_2.json",
        }

    def test_a_reference_round_with_nothing_settled_is_rejected(
        self, seeded_run, topic_path, runs_root
    ):
        keys = self._keys(seeded_run)
        _write_round(seeded_run, 1, {k: _decision(k, "include") for k in keys})
        _write_round(
            seeded_run, 2, {k: _decision(k, "unclear", queued=True) for k in keys}
        )

        result = runner.invoke(
            app,
            self._base(seeded_run, topic_path, runs_root) + ["--candidate-round", "1"],
        )

        assert result.exit_code == 2
        assert "无法当参考标签" in result.output

    def test_a_gold_seed_excluded_by_the_candidate_is_called_out(
        self, seeded_run, topic_path, runs_root
    ):
        rows = seeded_run.read_jsonl("corpus.jsonl")
        gold = next(
            item["key"]
            for item in rows
            if item["identifiers"].get("doi") == "10.1038/s41597-022-01875-5"
        )
        keys = self._keys(seeded_run)
        _write_round(
            seeded_run,
            1,
            {k: _decision(k, "exclude" if k == gold else "include") for k in keys},
        )
        _write_round(seeded_run, 2, {k: _decision(k, "include") for k in keys})

        result = runner.invoke(
            app,
            self._base(seeded_run, topic_path, runs_root) + ["--candidate-round", "1"],
        )

        assert result.exit_code == 0, result.output
        assert "金标种子被自动排除" in result.output
        assert gold in result.output

    def test_a_scores_file_is_routed_into_three_bands(
        self, seeded_run, topic_path, runs_root
    ):
        keys = self._keys(seeded_run)
        _write_round(seeded_run, 2, {k: _decision(k, "include") for k in keys})
        seeded_run.write_text(
            "probe_scores.jsonl",
            "\n".join(
                json.dumps({"record_key": key, "answers": {"I1": 0.9, "I2": 0.95}})
                for key in keys
            )
            + "\n",
        )

        result = runner.invoke(
            app,
            self._base(seeded_run, topic_path, runs_root)
            + [
                "--candidate-scores",
                "probe_scores.jsonl",
                "--score-keys",
                "I1,I2",
                "--include-at",
                "0.7",
                "--exclude-below",
                "0.1",
            ],
        )

        assert result.exit_code == 0, result.output
        report = (
            seeded_run.root / "screen_eval_probe_scores_vs_round2.md"
        ).read_text(encoding="utf-8")
        assert "排除带阈值扫描" in report
        assert "AUC 无法计算" in report or "AUC =" in report
        assert "人工队列 0（0.0%）" in result.output

    def test_a_scores_file_missing_a_requested_key_fails_loudly(
        self, seeded_run, topic_path, runs_root
    ):
        keys = self._keys(seeded_run)
        _write_round(seeded_run, 2, {k: _decision(k, "include") for k in keys})
        seeded_run.write_text(
            "probe_scores.jsonl",
            json.dumps({"record_key": keys[0], "answers": {"I1": 0.9}}) + "\n",
        )

        result = runner.invoke(
            app,
            self._base(seeded_run, topic_path, runs_root)
            + ["--candidate-scores", "probe_scores.jsonl", "--score-keys", "I1,I2"],
        )

        assert result.exit_code == 2
        assert "缺少打分项" in result.output


class _FakeCompletions:
    """最小的 OpenAI 兼容替身：对每批记录一律判 include。"""

    def __init__(self) -> None:
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        user = kwargs["messages"][-1]["content"]
        keys = [line.split("key: ")[1] for line in user.splitlines() if "key: " in line]
        payload = json.dumps(
            {
                "verdicts": [
                    {
                        "record_key": key,
                        "decision": "include",
                        "matched_criteria": ["I1"],
                        "reason": "符合 I1",
                        "confidence": 0.95,
                    }
                    for key in keys
                ]
            }
        )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        tool_calls=[
                            SimpleNamespace(
                                function=SimpleNamespace(name="submit", arguments=payload)
                            )
                        ]
                    )
                )
            ],
            usage=SimpleNamespace(
                prompt_cache_hit_tokens=10,
                prompt_cache_miss_tokens=20,
                completion_tokens=5,
            ),
        )


class _FakeClient:
    def __init__(self) -> None:
        self.completions = _FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class TestScreenCommitsItsArtifacts:
    """screen 的提交尾段此前没有任何 CLI 测试。

    它管着三件出错很难发现的事：轮次审计字段齐不齐、试跑会不会占掉正式轮次号、
    待人工裁定的记录会不会混进 included.jsonl。
    """

    @pytest.fixture
    def fake_llm(self, monkeypatch):
        client = _FakeClient()
        monkeypatch.setenv("LITSEARCH_LLM_API_KEY", "k-test")
        monkeypatch.setattr("litsearch.cli.build_screen_client", lambda *a, **k: client)
        return client

    @staticmethod
    def _cmd(topic_path, runs_root, *extra):
        return [
            "screen",
            "t",
            "--topic",
            str(topic_path),
            "--runs-root",
            str(runs_root),
            "--concurrency",
            "1",
            *extra,
        ]

    def test_a_full_run_writes_round_queue_and_included(
        self, seeded_run, topic_path, runs_root, fake_llm
    ):
        result = runner.invoke(app, self._cmd(topic_path, runs_root))

        assert result.exit_code == 0, result.output
        payload = json.loads((seeded_run.root / "screening_round_1.json").read_text())
        assert payload["model"] == "deepseek-v4-flash"
        assert payload["endpoint_host"] == "api.deepseek.com"
        assert payload["expected_records"] == payload["expected_records"]
        assert len(payload["system_prompt_sha256"]) == 64
        assert payload["parameters"]["channels"] == 2
        assert (seeded_run.root / "human_queue.csv").exists()
        assert seeded_run.read_jsonl("included.jsonl")

    def test_a_trial_does_not_occupy_a_round(
        self, seeded_run, topic_path, runs_root, fake_llm
    ):
        result = runner.invoke(app, self._cmd(topic_path, runs_root, "--limit", "2"))

        assert result.exit_code == 0, result.output
        assert (seeded_run.root / "screening_trial.json").exists()
        assert (seeded_run.root / "human_queue_trial.csv").exists()
        assert not list(seeded_run.root.glob("screening_round_*.json"))
        assert seeded_run.read_jsonl("included.jsonl") == []

    def test_a_dry_run_needs_no_key_and_writes_nothing(
        self, seeded_run, topic_path, runs_root, monkeypatch
    ):
        monkeypatch.delenv("LITSEARCH_LLM_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

        result = runner.invoke(app, self._cmd(topic_path, runs_root, "--dry-run"))

        assert result.exit_code == 0, result.output
        assert not list(seeded_run.root.glob("screening_round_*.json"))
        assert not (seeded_run.root / "screening_trial.json").exists()

    def test_a_plain_rerun_that_loses_settled_decisions_is_refused(
        self, seeded_run, topic_path, runs_root, fake_llm
    ):
        """退步守卫对普通重跑同样生效，不只是 --resume。

        规则见 learnings/2026-07-30：任何「最新的覆盖之前的」存储结构，都必须能
        拒绝一次退步的写入。下游只认轮次号最大的那一轮，普通重跑照样会遮蔽上一轮。
        """
        runner.invoke(app, self._cmd(topic_path, runs_root))
        rows = seeded_run.read_jsonl("corpus.jsonl")
        seeded_run.write_jsonl("corpus.jsonl", rows[:1])

        result = runner.invoke(app, self._cmd(topic_path, runs_root))

        assert result.exit_code == 1
        assert "丢失了已有结论" in result.output
        assert not (seeded_run.root / "screening_round_2.json").exists()

    def test_a_wholesale_failure_is_caught_although_the_count_is_unchanged(
        self, seeded_run, topic_path, runs_root, fake_llm, monkeypatch
    ):
        """判据是已定谳集合的丢失，不是判定条数——全灭时条数分毫不变。

        每个批次都失败时，merge_verdicts 仍会给每条记录产出一个判定（标为待人工），
        所以 len(decisions) 完全没变，只有「已定谳」从满额掉到 0。
        """
        assert runner.invoke(app, self._cmd(topic_path, runs_root)).exit_code == 0
        first = json.loads((seeded_run.root / "screening_round_1.json").read_text())
        settled_before = sum(
            1 for item in first["decisions"].values() if not item["needs_human"]
        )
        assert settled_before > 0

        async def boom(**kwargs):
            raise RuntimeError("connection reset")

        dead = _FakeClient()
        dead.chat = SimpleNamespace(completions=SimpleNamespace(create=boom))
        monkeypatch.setattr("litsearch.cli.build_screen_client", lambda *a, **k: dead)

        result = runner.invoke(app, self._cmd(topic_path, runs_root))

        assert result.exit_code == 1
        assert "丢失了已有结论" in result.output
        assert not (seeded_run.root / "screening_round_2.json").exists()

    def test_allow_regression_writes_it_and_records_that_it_was_deliberate(
        self, seeded_run, topic_path, runs_root, fake_llm
    ):
        runner.invoke(app, self._cmd(topic_path, runs_root))
        rows = seeded_run.read_jsonl("corpus.jsonl")
        seeded_run.write_jsonl("corpus.jsonl", rows[:1])

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, "--allow-regression")
        )

        assert result.exit_code == 0, result.output
        payload = json.loads((seeded_run.root / "screening_round_2.json").read_text())
        assert payload["parameters"]["allow_regression"] is True

    def test_an_unchanged_rerun_is_not_a_regression(
        self, seeded_run, topic_path, runs_root, fake_llm
    ):
        runner.invoke(app, self._cmd(topic_path, runs_root))

        result = runner.invoke(app, self._cmd(topic_path, runs_root))

        assert result.exit_code == 0, result.output
        assert (seeded_run.root / "screening_round_2.json").exists()

    def test_a_human_adjudication_survives_a_plain_rerun(
        self, seeded_run, topic_path, runs_root, fake_llm, tmp_path
    ):
        """人工裁决是终审，与这一轮怎么跑出来的无关。

        此前只有 --resume 会把裁决盖回来，普通重跑会让模型判定悄悄覆盖人工结论。
        """
        runner.invoke(app, self._cmd(topic_path, runs_root))
        first = json.loads((seeded_run.root / "screening_round_1.json").read_text())
        key = next(iter(first["decisions"]))
        csv_path = tmp_path / "adj.csv"
        csv_path.write_text(
            "record_key,decision,reviewer,reason\n"
            f"{key},exclude,louwill,核对全文后排除\n",
            encoding="utf-8",
        )
        adj = runner.invoke(
            app,
            [
                "adjudicate", "t", "--topic", str(topic_path),
                "--runs-root", str(runs_root), "--input", str(csv_path),
            ],
        )
        assert adj.exit_code == 0, adj.output

        result = runner.invoke(app, self._cmd(topic_path, runs_root))

        assert result.exit_code == 0, result.output
        latest = json.loads((seeded_run.root / "screening_round_3.json").read_text())
        assert latest["decisions"][key]["decision"] == "exclude"
        assert latest["decisions"][key]["adjudicated_by"] == "louwill"


JEV_URL = "https://api.typesafe.ai/v1/systemone"


def _jev_reply(answers: dict[str, float]) -> dict:
    return {
        "model": "jev-1.13.0",
        "answers": {key: {"type": "noul", "noul": value} for key, value in answers.items()},
        "usage": {"input_tokens": 1200, "output_tokens": 40},
    }


class TestScreenWithJev:
    """判定 API 后端。

    与另外两个后端的关键差别：先把打分落成 jev_scores.jsonl，再由纯函数路由成
    判定——改阈值不用重新花钱。但阈值没有通用默认值，所以配置是必填的。
    """

    @pytest.fixture
    def profile_path(self, tmp_path):
        path = tmp_path / "t.jev.yaml"
        path.write_text("topic_id: t\n", encoding="utf-8")
        return path

    @pytest.fixture
    def jev_key(self, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "k-test")

    @staticmethod
    def _cmd(topic_path, runs_root, *extra):
        return [
            "screen", "t", "--topic", str(topic_path),
            "--runs-root", str(runs_root), "--model", "jev", *extra,
        ]

    def test_it_refuses_to_guess_thresholds(self, seeded_run, topic_path, runs_root, jev_key):
        """阈值逐课题不同：同一套在一个课题上砍半队列，在另一个课题上更差。"""
        result = runner.invoke(app, self._cmd(topic_path, runs_root))

        assert result.exit_code == 2
        assert "--jev-profile" in result.output

    def test_a_profile_pinned_to_another_version_is_refused(
        self, seeded_run, topic_path, runs_root, tmp_path, jev_key
    ):
        path = tmp_path / "other.jev.yaml"
        path.write_text("topic_id: t\nmodel: jev-9.9.9\n", encoding="utf-8")

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, "--jev-profile", str(path))
        )

        assert result.exit_code == 2
        assert "阈值不跨版本转移" in result.output

    def test_a_dry_run_needs_no_key_and_prices_input_only(
        self, seeded_run, topic_path, runs_root, profile_path, monkeypatch
    ):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        monkeypatch.delenv("LITSEARCH_TYPESAFE_API_KEY", raising=False)

        result = runner.invoke(
            app,
            self._cmd(topic_path, runs_root, "--jev-profile", str(profile_path), "--dry-run"),
        )

        assert result.exit_code == 0, result.output
        assert "输出免费" in result.output
        assert not (seeded_run.root / "jev_scores.jsonl").exists()

    def test_a_full_run_writes_scores_then_the_round(
        self, seeded_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.95, "X1": 0.02}))
        )

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, "--jev-profile", str(profile_path))
        )

        assert result.exit_code == 0, result.output
        scores = seeded_run.read_jsonl("jev_scores.jsonl")
        assert scores and scores[0]["model"] == "jev-1.13.0"
        payload = json.loads((seeded_run.root / "screening_round_1.json").read_text())
        assert payload["parameters"]["judge"] == "jev"
        assert payload["parameters"]["channels"] == 1
        assert payload["parameters"]["profile"]["include_at"] == 0.7
        assert payload["model"] == "jev-1.13.0"
        assert seeded_run.read_jsonl("included.jsonl")

    def test_a_gold_seed_auto_excluded_blocks_the_round(
        self, seeded_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        """金标是「必须被检出并保留」的定义，被自动排掉是缺陷不是误差。"""
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.01, "X1": 0.9}))
        )

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, "--jev-profile", str(profile_path))
        )

        assert result.exit_code == 1
        assert "金标种子被**自动排除**" in result.output
        assert not list(seeded_run.root.glob("screening_round_*.json"))
        assert seeded_run.read_jsonl("jev_scores.jsonl"), "打分要留着，别让人白花钱"

    def test_a_trial_keeps_its_scores_separate(
        self, seeded_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.95, "X1": 0.02}))
        )

        result = runner.invoke(
            app,
            self._cmd(
                topic_path, runs_root, "--jev-profile", str(profile_path), "--limit", "2"
            ),
        )

        assert result.exit_code == 0, result.output
        assert (seeded_run.root / "jev_scores_trial.jsonl").exists()
        assert not (seeded_run.root / "jev_scores.jsonl").exists()
        assert not list(seeded_run.root.glob("screening_round_*.json"))

    def test_resume_only_scores_what_is_missing(
        self, seeded_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        route = respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.95, "X1": 0.02}))
        )
        runner.invoke(app, self._cmd(topic_path, runs_root, "--jev-profile", str(profile_path)))
        first_calls = route.call_count

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, "--jev-profile", str(profile_path), "--resume")
        )

        assert result.exit_code == 0, result.output
        assert "无需续跑" in result.output
        assert route.call_count == first_calls, "已有打分不该重花一次钱"

    def test_an_llm_resume_over_a_jev_round_is_refused(
        self, seeded_run, topic_path, runs_root, profile_path, jev_key, respx_mock, monkeypatch
    ):
        """混起来会产出一条看起来像双通道、实际来自两个判定器的判定。"""
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.95, "X1": 0.02}))
        )
        runner.invoke(app, self._cmd(topic_path, runs_root, "--jev-profile", str(profile_path)))
        monkeypatch.setenv("LITSEARCH_LLM_API_KEY", "k-test")

        result = runner.invoke(
            app,
            [
                "screen", "t", "--topic", str(topic_path),
                "--runs-root", str(runs_root), "--resume",
            ],
        )

        assert result.exit_code == 2
        assert "不能跨后端续跑" in result.output

    def test_too_many_failures_keeps_the_scores_but_writes_no_round(
        self, seeded_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        """打分留着，修好后 --resume 补齐即可，不必重跑已成功的部分。"""
        respx_mock.post(JEV_URL).mock(return_value=httpx.Response(503))

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, "--jev-profile", str(profile_path))
        )

        assert result.exit_code == 1
        assert "不写入轮次" in result.output
        assert not list(seeded_run.root.glob("screening_round_*.json"))

    def test_a_bad_key_aborts_instead_of_queueing_everything(
        self, seeded_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        respx_mock.post(JEV_URL).mock(return_value=httpx.Response(401, text="bad key"))

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, "--jev-profile", str(profile_path))
        )

        assert result.exit_code == 2
        assert "整轮中止" in result.output


class TestJevEventLoopDiscipline:
    """建客户端、打分、关闭必须在同一个事件循环里。

    httpx 的连接池绑在创建它的循环上。分两次 asyncio.run 会在关闭时抛
    "Event loop is closed"——而 respx 在传输层拦截、不建真实连接，所以上面那些
    测试一个都测不出来，只有真打网络才会炸。这里用一个"连接池"替身把不变量钉住。
    """

    class _LoopBoundClient:
        """模拟 httpx 的行为：在哪个循环里用过，就只能在哪个循环里关。"""

        def __init__(self) -> None:
            self.used_loop = None
            self.closed = False

        def note_use(self) -> None:
            self.used_loop = asyncio.get_running_loop()

        async def aclose(self) -> None:
            if self.used_loop is not None and asyncio.get_running_loop() is not self.used_loop:
                raise RuntimeError("Event loop is closed")
            self.closed = True

    def test_the_client_is_closed_in_the_loop_that_used_it(
        self, seeded_run, topic_path, runs_root, tmp_path, monkeypatch
    ):
        raw = self._LoopBoundClient()

        class _Judge:
            model = "jev-1.13.0"

            async def ask(self, state, questions):
                raw.note_use()
                return JevResponse(
                    model="jev-1.13.0",
                    answers={key: {"type": "noul", "noul": 0.9} for key in questions},
                    input_tokens=1200,
                    output_tokens=40,
                )

        monkeypatch.setenv("TYPESAFE_API_KEY", "k-test")
        monkeypatch.setattr(
            "litsearch.cli_judge.build_jev_client", lambda *a, **k: (_Judge(), raw)
        )
        profile = tmp_path / "t.jev.yaml"
        profile.write_text("topic_id: t\n", encoding="utf-8")

        result = runner.invoke(
            app,
            [
                "screen", "t", "--topic", str(topic_path), "--runs-root", str(runs_root),
                "--model", "jev", "--jev-profile", str(profile),
            ],
        )

        assert result.exit_code == 0, result.output
        assert raw.closed, "客户端必须被关掉，否则连接泄漏"


class TestTriage:
    """人工队列分诊。默认只排序和标注，**不替人裁定**。"""

    @pytest.fixture
    def profile_path(self, tmp_path):
        path = tmp_path / "t.jev.yaml"
        path.write_text("topic_id: t\n", encoding="utf-8")
        return path

    @pytest.fixture
    def jev_key(self, monkeypatch):
        monkeypatch.setenv("TYPESAFE_API_KEY", "k-test")

    @staticmethod
    def _disagreement(key: str):
        from litsearch.screen import Verdict

        return MergedDecision(
            record_key=key,
            decision=Decision.UNCLEAR,
            needs_human=True,
            reason="通道间分歧：['exclude', 'include']",
            channel_verdicts=[
                Verdict(record_key=key, decision=Decision.INCLUDE, confidence=0.9, channel=0),
                Verdict(record_key=key, decision=Decision.EXCLUDE, confidence=0.8, channel=1),
            ],
        )

    @pytest.fixture
    def queued_run(self, seeded_run):
        keys = [
            item["key"]
            for item in seeded_run.read_jsonl("corpus.jsonl")
            if item["window_status"] == "in_window"
        ]
        # 录制的 fixture 只有两条窗口内记录，所以别硬编码条数——
        # 把实际进队列的 key 交给测试，让断言跟着数据走。
        assert keys, "seeded_run 应当至少有一条窗口内记录"
        decisions = {key: self._disagreement(key) for key in keys}
        _write_round(seeded_run, 1, decisions, provider="api.deepseek.com")
        return seeded_run, keys

    @staticmethod
    def _cmd(topic_path, runs_root, profile_path, *extra):
        return [
            "triage", "t", "--topic", str(topic_path), "--runs-root", str(runs_root),
            "--jev-profile", str(profile_path), *extra,
        ]

    def test_an_empty_queue_needs_no_network(
        self, seeded_run, topic_path, runs_root, profile_path, jev_key
    ):
        keys = [item["key"] for item in seeded_run.read_jsonl("corpus.jsonl")]
        _write_round(
            seeded_run,
            1,
            {
                k: MergedDecision(
                    record_key=k, decision=Decision.INCLUDE, needs_human=False, reason=""
                )
                for k in keys
            },
        )

        result = runner.invoke(app, self._cmd(topic_path, runs_root, profile_path))

        assert result.exit_code == 0, result.output
        assert "队列是空的" in result.output

    def test_it_reorders_the_queue_most_likely_include_first(
        self, queued_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        run_dir, keys = queued_run
        scores = iter([0.2, 0.95, 0.6])

        def responder(request):
            value = next(scores, 0.5)
            return httpx.Response(200, json=_jev_reply({"I1": value, "X1": 0.01}))

        respx_mock.post(JEV_URL).mock(side_effect=responder)

        result = runner.invoke(app, self._cmd(topic_path, runs_root, profile_path))

        assert result.exit_code == 0, result.output
        lines = (run_dir.root / "human_queue.csv").read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("record_key,decision,reviewer,reason")
        assert "jev_score" in lines[0]
        written = [line.split(",")[4] for line in lines[1:]]
        assert written == sorted(written, reverse=True), "最可能纳入的要排最前"

    def test_it_does_not_adjudicate_unless_asked(
        self, queued_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        run_dir, _ = queued_run
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.95, "X1": 0.01}))
        )

        result = runner.invoke(app, self._cmd(topic_path, runs_root, profile_path))

        assert result.exit_code == 0, result.output
        assert not (run_dir.root / "screening_round_2.json").exists()
        assert "--auto-resolve" in result.output

    def test_auto_resolve_writes_a_machine_adjudicated_round(
        self, queued_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        run_dir, keys = queued_run
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.95, "X1": 0.01}))
        )

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, profile_path, "--auto-resolve")
        )

        assert result.exit_code == 0, result.output
        payload = json.loads((run_dir.root / "screening_round_2.json").read_text())
        assert payload["parameters"]["kind"] == "triage"
        assert payload["parameters"]["resolved"] == len(keys)
        resolved = [
            item for item in payload["decisions"].values() if item["adjudicated_by"]
        ]
        assert len(resolved) == len(keys)
        assert all(item["adjudicated_by"] == "jev:jev-1.13.0" for item in resolved)
        assert all(item["decision"] == "include" for item in resolved)
        assert all("机器裁定" in item["reason"] for item in resolved)

    def test_the_machine_round_lands_in_the_audit_trail(
        self, queued_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        run_dir, keys = queued_run
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.95, "X1": 0.01}))
        )

        runner.invoke(app, self._cmd(topic_path, runs_root, profile_path, "--auto-resolve"))

        audit = run_dir.read_jsonl("adjudications.jsonl")
        assert len(audit) == len(keys)
        assert all(item["reviewer"] == "jev:jev-1.13.0" for item in audit)

    def test_a_low_score_leaves_the_queue_to_a_human(
        self, queued_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        run_dir, _ = queued_run
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.3, "X1": 0.01}))
        )

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, profile_path, "--auto-resolve")
        )

        assert result.exit_code == 0, result.output
        assert "没有可自动裁定的僵局" in result.output
        assert not (run_dir.root / "screening_round_2.json").exists()

    def test_a_dry_run_needs_no_key(
        self, queued_run, topic_path, runs_root, profile_path, monkeypatch
    ):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        monkeypatch.delenv("LITSEARCH_TYPESAFE_API_KEY", raising=False)

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, profile_path, "--dry-run")
        )

        assert result.exit_code == 0, result.output
        assert "输出免费" in result.output

    def test_a_triage_round_does_not_block_a_later_jev_resume(
        self, queued_run, topic_path, runs_root, profile_path, jev_key, respx_mock
    ):
        """分诊只解开僵局，不改变「这批是谁判的」。"""
        from litsearch.cli_support import latest_round_judge

        run_dir, _ = queued_run
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(200, json=_jev_reply({"I1": 0.95, "X1": 0.01}))
        )
        runner.invoke(app, self._cmd(topic_path, runs_root, profile_path, "--auto-resolve"))

        assert latest_round_judge(run_dir) is None, "底下那轮是双通道 LLM 判的"


class TestFacets:
    """已纳入记录的标注。只产出独立文件，不碰证据表。"""

    @pytest.fixture
    def profile_path(self, tmp_path):
        path = tmp_path / "t.jev.yaml"
        path.write_text("topic_id: t\n", encoding="utf-8")
        return path

    @pytest.fixture
    def included_run(self, seeded_run):
        rows = [
            item
            for item in seeded_run.read_jsonl("corpus.jsonl")
            if item["window_status"] == "in_window"
        ]
        seeded_run.write_jsonl("included.jsonl", rows)
        return seeded_run, rows

    @staticmethod
    def _cmd(topic_path, runs_root, profile_path, *extra):
        return [
            "facets", "t", "--topic", str(topic_path), "--runs-root", str(runs_root),
            "--jev-profile", str(profile_path), *extra,
        ]

    def test_an_empty_included_set_is_refused(
        self, seeded_run, topic_path, runs_root, profile_path
    ):
        result = runner.invoke(app, self._cmd(topic_path, runs_root, profile_path))

        assert result.exit_code == 2
        assert "included.jsonl 是空的" in result.output

    def test_it_writes_labels_and_keeps_the_raw_probabilities(
        self, included_run, topic_path, runs_root, profile_path, respx_mock, monkeypatch
    ):
        run_dir, rows = included_run
        monkeypatch.setenv("TYPESAFE_API_KEY", "k-test")
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "jev-1.13.0",
                    "answers": {
                        "external_validation": {"type": "noul", "noul": 0.93},
                        "multi_center": {"type": "noul", "noul": 0.05},
                        "public_dataset": {"type": "noul", "noul": 0.88},
                        "code_available": {"type": "noul", "noul": 0.02},
                        "prospective": {"type": "noul", "noul": 0.04},
                    },
                    "usage": {"input_tokens": 900, "output_tokens": 30},
                },
            )
        )

        result = runner.invoke(app, self._cmd(topic_path, runs_root, profile_path))

        assert result.exit_code == 0, result.output
        table = (run_dir.root / "facets.csv").read_text(encoding="utf-8")
        assert "external_validation,external_validation_p" in table
        assert "stated,0.930" in table
        assert "not_stated,0.050" in table
        assert run_dir.read_jsonl("facets.jsonl")

    def test_the_summary_refuses_to_read_as_a_quality_score(
        self, included_run, topic_path, runs_root, profile_path, respx_mock, monkeypatch
    ):
        """「没说」不等于「没做」。这句话必须印在数字旁边，否则它就会被当成评分。"""
        monkeypatch.setenv("TYPESAFE_API_KEY", "k-test")
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "jev-1.13.0",
                    "answers": {
                        item.id: {"type": "noul", "noul": 0.9}
                        for item in DEFAULT_FACETS
                    },
                    "usage": {"input_tokens": 900, "output_tokens": 30},
                },
            )
        )

        result = runner.invoke(app, self._cmd(topic_path, runs_root, profile_path))

        assert result.exit_code == 0, result.output
        assert "没说不等于没做" in result.output

    def test_a_dry_run_needs_no_key(
        self, included_run, topic_path, runs_root, profile_path, monkeypatch
    ):
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        monkeypatch.delenv("LITSEARCH_TYPESAFE_API_KEY", raising=False)

        result = runner.invoke(
            app, self._cmd(topic_path, runs_root, profile_path, "--dry-run")
        )

        assert result.exit_code == 0, result.output
        assert "输出免费" in result.output
        assert not (included_run[0].root / "facets.csv").exists()

    def test_the_table_is_tracked_as_a_derived_artifact(
        self, included_run, topic_path, runs_root, profile_path, respx_mock, monkeypatch
    ):
        """included.jsonl 一变，lit verify 就该说 facets.csv 过期了。"""
        run_dir, _ = included_run
        monkeypatch.setenv("TYPESAFE_API_KEY", "k-test")
        respx_mock.post(JEV_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "model": "jev-1.13.0",
                    "answers": {
                        item.id: {"type": "noul", "noul": 0.9}
                        for item in DEFAULT_FACETS
                    },
                    "usage": {"input_tokens": 900, "output_tokens": 30},
                },
            )
        )

        runner.invoke(app, self._cmd(topic_path, runs_root, profile_path))

        registry = json.loads((run_dir.root / "artifacts.json").read_text())["artifacts"]
        assert registry["facets.csv"]["inputs"].keys() == {"included.jsonl"}
