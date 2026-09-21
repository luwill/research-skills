"""随包分发的 skill 副本必须与根目录逐字节一致。

`.claude/skills/lit-search/` 是整个项目的一份副本，用户装 skill 时拿到的是它。
两边漂移的后果很隐蔽：用户照着 README 跑，行为却和仓库里的代码不一样，而两份
代码看起来都对。历史上它已经漂过一次（根目录给 OpenAlex 请求加了 api_key 透传，
副本没跟上），是靠人工 diff 才发现的。

这个测试把"记得同步"从纪律变成硬检查。副本不存在时跳过——开发仓库里可能没打包。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VENDORED = ROOT / ".claude" / "skills" / "lit-search"
#: 必须逐字节一致的目录。examples/ 与 topics/ 不比——副本只随附部分样例协议。
MIRRORED = ("src/litsearch", "tests")
SKIP = {"__pycache__", ".pytest_cache", ".DS_Store"}

needs_vendored = pytest.mark.skipif(
    not VENDORED.exists(), reason="开发仓库里没有打包出的 skill 副本"
)


def _fingerprint(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        found[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


@needs_vendored
@pytest.mark.parametrize("folder", MIRRORED)
def test_the_vendored_copy_matches_the_repository(folder: str):
    here = _fingerprint(ROOT / folder)
    there = _fingerprint(VENDORED / folder)

    missing = sorted(set(here) - set(there))
    extra = sorted(set(there) - set(here))
    changed = sorted(name for name in set(here) & set(there) if here[name] != there[name])

    assert not (missing or extra or changed), (
        f"{folder} 与 skill 副本不一致——用户装到的将是另一份代码。\n"
        f"  副本里缺少：{missing}\n  副本里多出：{extra}\n  内容不同：{changed}\n"
        f"同步命令：rsync -a --delete --exclude='__pycache__' --exclude='.pytest_cache' "
        f"{folder}/ .claude/skills/lit-search/{folder}/"
    )


@needs_vendored
def test_the_copy_is_not_silently_empty():
    """副本目录存在但内容为空，会让上面的比对变成一句空话。"""
    assert len(_fingerprint(VENDORED / "src/litsearch")) > 10
