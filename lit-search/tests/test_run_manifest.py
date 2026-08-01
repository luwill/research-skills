"""Run 清单：采集完整性告警只看每条检索式的最新结局。

同一条检索式先失败、后补跑成功是常态——改限速、修解析缺陷之后就会这样
（本项目实测：Zenodo 因页大小超限整批 400，改成 25 后全部成功）。
把历史失败一直算进来，报告会永远挂着一个已经解决的告警；
而告警一旦变成噪声，真出问题时就没人看了。

反过来更要命的是漏报：一条**至今仍失败**的检索式必须继续告警，
否则"这个源采全了"就是一句假话。
"""

from __future__ import annotations

import json

from litsearch.run import QueryOutcome, RunManifest, latest_degraded, unrun_sources


def outcome(source, query_hash, status):
    return QueryOutcome(
        source=source,
        query_hash=query_hash,
        kind="phrase",
        label="l",
        query="q",
        reported_total=None,
        fetched=0,
        status=status,
    )


class TestLatestDegraded:
    def test_a_query_that_later_succeeded_is_no_longer_degraded(self):
        outcomes = [outcome("grey", "h1", "failed"), outcome("grey", "h1", "complete")]

        assert latest_degraded(outcomes) == set()

    def test_a_query_still_failing_stays_degraded(self):
        outcomes = [outcome("grey", "h1", "complete"), outcome("grey", "h1", "failed")]

        assert latest_degraded(outcomes) == {"grey"}

    def test_other_queries_of_the_same_source_do_not_mask_a_failure(self):
        """一个源里只要还有一条没取全，这个源的数字就是下界。"""
        outcomes = [outcome("grey", "h1", "complete"), outcome("grey", "h2", "failed")]

        assert latest_degraded(outcomes) == {"grey"}

    def test_partial_counts_as_degraded(self):
        assert latest_degraded([outcome("arxiv", "h1", "partial")]) == {"arxiv"}

    def test_dict_rows_from_a_manifest_file_are_accepted(self):
        """报告层读回来的是 JSON 字典，不是 dataclass。"""
        rows = [
            {"source": "grey", "query_hash": "h1", "status": "failed"},
            {"source": "grey", "query_hash": "h1", "status": "complete"},
        ]

        assert latest_degraded(rows) == set()

    def test_no_outcomes_means_nothing_degraded(self):
        assert latest_degraded([]) == set()


class TestExecutedSources:
    """`sources` 声明了什么，和实际访问了什么，是两件事。

    实测事故：续跑后 manifest 的 `sources` 有四个源，`outcomes` 里只有两个源——
    另外两个从没被访问过，而没有任何一份产物提到这件事。
    """

    def test_a_source_with_no_outcome_is_unrun(self):
        outcomes = [outcome("openalex", "h1", "complete")]

        assert unrun_sources(["openalex", "openreview"], outcomes) == ["openreview"]

    def test_a_failed_source_still_counts_as_run(self):
        """跑了没成功 ≠ 没跑。前者有 partial 告警管，后者连告警都没有。"""
        outcomes = [outcome("grey", "h1", "failed")]

        assert unrun_sources(["grey"], outcomes) == []

    def test_it_reads_manifest_dicts_too(self):
        """报告层拿到的是从 manifest.json 读回的字典。"""
        rows = [{"source": "openalex", "query_hash": "h1", "status": "complete"}]

        assert unrun_sources(["openalex", "grey"], rows) == ["grey"]


class TestDepthIsRecorded:
    def test_manifest_carries_the_depth(self):
        """档位决定了跑几个源、滚不滚雪球——不记下来，这次 run 就无法复现。"""
        manifest = RunManifest(
            run_id="r",
            topic_id="t",
            topic_sha256="a",
            topic_fingerprint="b",
            created_at="",
            window_start="",
            window_end="",
            harvest_start="",
            harvest_end="",
            date_priority=[],
            sources=[],
            depth="quick",
        )

        assert json.loads(manifest.to_json())["depth"] == "quick"

    def test_depth_is_optional_for_runs_that_predate_it(self):
        manifest = RunManifest(
            run_id="r",
            topic_id="t",
            topic_sha256="a",
            topic_fingerprint="b",
            created_at="",
            window_start="",
            window_end="",
            harvest_start="",
            harvest_end="",
            date_priority=[],
            sources=[],
        )

        assert json.loads(manifest.to_json())["depth"] is None
