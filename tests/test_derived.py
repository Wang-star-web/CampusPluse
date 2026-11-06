"""阶段03 约束计算测试（官方 S1/S2 场景 + 现场验证值）。

运行（仓库根目录）：py -m tests.test_derived
直接调用 backend.constraints.compute_derived（纯函数层测试，无需启动服务）。
"""

import math

from backend.constraints import compute_derived
from backend.schemas import DerivedInput


def derived(crowd: int, available: int, main_route: str, support: int) -> dict:
    return compute_derived(DerivedInput(
        crowd=crowd,
        entrance={"available": available},
        main_route=main_route,
        support=support,
    ))


def assert_close(actual, expected, msg):
    assert math.isclose(actual, expected, abs_tol=1e-9), f"{msg}: {actual} != {expected}"


def test_s1_stable_baseline():
    """S1｜稳定基线：crowd=300, entrance=2/2, route=normal, support=12。"""
    r = derived(300, 2, "normal", 12)
    d = r["derived"]
    assert d["capacity"]["remaining_capacity"] == 700
    assert_close(d["capacity"]["remaining_capacity_ratio"], 0.70, "S1 ratio")
    assert_close(d["entrance"]["entrance_ratio"], 1.00, "S1 entrance_ratio")
    assert d["support"]["support_gap"] == -2
    assert_close(d["support"]["support_ratio"], 1.20, "S1 support_ratio")
    assert d["route"]["route_flexibility"] == "normal"


def test_s2_crowd_sweep():
    """S2｜约束逐步逼近：只改人数 300→500→650→750，其余不变；容量派生持续变化，其余稳定。"""
    expected = {300: (700, 0.70), 500: (500, 0.50), 650: (350, 0.35), 750: (250, 0.25)}
    for crowd, (rem, ratio) in expected.items():
        r = derived(crowd, 2, "normal", 12)
        d = r["derived"]
        assert d["capacity"]["remaining_capacity"] == rem, f"S2 crowd={crowd}"
        assert_close(d["capacity"]["remaining_capacity_ratio"], ratio, f"S2 ratio crowd={crowd}")
        assert_close(d["entrance"]["entrance_ratio"], 1.00, f"S2 entrance crowd={crowd}")
        assert d["support"]["support_gap"] == -2
        assert_close(d["support"]["support_ratio"], 1.20, f"S2 support crowd={crowd}")
        assert d["route"]["route_flexibility"] == "normal"


def test_live_verification_crowd_620():
    """现场验证：crowd=620 → remaining_capacity=380、ratio=0.38。"""
    d = derived(620, 2, "normal", 12)["derived"]
    assert d["capacity"]["remaining_capacity"] == 380
    assert_close(d["capacity"]["remaining_capacity_ratio"], 0.38, "crowd=620 ratio")


def test_live_verification_support_11():
    """现场验证：support 8→11 → support_gap 2→-1、support_ratio 0.80→1.10。"""
    d8 = derived(300, 2, "normal", 8)["derived"]["support"]
    d11 = derived(300, 2, "normal", 11)["derived"]["support"]
    assert d8["support_gap"] == 2 and d11["support_gap"] == -1
    assert_close(d8["support_ratio"], 0.80, "support=8 ratio")
    assert_close(d11["support_ratio"], 1.10, "support=11 ratio")


def test_entrance_ratio_one_of_two():
    """入口 1/2 → entrance_ratio=0.50（分母取教学配置 entrance_total=2）。"""
    d = derived(300, 1, "normal", 10)["derived"]["entrance"]
    assert_close(d["entrance_ratio"], 0.50, "entrance 1/2 ratio")


def test_route_flexibility_mapping():
    """路线映射：normal→normal；limited→reduced（完整映射表）。"""
    assert derived(300, 2, "normal", 10)["derived"]["route"]["route_flexibility"] == "normal"
    assert derived(300, 2, "limited", 10)["derived"]["route"]["route_flexibility"] == "reduced"


def test_response_layers_not_mixed():
    """响应分层：config / states / derived 三层分开，derived 不含影响/态势字段。"""
    r = derived(750, 1, "limited", 8)
    assert set(r.keys()) >= {"config", "states", "derived", "computed_at", "activity_id"}
    flat = str(r)
    for banned in ("impact", "situation", "态势", "影响", "run_id"):
        assert banned not in flat, f"响应中出现被禁字段/概念: {banned}"


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}: {t.__doc__.strip().splitlines()[0]}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
