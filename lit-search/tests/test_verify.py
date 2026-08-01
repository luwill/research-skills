from __future__ import annotations

import json

from litsearch.run import Run, RunManifest, file_sha256
from litsearch.verify import verify_run


def healthy_run(tmp_path) -> Run:
    run = Run.create(tmp_path / "runs", "t", "r1")
    run.write_text("topic.yaml", "id: t\n")
    run.write_jsonl("records.jsonl", [{"source": "x", "source_id": "1", "title": "A"}])
    run.write_jsonl(
        "corpus.jsonl",
        [{"key": "k1", "title": "A", "window_status": "in_window"}],
    )
    run.save_manifest(
        RunManifest(
            run_id="r1",
            topic_id="t",
            topic_sha256=file_sha256(run.root / "topic.yaml"),
            topic_fingerprint="fp",
            created_at="",
            window_start="2020-01-01",
            window_end="2025-01-01",
            harvest_start="2019-01-01",
            harvest_end="2026-01-01",
            date_priority=[],
            sources=["x"],
            counts={"canonical_records": 1, "in_window": 1},
            phases={
                "initial": {
                    "status": "complete",
                    "record_file": "records.jsonl",
                }
            },
        )
    )
    return run


def codes(run: Run) -> set[str]:
    return {item.code for item in verify_run(run)}


class TestRunVerification:
    def test_a_healthy_v2_run_passes(self, tmp_path):
        assert verify_run(healthy_run(tmp_path)) == []

    def test_an_uncommitted_phase_is_detected(self, tmp_path):
        run = healthy_run(tmp_path)
        run.write_text("records_interrupted.jsonl", "")

        assert "phase-uncommitted" in codes(run)

    def test_a_tracked_report_becomes_stale_when_an_input_changes(self, tmp_path):
        run = healthy_run(tmp_path)
        run.write_artifact("coverage_report.md", "fresh", inputs=["corpus.jsonl"])
        run.write_jsonl(
            "corpus.jsonl",
            [{"key": "k1", "title": "Changed", "window_status": "in_window"}],
        )

        assert "artifact-stale" in codes(run)

    def test_an_old_untracked_report_is_explicitly_unverifiable(self, tmp_path):
        run = healthy_run(tmp_path)
        run.write_text("coverage_report.md", "legacy")

        issues = verify_run(run)

        assert any(
            item.code == "artifact-untracked" and item.severity == "warning" for item in issues
        )

    def test_screening_must_cover_the_current_strict_window_corpus(self, tmp_path):
        run = healthy_run(tmp_path)
        run.write_text(
            "screening_round_1.json",
            json.dumps({"expected_records": 1, "decisions": {}}),
        )

        assert {"screening-incomplete", "screening-corpus-mismatch"} <= codes(run)


class TestDeletedArtifacts:
    """交付物可以被主动删掉腾空间——那是正当操作，不是完整性损坏。

    `dois.md` / `references.md` 动辄几百 KB 到几 MB，用户清理它们是常态。
    把这件事报成 error，等于让工具把用户的一次正当动作叫做"损坏"，
    而真正的损坏（内容被改、输入变了）会淹没在同一个级别的噪声里。
    """

    def test_a_registered_artifact_that_was_deleted_is_only_a_warning(self, tmp_path):
        run = healthy_run(tmp_path)
        run.write_artifact("dois.md", "# 交付物", inputs=["corpus.jsonl"])
        (run.root / "dois.md").unlink()

        issues = [item for item in verify_run(run) if item.code == "artifact-deleted"]

        assert issues, "登记过但已不在的产物必须报出来"
        assert issues[0].severity == "warning"
        assert not any(item.severity == "error" for item in verify_run(run))

    def test_the_message_says_it_can_be_rebuilt(self, tmp_path):
        run = healthy_run(tmp_path)
        run.write_artifact("dois.md", "# 交付物", inputs=["corpus.jsonl"])
        (run.root / "dois.md").unlink()

        message = next(item.message for item in verify_run(run) if item.code == "artifact-deleted")
        assert "重建" in message

    def test_a_modified_artifact_is_still_an_error(self, tmp_path):
        """删掉是正当的，改掉不是——后者会让产物与它声称的输入对不上。"""
        run = healthy_run(tmp_path)
        run.write_artifact("dois.md", "# 交付物", inputs=["corpus.jsonl"])
        (run.root / "dois.md").write_text("被手改过", encoding="utf-8")

        assert "artifact-modified" in codes(run)
        assert any(item.severity == "error" for item in verify_run(run))

    def test_a_deleted_artifact_does_not_also_trigger_the_untracked_warning(self, tmp_path):
        """一件事只报一次。删掉的产物不该同时被说成"旧格式"。"""
        run = healthy_run(tmp_path)
        run.write_artifact("dois.md", "# 交付物", inputs=["corpus.jsonl"])
        (run.root / "dois.md").unlink()

        assert "artifact-untracked" not in codes(run)
