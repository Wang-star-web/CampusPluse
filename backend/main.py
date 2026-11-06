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


def _resolve_refs(ref_ids: list[str]) -> tuple[dict, list[str]]:
    """证据 id 列表 → 引用映射 {key: {"evidence_id", "status"}} 与校验错误列表。

    键 = evidence_role（非 current_fact）或 object_type（current_fact）。
    status != ok 的引用只允许 future_condition（天气取证失败必须被记录，
    由管线转为 unknown_items）；其余失败引用 → 错误（422）。
    """
    refs: dict[str, dict] = {}
    errors: list[str] = []
    for eid in ref_ids:
        ev = query_evidence(eid)
        if ev is None:
            errors.append(f"evidence not found: {eid}")
            continue
        key = ev["object_type"] if ev["evidence_role"] == "current_fact" else ev["evidence_role"]
        if ev["status"] != "ok" and ev["evidence_role"] != "future_condition":
            errors.append(f"evidence not ok: {eid} (status={ev['status']}, role={ev['evidence_role']})")
            continue
        refs[key] = {"evidence_id": eid, "status": ev["status"]}
    return refs, errors


def _normalize_refs(refs: dict) -> dict:
    """兼容阶段04/05 旧行（值为字符串）与新条目（值为 {evidence_id, status}）。"""
    out = {}
    for k, v in refs.items():
        out[k] = v if isinstance(v, dict) else {"evidence_id": v, "status": "ok"}
    return out


def _run_pipeline(states: DerivedInput, refs_entries: dict, scenario_id: str | None,
                  run_type: str = "reality", parent_run_id: str | None = None,
                  overrides: dict | None = None, assumptions: dict | None = None) -> dict:
    """完整分析链（reality 与 what-if 共用）：约束 → 派生 → impacts → situation → 落库。

    阶段07：unknown_items / affected_impacts / situation_completeness 由显式规则生成；
    只 INSERT 不 UPDATE——现实/推演各自全新 run_id。
    """
    derived = compute_derived(states)
    impacts, main_impacts, route_affected = build_impacts(derived["derived"])

    unknown_items: list[str] = []
    affected: list[str] = list(route_affected)
    refs_norm = _normalize_refs(refs_entries)
    for key, entry in refs_norm.items():
        if entry["status"] != "ok" and key == "future_condition":
            unknown_items.append("weather_future_condition")   # 天气取证失败 → 未来条件未知
            affected.append("future_route_impact")
    for ot in ("crowd", "entrance", "support"):                 # 缺失 current_fact 引用 → 未知
        if ot not in refs_norm:
            unknown_items.append(ot)
    if states.main_route is None:                               # 本次路线事实无法确认（未知 ≠ 异常）
        unknown_items.append("route_current_state")
    elif "main_route" not in refs_norm:
        unknown_items.append("main_route")
    unknown_items = sorted(set(unknown_items))
    affected = sorted(set(affected))

    situation = build_situation(impacts, main_impacts, unknown_items,
                                derived["derived"]["capacity"]["remaining_capacity_ratio"], affected)

    now = _dt.now(_tz.utc).isoformat()
    run_id = f"run-{_dt.now():%Y%m%d-%H%M%S}-{_uuid.uuid4().hex[:6]}"
    insert_run({
        "run_id": run_id,
        "scenario_id": scenario_id,
        "run_type": run_type,
        "parent_run_id": parent_run_id,
        "input_snapshot": {"states": derived["states"], "config": derived["config"]},
        "input_overrides": overrides,
        "assumptions": assumptions,
        "evidence_refs": refs_norm,
        "derived_results": derived["derived"],
        "impacts": impacts,
        "situation": situation,
        "unknown_items": unknown_items,
        "situation_completeness": situation["situation_completeness"],
        "created_at": now,
        "completed_at": now,
    })
    return {"run_id": run_id}


@app.post("/api/runs")
def api_create_run(req: RunRequest):
    """完整分析：输入状态+证据引用 → 约束 → 派生结果 → impacts → situation → 新 run_id 落库。

    reality 运行（run_type=reality, parent_run_id=null）；situation/summary 全部由
    Python 教学规则生成，LLM 不参与判定。完成后的 run 永不 UPDATE。
    """
    refs, errors = _resolve_refs(req.evidence_refs)
    if errors:
        raise HTTPException(status_code=422, detail="; ".join(errors))
    return _run_pipeline(req.states, refs, req.scenario_id)


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
    except sources.TeachingUnavailable as e:
        # 教学注入：本次取证失败（阶段07 S5）——unknown，不是业务天气异常
        row = insert_external_evidence(
            activity_id=sources.ACTIVITY_ID, object_type="weather",
            evidence_role="future_condition", source_type="web_api",
            source="weather_api", status="unavailable", value_json=None,
            error_message=str(e))
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


# ---------- A00 阶段06：模型预测证据 + LLM 解释层（LLM 只解释，不判定；解释是附加功能） ----------
from . import explain, predict
from .db import insert_explanation
from .schemas import ExplainRequest


@app.post("/api/tools/predict-crowd")
def tool_predict_crowd():
    """传统 ML 模型预测未来 30 分钟人数 → model_output 证据（独立证据，不覆盖当前 crowd 真实值）。

    数据不足/模型不可用 → status=unavailable，绝不伪造预测值。"""
    row = predict.run_prediction()
    return {"evidence": row}


