"""Jev 判定配置：阈值、跳过哪些标准、排除标准怎么用。

**为什么不放进 topic.yaml。** ``protocol_fingerprint`` 哈希的是含默认值的
``model_dump``，给协议加任何一个可选字段——哪怕默认是 ``None``——都会让所有历史
run 的指纹对不上，被 ``assert_topic_compatible`` 挡死，``screen`` /
``adjudicate`` / ``report`` / ``validate`` / ``snowball`` 全部失效。而阈值是要
反复调的，每调一次废掉一次 run 更不可接受。

所以它单独成文件，约定放在 ``topics/<id>.jev.yaml``，内容随轮次记进
``parameters``——协议管"判什么"，这份配置管"怎么分档"，两者本就不是一件事。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, ValidationError, model_validator

from litsearch.facets import FacetQuestion
from litsearch.jev_client import JEV_PINNED
from litsearch.protocol import Criterion, ProtocolError, ProtocolModel, Topic


class JevProfile(ProtocolModel):
    """一个课题的判定分档配置。

    ``extra="forbid"`` 继承自 ``ProtocolModel``：拼错的键名被静默忽略，
    等于让整套阈值无声失效。
    """

    #: 必须与协议的 id 一致。拿错配置去跑，阈值就完全不是为这批标准调的。
    topic_id: str
    #: 钉带版本的模型 id。别名随新版漂移 = 悄悄换掉判定标准。
    model: str = JEV_PINNED
    include_at: float = Field(default=0.7, ge=0.0, le=1.0)
    exclude_below: float = Field(default=0.1, ge=0.0, le=1.0)
    #: 只有读全文才判得了的标准（如"报告了 Dice/HD95"）。放着不跳，
    #: 它会把每一篇正经论文的分数都压下去。
    skip: list[str] = Field(default_factory=list)
    #: 排除标准怎么用。``annotate``：只记进 reason 供人看，不参与打分；
    #: ``ignore``：连问都不问。**默认不参与打分**——实测把分数乘上
    #: ``(1 - max 排除概率)`` 反而更差，官方文档也说一个问题与其否定式的
    #: 概率不满足互补关系。
    exclusions: Literal["ignore", "annotate"] = "annotate"
    #: 摘要截断长度。state 越大判别力越差（官方称之为 context rot）。
    max_abstract_chars: int = Field(default=6000, ge=200)
    #: ``lit facets`` 给已纳入记录打的标注维度。留空则用 facets.py 里随附的那一组。
    facets: list[FacetQuestion] = Field(default_factory=list)
    #: 标注的判定阈值。只影响 stated / not_stated 这一刀切在哪，原始概率始终保留。
    facet_at: float = Field(default=0.7, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _facet_ids_are_unique(self) -> JevProfile:
        seen = [facet.id for facet in self.facets]
        if len(seen) != len(set(seen)):
            duplicates = sorted({item for item in seen if seen.count(item) > 1})
            raise ProtocolError(f"标注维度 id 重复：{duplicates}——重名会让其中一个静默丢失")
        return self

    @model_validator(mode="after")
    def _bands_leave_room_for_the_queue(self) -> JevProfile:
        if not self.exclude_below < self.include_at:
            raise ValueError(
                f"exclude_below 必须小于 include_at，否则没有任何记录会进人工队列；"
                f"收到 exclude_below={self.exclude_below}、include_at={self.include_at}"
            )
        return self

    def active_inclusions(self, topic: Topic) -> list[Criterion]:
        return [item for item in topic.criteria.include if item.id not in set(self.skip)]

    def active_exclusions(self, topic: Topic) -> list[Criterion]:
        if self.exclusions == "ignore":
            return []
        return [item for item in topic.criteria.exclude if item.id not in set(self.skip)]

    def sha256(self) -> str:
        """配置内容的哈希，随轮次存档。阈值变了，轮次就该看得出来。"""
        payload = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, default=str
        )
        return hashlib.sha256(payload.encode()).hexdigest()


def load_profile(path: str | Path, topic: Topic) -> JevProfile:
    """读判定配置并对着协议校验。任何不一致都当场拒绝。"""
    profile_path = Path(path)
    try:
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ProtocolError(f"无法读取判定配置 {profile_path}：{error}") from error
    except yaml.YAMLError as error:
        raise ProtocolError(f"判定配置 {profile_path} 不是合法 YAML：{error}") from error
    if not isinstance(raw, dict):
        raise ProtocolError(f"判定配置 {profile_path} 必须是一个映射")

    try:
        profile = JevProfile.model_validate(raw)
    except ValidationError as error:
        raise ProtocolError(f"判定配置 {profile_path} 不合法：{error}") from error

    if profile.topic_id != topic.id:
        raise ProtocolError(
            f"判定配置的 topic_id 是 {profile.topic_id!r}，协议是 {topic.id!r}——"
            f"阈值是为某一套纳排标准调的，配错了就完全不成立"
        )

    known = {item.id for item in topic.criteria.include} | {
        item.id for item in topic.criteria.exclude
    }
    if unknown := [item for item in profile.skip if item not in known]:
        raise ProtocolError(
            f"skip 里有协议中不存在的标准编号：{unknown}。"
            f"写错编号等于悄悄放开一条标准。协议现有：{sorted(known)}"
        )

    if not profile.active_inclusions(topic):
        raise ProtocolError(
            "所有纳入标准都被 skip 了，分数无从谈起——每条记录都会得到同一个值"
        )
    return profile
