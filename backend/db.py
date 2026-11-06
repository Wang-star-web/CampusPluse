"""证据层持久化（A00 阶段02）。

observations：只存成功取得的业务事实（value_json 非空）。
evidence：每次获取尝试一行审计（status: ok/unavailable/error；"获取失败 ≠ 业务异常"）。

线程纪律：
- 写入只来自 mqtt_bridge.on_message（paho 网络线程，单线程）→ evidence_id 序列号
  用 COUNT+1 生成，天然无竞态；
- 读取来自 FastAPI 线程池；每次操作独立连接（sqlite3 跨线程共享连接会抛错）；
- connect() 幂等建表：即使阶段02 的 startup 事件晚于阶段01 MQTT 启动事件执行，
  首条消息到达时表必然已存在（CREATE TABLE IF NOT EXISTS）。
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schemas import ObservationEnvelope

DB_PATH = Path(__file__).parent / "campuspulse.db"  # 与 Day1 runs 表同一文件；位置见 README

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    source_type TEXT NOT NULL,
    value_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL,
    object_type TEXT NOT NULL,
    evidence_role TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source TEXT NOT NULL,
    observed_at TEXT NULL,
    retrieved_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ok','unavailable','error')),
    value_json TEXT NULL,
    error_message TEXT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_ot_retr ON evidence(object_type, retrieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_observations_ot_created ON observations(object_type, created_at DESC);
"""

EVIDENCE_ROLE = "current_fact"  # 阶段02 统一角色；阶段05 起扩展 current_fact/future_condition/...


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA_SQL)
    return conn


def init_evidence_db() -> None:
    """启动事件调用（幂等；connect() 本身也会建表，双保险）。"""
    connect().close()


def _parse_row(row: sqlite3.Row | None) -> dict | None:
    """查询行 → API dict；value_json 解析回对象（与 WS 证据帧结构一致）。"""
    if row is None:
        return None
    d = dict(row)
    d["value_json"] = json.loads(d["value_json"]) if d["value_json"] else None
    return d


def _next_evidence_id(conn: sqlite3.Connection, object_type: str) -> str:
    seq = conn.execute(
        "SELECT COUNT(*) FROM evidence WHERE object_type=?", (object_type,)
    ).fetchone()[0] + 1
    return f"ev_{object_type}_{seq:03d}"


def insert_success(env: ObservationEnvelope, source: str) -> dict:
    """成功获取：同一事务双写 observations + evidence(status='ok')。

    observed_at 取信封值（业务时间），retrieved_at 取系统本次获取时间。
    异常 → finally close 自动回滚（双写原子）。
    """
    ot = env.object_type.value
    observed_at = env.observed_at.isoformat()  # validator 保证成功信封非 None
    value_json = json.dumps(env.data, ensure_ascii=False)
    retrieved_at = _now_utc()
    conn = connect()
    try:
        evidence_id = _next_evidence_id(conn, ot)
        conn.execute(
            "INSERT INTO observations (activity_id, object_type, observed_at, source_type, value_json, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (env.activity_id, ot, observed_at, env.source_type, value_json, retrieved_at))
        conn.execute(
            "INSERT INTO evidence (evidence_id, activity_id, object_type, evidence_role, source_type,"
            " source, observed_at, retrieved_at, status, value_json, error_message, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (evidence_id, env.activity_id, ot, EVIDENCE_ROLE, env.source_type, source,
             observed_at, retrieved_at, "ok", value_json, None, retrieved_at))
        conn.commit()
        return {"evidence_id": evidence_id, "activity_id": env.activity_id, "object_type": ot,
                "evidence_role": EVIDENCE_ROLE, "source_type": env.source_type, "source": source,
                "observed_at": observed_at, "retrieved_at": retrieved_at, "status": "ok",
                "value_json": env.data, "error_message": None, "created_at": retrieved_at}
    finally:
        conn.close()


def insert_failure(object_type: str, status: str, error_message: str | None,
                   source: str, source_type: str, activity_id: str) -> dict:
    """获取失败：只写 evidence；observed_at/value_json 为 NULL（绝不伪造业务值），
    绝不触碰 observations 与内存 store。"""
    retrieved_at = _now_utc()
    conn = connect()
    try:
        evidence_id = _next_evidence_id(conn, object_type)
        conn.execute(
            "INSERT INTO evidence (evidence_id, activity_id, object_type, evidence_role, source_type,"
            " source, observed_at, retrieved_at, status, value_json, error_message, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (evidence_id, activity_id, object_type, EVIDENCE_ROLE, source_type, source,
             None, retrieved_at, status, None, error_message, retrieved_at))
        conn.commit()
        return {"evidence_id": evidence_id, "activity_id": activity_id, "object_type": object_type,
                "evidence_role": EVIDENCE_ROLE, "source_type": source_type, "source": source,
                "observed_at": None, "retrieved_at": retrieved_at, "status": status,
                "value_json": None, "error_message": error_message, "created_at": retrieved_at}
    finally:
        conn.close()


def query_history(object_type: str, limit: int = 50) -> list[dict]:
    """observations 按接收时间倒序（历史接口回答"对象过去怎样"）。"""
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT activity_id, object_type, observed_at, source_type, value_json, created_at"
            " FROM observations WHERE object_type=? ORDER BY created_at DESC, id DESC LIMIT ?",
            (object_type, limit)).fetchall()
        return [_parse_row(r) for r in rows]
    finally:
        conn.close()


def query_latest_evidence(object_type: str) -> dict | None:
    """该对象最新一条证据（证据接口回答"这一次为什么知道/为什么不知道"）。"""
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM evidence WHERE object_type=?"
            " ORDER BY retrieved_at DESC, evidence_id DESC LIMIT 1",
            (object_type,)).fetchone()
        return _parse_row(row)
    finally:
        conn.close()


def query_evidence(evidence_id: str) -> dict | None:
    conn = connect()
    try:
        row = conn.execute(
            "SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)
        ).fetchone()
        return _parse_row(row)
    finally:
        conn.close()