@app.post("/api/runs/{run_id}/explain")
def api_explain_run(run_id: str, body: ExplainRequest | None = None):
    """LLM 只解释该 run 已算好的结构化结果（不发明事实/不改态势/不发明约束）。

    解释存 explanations 表，禁止写回 runs 任何字段；LLM 未配置或不可用 → 503，
    核心态势/影响/run_id 功能完全不受影响。"""
    snap = query_run(run_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="run not found")
    question = body.question if body else None
    context = explain.build_context(snap, question)
    user_prompt = explain.build_user_prompt(context)
    try:
        text = explain.call_llm(explain.SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        raise HTTPException(status_code=503,
                            detail=f"LLM explanation unavailable: {e}（核心态势/影响/run_id 不受影响）")
    saved = insert_explanation(run_id, question, text, explain.LLM_MODEL,
                               {"system": explain.SYSTEM_PROMPT, "context": context})
    return {"run_id": run_id, "model": explain.LLM_MODEL,
            "explanation": text, "saved_id": saved["id"]}


# ---------- A00 阶段07：条件推演 what-if / 父子 run / 运行对比 / S5 可信降级 ----------
from .db import query_evidence_list, query_run_list
from .schemas import WhatIfRequest


@app.post("/api/runs/{parent_run_id}/what-if")
def api_what_if(parent_run_id: str, req: WhatIfRequest):
    """基于父 run 快照做条件推演：input_overrides 只改有限输入，其余继承父运行；
    用同一套 约束→派生→impact→态势 链完整重跑，生成全新 what-if run_id。

    绝不修改/覆盖父 run 记录；页面不得把 what-if 当最新现实状态。"""
    parent = query_run(parent_run_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="parent run not found")
    ps = parent["input_snapshot"]["states"]
    ov = req.overrides
    entrance_available = ov.entrance_available if ov.entrance_available is not None \
        else ps["entrance"]["available"]
    states = DerivedInput(
        crowd=ov.crowd if ov.crowd is not None else ps["crowd"],
        entrance={"available": entrance_available},
        main_route=ov.main_route if ov.main_route is not None else ps["main_route"],
        support=ov.support if ov.support is not None else ps["support"],
    )
    overrides = ov.model_dump(exclude_none=True)
    assumptions = {"other_conditions_unchanged": True}
    if req.assumptions:
        assumptions["text"] = req.assumptions
    refs = _normalize_refs(parent.get("evidence_refs") or {})  # 没改的条件仍来自父运行
    return _run_pipeline(states, refs, parent.get("scenario_id"),
                         run_type="what_if", parent_run_id=parent_run_id,
                         overrides=overrides, assumptions=assumptions)


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, key))
        else:
            out[key] = v
    return out


@app.get("/api/runs/{run_id}/compare/{other_run_id}")
def api_compare_runs(run_id: str, other_run_id: str):
    """对比两次运行：输入差异 / 派生结果差异 / impact 差异 / 态势差异。"""
    a = query_run(run_id)
    b = query_run(other_run_id)
    if a is None or b is None:
        raise HTTPException(status_code=404, detail="run not found")

    def _meta(r):
        return {"run_id": r["run_id"], "run_type": r["run_type"],
                "parent_run_id": r["parent_run_id"], "created_at": r["created_at"],
                "scenario_id": r["scenario_id"]}

    sa, sb = a["input_snapshot"]["states"], b["input_snapshot"]["states"]
    input_diff = [{"key": k, "a": sa.get(k), "b": sb.get(k), "changed": sa.get(k) != sb.get(k)}
                  for k in sorted(set(sa) | set(sb))]

    da, db = _flatten(a["derived_results"]), _flatten(b["derived_results"])
    derived_diff = [{"key": k, "a": da.get(k), "b": db.get(k), "changed": da.get(k) != db.get(k)}
                    for k in sorted(set(da) | set(db))]

    impact_diff = []
    for t in ("capacity", "entrance", "support", "route"):
        ma = next((i["message"] for i in a["impacts"] if i["impact_type"] == t), None)
        mb = next((i["message"] for i in b["impacts"] if i["impact_type"] == t), None)
        impact_diff.append({"impact_type": t, "a": ma, "b": mb, "changed": ma != mb})

    situation_diff = {
        "summary": {"a": a["situation"]["summary"], "b": b["situation"]["summary"],
                    "changed": a["situation"]["summary"] != b["situation"]["summary"]},
        "completeness": {"a": a["situation_completeness"], "b": b["situation_completeness"],
                         "changed": a["situation_completeness"] != b["situation_completeness"]},
        "unknown_items": {"a": a["unknown_items"], "b": b["unknown_items"],
                          "changed": a["unknown_items"] != b["unknown_items"]},
    }

    return {"run_a": _meta(a), "run_b": _meta(b),
            "input_diff": input_diff, "derived_diff": derived_diff,
            "impact_diff": impact_diff, "situation_diff": situation_diff}


@app.get("/api/runs")
def api_run_list(limit: int = Query(20, ge=1, le=200)):
    """最近运行列表（视图四：reality/what-if、父子关系）。"""
    return {"runs": query_run_list(limit)}


@app.get("/api/evidence")
def api_evidence_list(limit: int = Query(100, ge=1, le=500),
                      role: str | None = Query(None, pattern="^(current_fact|future_condition|knowledge_basis|model_output)$")):
    """最近证据列表（视图三：按 evidence_role 分组展示；role 参数按角色取各自窗口）。"""
    return {"evidence": query_evidence_list(limit, role)}


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """未知 GET 路径一律回退到看板页面（单页应用容错：/index.html、旧链接等不再 404）。

    必须注册在所有路由之后；/api/*、/ws、/docs、/health 等已注册路径不受影响。
    """
    return FileResponse(FRONTEND / "index.html")
