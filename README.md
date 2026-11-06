# CampusPulse · 校园活动脉搏（A00 态势认知 · 阶段01-08 完整实现）

## 项目简介

CampusPulse 是**校园大型活动现场指挥舱（多对象态势工作台）**：面向校园开放日等大型活动，
把多源现场状态放进显式约束，由 **Python 规则代码**计算出可追溯的派生结果、局部影响与整体态势，
并用 LLM 只做解释（不参与判定）。

完整认知链：**对象状态 → 证据 → 约束 → 派生结果 → 局部影响 → 整体态势 → run_id**。
全链路可追溯：任意整体结论都能沿 main_impacts → derived_results → constraints → evidence 逐层下钻。

**四个视图基于同一个 run_id 底座**（同一份结构化结果，任何视图都不重新计算另一套态势）：

| 视图 | 内容 |
|---|---|
| 视图一 · 整体态势 | run_id、summary、main_impacts、unknown_items、完整性；点击影响展开约束/派生结果/证据 |
| 视图二 · 对象与约束 | 每个对象 状态→证据→约束→派生结果→影响 五层追溯链（层层可点击） |
| 视图三 · 证据与运行 | 全部证据按 evidence_role 分组（current_fact/future_condition/knowledge_basis/model_output），状态/来源/时间 |
| 视图四 · 场景回放与条件推演 | S1-S5 场景加载、what-if 推演（父子 run）、运行对比 |

另有 **场地 3D 视图**（Three.js，本地 vendor）：**3D 只读 `/api/runs/{run_id}` 的结果做空间渲染，
不参与任何业务计算**；Three.js 加载失败自动降级为同数据 2D SVG 平面图（不影响功能评分）。

⚠️ **教学参数声明**：capacity=1000、entrance_total=2、support_reference=10 及全部影响阈值、
态势标签（如"组织压力上升"）**仅用于本教学案例的软件验证，不代表现实安全等级、
专业活动管理标准或应急风险阈值**；模拟数据保留 `SIMULATED` 标记；LLM 只解释已算好的结果，
不发明事实、不修改态势、不补齐缺失证据。

## 快速开始（验收演示最短路径）

```
1. 安装依赖     py -m pip install -r requirements.txt
2. 启动 broker   "C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto\mosquitto.conf -v
3. 启动后端     py -m uvicorn backend.main:app --port 8000
4. 启动模拟器   4 个终端分别 py simulators\{crowd,entrance,main_route,support}_sim.py
5. 打开看板     http://127.0.0.1:8000/
6. 跑回归       py -m tests.regression          （离线，5/5 教学预期校验）
                py -m tests.regression --live   （在线真实链路；S5 需教学注入，未注入自动跳过）
```

## 环境与配置（.env.example 说明）

复制 `.env.example` 为 `.env`（已被 git 忽略，**密钥绝不提交**），变量一览：

| 变量 | 默认 | 说明 |
|---|---|---|
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | deepseek / 空 / deepseek-chat | LLM 解释层（不配 key 时解释接口 503，核心功能不受影响） |
| OPEN_METEO_BASE_URL / LATITUDE / LONGITUDE | 官方 API / 上海坐标 | 天气 Web API（无需 Key） |
| WEATHER_TEACHING_CONDITION | 空 | 教学覆写：`heavy_rain_expected`（S3/S4 复现）/ `unavailable`（S5 取证失败） |
| ROUTE_TOOL_TEACHING_UNAVAILABLE | 空 | `1` 时路线工具取证失败（S5） |
| RAG_KB_DIR / TOOL_TIMEOUT_S | kb / 5 | 本地知识库目录 / 外部请求超时 |

后端通过 `backend/envloader.py` 自动读取仓库根 `.env`（UTF-8/GBK 双编码容错），任意方式启动均可生效。

## 回归测试

```
py -m tests.regression          # 离线：生产管线纯函数 pipeline.run_analysis，S1-S5 全量断言 + 报告
py -m tests.regression --live   # 在线：真实 API 完整证据+运行链路（S5 需教学注入否则跳过）
py -m tests.test_derived        # 阶段03 约束计算 7 条
py -m tests.test_situation      # 阶段04 影响与态势 10 条
py -m tests.test_sources        # 阶段05 多源证据 8 条
py -m tests.test_predict        # 阶段06 预测与解释 6 条
py -m tests.test_whatif         # 阶段07 推演与降级 5 条
```

回归校验内容（S1-S5 官方冻结预期）：派生结果数值、impact 文案、main_impacts、
summary、unknown_items、affected_impacts、situation_completeness；退出码 0=全部通过。

## S1-S5 复现总览（详情见各阶段章节）

