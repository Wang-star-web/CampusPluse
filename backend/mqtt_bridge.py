"""MQTT 订阅桥（A00 阶段01）。

paho-mqtt 2.x 要点：
- 必须显式传 callback_api_version=CallbackAPIVersion.VERSION2；
- VERSION2 的 on_connect/on_disconnect 是 5 参回调，用 reason_code.is_failure 判断，
  不要按 1.x 习惯判断 result == 0；
- clean_session 下每次重连都要重新 subscribe；
- on_message 整体 try/except：任何解析/校验异常都不能逃出 paho 的 loop 线程。

订阅策略：通配订阅 campuspulse/+/state/+，再按信封里的 activity_id 过滤。
信封是权威维度（统一消息外壳），topic 只是传输路径；未来多活动/多证据源
无需改动订阅语句。
"""

import asyncio
import json
import logging

import paho.mqtt.client as mqtt
from paho.mqtt.enums import MQTTErrorCode
from pydantic import ValidationError

from . import ws_hub
from .schemas import ObservationEnvelope, envelope_to_dict
from .state import store

log = logging.getLogger("campuspulse.mqtt")

# 与 simulators/common.py 中的同名常量需保持一致（进程间无共享代码路径）
MQTT_HOST = "127.0.0.1"
MQTT_PORT = 1883
ACTIVITY_ID = "campus_open_day_01"
SUB_TOPIC = "campuspulse/+/state/+"

_client: mqtt.Client | None = None

# 统计计数（仅日志/调试用，不进 API，避免污染规范响应结构）
received = 0
accepted = 0
dropped = 0


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        log.warning("MQTT connect failed: %s", reason_code)
        return
    # subscribe() 返回 MQTTErrorCode（无 is_failure 属性），与回调的 ReasonCode 不同
    err, _mid = client.subscribe(SUB_TOPIC, qos=0)
    if err != MQTTErrorCode.MQTT_ERR_SUCCESS:
        log.warning("MQTT subscribe failed: %s", err)
    else:
        log.info("MQTT subscribed %s", SUB_TOPIC)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    log.info("MQTT disconnected: %s", reason_code)


def on_message(client, userdata, msg):
    global received, accepted, dropped
    received += 1
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        env = ObservationEnvelope.model_validate(payload)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as e:
        dropped += 1
        log.warning("rejected message on %s: %s", msg.topic, e)
        return
    if env.activity_id != ACTIVITY_ID:
        dropped += 1
        log.warning("dropped message activity_id=%r (expected %r)", env.activity_id, ACTIVITY_ID)
        return
    if msg.topic.rsplit("/", 1)[-1] != env.object_type.value:
        # 信封优先，topic 尾段不一致仅告警
        log.warning("topic/object_type mismatch: topic=%s envelope=%s", msg.topic, env.object_type.value)
    accepted += 1
    store.update(env.object_type.value, envelope_to_dict(env))


def start() -> None:
    """在 FastAPI startup 事件（事件循环内）调用。"""
    global _client
    ws_hub.LOOP = asyncio.get_running_loop()
    store.add_listener(ws_hub.notify)  # 状态更新 → WebSocket 广播的桥接
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="campuspulse-backend",
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)  # broker 未启动/中途挂掉时后台自动重试
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    _client = client
    log.info("MQTT bridge started: %s:%s topic=%s", MQTT_HOST, MQTT_PORT, SUB_TOPIC)


def stop() -> None:
    """在 FastAPI shutdown 事件调用。"""
    global _client
    store.remove_listener(ws_hub.notify)
    if _client is not None:
        _client.loop_stop()
        _client.disconnect()
        _client = None
        log.info("MQTT bridge stopped")
