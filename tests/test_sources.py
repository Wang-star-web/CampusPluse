"""阶段05 多源证据测试（天气映射 / 路线工具 / RAG 三态 / 引用解析 / S3 链路）。

运行（仓库根目录）：py -m tests.test_sources
纯函数层（不依赖网络与服务进程）：天气映射与 RAG 检索可离线验证；
S3 链路验证"未来条件不篡改当前事实"。
"""

from pathlib import Path

from backend.constraints import compute_derived
from backend.schemas import DerivedInput
from backend.situation import build_impacts, build_situation
from backend.sources import (OBJECT_TYPES, get_route_status, map_weather_condition,
                             rag_retrieve, resolve_evidence_refs)

KB_DIR = Path(__file__).resolve().parent.parent / "kb"


# ---------- 天气 ----------
def test_weather_mapping():
    assert map_weather_condition(80, 0.0) == "heavy_rain_expected"   # 概率高
    assert map_weather_condition(40, 3.0) == "heavy_rain_expected"   # 雨量大
    assert map_weather_condition(40, 1.0) == "normal"
    assert map_weather_condition(None, None) == "normal"             # 缺字段防御


# ---------- 路线工具 ----------
def test_route_tool_ok():
    res = get_route_status("campus_open_day_01", state={
        "main_route": {"observed_at": "2026-11-06T04:00:00+00:00", "data": {"status": "normal"}}})
    assert res["status"] == "ok" and res["value_json"] == {"main_route": "normal"}


def test_route_tool_unavailable():
    res = get_route_status("campus_open_day_01", state={})  # 服务无路线状态
    assert res["status"] == "unavailable" and res["value_json"] is None


# ---------- RAG ----------
def test_rag_matched():
    r = rag_retrieve("强降雨 注意事项", kb_dir=KB_DIR)
    assert r["retrieval_status"] == "matched"
    assert len(r["retrieved_chunks"]) >= 1 and r["citation"]


def test_rag_no_match():
    r = rag_retrieve("火星基地 采矿 规范", kb_dir=KB_DIR)
    assert r["retrieval_status"] == "no_match" and r["retrieved_chunks"] == []


def test_rag_unavailable():
    try:
        rag_retrieve("任意", kb_dir=Path("D:/definitely_missing_kb_dir_xyz"))
        raise AssertionError("应当抛出异常（服务不可用）")
    except Exception:
        pass


# ---------- 引用解析 ----------
def test_resolve_refs_objects_and_roles():
    rows = {
        "ev_crowd_1": {"object_type": "crowd", "evidence_role": "current_fact"},
        "ev_weather_1": {"object_type": "weather", "evidence_role": "future_condition"},
        "ev_knowledge_1": {"object_type": "knowledge", "evidence_role": "knowledge_basis"},
        "ev_main_route_9": {"object_type": "main_route", "evidence_role": "current_fact"},
    }
    refs, _ = resolve_evidence_refs(rows, list(rows.keys()))
    assert refs == {"crowd": "ev_crowd_1", "future_condition": "ev_weather_1",
                    "knowledge_basis": "ev_knowledge_1", "main_route": "ev_main_route_9"}


# ---------- S3：未来强降雨不篡改当前事实 ----------
def test_s3_future_condition_boundary():
    """S3：crowd=750、路线 normal（current_fact）、未来 heavy_rain（future_condition）。

    断言：派生/影响/态势全部只由当前事实计算（route 稳定、summary=容量逼近），
    天气证据仅以 future_condition 引用进入运行，绝不改写当前路线状态。
    """
    states = DerivedInput(crowd=750, entrance={"available": 2},
                          main_route="normal", support=12)
    derived = compute_derived(states)
    impacts, main = build_impacts(derived["derived"])
    situation = build_situation(impacts, main, [],
                                derived["derived"]["capacity"]["remaining_capacity_ratio"])

    # 当前路线事实未被未来天气覆盖
    assert derived["states"]["main_route"] == "normal"
    assert derived["derived"]["route"]["route_flexibility"] == "normal"
    route_impact = [i for i in impacts if i["impact_type"] == "route"][0]
    assert route_impact["message"] == "路线条件稳定"
    assert "route" not in [i["impact_type"] for i in main]
    # 整体态势由当前事实归纳
    assert situation["summary"] == "容量约束正在逼近，其他主要条件保持稳定"

    # 天气证据作为 future_condition 引用进入运行（键=evidence_role）
    rows = {
        "ev_crowd_1": {"object_type": "crowd", "evidence_role": "current_fact"},
        "ev_entrance_1": {"object_type": "entrance", "evidence_role": "current_fact"},
        "ev_main_route_1": {"object_type": "main_route", "evidence_role": "current_fact"},
        "ev_support_1": {"object_type": "support", "evidence_role": "current_fact"},
        "ev_weather_1": {"object_type": "weather", "evidence_role": "future_condition"},
    }
    refs, _ = resolve_evidence_refs(rows, list(rows.keys()))
    assert refs["future_condition"] == "ev_weather_1"
    assert refs["main_route"] == "ev_main_route_1"  # 当前路线引用保留原事实证据
    assert set(OBJECT_TYPES) <= set(refs)           # 四个 current_fact 对象齐备 → unknown=[]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
