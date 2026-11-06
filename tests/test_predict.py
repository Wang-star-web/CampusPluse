"""阶段06 模型预测与 LLM 解释测试（纯函数层，不依赖网络/服务）。

运行（仓库根目录）：py -m tests.test_predict
覆盖：OLS 预测与评估、数据不足不可用、无未来信息泄漏、
解释 prompt 的硬边界条款、S4 全链（含 model_output 引用分层）。
"""

from backend.explain import SYSTEM_PROMPT, build_context, build_user_prompt
from backend.predict import MODEL_VERSION, PREDICTION_WINDOW_MIN, train_and_predict
from backend.sources import resolve_evidence_refs


def _history(*counts):
    return [{"observed_at": f"2026-11-06T0{i}:00:00+00:00",
             "value_json": {"count": c}} for i, c in enumerate(counts)]


def test_predict_linear_trend():
    """线性上升序列 → 预测值应高于末值且贴近趋势。"""
    r = train_and_predict(_history(300, 320, 340, 360, 380, 400, 420, 440, 460, 480))
    assert r["model_version"] == MODEL_VERSION
    assert r["prediction_window_min"] == PREDICTION_WINDOW_MIN
    assert r["predicted_crowd"] > 480            # 趋势外推
    assert r["metric_summary"]["train_points"] + r["metric_summary"]["test_points"] == 10
    assert "mae" in r["metric_summary"] and "baseline_mae" in r["metric_summary"]


def test_predict_insufficient_data():
    """数据不足 → 抛 ValueError（调用方写 unavailable 证据，不伪造预测值）。"""
    try:
        train_and_predict(_history(300, 320, 340, 360))
        raise AssertionError("应当因数据不足抛异常")
    except ValueError as e:
        assert "insufficient" in str(e)


def test_predict_no_leakage():
    """测试集不使用未来信息：预测只用训练段拟合（构造恒定序列验证无泄漏的拟合等价性）。"""
    r = train_and_predict(_history(500, 500, 500, 500, 500, 500, 500, 500))
    assert r["predicted_crowd"] == 500  # 常数序列 → 斜率 0


def test_explain_system_prompt_hard_rules():
    """系统 prompt 必须包含官方五条硬边界。"""
    for phrase in ["只解释已有计算结果", "不发明", "不新增", "不修改整体态势",
                   "不出现系统没有定义的专业安全等级"]:
        assert phrase in SYSTEM_PROMPT, f"prompt 缺少硬边界: {phrase}"


def test_explain_context_only_structured():
    """上下文只含该 run 的结构化结果，不包含数据库原文/观察历史。"""
    run = {
        "run_id": "run-1", "input_snapshot": {"states": {"crowd": 900}, "config": {"capacity": 1000}},
        "derived_results": {}, "impacts": [], "situation": {"summary": "组织压力上升"},
        "unknown_items": [], "situation_completeness": "complete",
        "evidence_refs": {"crowd": "ev_crowd_1", "model_output": "ev_crowd_2"},
    }
    ctx = build_context(run, None)
    user = build_user_prompt(ctx)
    assert ctx["situation"]["summary"] == "组织压力上升"
    assert "model_output" in str(ctx["evidence_refs"])
    assert "observations" not in user and "sqlite" not in user  # 不送数据库原文
    assert "run-1" in user


def test_s4_model_output_ref_layering():
    """S4：model_output 证据（object_type=crowd）以 role 键分层，不抢占 current_fact 的 crowd 键。"""
    rows = {
        "ev_crowd_1": {"object_type": "crowd", "evidence_role": "current_fact"},
        "ev_pred_1": {"object_type": "crowd", "evidence_role": "model_output"},
        "ev_weather_1": {"object_type": "weather", "evidence_role": "future_condition"},
    }
    refs, _ = resolve_evidence_refs(rows, list(rows.keys()))
    assert refs == {"crowd": "ev_crowd_1", "model_output": "ev_pred_1", "future_condition": "ev_weather_1"}


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
