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


@app.post("/api/runs")
def new_run():
    sit = compute_situation(SCENE)
    rid = f"run-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    conn = db()
    import json
    conn.execute(
        "INSERT INTO runs (run_id, created_at, scene_json, level, summary) VALUES (?,?,?,?,?)",
        (rid, datetime.now().isoformat(), json.dumps(SCENE, ensure_ascii=False), sit["level"], "；".join(sit["factors"])),
    )
    conn.commit()
    conn.close()
    return {"run_id": rid, "level": sit["level"], "factors": sit["factors"]}


@app.get("/api/runs")
def list_runs():
    conn = db()
    rows = [dict(r) for r in conn.execute(
        "SELECT run_id, created_at, level, summary FROM runs ORDER BY created_at DESC LIMIT 20").fetchall()]
    conn.close()
    return rows


app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
