"""TypeSafe Jev 判定 API 客户端。

回放录制的真实应答，不打网络。

这个客户端和检索源共用 ``HttpClient`` 的重试循环，所以这里只测**它自己新增**的
那部分：鉴权、请求体形状、应答校验，以及"哪些错误该整轮中止而不是逐条标失败"。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from litsearch.jev_client import (
    JEV_PINNED,
    JEV_URL,
    JevClient,
    JevError,
    JevFatalError,
    build_jev_client,
)
from litsearch.sources.base import HttpClient, QuotaExhausted, RateLimiter

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "jev_response.json").read_text(encoding="utf-8")
)
QUESTIONS = {
    "I1": {"type": "noul", "instructions": "人类缺血性卒中影像？"},
    "I2": {"type": "noul", "instructions": "存在病灶级别分割？"},
    "pub_type": {"type": "choice", "instructions": "文献类型？", "criteria": {"a": "x"}},
}
STATE = {"title": "A paper", "abstract": "..."}


def client(**kwargs) -> JevClient:
    http = HttpClient(
        httpx.AsyncClient(timeout=5.0),
        rate_limiter=RateLimiter(min_interval=0.0),
        backoff_base=0.0,
        max_attempts=kwargs.pop("max_attempts", 2),
    )
    return JevClient(http, api_key="k-secret", **kwargs)


class TestRequestShape:
    @respx.mock
    async def test_sends_state_model_and_questions_with_a_bearer_token(self):
        route = respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=FIXTURE))

        await client().ask(STATE, QUESTIONS)

        request = route.calls[0].request
        assert request.headers["authorization"] == "Bearer k-secret"
        body = json.loads(request.content)
        assert body["state"] == STATE
        assert body["model"] == JEV_PINNED
        assert set(body["questions"]) == set(QUESTIONS)

    @respx.mock
    async def test_the_model_is_pinned_by_default(self):
        """别名会随新版发布漂移。阈值是在某个具体版本上调出来的，必须钉住。"""
        route = respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=FIXTURE))

        await client().ask(STATE, QUESTIONS)

        assert json.loads(route.calls[0].request.content)["model"] == "jev-1.13.0"

    @respx.mock
    async def test_an_explicit_model_overrides_the_pin(self):
        route = respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=FIXTURE))

        await client(model="jev-latest").ask(STATE, QUESTIONS)

        assert json.loads(route.calls[0].request.content)["model"] == "jev-latest"


class TestResponse:
    @respx.mock
    async def test_exposes_answers_usage_and_the_versioned_model(self):
        respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=FIXTURE))

        reply = await client().ask(STATE, QUESTIONS)

        assert reply.model == "jev-1.13.0"
        assert reply.input_tokens == 1149
        assert reply.output_tokens == 67
        assert reply.noul("I1") == 0.99

    @respx.mock
    async def test_noul_on_a_choice_question_is_a_programming_error(self):
        respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=FIXTURE))

        reply = await client().ask(STATE, QUESTIONS)

        with pytest.raises(JevError, match="不是 noul"):
            reply.noul("pub_type")

    @respx.mock
    async def test_a_missing_answer_is_refused_rather_than_defaulted(self):
        """漏答一条标准就当它是 0，会把一篇该纳入的论文静默排掉。"""
        partial = {**FIXTURE, "answers": {"I1": FIXTURE["answers"]["I1"]}}
        respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=partial))

        with pytest.raises(JevError, match="未作答"):
            await client().ask(STATE, QUESTIONS)

    @respx.mock
    async def test_a_noul_outside_zero_to_one_is_refused(self):
        broken = {
            **FIXTURE,
            "answers": {**FIXTURE["answers"], "I2": {"type": "noul", "noul": 1.4}},
        }
        respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=broken))

        with pytest.raises(JevError, match="超出"):
            await client().ask(STATE, QUESTIONS)

    @respx.mock
    async def test_a_reply_without_a_model_field_is_refused(self):
        """轮次要记录到底是哪个版本判的，缺这个字段审计链就断了。"""
        anonymous = {key: value for key, value in FIXTURE.items() if key != "model"}
        respx.post(JEV_URL).mock(return_value=httpx.Response(200, json=anonymous))

        with pytest.raises(JevError, match="model"):
            await client().ask(STATE, QUESTIONS)


class TestFailureModes:
    @respx.mock
    async def test_an_auth_failure_aborts_the_whole_round(self):
        """key 错了就是每一条都会错。逐条标失败会产出一份"全部待人工"的假结果。"""
        route = respx.post(JEV_URL).mock(return_value=httpx.Response(401, text="bad key"))

        with pytest.raises(JevFatalError):
            await client().ask(STATE, QUESTIONS)

        assert route.call_count == 1

    @respx.mock
    @pytest.mark.parametrize("status", [400, 403, 404, 422])
    async def test_other_client_errors_are_fatal_too(self, status: int):
        respx.post(JEV_URL).mock(return_value=httpx.Response(status, text="nope"))

        with pytest.raises(JevFatalError):
            await client().ask(STATE, QUESTIONS)

    @respx.mock
    async def test_a_transient_429_is_retried_then_succeeds(self):
        respx.post(JEV_URL).mock(
            side_effect=[httpx.Response(429), httpx.Response(200, json=FIXTURE)]
        )

        reply = await client().ask(STATE, QUESTIONS)

        assert reply.noul("I1") == 0.99

    @respx.mock
    async def test_a_long_retry_after_surfaces_as_quota_exhaustion(self):
        respx.post(JEV_URL).mock(
            return_value=httpx.Response(429, headers={"retry-after": "3600"})
        )

        with pytest.raises(QuotaExhausted):
            await client().ask(STATE, QUESTIONS)

    @respx.mock
    async def test_a_persistent_server_error_is_retryable_not_fatal(self):
        """5xx 可能只是这一条赶上了。整轮中止太重，交给上层记为失败条目。"""
        respx.post(JEV_URL).mock(return_value=httpx.Response(503))

        with pytest.raises(JevError) as caught:
            await client().ask(STATE, QUESTIONS)

        assert not isinstance(caught.value, JevFatalError)


class TestBuildClient:
    def test_rate_limit_is_enforced_below_the_documented_ceiling(self):
        """实测 6 并发裸跑约 23 req/s，已超文档的 1200 req/min。"""
        judge, _ = build_jev_client("k", rate_per_second=16.0)

        assert judge._http._rate_limiter.min_interval == pytest.approx(1 / 16)

    def test_the_caller_owns_the_key_the_client_never_reads_the_environment(
        self, monkeypatch
    ):
        monkeypatch.setenv("TYPESAFE_API_KEY", "env-key-must-not-be-used")

        judge, _ = build_jev_client("explicit-key")

        assert judge._api_key == "explicit-key"

    def test_an_empty_key_is_refused_up_front(self):
        with pytest.raises(ValueError, match="API key"):
            build_jev_client("")
