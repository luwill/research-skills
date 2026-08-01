"""宿主模型后端的测试。

没有工具调用可用，所以模型输出是**自由文本里的 JSON**——解析必须扛得住
代码块围栏、前后废话、臆造的 key、缺失的字段。
"""

from __future__ import annotations

import json

import pytest

from litsearch.screen_host import (
    HOST_BATCH_SIZE,
    HostBackendError,
    HostUsage,
    build_prompt,
    estimate_calls,
    parse_output,
)
from litsearch.screen_runner import ScreeningRequest


def _request(keys=("doi:10.1/a", "doi:10.1/b")) -> ScreeningRequest:
    return ScreeningRequest(
        custom_id="c0-b00000",
        channel=0,
        batch_index=0,
        system="你是筛选员。",
        user_content="记录若干",
        record_keys=tuple(keys),
    )


def _payload(*rows) -> str:
    return json.dumps({"verdicts": list(rows)}, ensure_ascii=False)


def _row(key, decision="include", confidence=0.9):
    return {
        "record_key": key,
        "decision": decision,
        "matched_criteria": ["I1"],
        "reason": "理由",
        "confidence": confidence,
    }


class TestBuildPrompt:
    def test_carries_the_channel_prompt_and_records(self) -> None:
        text = build_prompt(_request())
        assert "你是筛选员。" in text
        assert "记录若干" in text

    def test_states_the_schema_because_there_is_no_tool_calling(self) -> None:
        text = build_prompt(_request())
        assert "verdicts" in text and "confidence" in text

    def test_demands_one_verdict_per_record(self) -> None:
        assert "一条都不能少" in build_prompt(_request())


class TestParseOutput:
    def test_plain_json(self) -> None:
        verdicts = parse_output(_payload(_row("doi:10.1/a")), _request())
        assert [item.record_key for item in verdicts] == ["doi:10.1/a"]

    def test_strips_markdown_fences(self) -> None:
        text = f"```json\n{_payload(_row('doi:10.1/a'))}\n```"
        assert len(parse_output(text, _request())) == 1

    def test_tolerates_chatter_around_the_json(self) -> None:
        text = f"好的，判定如下：\n{_payload(_row('doi:10.1/a'))}\n以上。"
        assert len(parse_output(text, _request())) == 1

    def test_drops_keys_that_were_not_in_the_batch(self) -> None:
        """挂在不存在 key 上的判定永远匹配不上记录，表现为"筛完了但计数对不上"。"""
        text = _payload(_row("doi:10.1/a"), _row("doi:10.9/invented"))
        assert [item.record_key for item in parse_output(text, _request())] == ["doi:10.1/a"]

    def test_drops_duplicates(self) -> None:
        text = _payload(_row("doi:10.1/a"), _row("doi:10.1/a", decision="exclude"))
        verdicts = parse_output(text, _request())
        assert len(verdicts) == 1
        assert verdicts[0].decision == "include"

    def test_stamps_the_channel_from_the_request(self) -> None:
        """通道是请求的属性，不能让模型填——续跑判据全靠它。"""
        request = ScreeningRequest("c1-b0", 1, 0, "s", "u", ("doi:10.1/a",))
        assert parse_output(_payload(_row("doi:10.1/a")), request)[0].channel == 1

    def test_unreadable_confidence_becomes_zero_not_one(self) -> None:
        """读不出置信度就落进人工队列；给 1.0 会让来路不明的判定绕过所有安全网。"""
        text = _payload(_row("doi:10.1/a", confidence="很高"))
        assert parse_output(text, _request())[0].confidence == 0.0

    def test_confidence_is_clamped(self) -> None:
        text = _payload(_row("doi:10.1/a", confidence=7))
        assert parse_output(text, _request())[0].confidence == 1.0

    def test_missing_verdicts_key_yields_nothing_rather_than_crashing(self) -> None:
        assert parse_output('{"ok": true}', _request()) == []

    def test_non_json_raises(self) -> None:
        with pytest.raises(HostBackendError):
            parse_output("我不确定该怎么判。", _request())

    def test_field_name_matches_the_api_backend_schema(self) -> None:
        """两条后端必须产出结构相同的判定，否则同一个 run 会有两种格式的判定文件。"""
        assert '"record_key"' in build_prompt(_request())

    def test_partial_batch_is_kept(self) -> None:
        """模型漏写一条时保留另一条——漏的会在续跑时被补判，不该整批作废。"""
        assert len(parse_output(_payload(_row("doi:10.1/a")), _request())) == 1


class TestEstimateCalls:
    def test_rounds_up(self) -> None:
        assert estimate_calls(61, 1, batch_size=60) == 2

    def test_multiplies_by_channels(self) -> None:
        assert estimate_calls(120, 2, batch_size=60) == 4

    def test_zero_records(self) -> None:
        assert estimate_calls(0, 2) == 0

    def test_host_batches_are_much_larger_than_api_batches(self) -> None:
        """框架开销按次算（实测约 20k token/次），批大才摊得薄。"""
        assert HOST_BATCH_SIZE >= 50


class TestHostUsage:
    def test_adds_up(self) -> None:
        total = HostUsage(calls=1, output_tokens=10, cost_usd=0.02) + HostUsage(
            calls=1, output_tokens=5, cost_usd=0.01
        )
        assert total.calls == 2
        assert total.output_tokens == 15
        assert total.cost_usd == pytest.approx(0.03)
