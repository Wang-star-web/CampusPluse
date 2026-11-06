"""WebSocket 广播中枢（A00 阶段01）。

线程纪律：
- CONNECTIONS 集合只在事件循环线程上增删（/ws 端点内），因此无需加锁；
- notify() 供 MQTT 线程调用，用 run_coroutine_threadsafe 把广播投递回事件循环；
- 本阶段消息速率约 2 条/秒，直接投递即可；若后续阶段速率上升，可改为
  asyncio.Queue + 单消费者任务的模式（既定回退方案）。
"""

import asyncio
import json

from fastapi import WebSocket

LOOP: asyncio.AbstractEventLoop | None = None
CONNECTIONS: set[WebSocket] = set()


def _consume_exc(fut: asyncio.Future) -> None:
    """吞掉广播协程的异常，避免 'exception never retrieved' 噪音。"""
    try:
        fut.result()
    except Exception:
        pass


def notify(object_type: str, envelope: dict) -> None:
    """MQTT 线程调用：把单对象更新投递到事件循环广播。"""
    if LOOP is None or LOOP.is_closed():
        return
    try:
        fut = asyncio.run_coroutine_threadsafe(_broadcast(object_type, envelope), LOOP)
        fut.add_done_callback(_consume_exc)
    except RuntimeError:
        pass  # 事件循环已关闭（进程关停竞态），丢弃本次广播


async def _send(payload: dict) -> None:
    """事件循环线程内广播一个 JSON 消息给全部连接。"""
    msg = json.dumps(payload, ensure_ascii=False)
    for ws in list(CONNECTIONS):  # 取快照副本，迭代中可安全 discard
        try:
            await ws.send_text(msg)
        except Exception:
            CONNECTIONS.discard(ws)  # 断线客户端容错


async def _broadcast(object_type: str, envelope: dict) -> None:
    await _send({"type": "update", "object_type": object_type, "envelope": envelope})


def notify_evidence(evidence: dict) -> None:
    """MQTT 线程调用：证据行广播（阶段02；与 notify 同一投递模式）。"""
    if LOOP is None or LOOP.is_closed():
        return
    try:
        fut = asyncio.run_coroutine_threadsafe(
            _send({"type": "evidence", "evidence": evidence}), LOOP)
        fut.add_done_callback(_consume_exc)
    except RuntimeError:
        pass  # 事件循环已关闭（进程关停竞态），丢弃本次广播


def register(ws: WebSocket) -> None:
    CONNECTIONS.add(ws)


def unregister(ws: WebSocket) -> None:
    CONNECTIONS.discard(ws)


def build_snapshot_message(payload: dict) -> str:
    """全量快照消息；payload 与 GET /api/current 共用同一份数据。"""
    return json.dumps({"type": "snapshot", "payload": payload}, ensure_ascii=False)
