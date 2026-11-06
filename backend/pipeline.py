"""分析管线纯函数（阶段08 抽出，供 API 与回归脚本共用同一套生产逻辑）。

固定链：状态+证据 → 约束 → 派生结果 → 局部影响 → 整体态势。
四个视图读取同一个 run 的结构化结果，任何地方都不重新计算另一套态势。
"""

from .constraints import compute_derived
from .schemas import DerivedInput
from .situation import build_impacts, build_situation


def run_analysis(states: DerivedInput, refs_norm: dict) -> dict:
    """执行完整分析（不落库）：返回 {states, config, derived, impacts, situation,
    unknown_items, situation_completeness}。

    refs_norm: {key: {"evidence_id", "status"}}（已归一化的证据引用）。
    unknown/affected 规则（与官方 S5 语义一致）：
    - future_condition 引用 status=unavailable → weather_future_condition 未知 + future_route_impact 受影响；
    - states.main_route is None → route_current_state 未知（路线取证失败，未知 ≠ 异常）；
    - crowd/entrance/support（及已确认的 main_route）缺 current_fact 引用 → 对应对象未知。
    """
    derived = compute_derived(states)
    impacts, main_impacts, route_affected = build_impacts(derived["derived"])

    unknown_items: list[str] = []
    affected: list[str] = list(route_affected)
    for key, entry in refs_norm.items():
        if entry["status"] != "ok" and key == "future_condition":
            unknown_items.append("weather_future_condition")
            affected.append("future_route_impact")
    for ot in ("crowd", "entrance", "support"):
        if ot not in refs_norm:
            unknown_items.append(ot)
    if states.main_route is None:
        unknown_items.append("route_current_state")
    elif "main_route" not in refs_norm:
        unknown_items.append("main_route")
    unknown_items = sorted(set(unknown_items))
    affected = sorted(set(affected))

    situation = build_situation(impacts, main_impacts, unknown_items,
                                derived["derived"]["capacity"]["remaining_capacity_ratio"],
                                affected)
    return {
        "states": derived["states"],
        "config": derived["config"],
        "derived": derived["derived"],
        "impacts": impacts,
        "situation": situation,
        "unknown_items": unknown_items,
        "situation_completeness": situation["situation_completeness"],
    }
