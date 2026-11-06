"""阶段04 局部影响与整体态势（纯 Python 教学规则，LLM 禁止参与判定）。

固定链：派生结果 → 局部影响（impact）→ 整体态势（situation）。
影响阈值与文案只用于本教学案例的软件验证，不等同于现实安全等级/专业标准。

官方契约（指南阶段04）：
- impact 至少保留 impact_id / impact_type / source_constraint / source_derived_result / message；
- main_impacts 只放"需要提高关注程度"的影响（S1 为空、S2 为 [capacity]）；
- situation 至少含 summary / main_impacts / unknown_items；summary 是对结构化影响的可解释归纳；
- 规则集中在本模块，页面里不再单独写另一套阈值。
"""

IMPACT_TO_OBJECT = {
    "capacity": "crowd",
    "entrance": "entrance",
    "support": "support",
    "route": "main_route",
}

# 容量影响（官方逐字文案）
CAPACITY_MESSAGES = {
    "high": "容量余量充足",                       # ratio >= 0.50
    "mid": "容量余量缩小 / 容量约束正在逼近",       # 0.20 <= ratio < 0.50
    "low": "容量余量明显缩小 / 容量相关压力上升",    # ratio < 0.20
}
# summary 归纳用的简短标签
SUMMARY_LABELS = {
    "capacity_mid": "容量约束正在逼近",
    "capacity_low": "容量余量明显缩小",
    "entrance": "通行灵活性下降",
    "support": "支持能力下降",
    "route": "路线灵活性下降",
}


def _capacity(ratio: float) -> tuple[str, bool]:
    """返回 (message, 是否需要提高关注)。"""
    if ratio >= 0.50:
        return CAPACITY_MESSAGES["high"], False
    if ratio >= 0.20:
        return CAPACITY_MESSAGES["mid"], True
    return CAPACITY_MESSAGES["low"], True


def build_impacts(derived: dict) -> tuple[list[dict], list[dict]]:
    """派生结果 → 4 条局部影响。返回 (全部 impacts, main_impacts)。

    每条 impact 可追溯：impact_type → source_constraint（哪条约束）→
    source_derived_result（哪项派生结果）→ message（教学文案）。
    """
    cap = derived["capacity"]
    cap_msg, cap_attn = _capacity(cap["remaining_capacity_ratio"])

    ent = derived["entrance"]["entrance_ratio"]
    ent_msg = "入口条件稳定" if ent == 1.0 else "通行灵活性下降"
    ent_attn = ent < 1.0

    sup = derived["support"]["support_ratio"]
    sup_msg = "支持条件充足" if sup >= 1.0 else "支持能力下降"
    sup_attn = sup < 1.0

    rt = derived["route"]["route_flexibility"]
    rt_msg = "路线条件稳定" if rt == "normal" else "路线灵活性下降"
    rt_attn = rt == "reduced"

    impacts = [
        {"impact_id": "impact_capacity", "impact_type": "capacity",
         "source_constraint": "capacity",
         "source_derived_result": f"remaining_capacity_ratio={cap['remaining_capacity_ratio']}",
         "message": cap_msg},
        {"impact_id": "impact_entrance", "impact_type": "entrance",
         "source_constraint": "entrance_total",
         "source_derived_result": f"entrance_ratio={ent}",
         "message": ent_msg},
        {"impact_id": "impact_support", "impact_type": "support",
         "source_constraint": "support_reference",
         "source_derived_result": f"support_ratio={sup}",
         "message": sup_msg},
        {"impact_id": "impact_route", "impact_type": "route",
         "source_constraint": "route_flexibility",
         "source_derived_result": f"route_flexibility={rt}",
         "message": rt_msg},
    ]
    main_impacts = [i for i, attn in zip(impacts, (cap_attn, ent_attn, sup_attn, rt_attn)) if attn]
    return impacts, main_impacts


def build_situation(impacts: list[dict], main_impacts: list[dict],
                    unknown_items: list[str], capacity_ratio: float) -> dict:
    """聚合全部影响生成整体态势（有限教学聚合规则，非总分、非等级）。

    summary 规则（可解释归纳）：
    - 无需要关注的影响 → "当前主要条件稳定"
    - 有 → 各影响简短标签以"、"连接；若未全部命中，追加"，其他主要条件保持稳定"
    """
    if not main_impacts:
        summary = "当前主要条件稳定"
    else:
        labels = []
        for i in main_impacts:
            t = i["impact_type"]
            if t == "capacity":
                labels.append(SUMMARY_LABELS["capacity_low"] if capacity_ratio < 0.20
                              else SUMMARY_LABELS["capacity_mid"])
            else:
                labels.append(SUMMARY_LABELS[t])
        summary = "、".join(labels)
        if len(main_impacts) < len(impacts):
            summary += "，其他主要条件保持稳定"

    return {
        "summary": summary,
        "main_impacts": main_impacts,
        "unknown_items": unknown_items,
        "situation_completeness": "complete" if not unknown_items else "partial",
    }
