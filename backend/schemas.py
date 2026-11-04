"""统一消息外壳（A00 阶段01）。

每条 MQTT 消息都必须携带五字段信封；object_type 未知或时间戳非法会被整体拒绝。
阶段02 起 observations 表的 value_json 即本信封的 data 字段，字段设计为其服务。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class ObjectType(str, Enum):
    crowd = "crowd"                  # 人群数量
    entrance = "entrance"            # 入口
    main_route = "main_route"        # 主要路线
    support = "support"              # 支持人员


class ObservationEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")  # 前向兼容：忽略信封未来新增的字段

    activity_id: str
    object_type: ObjectType                     # 未知 object_type 直接拒绝
    observed_at: datetime                       # ISO8601；非法时间戳拒绝
    source_type: Literal["SIMULATED"]           # 本阶段唯一来源；阶段05 起扩展枚举值
    data: dict[str, Any]                        # 原始业务值 → 阶段02 直接映射 value_json


def envelope_to_dict(env: ObservationEnvelope) -> dict:
    """转为 JSON 可序列化 dict（observed_at 字符串化、object_type 取 value）。"""
    return {
        "activity_id": env.activity_id,
        "object_type": env.object_type.value,
        "observed_at": env.observed_at.isoformat(),
        "source_type": env.source_type,
        "data": env.data,
    }
