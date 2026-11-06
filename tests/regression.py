"""阶段08 回归测试：自动跑 S1-S5，校验派生结果/impact/situation/unknown_items 是否符合教学预期。

运行（仓库根目录）：
    py -m tests.regression            # 离线模式：直接用生产管线纯函数（pipeline.run_analysis）
    py -m tests.regression --live     # 在线模式：对 http://127.0.0.1:8000 跑完整证据+运行链
                                       （S5 需要 .env 教学注入 weather/route unavailable，未注入时自动跳过并提示）

输出：每场景逐项 PASS/FAIL 明细 + 汇总报告；退出码 0=全部通过。
说明：教学预期来自官方指南冻结的 S1-S5 输入与派生/影响/态势文案
（教学参数与态势标签仅用于教学验证，不代表现实安全标准）。
"""

import json
import sys
import urllib.error
import urllib.request

from backend.pipeline import run_analysis
from backend.schemas import DerivedInput

BASE = "http://127.0.0.1:8000"

# S1-S5 官方冻结输入（教学场景，非现实标准）
SCENARIOS = {
    "S1": {"crowd": 300, "entrance_available": 2, "main_route": "normal", "support": 12},
    "S2": {"crowd": 750, "entrance_available": 2, "main_route": "normal", "support": 12},
    "S3": {"crowd": 750, "entrance_available": 2, "main_route": "normal", "support": 12},
    "S4": {"crowd": 900, "entrance_available": 1, "main_route": "limited", "support": 8},
    "S5": {"crowd": 900, "entrance_available": 1, "main_route": None, "support": 8},
}

# 各场景的证据引用形态（离线模式模拟；online 模式从真实 evidence 表取）
SCENARIO_REFS = {
    "S1": {"crowd": "ok", "entrance": "ok", "main_route": "ok", "support": "ok"},
    "S2": {"crowd": "ok", "entrance": "ok", "main_route": "ok", "support": "ok"},
    "S3": {"crowd": "ok", "entrance": "ok", "main_route": "ok", "support": "ok",
           "future_condition": "ok"},
    "S4": {"crowd": "ok", "entrance": "ok", "main_route": "ok", "support": "ok",
           "future_condition": "ok", "knowledge_basis": "ok", "model_output": "ok"},
    "S5": {"crowd": "ok", "entrance": "ok", "support": "ok",
           "future_condition": "unavailable", "knowledge_basis": "ok"},
}

# 教学预期（官方冻结）：每个场景校验 derived 关键值、impact 文案、situation 三要素
EXPECT = {
    "S1": {
        "derived": {"remaining_capacity": 700, "remaining_capacity_ratio": 0.70,
                    "entrance_ratio": 1.00, "support_gap": -2, "support_ratio": 1.20,
                    "route_flexibility": "normal"},
        "impacts": {"capacity": "容量余量充足", "entrance": "入口条件稳定",
                    "support": "支持条件充足", "route": "路线条件稳定"},
        "main_impacts": [],
        "summary": "当前主要条件稳定",
        "unknown_items": [], "completeness": "complete",
    },
    "S2": {
        "derived": {"remaining_capacity": 250, "remaining_capacity_ratio": 0.25,
                    "entrance_ratio": 1.00, "support_gap": -2, "route_flexibility": "normal"},
        "impacts": {"capacity": "容量余量缩小 / 容量约束正在逼近"},
        "main_impacts": ["capacity"],
        "summary": "容量约束正在逼近，其他主要条件保持稳定",
        "unknown_items": [], "completeness": "complete",
    },
    "S3": {
        "derived": {"remaining_capacity": 250, "remaining_capacity_ratio": 0.25,
                    "route_flexibility": "normal"},
        "impacts": {"route": "路线条件稳定", "capacity": "容量余量缩小 / 容量约束正在逼近"},
        "main_impacts": ["capacity"],   # 未来天气只是证据，不改写当前事实
        "summary": "容量约束正在逼近，其他主要条件保持稳定",
        "unknown_items": [], "completeness": "complete",
    },
    "S4": {
        "derived": {"remaining_capacity": 100, "remaining_capacity_ratio": 0.10,
                    "entrance_ratio": 0.50, "support_gap": 2, "support_ratio": 0.80,
                    "route_flexibility": "reduced"},
        "impacts": {"capacity": "容量余量明显缩小 / 容量相关压力上升",
                    "entrance": "通行灵活性下降", "support": "支持能力下降",
                    "route": "路线灵活性下降"},
        "main_impacts": ["capacity", "entrance", "support", "route"],
        "summary": "组织压力上升",
        "unknown_items": [], "completeness": "complete",
    },
    "S5": {
        "derived": {"remaining_capacity": 100, "remaining_capacity_ratio": 0.10,
                    "route_flexibility": "unknown"},
        "impacts": {"capacity": "容量余量明显缩小 / 容量相关压力上升",
                    "entrance": "通行灵活性下降", "support": "支持能力下降",
                    "route": "路线条件无法确认（本次取证失败）"},
        "main_impacts": ["capacity", "entrance", "support"],
        "summary": "容量余量明显缩小、通行灵活性下降、支持能力下降，部分影响判断不完整（证据不完整）",
        "unknown_items": ["route_current_state", "weather_future_condition"],
        "affected_impacts": ["future_route_impact", "route_impact"],
        "completeness": "partial",
    },
}

