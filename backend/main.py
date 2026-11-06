"""CampusPulse 校园活动脉搏 - 后端骨架（Day 1）

教学案例来源：S03-B 案例 B-A00《CampusPulse 态势认知》（改造参赛）
国赛升级路线：B-B00《目标任务认知》

已实现的：
- 演示场景：校园大型活动（容量 1000，当前 900 人，入口 1/2，强降雨预报，8 名支持人员）
- 整体态势由**规则计算**得出（不是 LLM 生成）
- run_id 运行追踪雏形 + 条件推演（what-if）

留给学生用 AI 完成的（按学生实践指南阶段推进）：
- TODO[阶段1] 证据链：每个态势结论能回到具体证据与 run_id
- TODO[阶段2] 场景回放：同一场景前后两次运行的对比
- TODO[阶段3] LLM 解释层：只解释结构化结果，**不直接判定态势**（本项目的灵魂）
- TODO[阶段4] 活动保障规范 RAG 问答
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

DB = Path(__file__).parent / "campuspulse.db"
FRONTEND = Path(__file__).parent.parent / "frontend"

app = FastAPI(title="CampusPulse 校园活动脉搏", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ---------- 演示场景（教学演练数据） ----------
# 对应案例书 1.6 节的完整小例子
SCENE = {
    "event_name": "秋季运动会 · 主操场",
    "capacity": 1000,
    "crowd": 900,
    "entrances": [
        {"id": "E1", "name": "入口1（东门）", "status": "normal"},
        {"id": "E2", "name": "入口2（南门）", "status": "congested"},
    ],
    "weather": {"text": "预计 14:00 强降雨", "rain_expected": True},
    "staff": {"total": 8, "available": 5},
    "support_points": [
        {"id": "S1", "name": "医疗点", "status": "ok"},
        {"id": "S2", "name": "饮水点", "status": "ok"},
        {"id": "S3", "name": "广播站", "status": "unknown"},  # 接口超时，状态未知
    ],
}


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            scene_json TEXT NOT NULL,
            level TEXT NOT NULL,
            summary TEXT
        );
    """)
    conn.commit()
    conn.close()


def compute_situation(scene: dict) -> dict:
    """整体态势由显式规则计算（先计算，再解释——LLM 不参与判定）。

    规则（教学基线，可由学生扩展）：
    - 人流利用率 ≥90% → 偏高
    - 任一入口 congested 且利用率 ≥80% → 受阻
    - 降雨预报 + 室外 → 风险上升
    - 支持点 unknown → 部分未知（不判死）
    """
    util = scene["crowd"] / scene["capacity"]
    congested = [e for e in scene["entrances"] if e["status"] == "congested"]
    unknown = [s for s in scene["support_points"] if s["status"] == "unknown"]

    factors = []
    level = "normal"
    if util >= 0.9:
        factors.append(f"人流利用率 {util:.0%}，接近容量上限")
        level = "elevated"
    if congested and util >= 0.8:
        factors.append(f"{congested[0]['name']} 拥堵且人流偏高")
        level = "blocked"
    if scene["weather"]["rain_expected"]:
        factors.append(f"{scene['weather']['text']}，室外疏散压力上升")
        if level == "normal":
            level = "elevated"
    if unknown:
        factors.append(f"{unknown[0]['name']} 状态未知（接口超时，不等于故障）")

    return {
        "level": level,  # normal / elevated / blocked
        "util": round(util, 3),
        "factors": factors,
        "computed_at": datetime.now().isoformat(),
    }


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/scene")
def get_scene():
    return SCENE


@app.get("/api/overview")
def overview():
    """整体态势 = 规则计算结果 + 证据引用。"""
    sit = compute_situation(SCENE)
    return {"scene": SCENE, "situation": sit}


@app.get("/api/whatif")
def whatif(rain: int = 0, crowd: int | None = None, e2: str | None = None):
    """条件推演：改条件重新计算（不污染当前运行，单独成 run）。"""
    scene = dict(SCENE)
    scene["weather"] = {**SCENE["weather"], "rain_expected": bool(rain)}
    if crowd is not None:
        scene["crowd"] = crowd
    if e2:
        scene["entrances"] = [
            {**e, "status": e2} if e["id"] == "E2" else e for e in SCENE["entrances"]
        ]
    return {"modified": {"rain": bool(rain), "crowd": crowd, "e2": e2}, "situation": compute_situation(scene)}


# 说明：Day1 演示用 POST/GET /api/runs 已退役（2026-11-06 用户拍板）——
# 阶段04 正式接管 /api/runs（runs 表经 db._ensure_runs_schema 列迁移兼容旧数据，
# Day1 其余演示路由 /api/scene、/api/overview、/api/whatif 保持不动）。


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")


# ---------- A00 阶段01：多对象现场数据链（在 Day1 内容之上追加，不改动既有代码） ----------
from fastapi import WebSocket, WebSocketDisconnect

from . import mqtt_bridge, ws_hub
from .state import store


@app.on_event("startup")
def startup_stage01_mqtt():
    mqtt_bridge.start()


