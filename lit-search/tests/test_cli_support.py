"""CLI 各命令共用的助手。

重点是 ``latest_round_judge``：它决定能不能续跑。判错的后果是把两个不同判定器的
结果合并成一条看起来像双通道、实际不是的判定——而它和真的长得一模一样。
"""

from __future__ import annotations

import json

import pytest

from litsearch.cli_support import latest_round_judge
from litsearch.run import Run


@pytest.fixture
def run(tmp_path) -> Run:
    return Run.create(tmp_path / "runs", "t", "20200101T000000Z")


def write_round(run: Run, number: int, **payload) -> None:
    body = {"number": number, "topic_sha256": "a" * 64, "decisions": {}, **payload}
    run.write_text(f"screening_round_{number}.json", json.dumps(body, ensure_ascii=False))


class TestLatestRoundJudge:
    def test_no_rounds_means_no_judge(self, run):
        assert latest_round_judge(run) is None

    def test_a_dual_channel_llm_round_has_no_judge_marker(self, run):
        write_round(run, 1, provider="api.deepseek.com", parameters={"channels": 2})

        assert latest_round_judge(run) is None

    def test_a_jev_round_reports_its_judge(self, run):
        write_round(run, 1, provider="api.typesafe.ai", parameters={"judge": "jev"})

        assert latest_round_judge(run) == "jev"

    def test_a_human_adjudication_round_does_not_change_the_judge(self, run):
        """裁定轮次是加在模型轮次之上的一层，它本身不判筛选。"""
        write_round(run, 1, provider="api.typesafe.ai", parameters={"judge": "jev"})
        write_round(run, 2, provider="human", parameters={"kind": "screening"})

        assert latest_round_judge(run) == "jev"

    def test_a_machine_triage_round_does_not_change_the_judge_either(self, run):
        """分诊轮次同理：它只解开队列里的僵局，不重判整批记录。

        不跳过它的话，判定器名字会从 "jev" 变成 "jev:jev-1.13.0"，
        于是一次完全正当的 --resume 会被误拦。
        """
        write_round(run, 1, provider="api.typesafe.ai", parameters={"judge": "jev"})
        write_round(
            run,
            2,
            provider="jev:jev-1.13.0",
            parameters={"kind": "triage", "judge": "jev:jev-1.13.0"},
        )

        assert latest_round_judge(run) == "jev"

    def test_the_newest_model_round_wins(self, run):
        write_round(run, 1, provider="api.typesafe.ai", parameters={"judge": "jev"})
        write_round(run, 2, provider="api.deepseek.com", parameters={"channels": 2})

        assert latest_round_judge(run) is None

    def test_round_numbers_sort_numerically_not_lexically(self, run):
        """轮次 10 必须排在轮次 9 之后，否则守卫会看着一轮很老的判定做决定。"""
        write_round(run, 9, provider="api.deepseek.com", parameters={"channels": 2})
        write_round(run, 10, provider="api.typesafe.ai", parameters={"judge": "jev"})

        assert latest_round_judge(run) == "jev"