IMPACT_MAP = {"capacity": "impact_capacity", "entrance": "impact_entrance",
              "support": "impact_support", "route": "impact_route"}


def build_refs(scenario: str) -> dict:
    refs = {}
    for i, (key, status) in enumerate(SCENARIO_REFS[scenario].items()):
        refs[key] = {"evidence_id": f"ev_{key}_{i:03d}", "status": status}
    return refs


def offline_run(scenario: str) -> dict:
    """离线跑生产管线纯函数，并映射为与 run 快照相同的字段形态（回归与在线共用断言）。"""
    cfg = SCENARIOS[scenario]
    states = DerivedInput(crowd=cfg["crowd"], entrance={"available": cfg["entrance_available"]},
                          main_route=cfg["main_route"], support=cfg["support"])
    a = run_analysis(states, build_refs(scenario))
    return {"derived_results": a["derived"], "impacts": a["impacts"],
            "situation": a["situation"], "unknown_items": a["unknown_items"],
            "situation_completeness": a["situation_completeness"]}


def live_run(scenario: str, weather_status: str, object_refs: list[str],
             weather_ref: str | None, rag_ref: str | None) -> dict:
    cfg = SCENARIOS[scenario]
    refs = list(object_refs)
    if scenario in ("S3", "S4") and weather_ref:
        refs.append(weather_ref)
    if scenario == "S4" and rag_ref:
        refs.append(rag_ref)
    if scenario == "S5" and weather_ref:
        refs.append(weather_ref)  # unavailable 天气引用必须被记录（S5 语义）
    body = {"scenario_id": scenario,
            "states": {"crowd": cfg["crowd"], "entrance": {"available": cfg["entrance_available"]},
                       "main_route": cfg["main_route"], "support": cfg["support"]},
            "evidence_refs": refs}
    req = urllib.request.Request(BASE + "/api/runs",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        run_id = json.loads(r.read().decode("utf-8"))["run_id"]
    with urllib.request.urlopen(BASE + f"/api/runs/{run_id}") as r:
        return json.loads(r.read().decode("utf-8"))


def check(scenario: str, snap: dict, failures: list):
    exp = EXPECT[scenario]
    d = snap["derived_results"]
    imp = {i["impact_type"]: i["message"] for i in snap["impacts"]}
    for key, want in exp["derived"].items():
        got = d.get(key) if isinstance(d, dict) else None
        # derived 是分组结构时按 key 直接取
        if got is None:
            for section in ("capacity", "entrance", "support", "route"):
                if key in (d.get(section) or {}):
                    got = d[section][key]
                    break
        ok = (abs(got - want) < 1e-9) if isinstance(want, float) else (got == want)
        if not ok:
            failures.append(f"{scenario} derived.{key}: got {got}, want {want}")
    for key, want in exp["impacts"].items():
        if imp.get(key) != want:
            failures.append(f"{scenario} impact.{key}: got {imp.get(key)!r}, want {want!r}")
    main = [i["impact_type"] for i in snap["situation"]["main_impacts"]]
    if main != exp["main_impacts"]:
        failures.append(f"{scenario} main_impacts: got {main}, want {exp['main_impacts']}")
    if snap["situation"]["summary"] != exp["summary"]:
        failures.append(f"{scenario} summary: got {snap['situation']['summary']!r}, want {exp['summary']!r}")
    if snap["unknown_items"] != exp["unknown_items"]:
        failures.append(f"{scenario} unknown_items: got {snap['unknown_items']}, want {exp['unknown_items']}")
    if "affected_impacts" in exp and snap["situation"]["affected_impacts"] != exp["affected_impacts"]:
        failures.append(f"{scenario} affected: got {snap['situation']['affected_impacts']}, want {exp['affected_impacts']}")
    if snap["situation_completeness"] != exp["completeness"]:
        failures.append(f"{scenario} completeness: got {snap['situation_completeness']}, want {exp['completeness']}")


def main():
    live = "--live" in sys.argv
    print("=" * 66)
    print("CampusPulse A00 阶段08 回归测试（S1-S5 教学预期校验）")
    print(f"模式: {'在线（真实 API 链路）' if live else '离线（生产管线纯函数 pipeline.run_analysis）'}")
    print("说明: 教学参数与态势标签仅用于教学验证，不代表现实安全标准")
    print("=" * 66)

    if live:
        # 在线：收集真实证据引用
        try:
            weather = json.loads(urllib.request.urlopen(
                urllib.request.Request(BASE + "/api/tools/weather", method="POST")).read())["evidence"]
            weather_status = weather["status"]
        except Exception as e:
            print("无法调用 /api/tools/weather（后端未启动？）:", e)
            return 1
        refs = []
        for ot in ("crowd", "entrance", "main_route", "support"):
            ev = json.loads(urllib.request.urlopen(
                BASE + f"/api/evidence/latest/{ot}").read())["evidence"]
            if ev and ev["status"] == "ok":
                refs.append(ev["evidence_id"])
        rag = None
        try:
            rag_req = urllib.request.Request(BASE + "/api/tools/rag",
                                             data=json.dumps({"query": "强降雨 注意事项"}).encode("utf-8"),
                                             headers={"Content-Type": "application/json"}, method="POST")
            rag = json.loads(urllib.request.urlopen(rag_req).read())["evidence"]["evidence_id"]
        except Exception:
            pass
        if weather_status != "unavailable":
            print(f"[提示] 当前天气教学覆写 = {weather_status!r}；"
                  "S5 需要 WEATHER_TEACHING_CONDITION=unavailable + ROUTE_TOOL_TEACHING_UNAVAILABLE=1 才会执行，否则跳过")

    failures = []
    skipped = []
    for sc in ("S1", "S2", "S3", "S4", "S5"):
        if live and sc == "S5" and weather_status != "unavailable":
            print(f"{sc}: SKIPPED（需天气教学注入，见提示）")
            skipped.append(sc)
            continue
        try:
            if live:
                snap = live_run(sc, weather_status, refs, weather["evidence_id"], rag)
            else:
                snap = offline_run(sc)
            before = len(failures)
            check(sc, snap, failures)
            status = "PASS" if len(failures) == before else "FAIL"
            print(f"{sc}: {status}  summary={snap['situation']['summary']!r} "
                  f"main={[i['impact_type'] for i in snap['situation']['main_impacts']]} "
                  f"unknown={snap['unknown_items']} completeness={snap['situation_completeness']}")
        except Exception as e:
            failures.append(f"{sc}: 异常 {e}")
            print(f"{sc}: FAIL（异常）: {e}")

    print("-" * 66)
    failed_scenarios = len({f.split(" ")[0] for f in failures if f.split(" ")[0] in ("S1", "S2", "S3", "S4", "S5")})
    passed = 5 - failed_scenarios - len(skipped)
    print(f"报告: {passed}/5 场景通过，{len(skipped)} 跳过（S5 需教学注入），{len(failures)} 项断言失败")
    for f in failures:
        print("  [X]", f)
    if failures:
        print("RESULT: FAIL")
        return 1
    print("RESULT: ALL PASS [OK]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
