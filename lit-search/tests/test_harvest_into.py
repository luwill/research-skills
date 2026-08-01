"""把新一批采集并入已有 run。

采集是分阶段进行的：主干四源 → 顶会/灰色文献 → 会议录整卷 → 引文滚雪球。
每一阶段都单独写 ``records_<阶段>.jsonl``，语料由它们合并去重而来。

两条不能破的规矩：

- **原始记录只追加，不改写。** 每个阶段的产出各占一个文件，"哪一条是哪一阶段
  拿到的"永远可回答；派生产物（corpus.jsonl）随时可重算。
- **协议必须一致。** 协议一改，两批结果就不再属于同一次系统检索，
  拼在一起的语料无法追溯到单一协议版本，必须拒绝。
"""

from __future__ import annotations

import json

import httpx
import pytest
import yaml

from litsearch.harvest import harvest, harvest_into
from litsearch.protocol import Topic, freeze_topic, protocol_fingerprint
from litsearch.run import Run
from litsearch.sources.grey import ENDPOINT as ZENODO
from litsearch.sources.registry import Credentials

from .conftest import fixture_text


@pytest.fixture
def topic_file(tmp_path):
    payload = """
id: t
title: T
window: {start: 2021-07-01, end: 2026-07-27, harvest_margin_days: 365}
concepts:
  condition:
    required: true
    terms: [ischemic stroke, stroke lesion]
    wildcards: [infarct*]
  task:
    required: true
    terms: [segmentation]
query_plan: {combinations: [[condition, task]]}
criteria: {include: [{id: I1, text: x}]}
sources:
  openalex: {enabled: true}
  grey: {enabled: true}
"""
    path = tmp_path / "topic.yaml"
    path.write_text(payload, encoding="utf-8")
    return path


def _load(topic_file) -> Topic:
    return Topic.model_validate(yaml.safe_load(topic_file.read_text(encoding="utf-8")))


@pytest.fixture
async def base_run(tmp_path, topic_file, respx_mock):
    """先做一次只跑 openalex 的主干采集，作为后续并入的基线。

    用**可终止的响应序列**：OpenAlex 靠 cursor 翻页，一个反复返回同一页
    （且带 next_cursor）的桩会让它永远翻下去。
    """
    empty = json.dumps({"meta": {"count": 369, "next_cursor": None}, "results": []})
    respx_mock.get("https://api.openalex.org/works").mock(
        side_effect=[
            httpx.Response(200, text=fixture_text("openalex_page1.json")),
            httpx.Response(200, text=empty),
        ]
    )
    run = Run.create(tmp_path / "runs", "t")
    await harvest(_load(topic_file), topic_file, run, Credentials(), only=["openalex"])
    return run


class TestHarvestInto:
    async def test_initial_harvest_freezes_the_exact_topic_and_phase_commit(
        self, base_run, topic_file
    ):
        assert (base_run.root / "topic.yaml").read_bytes() == topic_file.read_bytes()
        manifest = base_run.load_manifest()
        assert manifest["schema_version"] == 2
        assert manifest["phases"]["initial"]["status"] == "complete"

    async def test_new_phase_writes_its_own_record_file(self, base_run, topic_file, respx_mock):
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )

        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="stage3",
            only=["grey"],
        )

        assert (base_run.root / "records.jsonl").exists()
        assert (base_run.root / "records_stage3.jsonl").exists()

    async def test_the_earlier_phase_file_is_never_rewritten(
        self, base_run, topic_file, respx_mock
    ):
        before = (base_run.root / "records.jsonl").read_text()
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )

        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="stage3",
            only=["grey"],
        )

        assert (base_run.root / "records.jsonl").read_text() == before

    async def test_corpus_is_rebuilt_from_every_phase(self, base_run, topic_file, respx_mock):
        before = len(base_run.read_jsonl("corpus.jsonl"))
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )

        report = await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="stage3",
            only=["grey"],
        )

        assert len(report.canonical) > before
        assert len(base_run.read_jsonl("corpus.jsonl")) == len(report.canonical)

    async def test_manifest_keeps_both_phases_outcomes(self, base_run, topic_file, respx_mock):
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )

        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="stage3",
            only=["grey"],
        )

        manifest = base_run.load_manifest()
        sources = {item["source"] for item in manifest["outcomes"]}
        assert sources == {"openalex", "grey"}
        assert "grey" in manifest["sources"]

    async def test_a_changed_protocol_is_refused(self, base_run, topic_file, respx_mock):
        """协议一改，两批结果就不属于同一次系统检索，拼起来无法追溯。"""
        topic_file.write_text(
            topic_file.read_text().replace("segmentation]", "segmentation, volumetry]"),
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="协议"):
            await harvest_into(
                _load(topic_file),
                topic_file,
                base_run,
                Credentials(),
                phase="stage3",
                only=["grey"],
            )

    async def test_rerunning_the_same_phase_is_refused(self, base_run, topic_file, respx_mock):
        """同名阶段重跑会覆盖上一次的原始记录——必须换个阶段名或新开 run。"""
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )
        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="stage3",
            only=["grey"],
        )

        with pytest.raises(FileExistsError, match="stage3"):
            await harvest_into(
                _load(topic_file),
                topic_file,
                base_run,
                Credentials(),
                phase="stage3",
                only=["grey"],
            )

    async def test_an_uncommitted_v2_phase_can_be_retried(self, base_run, topic_file, respx_mock):
        """records 文件写完、manifest 未提交时属于可恢复中断，不是假完成。"""
        base_run.write_text("records_retry.jsonl", "")
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )

        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="retry",
            only=["grey"],
        )

        assert base_run.load_manifest()["phases"]["retry"]["status"] == "complete"
        assert base_run.read_jsonl("records_retry.jsonl")

    async def test_phase_name_must_be_a_safe_filename(self, base_run, topic_file):
        with pytest.raises(ValueError, match="阶段名"):
            await harvest_into(
                _load(topic_file),
                topic_file,
                base_run,
                Credentials(),
                phase="../escape",
                only=["grey"],
            )

    async def test_failed_queries_are_recorded_not_swallowed(
        self, base_run, topic_file, respx_mock
    ):
        respx_mock.get(ZENODO).mock(return_value=httpx.Response(500, text="boom"))

        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="stage3",
            only=["grey"],
        )

        manifest = base_run.load_manifest()
        grey = [item for item in manifest["outcomes"] if item["source"] == "grey"]
        assert grey and all(item["status"] == "failed" for item in grey)
        assert any("grey" in note for note in manifest["notes"])


