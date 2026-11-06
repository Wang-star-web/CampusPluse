"""阶段07 条件推演与可信降级测试（纯函数层 + DB 层）。

运行（仓库根目录）：py -m tests.test_whatif
覆盖：what-if 输入继承、run_type/parent 落库、compare 五维差异、
S4-D 对照（入口 1/2→2/2 只改入口链）、S5 天气+路线双未知。
"""

import sqlite3
import tempfile
from pathlib import Path

from backend import db
from backend.constraints import compute_derived
from backend.schemas import DerivedInput
from backend.situation import build_impacts, build_situation


def chain(states: DerivedInput, unknown: list[str] | None = None,
          affected_extra: list[str] | None = None):
    derived = compute_derived(states)
    impacts, main, affected = build_impacts(derived["derived"])
    affected = sorted(set(affected) | set(affected_extra or []))
    unknown = list(unknown or [])
    if states.main_route is None:  # 管线规则：本次路线事实无法确认 → unknown
        unknown.append("route_current_state")
    sit = build_situation(impacts, main, sorted(set(unknown)),
                          derived["derived"]["capacity"]["remaining_capacity_ratio"], affected)
    return derived["derived"], impacts, main, affected, sit


def s4_states(available=1, support=8, route="limited", crowd=900):
    return DerivedInput(crowd=crowd, entrance={"available": available},
                        main_route=route, support=support)


def test_s4_benchmark():
    """S4-C 基准：summary=组织压力上升、四影响齐、complete。"""
    d, impacts, main, affected, sit = chain(s4_states())
    assert sit["summary"] == "组织压力上升" and len(main) == 4
    assert affected == [] and sit["situation_completeness"] == "complete"


def test_s4_d_restore_entrance():
    """S4-D（入口恢复 2/2，支持仍 8）：入口影响变为稳定、支持影响保留、summary 变化可解释。"""
    d, impacts, main, _, sit = chain(s4_states(available=2, support=8))
    ent = [i for i in impacts if i["impact_type"] == "entrance"][0]
    sup = [i for i in impacts if i["impact_type"] == "support"][0]
    assert ent["message"] == "入口条件稳定"
    assert sup["message"] == "支持能力下降"           # 未改动对象事实保留
    assert "entrance" not in [i["impact_type"] for i in main]
    assert sit["summary"] == "容量余量明显缩小、支持能力下降、路线灵活性下降，其他主要条件保持稳定"


def test_s4_a_baseline_start():
    """S4-A（入口 2/2、支持 10）：入口/支持均稳定；容量与路线影响仍在，不能宣称完全无压力。"""
    _, _, main, _, sit = chain(s4_states(available=2, support=10))
    assert [i["impact_type"] for i in main] == ["capacity", "route"]
    assert sit["summary"] == "容量余量明显缩小、路线灵活性下降，其他主要条件保持稳定"


def test_s5_weather_route_unknown():
    """S5：路线无法确认 + 天气取证失败 → unknown/affected/completeness=partial；无伪造异常。"""
    d, impacts, main, affected, sit = chain(
        s4_states(route=None), unknown=["weather_future_condition"],
        affected_extra=["future_route_impact"])
    assert sorted(sit["unknown_items"]) == ["route_current_state", "weather_future_condition"]
    assert sorted(sit["affected_impacts"]) == ["future_route_impact", "route_impact"]
    assert sit["situation_completeness"] == "partial"
    assert [i["impact_type"] for i in main] == ["capacity", "entrance", "support"]
    assert "异常" not in sit["summary"]


def test_whatif_insert_and_parent_untouched():
    """DB 层：what-if 落库带 parent/overrides/assumptions；父行保持不变（不可覆盖纪律）。"""
    with tempfile.TemporaryDirectory() as tmp:
        db.DB_PATH = Path(tmp) / "t.db"
        try:
            snap = {
                "run_id": "run-1", "scenario_id": "S4", "run_type": "reality",
                "parent_run_id": None,
                "input_snapshot": {"states": {"crowd": 900}, "config": {"capacity": 1000}},
                "input_overrides": None, "assumptions": None,
                "evidence_refs": {}, "derived_results": {}, "impacts": [],
                "situation": {"summary": "x"}, "unknown_items": [],
                "situation_completeness": "complete",
                "created_at": "2026-11-06T00:00:00+00:00", "completed_at": "2026-11-06T00:00:00+00:00",
            }
            db.insert_run(snap)
            child = {**snap, "run_id": "run-2", "run_type": "what_if", "parent_run_id": "run-1",
                     "input_overrides": {"entrance_available": 2},
                     "assumptions": {"other_conditions_unchanged": True}}
            db.insert_run(child)
            a = db.query_run("run-1")
            b = db.query_run("run-2")
            assert a["run_type"] == "reality" and a["parent_run_id"] is None
            assert b["run_type"] == "what_if" and b["parent_run_id"] == "run-1"
            assert b["input_overrides"] == {"entrance_available": 2}
            assert b["assumptions"] == {"other_conditions_unchanged": True}
            assert a["input_snapshot"]["states"]["crowd"] == 900  # 父行未被覆盖
        finally:
            db.DB_PATH = Path(__file__).resolve().parent.parent / "backend" / "campuspulse.db"


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
