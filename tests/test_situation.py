"""阶段04 影响与整体态势测试（官方 S1/S2 + 现场验证值 + 边界）。

运行（仓库根目录）：py -m tests.test_situation
纯函数层：派生结果 → impacts → situation（不落库、不依赖服务）。
"""

from backend.constraints import compute_derived
from backend.schemas import DerivedInput
from backend.situation import build_impacts, build_situation


def full_chain(crowd: int, available: int = 2, main_route: str = "normal",
               support: int = 12, unknown: list[str] | None = None):
    states = DerivedInput(crowd=crowd, entrance={"available": available},
                          main_route=main_route, support=support)
    derived = compute_derived(states)
    impacts, main = build_impacts(derived["derived"])
    situation = build_situation(impacts, main, unknown if unknown is not None else [],
                                derived["derived"]["capacity"]["remaining_capacity_ratio"])
    return derived["derived"], impacts, main, situation


def test_s1_stable():
    """S1：crowd=300 全部正常 → 4 条稳定影响，main_impacts=[]，summary=当前主要条件稳定。"""
    _, impacts, main, sit = full_chain(300)
    assert {i["impact_type"] for i in impacts} == {"capacity", "entrance", "support", "route"}
    assert [i["message"] for i in impacts] == ["容量余量充足", "入口条件稳定", "支持条件充足", "路线条件稳定"]
    assert main == [] and sit["unknown_items"] == []
    assert sit["summary"] == "当前主要条件稳定"
    assert sit["situation_completeness"] == "complete"
    # 追溯字段齐备
    assert all({"impact_id", "impact_type", "source_constraint", "source_derived_result", "message"} <= set(i)
               for i in impacts)


def test_s2_750():
    """S2-750：ratio=0.25 → 容量影响中档；summary=容量约束正在逼近，其他主要条件保持稳定。"""
    _, impacts, main, sit = full_chain(750)
    assert main == [i for i in impacts if i["impact_type"] == "capacity"]
    assert main[0]["message"] == "容量余量缩小 / 容量约束正在逼近"
    assert main[0]["source_constraint"] == "capacity"
    assert main[0]["source_derived_result"] == "remaining_capacity_ratio=0.25"
    assert sit["summary"] == "容量约束正在逼近，其他主要条件保持稳定"


def test_s2_sweep():
    """S2 全序列：500 仍充足（main=[]）；650/750 进入逼近档（main=[capacity]）。"""
    for crowd, expect_main in ((300, False), (500, False), (650, True), (750, True)):
        _, _, main, _ = full_chain(crowd)
        assert (bool(main)) is expect_main, f"crowd={crowd}"


def test_live_crowd_620():
    """现场验证：crowd=620（ratio=0.38 中档）→ main=[capacity]，summary 逼近档。"""
    _, _, main, sit = full_chain(620)
    assert len(main) == 1 and main[0]["impact_type"] == "capacity"
    assert sit["summary"] == "容量约束正在逼近，其他主要条件保持稳定"


def test_entrance_one_of_two():
    """入口 1/2 → 通行灵活性下降（进入 main_impacts）。"""
    _, _, main, sit = full_chain(300, available=1)
    assert "entrance" in [i["impact_type"] for i in main]
    assert sit["summary"] == "通行灵活性下降，其他主要条件保持稳定"


def test_support_8():
    """support=8（ratio 0.8 <1）→ 支持能力下降。"""
    _, impacts, main, _ = full_chain(300, support=8)
    sup = [i for i in impacts if i["impact_type"] == "support"][0]
    assert sup["message"] == "支持能力下降"
    assert "support" in [i["impact_type"] for i in main]


def test_route_limited():
    """main_route=limited → 路线灵活性下降。"""
    _, impacts, main, _ = full_chain(300, main_route="limited")
    rt = [i for i in impacts if i["impact_type"] == "route"][0]
    assert rt["message"] == "路线灵活性下降"
    assert "route" in [i["impact_type"] for i in main]


def test_all_attention():
    """全部命中关注档（S4：crowd=900 低档+1/2+limited+8）→ 案例书冻结 summary"组织压力上升"。"""
    _, _, main, sit = full_chain(900, available=1, main_route="limited", support=8)
    assert len(main) == 4
    assert sit["summary"] == "组织压力上升"
    assert not sit["summary"].endswith("其他主要条件保持稳定")


def test_unknown_partial():
    """证据引用缺 entrance → unknown_items=['entrance']、completeness=partial；summary 不受影响。"""
    _, _, _, sit = full_chain(300, unknown=["entrance"])
    assert sit["unknown_items"] == ["entrance"]
    assert sit["situation_completeness"] == "partial"
    assert sit["summary"] == "当前主要条件稳定"  # 未知不自动转异常


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