| 场景 | 输入（教学） | 期望整体态势 | 快速方式 |
|---|---|---|---|
| S1 稳定基线 | 300 人、2/2、normal、12 | 当前主要条件稳定 | 看板点【300】预设→执行现实运行；或视图四选 S1 |
| S2 约束逼近 | 750 人，其余同 S1 | 容量约束正在逼近，其他主要条件保持稳定 | 预设【750】或视图四选 S2 |
| S3 外部扰动 | 750 人 + 未来强降雨预报 | 同 S2（**未来条件不改写当前路线**） | .env 天气覆写 + 视图四选 S3 |
| S4 多因素 golden | 900、1/2、limited、8 + 天气/RAG/预测证据 | 组织压力上升（教学标签） | 阶段06 整段脚本或视图四选 S4 |
| S5 信息退化 | 天气/路线取证失败，其余同 S4 | 部分影响判断不完整（证据不完整），partial | .env 两行注入 + 视图四选 S5 或回归 --live |

每次运行生成唯一 `run_id`（run_type=reality/what_if）；完成后的 run **永不覆盖**，
改条件走 what-if 新运行，丢证据走 reality 新运行（可信降级）。

## 架构

```
浏览器看板 / curl / FastAPI /docs
   │ POST /api/sim/set（改模拟配置；纯内存，重启回默认）
   ▼
backend: sim_config 内存配置 ◀──GET /api/sim/config（每 2s 轮询）── 4 个模拟器
                                    │ publish (qos=0, retain=False)
   ┌────────────────────────────────▼
   │ Mosquitto 127.0.0.1:1883（topic: campuspulse/campus_open_day_01/state/*）
   ▼
backend: mqtt_bridge（通配订阅+信封校验）→ state.py store ──┬─▶ GET /api/current
        ├─▶ db.py 双写（成功：observations+evidence(ok) 同事务；失败：仅 evidence）  └─▶ ws_hub → /ws → 浏览器看板
        └─▶ 证据查询：/api/history /api/evidence/latest /api/evidence/{id}
```

统一消息外壳（每条 MQTT 消息）：

```json
{"activity_id":"campus_open_day_01","object_type":"crowd","observed_at":"2026-11-05T04:00:00+00:00","source_type":"SIMULATED","data":{"count":500}}
```

## 依赖安装

Windows 下 pip 不在 PATH，用 `py -m pip`：

```
py -m pip install -r requirements.txt
```

Mosquitto 使用系统已安装的 `C:\Program Files\mosquitto`（本仓库自带配置文件 `mosquitto\mosquitto.conf`）。

## 启动步骤（按顺序，共 4 类进程）

**① 启动 MQTT broker**（终端 A，仓库根目录）

```
"C:\Program Files\mosquitto\mosquitto.exe" -c mosquitto\mosquitto.conf -v
```

> 若 Windows 服务 `mosquitto` 正在运行会占用 1883 端口，先 `net stop mosquitto`。

**② 启动后端 FastAPI**（终端 B，仓库根目录）

```
py -m uvicorn backend.main:app --port 8000
```

验证：`curl http://127.0.0.1:8000/health` → `{"status":"ok"}`

**③ 启动 4 个模拟器**（终端 C/D/E/F，仓库根目录）

```
py simulators\crowd_sim.py
py simulators\entrance_sim.py
py simulators\main_route_sim.py
py simulators\support_sim.py
```

> 模拟器冷启动后先轮询后端配置，拉取成功才开始发布（后端未启动时不会发消息）。

**④ 打开看板**

浏览器访问 http://127.0.0.1:8000/ ，看到 4 张卡片实时数值与"已连接"状态。

## 修改数据源（三种等价方式）

配置唯一入口是后端内存（`POST /api/sim/set`），模拟器每 2s 轮询一次；改完 ≤3s 页面自动更新，无需重启任何进程。

**方式一：页面预设按钮**（看板顶部【300】【500】【650】【750】【900】）

| 预设 | crowd | entrance_available | main_route | support |
|---|---|---|---|---|
| 300 | 300 | 2 | normal | 10 |
| 500 | 500 | 2 | normal | 10 |
| 650 | 650 | 2 | normal | 10 |
| 750 | 750 | 1 | normal | 8 |
| 900 | 900 | 1 | limited | 8 |

**方式二：FastAPI /docs 在线调试**

打开 http://127.0.0.1:8000/docs → 找到 `POST /api/sim/set` → Try it out → 填入请求体执行。
（各字段可取值直接列在 schema 里；非法值返回 422。）

**方式三：curl**

```
curl -X POST http://127.0.0.1:8000/api/sim/set -H "Content-Type: application/json" -d "{\"crowd\":900,\"entrance_available\":1,\"main_route\":\"limited\",\"support\":8}"
```

可取值：crowd ∈ {300,500,650,750,900}；entrance_available ∈ {1,2}；main_route ∈ {normal,limited}；support ∈ {8,10,12}（support=12 无预设按钮，但 API 合法）。

**取证模式（阶段02）**：`mode` 字段按对象切换 `ok / unavailable / error`（可选，缺省全 ok；POST 不带 mode 会把模式重置为 ok）：

```
curl -X POST http://127.0.0.1:8000/api/sim/set -H "Content-Type: application/json" -d "{\"crowd\":500,\"entrance_available\":2,\"main_route\":\"normal\",\"support\":10,\"mode\":{\"entrance\":\"unavailable\"}}"
```

