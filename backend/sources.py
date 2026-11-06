"""阶段05 多源证据接入（Open-Meteo 天气 / 路线工具 / 本地知识库 RAG）。

固定原则（官方）：
- 证据角色分层：evidence_role（current_fact / future_condition / knowledge_basis）
  ≠ source_type（web_api / tool / rag）≠ status（这一次取得是否成功）；
- future_condition 未来条件仅作证据保存，绝不篡改当前事实（未来强降雨 ≠ 当前路线异常）；
- no_match 是"检索成功但无匹配"，不是取证失败（status=ok）；服务挂掉才是 status=unavailable；
- 配置经环境变量读取（模板 .env.example，只放变量名），不把密钥提交 Git。
"""

import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .envloader import load_dotenv
from .state import store

load_dotenv()

ACTIVITY_ID = "campus_open_day_01"

# ---------- 配置（环境变量 + 教学默认值） ----------
OPEN_METEO_BASE_URL = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast")
OPEN_METEO_LATITUDE = os.getenv("OPEN_METEO_LATITUDE", "31.23")
OPEN_METEO_LONGITUDE = os.getenv("OPEN_METEO_LONGITUDE", "121.47")
WEATHER_FORECAST_WINDOW_MIN = int(os.getenv("WEATHER_FORECAST_WINDOW_MIN", "30"))
# 教学覆写：非空时跳过真实请求、强制条件（保证 S3 可复现；value_json 标注 teaching_override）
WEATHER_TEACHING_CONDITION = os.getenv("WEATHER_TEACHING_CONDITION", "").strip()
RAG_KB_DIR = Path(os.getenv("RAG_KB_DIR", "kb"))
TOOL_TIMEOUT_S = float(os.getenv("TOOL_TIMEOUT_S", "5"))

OBJECT_TYPES = {"crowd", "entrance", "main_route", "support"}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- 1. Open-Meteo 天气 Web API → future_condition 证据 ----------

def map_weather_condition(prob: float | None, precip: float | None) -> str:
    """原始 API 字段 → 项目统一条件（教学映射，不是行业标准）：
    预报窗口内降水概率 >= 60% 或降水量 >= 2.5mm → heavy_rain_expected；否则 normal。
    """
    prob = prob or 0
    precip = precip or 0.0
    if prob >= 60 or precip >= 2.5:
        return "heavy_rain_expected"
    return "normal"


def fetch_weather() -> dict:
    """真实 HTTP 请求 Open-Meteo，返回统一天气 value_json（时间属性：未来）。

    WEATHER_TEACHING_CONDITION 非空 → 教学覆写（跳过网络，标注 teaching_override）；
    网络/解析失败抛异常（由调用方写 status=error 证据，未知 ≠ 异常）。
    """
    if WEATHER_TEACHING_CONDITION:
        return {
            "forecast_window_min": WEATHER_FORECAST_WINDOW_MIN,
            "condition": WEATHER_TEACHING_CONDITION,
            "teaching_override": True,
        }
    url = (f"{OPEN_METEO_BASE_URL}?latitude={OPEN_METEO_LATITUDE}&longitude={OPEN_METEO_LONGITUDE}"
           f"&hourly=precipitation_probability,precipitation&forecast_hours=2&timezone=auto")
    with urllib.request.urlopen(url, timeout=TOOL_TIMEOUT_S) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    hourly = data.get("hourly", {})
    probs = hourly.get("precipitation_probability") or [None]
    precips = hourly.get("precipitation") or [None]
    return {
        "forecast_window_min": WEATHER_FORECAST_WINDOW_MIN,
        "condition": map_weather_condition(probs[0], precips[0]),
        "raw_time": (hourly.get("time") or [None])[0],
    }


# ---------- 2. 路线查询工具 → current_fact 证据（source_type=tool） ----------

def get_route_status(activity_id: str, state: dict | None = None) -> dict:
    """路线工具真实执行：读取当前路线状态服务（后端内存 store 即路线状态服务）。

    返回 {tool_call_id, status, observed_at, value_json|None}；
    store 无路线状态 → status=unavailable（工具这次没取到，不等于业务路线异常）。
    state 参数仅供测试注入。
    """
    route = (state if state is not None else store.snapshot()).get("main_route")
    if route is None:
        return {"tool_call_id": None, "status": "unavailable",
                "observed_at": None, "value_json": None}
    return {"tool_call_id": None, "status": "ok",
            "observed_at": route["observed_at"],
            "value_json": {"main_route": route["data"]["status"]}}


# ---------- 3. 本地知识库 RAG → knowledge_basis 证据（source_type=rag） ----------

def _load_kb_chunks(kb_dir: Path) -> list[dict]:
    """加载知识库 txt 文档并切分：每个非空内容行 = 一个 chunk（简易切分/索引）。

    解析"标题/来源/获取时间"头部；返回 [{title, source, text}]。
    """
    chunks = []
    for path in sorted(kb_dir.glob("*.txt")):
        title, source = path.stem, str(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith(("标题：", "来源：", "获取时间：", "知识库使用说明：")):
                if line.startswith("标题："):
                    title = line[3:].strip()
                elif line.startswith("来源："):
                    source = line[3:].strip()
                continue
            chunks.append({"title": title, "source": source, "text": line})
    return chunks


def rag_retrieve(query: str, top_k: int = 3, kb_dir: Path | None = None) -> dict:
    """简易关键词检索。返回：
    {retrieval_status: matched|no_match, retrieved_chunks: [...], citation: [...]}
    检索服务不可用（知识库目录缺失/不可读）→ 抛异常（调用方写 status=unavailable）。
    """
    kb_dir = kb_dir or (Path(__file__).resolve().parent.parent / RAG_KB_DIR)
    chunks = _load_kb_chunks(kb_dir)
    keywords = [k for k in query.replace("，", " ").replace("。", " ").split() if k]
    scored = []
    for c in chunks:
        score = sum(1 for k in keywords if k in c["text"])
        if score > 0:
            scored.append((score, c))
    scored.sort(key=lambda x: -x[0])
    top = [{"title": c["title"], "source": c["source"], "text": c["text"], "score": s}
           for s, c in scored[:top_k]]
    if not top:
        return {"retrieval_status": "no_match", "retrieved_chunks": [], "citation": []}
    return {"retrieval_status": "matched", "retrieved_chunks": top,
            "citation": [c["title"] for c in top]}


# ---------- 4. 外部证据引用解析（POST /api/runs 用） ----------

def resolve_evidence_refs(rows: dict[str, dict], ref_ids: list[str]) -> tuple[dict, list[str]]:
    """证据 id 列表 → 引用映射。

    键选择规则（阶段06 扩展）：
    - evidence_role != current_fact → 键 = evidence_role（future_condition/knowledge_basis/
      model_output 等；即使 object_type 是业务对象也不抢占 current_fact 键）；
    - current_fact → 键 = object_type。
    """
    refs: dict[str, str] = {}
    for eid in ref_ids:
        ev = rows.get(eid)
        if ev is None:
            continue  # 存在性由调用方校验（422）
        key = ev["object_type"] if ev["evidence_role"] == "current_fact" else ev["evidence_role"]
        refs[key] = eid
    return refs, []