@app.on_event("shutdown")
def shutdown_stage01_mqtt():
    mqtt_bridge.stop()


@app.get("/health")
def health():
    return {"status": "ok"}


def current_payload() -> dict:
    """当前全部对象的最新状态。与 WebSocket 快照共用，保证页面与接口一致。

    对象值全部来自 MQTT 实时消息（store），绝不写死；尚未收到任何消息时 objects 为空。
    """
    objects = store.snapshot()
    observed = [o["observed_at"] for o in objects.values()]
    return {
        "activity_id": mqtt_bridge.ACTIVITY_ID,
        "objects": objects,
        "updated_at": max(observed) if observed else None,
    }


@app.get("/api/current")
def api_current():
    return current_payload()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    # 先推全量快照再注册；注册前到达的更新会漏掉，
    # 但模拟器每 2s 全量刷新一次，最迟下个周期自然补齐（有界自愈）。
    await ws.send_text(ws_hub.build_snapshot_message(current_payload()))
    ws_hub.register(ws)
    try:
        while True:
            await ws.receive_text()  # 客户端不发业务消息，仅作保活与断开检测
    except WebSocketDisconnect:
        pass
    finally:
        ws_hub.unregister(ws)


# ---------- A00 阶段01增量：模拟配置 API（按钮/curl → 内存配置 → 模拟器轮询） ----------
from .schemas import SimConfig
from .state import sim_config


@app.get("/api/sim/config")
def sim_get_config():
    """模拟器每 2s 轮询此接口拉取配置（模拟器进程不共享后端内存）。"""
    return sim_config.get()


@app.post("/api/sim/set")
def sim_set_config(cfg: SimConfig):
    """更新内存配置并立即返回新配置。

    刻意不直接发 MQTT：页面变化必须走 模拟器轮询 → MQTT → 后端 store → WS 链路，
    保证"页面变化必然来自数据源变化"这一验收点不被旁路（延迟典型 ≤3s）。
    """
    sim_config.set(cfg.model_dump())
    return sim_config.get()


# ---------- A00 阶段02：证据层（双写、历史与证据查询；注册在 spa 兜底路由之前） ----------
from fastapi import HTTPException, Query

from .db import init_evidence_db, query_evidence, query_history, query_latest_evidence
from .schemas import ObjectType


@app.on_event("startup")
def startup_stage02_evidence():
    init_evidence_db()  # 幂等；db.connect() 每次也会自建表，防 MQTT 启动事件先行的竞态


@app.get("/api/history/{object_type}")
def api_history(object_type: ObjectType, limit: int = Query(50, ge=1, le=200)):
    """对象过去怎样（只含成功业务事实）；非法 object_type → 422。"""
    rows = query_history(object_type.value, limit)
    return {"activity_id": mqtt_bridge.ACTIVITY_ID, "object_type": object_type.value,
            "count": len(rows), "history": rows}


@app.get("/api/evidence/latest/{object_type}")
def api_evidence_latest(object_type: ObjectType):
    """这一次为什么知道/为什么不知道；status 是获取状态，不是业务状态。"""
    return {"object_type": object_type.value, "evidence": query_latest_evidence(object_type.value)}


@app.get("/api/evidence/{evidence_id}")
def api_evidence_by_id(evidence_id: str):
    row = query_evidence(evidence_id)
    if row is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    return {"evidence": row}


# ---------- A00 阶段03：显式约束与派生结果（只算派生结果，禁止影响/态势/run_id） ----------
from .constraints import compute_derived, load_config
from .schemas import DerivedInput


@app.post("/api/compute-derived")
def api_compute_derived(states: DerivedInput):
    """输入各对象最新有效业务状态（来自 observations），返回结构化派生结果。

    派生结果由显式规则重新计算（不是场景文件写死答案）；响应只含 config/states/derived
    三层，不生成局部影响与整体态势。
    """
    return compute_derived(states)


# ---------- A00 阶段04：局部影响 → 整体态势 → run_id（reality 运行；完成后永不覆盖） ----------
import uuid as _uuid
from datetime import datetime as _dt, timezone as _tz

from . import sources as _sources
from .db import insert_run, query_evidence, query_latest_run, query_run
from .schemas import RunRequest
from .situation import IMPACT_TO_OBJECT, build_impacts, build_situation