unavailable/error 只表示"本次取证失败"：新增失败证据（value_json=null），**不伪造业务值、不覆盖最后成功值**；改回 ok 即恢复双写。

查看当前配置：`GET /api/sim/config`。

## 接口

- `GET /health` → `{"status":"ok"}`
- `GET /api/current` → 当前全部对象最新状态（全部来自 MQTT 实时消息，非写死；结构：
  `{activity_id, objects: {crowd/entrance/main_route/support: 信封}, updated_at}`）
- `WS /ws` → 连接即推全量快照，之后每个对象更新推增量
- `GET /api/sim/config` → 当前模拟器配置（模拟器每 2s 轮询此接口）
- `POST /api/sim/set` → 更新模拟器配置（body 见上表；非法值 422）
- `GET /api/history/{object_type}` → 对象历史观测（只含成功业务事实；`limit` 默认 50，1~200；非法对象 422）
- `GET /api/evidence/latest/{object_type}` → 对象最新一条证据（获取状态 ≠ 业务状态）
- `GET /api/evidence/{evidence_id}` → 单条证据详情（不存在 404）

## 关闭与重启复现

1. 四个模拟器终端分别 Ctrl+C；
2. uvicorn 终端 Ctrl+C；
3. mosquitto 终端 Ctrl+C；
4. 再按上面"启动步骤"依次重新启动，看板恢复实时更新。

模拟器 `retain=False` + 后端纯内存态：重启后状态从 MQTT 实时消息重新建立，不依赖上次运行残留。
注意：**后端重启后模拟配置回到默认（500 预设：crowd=500、entrance_available=2、normal、support=10）**，
模拟器会在一个轮询周期（2s）内自动跟随——这是内存态设计，不是 bug。

## 端口排查

- 1883 被占：`netstat -ano | findstr :1883`，通常是 mosquitto 服务，`net stop mosquitto` 后再手动启动。
- 8000 被占：`netstat -ano | findstr :8000`，`taskkill /F /PID <pid>`。

## 阶段01 验收对照

| 验收点 | 做法 |
|---|---|
| 页面变化必须来自数据源变化 | 点预设按钮/调 `/api/sim/set`，看板 ≤3s 自动变化、无手动刷新；卡片只由 WebSocket 消息渲染 |
| `/api/current` 非写死 | 用 mosquitto_pub 手工发布 `data.count=777`，接口与页面立即显示 777 |
| 统一消息外壳 | 每条消息含 activity_id/object_type/observed_at/source_type/data，全部属于 campus_open_day_01 |
| 模拟器只输出原始状态 | 模拟器只做配置→data 映射与发布，无阈值/标签/结论逻辑；配置校验由后端 Literal 承担 |
| 关闭重启可复现 | 按上文"关闭与重启复现"步骤（配置回 500 默认属预期） |

## A00 阶段02：证据层（SQLite 双写 + 证据查询）

### 数据库

位置：`backend/campuspulse.db`（与 Day1 的 `runs` 表同一文件；被 .gitignore 忽略，重启后历史仍在）。
每次数据库操作独立连接 + WAL 模式；建表幂等（`CREATE TABLE IF NOT EXISTS`）。

建表 SQL：

```sql
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
```

### 证据语义（重要）

| 概念 | 含义 |
|---|---|
| `status` | **只表示本次取证是否成功**（ok / unavailable / error），不表示业务对象正常/异常 |
| `value_json` | 只保存**成功取得**的业务事实；失败时为 null（不伪造业务值） |
| `observed_at` | 业务状态被观察到的时间；失败时为 null（不伪造新时间），`retrieved_at` 为本次获取时间 |
| 双写 | 成功消息 → 同一事务写 observations + evidence(status=ok)；失败消息 → 只写 evidence |
| 最后成功值 | 取证失败期间，内存 store 与页面"最后成功确认"值保留上一次成功结果 |

### 模拟 unavailable / error（手动测试）

1. 正常模式下记下入口卡片值与 `/api/history/entrance` 的 count；
2. 切失败：
   ```
   curl -X POST http://127.0.0.1:8000/api/sim/set -H "Content-Type: application/json" -d "{\"crowd\":500,\"entrance_available\":2,\"main_route\":\"normal\",\"support\":10,\"mode\":{\"entrance\":\"unavailable\"}}"
   ```
3. 观察（约 2~4s 后）：看板"证据追踪"区入口行 `最新获取` 变为灰色 unavailable 徽章（带 retrieved_at/来源/evidence_id）；入口卡片数值**保持最后成功值不变**；`/api/evidence/latest/entrance` 的 `status=unavailable、value_json=null、observed_at=null`；`/api/history/entrance` 的 count **不再增长**（无伪造 observations）；
4. `mode.entrance` 改 `error` → 琥珀色徽章 + `error_message`；
5. 改回 `"mode":{"entrance":"ok"}` → 双写恢复、卡片与"最后成功确认"行继续更新。

完整演示流：`ok → unavailable → ok`。失败模式下每 2s 落一条失败证据属预期（每次取证尝试都记录；qos0 丢失下周期自愈）。