class TestLabelFilter:
    """定点补跑：修好某个源的解析缺陷后，不必把整个源重跑一遍。"""

    async def test_only_the_named_queries_run(self, base_run, topic_file, respx_mock):
        route = respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )

        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="fix",
            only=["grey"],
            labels=["ischemic stroke"],
        )

        assert len(route.calls) == 1
        assert route.calls[0].request.url.params["q"] == '"ischemic stroke"'

    async def test_an_unknown_label_is_rejected_rather_than_silently_empty(
        self, base_run, topic_file
    ):
        """打错一个 label 就静默跑出 0 条，会被当成"这批确实没有结果"。"""
        with pytest.raises(ValueError, match="label"):
            await harvest_into(
                _load(topic_file),
                topic_file,
                base_run,
                Credentials(),
                phase="fix",
                only=["grey"],
                labels=["拼错了"],
            )


class TestProtocolFingerprint:
    """协议一致性该按**语义**判，不是按字节。

    按字节判会让"给 topic.yaml 加一行注释"直接废掉整次 run 的续接能力——
    而注释根本没有改变任何检索行为。反过来，改一个术语必须被拦下。
    """

    def test_comments_and_formatting_do_not_change_the_fingerprint(self, topic_file):
        before = protocol_fingerprint(_load(topic_file))
        topic_file.write_text(
            "# 一句说明，不改变任何检索行为\n" + topic_file.read_text(), encoding="utf-8"
        )

        assert protocol_fingerprint(_load(topic_file)) == before
        assert freeze_topic(topic_file) != before  # 字节哈希确实变了

    def test_changing_a_term_changes_the_fingerprint(self, topic_file):
        before = protocol_fingerprint(_load(topic_file))
        topic_file.write_text(
            topic_file.read_text().replace("segmentation]", "segmentation, volumetry]"),
            encoding="utf-8",
        )

        assert protocol_fingerprint(_load(topic_file)) != before

    def test_reordering_concept_blocks_does_not_change_it(self, topic_file):
        """概念块是映射，YAML 里换个书写顺序不改变检索空间。"""
        before = protocol_fingerprint(_load(topic_file))
        text = topic_file.read_text()
        reordered = text.replace(
            """concepts:
  condition:
    required: true
    terms: [ischemic stroke, stroke lesion]
    wildcards: [infarct*]
  task:
    required: true
    terms: [segmentation]""",
            """concepts:
  task:
    required: true
    terms: [segmentation]
  condition:
    required: true
    terms: [ischemic stroke, stroke lesion]
    wildcards: [infarct*]""",
        )
        topic_file.write_text(reordered, encoding="utf-8")

        assert protocol_fingerprint(_load(topic_file)) == before

    def test_term_order_within_a_block_does_change_it(self, topic_file):
        """术语顺序是语义的：max_terms_per_block 按顺序截断。"""
        before = protocol_fingerprint(_load(topic_file))
        topic_file.write_text(
            topic_file.read_text().replace(
                "[ischemic stroke, stroke lesion]", "[stroke lesion, ischemic stroke]"
            ),
            encoding="utf-8",
        )

        assert protocol_fingerprint(_load(topic_file)) != before

    async def test_a_comment_only_edit_no_longer_blocks_merging(
        self, base_run, topic_file, respx_mock
    ):
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )
        topic_file.write_text("# 只是注释\n" + topic_file.read_text(), encoding="utf-8")

        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="stage3",
            only=["grey"],
        )

        assert (base_run.root / "records_stage3.jsonl").exists()

    async def test_legacy_manifests_without_a_fingerprint_gain_one(
        self, base_run, topic_file, respx_mock
    ):
        """早于该字段的 run：字节哈希一致就补记指纹，此后按语义比对。"""
        manifest = base_run.load_manifest()
        manifest.pop("topic_fingerprint", None)
        base_run.write_text("manifest.json", json.dumps(manifest, ensure_ascii=False))
        respx_mock.get(ZENODO).mock(
            return_value=httpx.Response(200, text=fixture_text("zenodo_records.json"))
        )

        await harvest_into(
            _load(topic_file),
            topic_file,
            base_run,
            Credentials(),
            phase="stage3",
            only=["grey"],
        )

        assert base_run.load_manifest()["topic_fingerprint"] == protocol_fingerprint(
            _load(topic_file)
        )


class TestRecordFileNaming:
    def test_phase_files_sort_after_the_main_file(self, tmp_path):
        """合并读取靠 glob 排序，主采集必须排在补全阶段之前，语义才稳定。"""
        names = sorted(["records_stage3.jsonl", "records.jsonl", "records_snowball.jsonl"])

        assert names[0] == "records.jsonl"


async def test_manifest_json_is_still_valid_after_merge(base_run, topic_file):
    json.loads((base_run.root / "manifest.json").read_text())
