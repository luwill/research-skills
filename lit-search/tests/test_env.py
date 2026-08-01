"""`.env` 加载与凭据解析。

凭据只从环境或 `.env` 读，绝不写进代码或协议文件。``.env`` 的容错要足够——
用户手写的文件里 `KEY = value`（等号两边有空格）、行尾注释、引号都很常见，
解析不到就会变成"没配 key"，然后源静默降级成匿名限速，最后表现为少召回。
"""

from __future__ import annotations

from litsearch.envfile import load_env_file
from litsearch.sources.registry import Credentials


class TestLoadEnvFile:
    def test_reads_plain_pairs(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\nB=2\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "1", "B": "2"}

    def test_tolerates_spaces_around_the_equals_sign(self, tmp_path):
        """手写的 .env 里 `KEY = value` 很常见，按裸 split 会得到带空格的 key。"""
        path = tmp_path / ".env"
        path.write_text("OPENALEX_API = axJ123\n", encoding="utf-8")

        assert load_env_file(path) == {"OPENALEX_API": "axJ123"}

    def test_strips_quotes_and_export_prefix(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("export A=\"q\"\nB='s'\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "q", "B": "s"}

    def test_ignores_comments_and_blank_lines(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("# 注释\n\nA=1\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "1"}

    def test_a_line_without_an_equals_sign_is_skipped(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("garbage\nA=1\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "1"}

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        assert load_env_file(tmp_path / "nope.env") == {}

    def test_values_containing_equals_are_preserved(self, tmp_path):
        """base64 结尾的 `=` 很常见，只能按第一个等号切。"""
        path = tmp_path / ".env"
        path.write_text("A=abc==\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "abc=="}


class TestCredentials:
    def test_openalex_key_is_picked_up_from_the_env_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("LITSEARCH_OPENALEX_API_KEY", raising=False)
        path = tmp_path / ".env"
        path.write_text("OPENALEX_API = axJsecret\n", encoding="utf-8")

        credentials = Credentials.from_env(env_file=path)

        assert credentials.api_keys["openalex"] == "axJsecret"

    def test_the_real_environment_wins_over_the_file(self, tmp_path, monkeypatch):
        """显式导出的环境变量优先——临时换 key 不该被文件里的旧值盖掉。"""
        monkeypatch.setenv("LITSEARCH_OPENALEX_API_KEY", "from-env")
        path = tmp_path / ".env"
        path.write_text("OPENALEX_API=from-file\n", encoding="utf-8")

        credentials = Credentials.from_env(env_file=path)

        assert credentials.api_keys["openalex"] == "from-env"

    def test_deepseek_key_is_read(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        path = tmp_path / ".env"
        path.write_text("DEEPSEEK_API_KEY=sk-abc\n", encoding="utf-8")

        assert Credentials.from_env(env_file=path).api_keys["deepseek"] == "sk-abc"

    def test_absent_keys_simply_do_not_appear(self, tmp_path):
        credentials = Credentials.from_env(env_file=tmp_path / "nope.env")

        assert "openalex" not in credentials.api_keys