## A00 阶段03：显式约束与派生结果

### 教学配置（独立 config.json，教学参数，不是行业标准）

```json
{
  "capacity": 1000,
  "entrance_total": 2,
  "support_reference": 10
}
```

- 位置：`campuspulse/config.json`（后端每次计算时读取同一份参数；改文件即生效，无需重启）
- 只用于 CampusPulse 教学场景，不代表真实活动行业标准
- 文件缺失/非法时接口返回 500 并说明，绝不静默使用默认值

### 约束计算逻辑（状态 + 证据 → 约束 → 派生结果）

| 约束 | 公式 | 派生结果 |
|---|---|---|
| 人数容量 | remaining_capacity = capacity − crowd | remaining_capacity、remaining_capacity_ratio = remaining_capacity / capacity |
| 入口 | entrance_ratio = available / total（total 取配置 entrance_total） | entrance_ratio |
| 支持资源 | support_gap = support_reference − support（可为负） | support_gap、support_ratio = support / support_reference |
| 路线 | main_route 映射（normal→normal；limited→reduced） | route_flexibility |

⚠️ 本阶段只计算派生结果，**不生成局部影响与整体态势**（阶段04 再做）。

### 接口 POST /api/compute-derived

请求体（输入各对象最新有效业务状态，来自 observations）：

```json
{
  "crowd": 300,
  "entrance": { "available": 2 },
  "main_route": "normal",
  "support": 12
}
```

响应体（config / states / derived 分层，不混层）：

```json
{
  "activity_id": "campus_open_day_01",
  "config": { "capacity": 1000, "entrance_total": 2, "support_reference": 10 },
  "states": { "crowd": 300, "entrance": { "available": 2 }, "main_route": "normal", "support": 12 },
  "derived": {
    "capacity": { "remaining_capacity": 700, "remaining_capacity_ratio": 0.7 },
    "entrance": { "entrance_ratio": 1.0 },
    "support": { "support_gap": -2, "support_ratio": 1.2 },
    "route": { "route_flexibility": "normal" }
  },
  "computed_at": "2026-11-06T04:00:00+00:00"
}
```

非法输入（crowd<0 / main_route 非 normal|limited / 缺字段）→ 422。

### 手动测试步骤（S1 / S2）

**S1（稳定基线）**：
```
curl -X POST http://127.0.0.1:8000/api/compute-derived -H "Content-Type: application/json" -d '{"crowd":300,"entrance":{"available":2},"main_route":"normal","support":12}'
```
期望：remaining_capacity=700、ratio=0.70、entrance_ratio=1.00、support_gap=−2、route_flexibility=normal。

**S2（约束逐步逼近）**：只改 crowd 300→500→650→750 重发四次，其余字段不变——
remaining_capacity=700→500→350→250、ratio=0.70→0.50→0.35→0.25 持续变化；入口/路线/支持派生结果保持稳定。

**现场验证值**：crowd=620 → 380/0.38；support 8→11 → support_gap 2→−1、support_ratio 0.80→1.10。

**自动化测试**：`py -m tests.test_derived`（7 条：S1、S2 全序列、现场验证值×2、入口 1/2、路线映射、响应分层禁词守卫）。

## A00 阶段04：局部影响 → 整体态势 → run_id

### 硬性红线

- 态势全部由 **Python 规则代码**计算，LLM 不参与判定；
- run 记录存入 SQLite `runs` 表，**完成之后禁止原地覆盖**（代码中不存在 UPDATE runs 的路径，只有 INSERT 与 SELECT）；每次完整分析生成全新 `run_id`；
- 只做 reality 运行（`run_type=reality`、`parent_run_id=null`）；what-if 属阶段07。

### 教学影响映射规则（仅教学验证，不是真实安全标准）

| 对象 | 条件 | 影响文案（message） | 是否进入 main_impacts |
|---|---|---|---|
| 容量 | remaining_capacity_ratio ≥ 0.50 | 容量余量充足 | 否 |
| 容量 | 0.20 ≤ ratio < 0.50 | 容量余量缩小 / 容量约束正在逼近 | **是** |
| 容量 | ratio < 0.20 | 容量余量明显缩小 / 容量相关压力上升 | **是** |
| 入口 | entrance_ratio = 1.0 | 入口条件稳定 | 否 |
| 入口 | entrance_ratio < 1.0 | 通行灵活性下降 | **是** |
| 支持 | support_ratio ≥ 1 | 支持条件充足 | 否 |
| 支持 | support_ratio < 1 | 支持能力下降 | **是** |
| 路线 | route_flexibility = normal | 路线条件稳定 | 否 |
| 路线 | route_flexibility = reduced | 路线灵活性下降 | **是** |

每条 impact 结构：`impact_id / impact_type / source_constraint / source_derived_result / message`（可追溯回约束与派生结果）。

### 整体态势聚合（有限教学聚合规则）

