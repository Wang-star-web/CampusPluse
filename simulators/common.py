"""CampusPulse A00 阶段01 - 模拟数据源公共模块。

约定：
- 模拟器只发布原始业务状态（source_type=SIMULATED），绝不输出任何态势结论；
- 配置唯一入口是后端内存（经 POST /api/sim/set 修改），模拟器每个发布周期
  轮询 GET /api/sim/config 拉取配置；后端不可达时沿用上次有效配置并告警，
  冷启动未拉到配置前不发布任何消息；
- 与 backend/mqtt_bridge.py 中的 ACTIVITY_ID / topic 约定需保持一致。
"""

import json
import time
import urllib.request
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

ACTIVITY_ID = "campus_open_day_01"
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
PUBLISH_INTERVAL_S = 2.0

# 与 README 中 uvicorn 端口一致；模拟器进程不共享后端内存，只能经 HTTP 轮询
CONFIG_URL = "http://127.0.0.1:8000/api/sim/config"
CONFIG_KEYS = ("crowd", "entrance_available", "main_route", "support")
FETCH_TIMEOUT_S = 1.0


def fetch_config() -> dict | None:
    """轮询后端内存配置；超时/后端未启动/响应异常一律返回 None（调用方沿用上次配置）。"""
    try:
        with urllib.request.urlopen(CONFIG_URL, timeout=FETCH_TIMEOUT_S) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception:
        # 模拟器绝不能因配置拉取失败而退出（URLError/JSONDecodeError 等全兜住）
        return None
    if not isinstance(raw, dict) or any(k not in raw for k in CONFIG_KEYS):
        return None
    return raw


def build_envelope(object_type: str, data: dict, observed_at: str | None = None) -> dict:
    """统一消息外壳（成功）；observed_at 缺省为当前 UTC 时间（ISO8601）。"""
    return {
        "activity_id": ACTIVITY_ID,
        "object_type": object_type,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_type": "SIMULATED",
        "data": data,
    }


def build_failure_envelope(object_type: str, status: str, error_message: str | None = None) -> dict:
    """获取失败信封（阶段02）：observed_at 不伪造、data 不携带业务值。"""
    return {
        "activity_id": ACTIVITY_ID,
        "object_type": object_type,
        "observed_at": None,
        "source_type": "SIMULATED",
        "data": None,
        "retrieval_status": status,
        "error_message": error_message,
    }


def run_simulator(object_type: str, to_data) -> None:
    """发布循环：轮询后端配置 → to_data(cfg) → 信封 → MQTT publish（qos=0, retain=False）。

    to_data(cfg: dict) -> dict | None：把整份配置转换为 data 字段。
    冷启动在首次成功拉到配置前不发布任何消息；运行中后端不可达则沿用上次配置继续发布。
    配置值的合法性由后端 pydantic（Literal）保证，模拟器只做键存在性防御。
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
    last_mode = "ok"  # 阶段02：取证模式；后端不可达时沿用（与 keep last config 一致）
    cfg_unreachable = False  # 仅在状态切换时告警，避免每 2s 刷屏
    print(f"[{object_type}] simulator started: topic={topic}, interval={PUBLISH_INTERVAL_S}s (Ctrl+C to stop)")
    try:
        while True:
            cfg = fetch_config()
            if cfg is None:
                if not cfg_unreachable:
                    note = "not publishing until first successful fetch" if last_data is None else "keeping last config"
                    print(f"[{object_type}] WARN backend config unreachable, {note}")
                    cfg_unreachable = True
            else:
                if cfg_unreachable:
                    print(f"[{object_type}] backend config recovered: {cfg}")
                cfg_unreachable = False
                mode_cfg = cfg.get("mode")  # 旧后端无 mode → 防御默认 ok
                m = mode_cfg.get(object_type, "ok") if isinstance(mode_cfg, dict) else "ok"
                last_mode = m if m in ("unavailable", "error") else "ok"  # 未知值防御 → ok
                if last_mode == "ok":
                    data = to_data(cfg)
                    if data is not None:
                        last_data = data
            if last_mode in ("unavailable", "error"):
                # 取证失败：主动上报失败信封（每周期一次，qos0 丢失下周期自愈）；绝不触碰 last_data
                msg = "SIMULATED mode=error" if last_mode == "error" else None
                client.publish(topic, json.dumps(build_failure_envelope(object_type, last_mode, msg)),
                               qos=0, retain=False)
                print(f"[{object_type}] published retrieval failure: status={last_mode}")
            elif last_data is not None:
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
