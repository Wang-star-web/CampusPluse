"""阶段06 传统 ML 人数预测（model_output 证据）。

官方契约：
- 简单传统模型即可（自选算法），本实现用最小二乘线性回归（时间序号 → crowd），
  Baseline = 上一窗口人数（下一窗口人数 = 当前人数）；
- 时间序划分训练/测试，MAE 评估并与 Baseline 对比（诚实保留结果，不夸大）；
- 只使用少量可解释特征（最近窗口值），不使用未来信息泄漏到训练输入；
- 预测是未来证据，绝不覆盖当前 crowd 真实值；
- 数据不足/模型不可用 → status=unavailable，绝不伪造预测值。
"""

import json
from datetime import datetime, timedelta, timezone

from . import db

MODEL_VERSION = "crowd_forecast_v1"
PREDICTION_WINDOW_MIN = 30
MIN_TRAIN_POINTS = 5   # 少于该数量视为模型不可用（教学口径）


def _ols_slope(xs: list[float], ys: list[float]) -> float:
    """一元线性回归斜率（最小二乘，纯 Python 实现）。"""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0
    return num / den


def _mae(actual: list[float], predicted: list[float]) -> float:
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual) if actual else 0.0


def train_and_predict(history: list[dict], window_min: int = PREDICTION_WINDOW_MIN) -> dict:
    """基于历史 crowd 观测（按时间升序）训练并预测下一窗口人数。

    history: [{observed_at, value_json: {count}}]（observations 查询结果）。
    返回 {model_version, prediction_for, prediction_window_min, predicted_crowd,
          metric_summary{mae, baseline_mae, train_points, test_points}, trained_at}
    数据不足 → 抛 ValueError（调用方写 status=unavailable 证据）。
    """
    values = [h["value_json"]["count"] for h in history]
    if len(values) < MIN_TRAIN_POINTS:
        raise ValueError(f"insufficient training data: {len(values)} < {MIN_TRAIN_POINTS}")

    # 时间序划分：前 80% 训练、后 20% 测试（无未来信息泄漏）
    split = max(int(len(values) * 0.8), MIN_TRAIN_POINTS - 1)
    train, test = values[:split], values[split:]

    # 线性回归：特征=时间序号（0..n-1），标签=crowd；预测下一个序号 n
    slope = _ols_slope([float(i) for i in range(len(train))], [float(v) for v in train])
    intercept = sum(train) / len(train) - slope * ((len(train) - 1) / 2)
    predicted_crowd = max(0, round(slope * len(values) + intercept))

    # 评估：模型 vs Baseline（上一窗口值）在测试集上的 MAE
    test_x = [float(i) for i in range(split, len(values))]
    model_pred = [max(0.0, slope * x + intercept) for x in test_x]
    baseline_pred = [float(values[i - 1]) for i in range(split, len(values))]
    mae = round(_mae([float(v) for v in test], model_pred), 2)
    baseline_mae = round(_mae([float(v) for v in test], baseline_pred), 2)

    now = datetime.now(timezone.utc)
    return {
        "model_version": MODEL_VERSION,
        "prediction_for": (now + timedelta(minutes=window_min)).isoformat(),
        "prediction_window_min": window_min,
        "predicted_crowd": predicted_crowd,
        "metric_summary": {
            "mae": mae,
            "baseline_mae": baseline_mae,
            "train_points": len(train),
            "test_points": len(test),
            "algorithm": "linear_regression_on_time_index",
        },
        "trained_at": now.isoformat(),
    }


def run_prediction() -> dict:
    """取历史观测 → 训练 → 预测 → 写入 model_output 证据行。

    历史取自 observations（成功业务事实），预测结果存 evidence 表
    （evidence_role=model_output, source_type=ml_model）——独立证据，不改写当前值。
    """
    history = db.query_history("crowd", limit=200)
    history.reverse()  # 时间升序
    try:
        value = train_and_predict(history)
        row = db.insert_external_evidence(
            activity_id="campus_open_day_01", object_type="crowd",
            evidence_role="model_output", source_type="ml_model", source="crowd_forecast_v1",
            status="ok", value_json=value, observed_at=value["trained_at"])
    except Exception as e:
        row = db.insert_external_evidence(
            activity_id="campus_open_day_01", object_type="crowd",
            evidence_role="model_output", source_type="ml_model", source="crowd_forecast_v1",
            status="unavailable", value_json=None,
            error_message=f"prediction unavailable: {e}")
    return row