- `main_impacts` 只放需要提高关注的影响（S1 → `[]`；S2 → `[capacity]`）；
- `summary` 由规则归纳：无关注影响 → **当前主要条件稳定**；否则各影响标签以"、"连接，
  未全部命中时追加"，其他主要条件保持稳定"（官方逐字：S2 → **容量约束正在逼近，其他主要条件保持稳定**）；
- `unknown_items` = 本次运行缺少成功证据引用的对象；`situation_completeness` = complete / partial。

### runs 建表 SQL（全新库；旧 Day1 表自动改名为 runs_legacy 保留）

```sql
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    scenario_id TEXT NULL,
    run_type TEXT NOT NULL CHECK(run_type IN ('reality','what_if')),
    parent_run_id TEXT NULL,
    input_snapshot_json TEXT NOT NULL,
    evidence_refs_json TEXT NOT NULL,
    derived_results_json TEXT NOT NULL,
    impacts_json TEXT NOT NULL,
    situation_json TEXT NOT NULL,
    unknown_items_json TEXT NOT NULL,
    situation_completeness TEXT NOT NULL CHECK(situation_completeness IN ('complete','partial')),
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL
);
```

> 迁移说明：Day1 骨架的旧 `runs` 表（含 scene_json/level/summary 的演示结构）在首次访问时
> 整体改名保留为 `runs_legacy`（旧数据不丢），再按上表重建 `runs`。Day1 的 POST/GET /api/runs
> 演示路由已退役（其余演示路由保留）。

### 接口

- `POST /api/runs` — 请求：`{"scenario_id": "S1"|null, "states": {crowd, entrance:{available}, main_route, support}, "evidence_refs": ["ev_...", ...]}`；
  `evidence_refs` 中的每个 id 必须存在于 evidence 表且 `status=ok`（否则 422）；执行完整分析并落库，返回 `{"run_id": "run-..."}`
- `GET /api/runs/{run_id}` — 整套运行快照：input_snapshot（states+config）/ evidence_refs（对象→证据id 映射）/ derived_results / impacts / situation / unknown_items / situation_completeness / created_at / completed_at；不存在 404
- `GET /api/runs/latest` — 最近一次 reality 运行快照（首页"当前 run_id"用）

### 前端【视图一：整体态势页面】

首页顶部展示：当前 `run_id`、`summary` 整体结论、`main_impacts` 主要影响（点击展开约束/派生结果，
点击证据 id 查看证据详情）、`unknown_items`、完整性徽章；按钮"执行现实运行"用当前数据源状态 +
最新成功证据生成新 run_id（reality）。

### 手动复现 S1 / S2（完整链路：状态→证据→约束→派生→影响→态势→run_id）

PowerShell（单引号 JSON + `Invoke-RestMethod`，无引号坑）；先取四个最新成功证据 id：
```powershell
(Invoke-RestMethod http://127.0.0.1:8000/api/evidence/latest/crowd).evidence.evidence_id
(Invoke-RestMethod http://127.0.0.1:8000/api/evidence/latest/entrance).evidence.evidence_id
(Invoke-RestMethod http://127.0.0.1:8000/api/evidence/latest/main_route).evidence.evidence_id
(Invoke-RestMethod http://127.0.0.1:8000/api/evidence/latest/support).evidence.evidence_id
```
把四个 id 代入下面命令的 evidence_refs（也可用 /docs 页面操作）：

**S1**：
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/runs -Method Post -ContentType 'application/json' -Body '{"scenario_id":"S1","states":{"crowd":300,"entrance":{"available":2},"main_route":"normal","support":12},"evidence_refs":["ev_crowd_xxx","ev_entrance_xxx","ev_main_route_xxx","ev_support_xxx"]}'
```
返回 `run_id`（如 `run-20261106-175632-7cfcd3`）。`Invoke-RestMethod http://127.0.0.1:8000/api/runs/<run_id>` 查看快照，
期望：`summary = 当前主要条件稳定`、`main_impacts = []`、`unknown_items = []`、`situation_completeness = complete`。

**S2**：把 `"crowd":300` 改成 `"crowd":750`（scenario_id 改 "S2"）重发 → **新的 run_id**，
期望：`summary = 容量约束正在逼近，其他主要条件保持稳定`、`main_impacts = [capacity]`、
`derived_results.capacity = {remaining_capacity: 250, remaining_capacity_ratio: 0.25}`。

**验证不可覆盖**：再次取第一次的 `/api/runs/<S1的run_id>` → 快照与之前完全一致（旧运行未被改写）；
`GET /api/runs/latest` = 最后一次运行。

**自动化测试**：`py -m tests.test_situation`（9 条：S1、S2-750、S2 全序列、620 现场值、入口 1/2、
支持 8、路线 limited、全命中档、unknown/partial）。

## A00 阶段05：接入多源证据（天气 / 路线工具 / 本地知识库 RAG）

### 证据角色分层（固定原则）

| 信息 | evidence_role | source_type | 时间属性 |
|---|---|---|---|
| 当前人数/入口 | current_fact | simulated | 当前 / 已发生 |
| 当前路线（工具查询） | current_fact | tool | 当前 / 已发生 |
| 天气预报（Open-Meteo） | future_condition | web_api | **未来** |
| 场馆/活动规则（本地 RAG） | knowledge_basis | rag | 规则有效期 |

