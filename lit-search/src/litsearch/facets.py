"""给已纳入的记录打类型化标注。

**只标注，不过滤，也不进证据表。** ``report.py`` 明令禁止猜测只有全文才知道的
字段，所以这一层的产物是独立文件，供人筛选和排序，不参与任何自动判定。

措辞纪律：每个问题都问「摘要**明确陈述**了 X 吗」，答案只有 ``stated`` /
``not_stated``，**永远没有 no**。摘要没提外部验证，不等于这篇研究没做外部验证——
它只是没在摘要里说。把「没说」记成「没有」，是这一层最容易犯、也最难被发现的错：
产出的表看起来完全正常，只是每一个 no 都可能是假的。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import model_validator

from litsearch.dedupe import CanonicalRecord
from litsearch.protocol import ProtocolError, ProtocolModel

STATED = "stated"
NOT_STATED = "not_stated"
UNSCORED = "未标注"

#: 措辞必须同时出现这两个词。这不是风格要求——它是「问摘要说了什么」和
#: 「问世界是什么样」之间的分界线，而后者摘要根本答不了。
_REQUIRED_WORDING = ("摘要", "明确")


class FacetQuestion(ProtocolModel):
    id: str
    ask: str

    @model_validator(mode="after")
    def _wording(self) -> FacetQuestion:
        missing = [word for word in _REQUIRED_WORDING if word not in self.ask]
        if missing:
            raise ProtocolError(
                f"标注问题 {self.id!r} 的措辞缺少 {missing}。必须问「摘要是否**明确**陈述了 X」"
                f"而不是「这项研究是否做了 X」——后者摘要答不了，只会把「没说」变成「没有」。"
            )
        return self


#: 随附的一组通用标注，对照 CLAIM / TRIPOD+AI 这类报告规范里最常被问到的几项。
#: 它们是起点不是定论：课题特有的维度请在判定配置的 ``facets`` 里覆盖。
DEFAULT_FACETS: tuple[FacetQuestion, ...] = (
    FacetQuestion(
        id="external_validation",
        ask="摘要是否明确陈述了在训练数据之外的独立数据集上做过评估（外部验证）？",
    ),
    FacetQuestion(id="multi_center", ask="摘要是否明确陈述了数据来自多个中心或多家机构？"),
    FacetQuestion(id="public_dataset", ask="摘要是否明确陈述了使用公开数据集？"),
    FacetQuestion(id="code_available", ask="摘要是否明确陈述了代码或模型权重公开可获取？"),
    FacetQuestion(id="prospective", ask="摘要是否明确陈述了前瞻性的研究设计？"),
)


@dataclass(frozen=True, slots=True)
class FacetRow:
    record_key: str
    model: str
    questions_sha256: str
    answers: Mapping[str, float]
    input_tokens: int

    def to_json(self) -> dict:
        return {
            "record_key": self.record_key,
            "model": self.model,
            "questions_sha256": self.questions_sha256,
            "answers": dict(self.answers),
            "input_tokens": self.input_tokens,
        }

    @classmethod
    def from_json(cls, payload: Mapping) -> FacetRow:
        return cls(
            record_key=payload["record_key"],
            model=payload.get("model", ""),
            questions_sha256=payload.get("questions_sha256", ""),
            answers={key: float(value) for key, value in (payload.get("answers") or {}).items()},
            input_tokens=int(payload.get("input_tokens") or 0),
        )


def active_facets(profile) -> tuple[FacetQuestion, ...]:
    """配置里写了就用配置的，没写就用随附的那一组。"""
    return tuple(profile.facets) if profile.facets else DEFAULT_FACETS


def compile_facet_questions(profile) -> dict[str, dict]:
    return {
        facet.id: {"type": "noul", "instructions": facet.ask} for facet in active_facets(profile)
    }


def facet_questions_sha256(questions: Mapping[str, dict]) -> str:
    payload = json.dumps(questions, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def facet_label(value: float, *, threshold: float) -> str:
    """概率转标签。低概率是「摘要没说」，**不是**「研究没做」。"""
    return STATED if value >= threshold else NOT_STATED


def facets_for(row: FacetRow, profile) -> dict[str, str]:
    """模型没答的维度**不出现**在结果里，而不是补一个猜测值。"""
    return {
        facet.id: facet_label(row.answers[facet.id], threshold=profile.facet_at)
        for facet in active_facets(profile)
        if facet.id in row.answers
    }


def facets_csv(
    rows: Mapping[str, FacetRow], records: Sequence[CanonicalRecord], profile
) -> str:
    """每条已纳入记录一行。标签与**原始概率**都留着——标签只是阈值切出来的一刀，
    切在哪里是可以改的，把概率丢掉就改不动了。"""
    facets = active_facets(profile)
    columns = [part for facet in facets for part in (facet.id, f"{facet.id}_p")]
    lines = [",".join(["record_key", "doi", *columns, "title"])]
    for record in records:
        row = rows.get(record.key)
        title = record.title.replace('"', "'")
        doi = record.identifiers.get("doi", "")
        if row is None:
            cells = [UNSCORED, ""] * len(facets)
        else:
            labels = facets_for(row, profile)
            cells = []
            for facet in facets:
                probability = row.answers.get(facet.id)
                cells.append(labels.get(facet.id, UNSCORED))
                cells.append("" if probability is None else f"{probability:.3f}")
        lines.append(",".join([record.key, doi, *cells, f'"{title}"']))
    return "\n".join(lines) + "\n"


async def score_facets(
    client,
    records: Sequence[CanonicalRecord],
    profile,
    *,
    state_of,
    concurrency: int = 16,
    on_error=None,
    checkpoint=None,
    progress=None,
) -> tuple[list[FacetRow], int]:
    """给记录打标注。

    ``state_of`` 由调用方传入而不是在这里 import——否则
    ``screen_jev → jev_profile → facets → screen_jev`` 就绕成环了。
    """
    from litsearch.jev_client import ask_each

    questions = compile_facet_questions(profile)
    digest = facet_questions_sha256(questions)

    def to_row(judged) -> FacetRow:
        return FacetRow(
            record_key=judged.key,
            model=judged.reply.model,
            questions_sha256=digest,
            answers=judged.reply.nouls(),
            input_tokens=judged.reply.input_tokens,
        )

    judged, tokens = await ask_each(
        client,
        [(item.key, state_of(item)) for item in records],
        questions,
        concurrency=concurrency,
        on_error=on_error,
        checkpoint=(lambda item: checkpoint(to_row(item))) if checkpoint else None,
        progress=progress,
    )
    return [to_row(item) for item in judged], tokens


def pending_facets(
    records: Sequence[CanonicalRecord], rows: Mapping[str, FacetRow], questions_hash: str
) -> list[CanonicalRecord]:
    """还没按当前问题集标注过的记录。问题集改了，旧标注就不再对应同一组维度。"""
    return [
        item
        for item in records
        if (row := rows.get(item.key)) is None or row.questions_sha256 != questions_hash
    ]
