"""命令行层：参数校验、错误路径、产物落盘。

这一层的价值不在算法，而在**出错时说人话且退出码正确**——
协议写错、run 找不到、参数不成对，都必须当场拦下并指明怎么改，
而不是抛一个栈回溯或者静默跑出一份不完整的结果。

不打网络：需要采集的命令用录制的 fixture 打桩。
"""

from __future__ import annotations

import json

import httpx
import pytest
from typer.testing import CliRunner

from litsearch.cli import app
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
