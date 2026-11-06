# CampusPulse · 校园活动脉搏（A00：多对象现场数据链 + 证据层）

阶段01 打通：**模拟数据源 → MQTT → FastAPI 内存状态 → WebSocket → 浏览器最小看板**。
阶段02 新增：**证据层** —— SQLite 双表（observations / evidence）双写、3 个证据查询接口、看板证据追踪区。
阶段03 新增：**显式约束与派生结果** —— 独立教学配置 + `POST /api/compute-derived` 约束计算接口 + S1/S2 测试。

页面展示 4 个对象的**原始业务数值**与**本次取证状态**（严格区分"最后成功确认的业务值"与
"最新获取状态"）；各阶段刻意**不做**：态势计算、影响链、run_id。所有数据来自模拟器经 MQTT
推送的实时状态（`source_type=SIMULATED`），页面自己不维护另一套"当前值"。

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

## 开发约定

- 代码为本项目新写，基于已学能力迁移式实现（多站点并列判定思路 → 多对象状态并行采集）。
- 每阶段独立 commit；AI 开发会话快照存 `docs/ai-sessions/`。
- 后端从仓库根目录以 `py -m uvicorn backend.main:app` 启动（backend 内部使用相对导入）。