`evidence_role` 回答"扮演什么角色"；`source_type` 回答"通过什么通道取得"；`status` 回答"这一次取得是否成功"。
**未来条件不篡改当前事实**：未来强降雨 ≠ 当前路线异常；**no_match ≠ 取证失败**（status=ok）；
**工具 unavailable ≠ 业务对象失败**（不是 route=blocked）。

### 三个工具接口

- `POST /api/tools/weather` — 真实 HTTP 请求 Open-Meteo，返回 future_condition 证据：
  `value_json = {forecast_window_min, condition(normal|heavy_rain_expected), raw_time}`；
  请求失败 → status=error、value_json=null（未知 ≠ 异常）
- `POST /api/tools/route` — 路线查询工具真实执行（读取路线状态服务=后端内存 store），
  返回 current_fact 证据（source_type=tool）；store 无路线状态 → status=unavailable
- `POST /api/tools/rag` — 请求体 `{"query": "..."}`；本地知识库（kb/*.txt，含标题/来源/获取时间）关键词检索：
  matched → status=ok + `retrieval_status=matched` + retrieved_chunks + citation；
  no_match → status=ok + `retrieval_status=no_match`（检索成功但无匹配，不编造引用）；
  知识库目录不可读 → status=unavailable、value_json=null

三类证据统一写入 evidence 表（带各自 evidence_role/source_type），
evidence_id 沿用 `ev_{object_type}_{seq:03d}`（weather/knowledge/main_route 各自序列）。

### POST /api/runs 外部证据引用（阶段05 扩展）

`evidence_refs` 可混入各角色证据 id；写入 `evidence_refs_json` 的映射键 =
业务对象 object_type（crowd/entrance/main_route/support，即 current_fact）
或 evidence_role（future_condition / knowledge_basis 等外部证据）。
查询 run_id 即可看出本次分析使用了哪些角色的证据。

### .env.example（只放变量名，不要密钥；复制为 .env 后填写，.env 已被 git 忽略）

| 变量 | 默认值 | 说明 |
|---|---|---|
| OPEN_METEO_BASE_URL | https://api.open-meteo.com/v1/forecast | 天气 API 地址（无需 Key） |
| OPEN_METEO_LATITUDE / LONGITUDE | 31.23 / 121.47 | 场地坐标 |
| WEATHER_FORECAST_WINDOW_MIN | 30 | 预报窗口（分钟） |
| WEATHER_TEACHING_CONDITION | （空） | 设为 heavy_rain_expected 时强制降雨条件（教学覆写，value_json 标注 teaching_override，保证 S3 可复现） |
| RAG_KB_DIR | kb | 知识库目录 |
| TOOL_TIMEOUT_S | 5 | 外部请求超时 |

### S3 复现（未来强降雨不篡改当前路线）

1. 后端以教学覆写启动（保证可复现；去掉该变量则走真实预报）：
   ```
   set WEATHER_TEACHING_CONDITION=heavy_rain_expected   （cmd；PowerShell 用 $env:WEATHER_TEACHING_CONDITION='heavy_rain_expected'）
   py -m uvicorn backend.main:app --port 8000
   ```
2. 取三类证据（PowerShell 可用 /docs 代替）：
   - `POST /api/tools/weather` → `ev_weather_xxx`（future_condition，condition=heavy_rain_expected）
   - `POST /api/tools/route` → `ev_main_route_xxx`（current_fact/tool，main_route=normal）
   - `POST /api/tools/rag` body `{"query":"强降雨 注意事项"}` → `ev_knowledge_xxx`（knowledge_basis，matched）
   - 四个对象的最新 ok 证据 id（`GET /api/evidence/latest/{object_type}`）
3. 提交 S3 运行（states: crowd=750、entrance 2/2、main_route=normal、support=12；evidence_refs 含上述全部 id）：
   `POST /api/runs` → 新 run_id
4. 验证：`GET /api/runs/{run_id}` → evidence_refs 同时含 `future_condition` 与 `knowledge_basis` 键；
   `derived_results.route = normal`（**当前路线事实未被未来天气覆盖**）；
   summary = 容量约束正在逼近，其他主要条件保持稳定；`GET /api/current` 的 main_route 仍为 normal。

**自动化测试**：`py -m tests.test_sources`（8 条：天气映射、路线工具 ok/unavailable、
RAG matched/no_match/unavailable、引用解析、S3 边界链）。

## A00 阶段06：模型预测证据 + LLM 解释层

### 硬边界

- **模型预测不是当前事实**：`evidence_role=model_output` 是独立预测证据，绝不覆盖当前 crowd 真实值
- **LLM 只解释、不判定**：只读取 run 已算好的结构化结果，输出解释文本；不返回/不修改
  impact、situation、summary；**禁止写回 runs 表任何字段**（解释单独存 explanations 表）
- **先计算，再解释**：关闭 LLM 服务时，态势/影响/run_id/证据全部功能照常可用，解释只是附加功能

### ML 人数预测（POST /api/tools/predict-crowd）

- 模型 `crowd_forecast_v1`：一元线性回归（时间序号→crowd），Baseline=上一窗口值；
  时间序前 80% 训练 / 后 20% 测试，MAE 评估并与 Baseline 对比（诚实保留结果）
- 训练数据 = observations 里的历史 crowd 成功事实；无未来信息泄漏
- 证据 value_json（官方字段）：`model_version / prediction_for / prediction_window_min(30) /
  predicted_crowd / metric_summary{mae, baseline_mae, train_points, test_points} / trained_at`
- 数据不足（<5 点）→ `status=unavailable`，**绝不伪造预测值**

### LLM 解释（POST /api/runs/{run_id}/explain）

请求体 `{"question": "..."}`（可选）。后端组装该 run 的结构化上下文（当前状态/证据引用/
约束/派生/影响/态势/未知项/预测证据），交给 LLM；解释存 `explanations` 表
（id/run_id/question/explanation/model/prompt_json/created_at）。LLM 未配置或不可用 → 503 并说明，
核心功能不受影响。

**prompt 样例**（系统提示，五条硬边界）：
```
你是 CampusPulse 校园活动脉搏系统的态势解释助手。
你只解释下面已经计算好的结构化运行结果，严格遵守：
1. 只解释已有计算结果，不发明任何新事实、不补充缺失数据；
2. 不新增、不修改任何业务约束或规则；
3. 不修改整体态势标签（summary）、不修改任何 impact 文案；
4. 缺证据时明确说明"当前缺少相关证据"，不得编造；
5. 不出现系统没有定义的专业安全等级（如"高风险""必须疏散"等）。
你的输出只用于帮助人理解系统已经算出的结论，不是新的裁决。
```

### LLM 配置（.env；DeepSeek 或任何 OpenAI 兼容 chat/completions）

```
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=          ← 填真实 key（.env 已被 git 忽略；不填则解释接口 503，核心不受影响）
LLM_MODEL=deepseek-chat
```

### 前端

视图一新增：`生成人数预测证据（ML）` 按钮（显示证据 id/预测值/MAE）；`LLM 解释当前运行`
输入框+按钮（显示解释文本；不可用时明确提示"解释不可用，核心态势不受影响"）。
首页保持"整体结论+影响链"结构，不是聊天框。

### S4 golden 复现（900 人全链路：多源证据→约束→派生→impact→态势→ML预测→LLM解释）

1. 后端带天气教学覆写启动：PowerShell `$env:WEATHER_TEACHING_CONDITION='heavy_rain_expected'` 后
   `py -m uvicorn backend.main:app --port 8000`（.env 里配好 LLM_API_KEY 才有解释）
2. 取证据：四对象最新 ok 证据 id + `POST /api/tools/weather`（future_condition）+
   `POST /api/tools/rag` `{"query":"强降雨 注意事项"}`（knowledge_basis）+
   `POST /api/tools/predict-crowd`（model_output）
3. 提交 S4 运行：states = {crowd:900, entrance:{available:1}, main_route:"limited", support:8}，
   evidence_refs 含上面全部 id → `POST /api/runs` → run_id
4. 验证：`GET /api/runs/{run_id}` → `summary = 组织压力上升`（教学态势标签，非专业安全评估）、
   main_impacts = 4 项（capacity/entrance/support/route）、evidence_refs 分层含
   model_output/future_condition/knowledge_basis；`/api/current` 的 crowd 仍是 900（预测没篡改现实）
5. `POST /api/runs/{run_id}/explain` `{"question":"为什么组织压力上升"}` → 自然语言解释
   （只解释已有结果）；停掉 LLM（不配 key）再调 → 503，第 4 步全部功能依旧可用

**自动化测试**：`py -m tests.test_predict`（6 条：趋势外推、数据不足、无泄漏、prompt 五条硬边界、
上下文只含结构化结果、S4 model_output 引用分层）；全量回归 30/30。

## A00 阶段07：条件推演 what-if、父子 run、S5 可信降级

### 硬约束

- `run_type` 只取 reality / what_if；what-if 必须携带 `parent_run_id`、`input_overrides_json`、
  `assumptions_json`（至少含 `other_conditions_unchanged: true`）；**what-if 生成全新 run_id，
  绝不修改/覆盖父 run**（runs 表只有 INSERT/SELECT）
- 取证失败 status=unavailable → 标记 unknown_items；**unknown ≠ 业务异常**，绝不编造业务状态
- 两条链不能混：改条件 → what-if 新运行；丢证据 → reality 新运行（可信降级）

### 数据库字段（阶段07 追加两列，旧 run 行不受影响）

```sql
ALTER TABLE runs ADD COLUMN input_overrides_json TEXT NULL;
ALTER TABLE runs ADD COLUMN assumptions_json TEXT NULL;
```

### 接口

- `POST /api/runs/{parent_run_id}/what-if` — 请求体 `{"overrides": {crowd?/entrance_available?/main_route?/support?}, "assumptions": "可选说明"}`；
  基于父 run 快照只改有限输入、其余继承（含证据引用），**完整重跑 约束→派生→impact→态势 链**，返回新 run_id
- `GET /api/runs/{run_id}/compare/{other_run_id}` — 五维对比：输入差异 / 派生结果差异 / impact 差异 /
  态势差异（summary/completeness/unknown_items）；只列变化项 + 逐项 a→b
- `GET /api/runs?limit=30` — 运行列表（reality/what_if、父子关系）；`GET /api/evidence?limit=200` — 证据列表（视图三）

### S5 可信降级语义

- 路线：`states.main_route = null` 表示"本次路线事实无法确认"→ derived `route_flexibility=unknown`、
  impact="路线条件无法确认（本次取证失败）"、affected_impacts += route_impact、unknown_items += route_current_state；
  业务状态绝不写成 blocked/unavailable
- 天气：evidence_refs 可引用 status=unavailable 的 future_condition 证据（记录"这次没拿到"）→
  unknown_items += weather_future_condition、affected_impacts += future_route_impact
- summary 规则新增：有受影响判断时 → "…，部分影响判断不完整（证据不完整）"
- situation_completeness：complete / partial（只两值，无百分比）

### 前端

- **场地视图（3D）**：Three.js（本地 vendor，无其他第三方库）——场地平面 + 入口立体块 + 拥堵色阶 +
  简单动画（缓慢自转/拖拽视角/受限入口脉冲）；**3D 不参与计算**，只呈现最新 run 已算出的
  remaining_capacity_ratio 与实时原始状态；Three.js 加载失败自动降级 2D SVG（同一份数据）
- **视图三 证据与运行**：按 evidence_role 分组展示全部证据（current_fact/future_condition/
  knowledge_basis/model_output）+ status 徽章 + 来源时间 + 当前运行 unknown_items
- **视图四 场景回放与条件推演**：运行列表（reality/what_if/父子标注）、查看、对比父运行、
  覆盖表单生成 what-if（留空=继承父运行）、前后对比展示

### S4-D 对照与 S5 手动测试步骤

**S4-C 基准 + S4-D 推演（PowerShell；服务在跑时直接执行）**：
```powershell
# 1) S4-C reality 基准（900 / 1-2 / limited / 8 + 天气/RAG 证据）——用阶段06 的 S4 整段脚本生成，得到 $run.run_id
# 2) S4-D what-if：入口恢复 2/2（支持仍 8）
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/runs/$($run.run_id)/what-if" -Method Post -ContentType 'application/json' -Body '{"overrides":{"entrance_available":2},"assumptions":"假设入口恢复"}'
# 3) 对比
Invoke-RestMethod "http://127.0.0.1:8000/api/runs/$($run.run_id)/compare/<whatif_run_id>"
```
期望：S4-C summary=组织压力上升；S4-D 为 what_if、parent 指向 S4-C、entrance impact 变"入口条件稳定"、
支持/容量/路线影响保留；对比里 input_diff 只有 entrance、derived 只有 entrance_ratio、impact 只有 entrance 变化；
**父 run 快照原样可查（未被覆盖）**。（S4-A/B 同理：A=overrides {entrance_available:2, support:10}；B={support:10}。）

**S5 信息退化**：
1. 改 `.env`：`WEATHER_TEACHING_CONDITION=unavailable` + 加 `ROUTE_TOOL_TEACHING_UNAVAILABLE=1`，重启后端
2. `POST /api/tools/weather` → status=unavailable（value_json=null）；`POST /api/tools/route` → unavailable；
   `POST /api/tools/rag`（强降雨）→ no_match（status=ok，不算失败）
3. 提交 S5 reality 运行：states 的 main_route 填 null（PowerShell：`main_route=$null`），
   evidence_refs 含 crowd/entrance/support 的 ok 证据 + 天气 unavailable 证据 + RAG no_match 证据
4. 验证：unknown_items=[route_current_state, weather_future_condition]、
   affected_impacts=[future_route_impact, route_impact]、completeness=partial、
   main_impacts 仅 [capacity, entrance, support]（仍有证据的部分继续计算）、
   summary 含"部分影响判断不完整（证据不完整）"、全文无 blocked/异常；
   `/api/current` 的 main_route 业务状态仍是 normal（取证失败 ≠ 业务异常）
5. 恢复 `.env`（heavy_rain_expected、去掉 ROUTE_TOOL_TEACHING_UNAVAILABLE）重启

**自动化测试**：`py -m tests.test_whatif`（5 条：S4 基准、S4-D 恢复入口、S4-A 起点、S5 双未知、
what-if 落库与父行不可覆盖）；全量回归 **41/41**。

## 开发约定

- 代码为本项目新写，基于已学能力迁移式实现（多站点并列判定思路 → 多对象状态并行采集）。
- 每阶段独立 commit；AI 开发会话快照存 `docs/ai-sessions/`。
- 后端从仓库根目录以 `py -m uvicorn backend.main:app` 启动（backend 内部使用相对导入）。
