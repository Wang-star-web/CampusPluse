"""统一消息外壳（A00 阶段01）。

每条 MQTT 消息都必须携带五字段信封；object_type 未知或时间戳非法会被整体拒绝。
阶段02 起 observations 表的 value_json 即本信封的 data 字段，字段设计为其服务。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ObjectType(str, Enum):
    crowd = "crowd"                  # 人群数量
    entrance = "entrance"            # 入口
    main_route = "main_route"        # 主要路线
    support = "support"              # 支持人员


class ObservationEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")  # 前向兼容：忽略信封未来新增的字段

    activity_id: str
    object_type: ObjectType                     # 未知 object_type 直接拒绝
    observed_at: datetime | None = None         # 阶段02：失败信封显式 null（不伪造新时间）
    source_type: Literal["SIMULATED"]           # 本阶段唯一来源；阶段05 起扩展枚举值
    data: dict[str, Any] | None = None          # 原始业务值；失败时 null。阶段01 旧消息不带新字段仍合法
    retrieval_status: Literal["unavailable", "error"] | None = None   # None = 成功消息
    error_message: str | None = None            # error 必填；ok/unavailable 必须为 null

    @model_validator(mode="after")
    def _check_retrieval_consistency(self):
        if self.retrieval_status is None:
            # 成功业务消息：observed_at 与 data 必填，且不得携带错误说明
            if self.observed_at is None or self.data is None:
                raise ValueError("成功信封必须携带 observed_at 与 data")
            if self.error_message is not None:
                raise ValueError("成功信封不得携带 error_message")
        else:
            # 取证失败信号：结构上禁止携带业务值（不伪造 value，不伪造 observed_at）
            if self.observed_at is not None or self.data is not None:
                raise ValueError("失败信封不得携带业务值（observed_at/data 必须为 null）")
            if self.retrieval_status == "error" and not self.error_message:
                raise ValueError("status=error 必须携带 error_message")
            if self.retrieval_status == "unavailable" and self.error_message is not None:
                raise ValueError("status=unavailable 不得携带 error_message")
        return self


def envelope_to_dict(env: ObservationEnvelope) -> dict:
    """转为 JSON 可序列化 dict（observed_at 字符串化、object_type 取 value）。"""
    return {
        "activity_id": env.activity_id,
        "object_type": env.object_type.value,
        "observed_at": env.observed_at.isoformat(),
        "source_type": env.source_type,
        "data": env.data,
    }


class SimMode(BaseModel):
    """取证模式（阶段02）：按对象切换 ok / unavailable / error。

    unavailable/error 只影响"本次取证是否成功"，绝不改变业务值本身。
    extra="forbid"：mode 内打错键名（如 mode.foo）会 422 而不是被静默忽略。
    """

    model_config = ConfigDict(extra="forbid")

    crowd: Literal["ok", "unavailable", "error"] = "ok"
    entrance: Literal["ok", "unavailable", "error"] = "ok"
    main_route: Literal["ok", "unavailable", "error"] = "ok"
    support: Literal["ok", "unavailable", "error"] = "ok"


class SimConfig(BaseModel):
    """模拟器配置（POST /api/sim/set 请求体）。

    4 个基础字段全部必填（无默认值）：打错字段名（如 entrance）会 422 而不是被静默忽略。
    取值集合是阶段01表格的超集：support=12 无预设按钮，但仍可经 API 设置。
    mode 可选（缺省全 ok）：**全量替换语义**——POST 不带 mode 会把各对象模式重置为 ok。
    """

    crowd: Literal[300, 500, 650, 750, 900]
    entrance_available: Literal[1, 2]
    main_route: Literal["normal", "limited"]
    support: Literal[8, 10, 12]
    mode: SimMode = SimMode()


class TeachingConfig(BaseModel):
    """阶段03 教学约束参数（独立 config.json 加载）。

    只用于 CampusPulse 教学场景，不代表真实行业标准。
    """

    capacity: int = Field(gt=0)          # 场地容量
    entrance_total: int = Field(gt=0)    # 入口总数（entrance_ratio 的分母）
    support_reference: int = Field(gt=0) # 支持人员教学参考值


class DerivedEntranceState(BaseModel):
    """入口输入状态：available 为本次观察到可用入口数；total 为教学参数，来自 config。"""

    available: int = Field(ge=0)


class DerivedInput(BaseModel):
    """POST /api/compute-derived 请求体：各对象最新有效业务状态（来自 observations）。"""

    crowd: int = Field(ge=0)
    entrance: DerivedEntranceState
    main_route: Literal["normal", "limited"]
    support: int = Field(ge=0)


class RunRequest(BaseModel):
    """POST /api/runs 请求体：一组业务状态 + 关联证据 id 列表（阶段04/05 reality 运行）。

    evidence_refs 中的每个 id 必须存在于 evidence 表且 status=ok（引用必须指向真实成功证据）；
    阶段05 起可混入 current_fact / future_condition / knowledge_basis 各类证据引用。
    """

    scenario_id: str | None = None      # 教学场景标识（如 S1/S2/S3）；reality 运行可空
    states: DerivedInput
    evidence_refs: list[str] = []


class RagQuery(BaseModel):
    """POST /api/tools/rag 请求体。"""

    query: str = Field(min_length=1)
