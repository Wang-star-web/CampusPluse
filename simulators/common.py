"""CampusPulse A00 阶段01 - 模拟数据源公共模块。

约定：
- 模拟器只发布原始业务状态（source_type=SIMULATED），绝不输出任何态势结论；
- 每个发布周期热读 sim_values.json，改文件即生效、无需重启模拟器；
- 与 backend/mqtt_bridge.py 中的 ACTIVITY_ID / topic 约定需保持一致。
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

ACTIVITY_ID = "campus_open_day_01"
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
PUBLISH_INTERVAL_S = 2.0
SIM_VALUES_PATH = Path(__file__).resolve().parent / "sim_values.json"

# 可取值集合（与阶段01表格一致）；超出集合的文件值会被拒绝并沿用上次有效值
ALLOWED = {
    "crowd": {300, 500, 650, 750, 900},
    "entrance": {"2/2", "1/2"},
    "main_route": {"normal", "limited"},
    "support": {8, 10, 12},
}


def load_sim_values() -> dict | None:
    """热读 sim_values.json；文件不存在/损坏/非对象时返回 None。"""
    try:
        raw = json.loads(SIM_VALUES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def build_envelope(object_type: str, data: dict, observed_at: str | None = None) -> dict:
    """统一消息外壳；observed_at 缺省为当前 UTC 时间（ISO8601）。"""
    return {
        "activity_id": ACTIVITY_ID,
        "object_type": object_type,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_type": "SIMULATED",
        "data": data,
    }


def run_simulator(object_type: str, key: str, to_data) -> None:
    """发布循环：热读配置 → 校验 → 构建信封 → MQTT publish（qos=0, retain=False）。

    to_data(value) -> dict | None：把文件中的原始值转换为 data 字段；
    返回 None 表示转换失败，跳过本次发布并沿用上次有效值。
    """
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"campuspulse-sim-{object_type}",
        protocol=mqtt.MQTTv311,
    )
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    topic = f"campuspulse/{ACTIVITY_ID}/state/{object_type}"
    last_data: dict | None = None
    print(f"[{object_type}] simulator started: topic={topic}, interval={PUBLISH_INTERVAL_S}s (Ctrl+C to stop)")
    try:
        while True:
            values = load_sim_values()
            if values is None:
                print(f"[{object_type}] WARN sim_values.json missing/invalid, keeping last value")
            elif key not in values:
                print(f"[{object_type}] WARN key {key!r} missing in sim_values.json, keeping last value")
            elif values[key] not in ALLOWED[key]:
                allowed = sorted(ALLOWED[key], key=str)
                print(f"[{object_type}] WARN value {values[key]!r} not allowed (allowed: {allowed}), keeping last value")
            else:
                data = to_data(values[key])
                if data is not None:
                    last_data = data
            if last_data is not None:
                payload = json.dumps(build_envelope(object_type, last_data), ensure_ascii=False)
                client.publish(topic, payload, qos=0, retain=False)
                print(f"[{object_type}] published {last_data}")
            time.sleep(PUBLISH_INTERVAL_S)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print(f"[{object_type}] simulator stopped")
