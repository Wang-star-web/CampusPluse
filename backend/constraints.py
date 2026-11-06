"""阶段03 显式约束与派生结果（A00）。

规则：状态 + 证据 → 约束 → 派生结果。
本阶段只计算派生结果，禁止生成局部影响（impact）与整体态势（situation）；run_id 属阶段04。

教学参数从独立配置文件 config.json 加载（教学参数，不是行业标准），
不散落在任何页面/函数里；每次计算读取同一份参数。
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .schemas import DerivedInput, TeachingConfig

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

# 主路线 → 通行灵活性映射（阶段03 仅此两条；阶段04 才解释"灵活性下降"意味着什么）
ROUTE_FLEXIBILITY = {
    "normal": "normal",
    "limited": "reduced",
}


def load_config() -> TeachingConfig:
    """读取并校验教学约束参数；文件缺失/非法时抛 ValueError（接口 500 并说明，绝不静默用默认值）。"""
    try:
        text = CONFIG_PATH.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"约束配置文件不可读: {CONFIG_PATH} ({e})") from e
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"约束配置文件不是合法 JSON: {CONFIG_PATH} ({e})") from e
    try:
        return TeachingConfig.model_validate(raw)
    except Exception as e:
        raise ValueError(f"约束配置文件字段非法: {CONFIG_PATH} ({e})") from e


def compute_derived(states: DerivedInput) -> dict:
    """按显式约束计算结构化派生结果（只算派生结果，不做影响/态势解读）。

    返回分层结构：config（本次使用的约束参数）/ states（回显输入状态）/
    derived（派生结果）/ computed_at。原始状态与派生结果分层，不混层。
    """
    cfg = load_config()

    remaining_capacity = cfg.capacity - states.crowd
    remaining_capacity_ratio = remaining_capacity / cfg.capacity

    entrance_ratio = states.entrance.available / cfg.entrance_total

    support_gap = cfg.support_reference - states.support
    support_ratio = states.support / cfg.support_reference

    route_flexibility = ROUTE_FLEXIBILITY[states.main_route]

    return {
        "activity_id": "campus_open_day_01",
        "config": {
            "capacity": cfg.capacity,
            "entrance_total": cfg.entrance_total,
            "support_reference": cfg.support_reference,
        },
        "states": {
            "crowd": states.crowd,
            "entrance": {"available": states.entrance.available},
            "main_route": states.main_route,
            "support": states.support,
        },
        "derived": {
            "capacity": {
                "remaining_capacity": remaining_capacity,
                "remaining_capacity_ratio": remaining_capacity_ratio,
            },
            "entrance": {"entrance_ratio": entrance_ratio},
            "support": {
                "support_gap": support_gap,
                "support_ratio": support_ratio,
            },
            "route": {"route_flexibility": route_flexibility},
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