@app.post("/api/runs")
def api_create_run(req: RunRequest):
    """完整分析：输入状态+证据引用 → 约束 → 派生结果 → impacts → situation → 新 run_id 落库。

    只做 reality（run_type=reality, parent_run_id=null）；what-if 属阶段07。
    situation/summary 全部由 Python 教学规则生成，LLM 不参与判定。
    完成后的 run 永不 UPDATE——新输入必然生成全新 run_id。
    """
    refs = {}  # 键 = 业务对象 object_type（current_fact）或 evidence_role（future_condition/knowledge_basis 等外部证据）
    for eid in req.evidence_refs:
        ev = query_evidence(eid)
        if ev is None:
            raise HTTPException(status_code=422, detail=f"evidence not found: {eid}")
        if ev["status"] != "ok":
            raise HTTPException(status_code=422, detail=f"evidence not ok: {eid} (status={ev['status']})")
        key = ev["object_type"] if ev["object_type"] in _sources.OBJECT_TYPES else ev["evidence_role"]
        refs[key] = eid

    derived = compute_derived(req.states)
    impacts, main_impacts = build_impacts(derived["derived"])
    unknown_items = sorted(set(IMPACT_TO_OBJECT.values()) - set(refs))
    situation = build_situation(impacts, main_impacts, unknown_items,
                                derived["derived"]["capacity"]["remaining_capacity_ratio"])

    now = _dt.now(_tz.utc).isoformat()
    run_id = f"run-{_dt.now():%Y%m%d-%H%M%S}-{_uuid.uuid4().hex[:6]}"
    insert_run({
        "run_id": run_id,
        "scenario_id": req.scenario_id,
        "input_snapshot": {
            "states": derived["states"],
            "config": derived["config"],
        },
        "evidence_refs": refs,
        "derived_results": derived["derived"],
        "impacts": impacts,
        "situation": situation,
        "unknown_items": unknown_items,
        "situation_completeness": situation["situation_completeness"],
        "created_at": now,
        "completed_at": now,
    })
    return {"run_id": run_id}


@app.get("/api/runs/latest")
def api_latest_run():
    """最近一次 reality 运行快照（首页"当前 run_id"用）。"""
    snap = query_latest_run()
    if snap is None:
        raise HTTPException(status_code=404, detail="no run yet")
    return snap


@app.get("/api/runs/{run_id}")
def api_get_run(run_id: str):
    """按 run_id 获取整套运行快照：输入、证据引用、派生结果、impacts、situation、unknown_items。"""
    snap = query_run(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="run not found")
    return snap


# ---------- A00 阶段05：多源证据（天气 web_api / 路线工具 / RAG 知识库） ----------
from . import sources
from .db import insert_external_evidence
from .schemas import RagQuery


@app.post("/api/tools/weather")
def tool_weather():
    """真实调用 Open-Meteo 天气 Web API → future_condition 证据。

    只存证据，绝不篡改当前 crowd/route 等 current_fact 业务状态；
    请求失败 → status=error、value_json=null（未知 ≠ 异常）。
    """
    try:
        value = sources.fetch_weather()
        row = insert_external_evidence(
            activity_id=sources.ACTIVITY_ID, object_type="weather",
            evidence_role="future_condition", source_type="web_api",
            source="weather_api", status="ok", value_json=value)
    except Exception as e:
        row = insert_external_evidence(
            activity_id=sources.ACTIVITY_ID, object_type="weather",
            evidence_role="future_condition", source_type="web_api",
            source="weather_api", status="error", value_json=None,
            error_message=f"weather fetch failed: {e}")
    return {"evidence": row}


@app.post("/api/tools/route")
def tool_route():
    """路线查询工具真实执行（读取路线状态服务=后端内存 store）→ current_fact 证据（source_type=tool）。

    工具这次没取到（store 无路线状态）→ status=unavailable——是取证失败，
    绝不写成业务路线异常（route=blocked 之类）。"""
    result = sources.get_route_status(sources.ACTIVITY_ID)
    if result["status"] == "ok":
        row = insert_external_evidence(
            activity_id=sources.ACTIVITY_ID, object_type="main_route",
            evidence_role="current_fact", source_type="tool", source="route_tool",
            status="ok", value_json=result["value_json"], observed_at=result["observed_at"])
    else:
        row = insert_external_evidence(
            activity_id=sources.ACTIVITY_ID, object_type="main_route",
            evidence_role="current_fact", source_type="tool", source="route_tool",
            status="unavailable", value_json=None,
            error_message="route state service has no main_route state")
    return {"evidence": row}


@app.post("/api/tools/rag")
def tool_rag(body: RagQuery):
    """本地知识库检索 → knowledge_basis 证据。

    no_match = 检索成功执行但无足够匹配（status=ok，retrieval_status=no_match，
    不代表"规则不存在/相反"）；知识库目录不可读 → status=unavailable、value_json=null。"""
    try:
        result = sources.rag_retrieve(body.query)
        value = {"query": body.query, "top_k": 3, "retrieval_status": result["retrieval_status"],
                 "retrieved_chunks": result["retrieved_chunks"], "citation": result["citation"]}
        row = insert_external_evidence(
            activity_id=sources.ACTIVITY_ID, object_type="knowledge",
            evidence_role="knowledge_basis", source_type="rag", source="rag_local_kb",
            status="ok", value_json=value)
    except Exception as e:
        row = insert_external_evidence(
            activity_id=sources.ACTIVITY_ID, object_type="knowledge",
            evidence_role="knowledge_basis", source_type="rag", source="rag_local_kb",
            status="unavailable", value_json=None, error_message=f"rag unavailable: {e}")
    return {"evidence": row}


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """未知 GET 路径一律回退到看板页面（单页应用容错：/index.html、旧链接等不再 404）。

    必须注册在所有路由之后；/api/*、/ws、/docs、/health 等已注册路径不受影响。
    """
    return FileResponse(FRONTEND / "index.html")
