# CampusPulse · 校园活动脉搏（A00 阶段01：多对象现场数据链）

本阶段打通：**模拟数据源 → MQTT → FastAPI 内存状态 → WebSocket → 浏览器最小看板**。

页面只展示 4 个对象的**原始业务数值**，本阶段刻意**不做**：态势计算、影响链、证据、
run_id、SQLite。所有数据来自模拟器经 MQTT 推送的实时状态（`source_type=SIMULATED`），
页面自己不维护另一套"当前值"。

## 架构

```
simulators/*_sim.py                     backend/
（每 2s 热读 sim_values.json）           mqtt_bridge.py（paho 订阅线程）
   │ publish (qos=0, retain=False)        │ 通配订阅 campuspulse/+/state/+
   ▼                                      ▼ JSON 信封校验 + activity_id 过滤
Mosquitto 127.0.0.1:1883 ──────────▶ state.py（内存最新状态）──┬─▶ GET /api/current
   topic: campuspulse/campus_open_day_01/state/*                └─▶ ws_hub.py ─▶ /ws ─▶ 浏览器看板
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

**④ 打开看板**

浏览器访问 http://127.0.0.1:8000/ ，看到 4 张卡片实时数值与"已连接"状态。

## 修改数据源，页面自动刷新

模拟器每个发布周期（2s）热读一次 `simulators\sim_values.json`，**改文件即生效，无需重启模拟器**：

| 对象 | 文件键 | 可取值 |
|---|---|---|
| 人群数量 crowd | `"crowd"` | 300 / 500 / 650 / 750 / 900 |
| 入口 entrance | `"entrance"` | `"2/2"` / `"1/2"`（开放数/总数） |
| 主要路线 main_route | `"main_route"` | `"normal"` / `"limited"` |
| 支持人员 support | `"support"` | 8 / 10 / 12 |

演示：把 `"crowd": 500` 改为 `650` 并保存 → 看板人数卡片 ≤2s 自动变为 650，无需刷新页面。

恢复默认值：`git checkout -- simulators\sim_values.json`

## 接口

- `GET /health` → `{"status":"ok"}`
- `GET /api/current` → 当前全部对象最新状态（全部来自 MQTT 实时消息，非写死；结构：
  `{activity_id, objects: {crowd/entrance/route/support: 信封}, updated_at}`）
- `WS /ws` → 连接即推全量快照，之后每个对象更新推增量

## 关闭与重启复现

1. 四个模拟器终端分别 Ctrl+C；
2. uvicorn 终端 Ctrl+C；
3. mosquitto 终端 Ctrl+C；
4. 再按上面"启动步骤"依次重新启动，看板恢复实时更新。

模拟器 `retain=False` + 后端纯内存态：重启后状态从 MQTT 实时消息重新建立，不依赖上次运行残留。

## 端口排查

- 1883 被占：`netstat -ano | findstr :1883`，通常是 mosquitto 服务，`net stop mosquitto` 后再手动启动。
- 8000 被占：`netstat -ano | findstr :8000`，`taskkill /F /PID <pid>`。

## 阶段01 验收对照

| 验收点 | 做法 |
|---|---|
| 页面变化必须来自数据源变化 | 改 `sim_values.json`，看板 ≤2s 自动变化、无手动刷新 |
| `/api/current` 非写死 | 用 mosquitto_pub 手工发布 `data.count=777`，接口与页面立即显示 777 |
| 统一消息外壳 | 每条消息含 activity_id/object_type/observed_at/source_type/data，全部属于 campus_open_day_01 |
| 模拟器只输出原始状态 | simulators 代码只做取值映射与发布，无阈值/标签/结论逻辑 |
| 关闭重启可复现 | 按上文"关闭与重启复现"步骤 |

## 开发约定

- 代码为本项目新写，基于已学能力迁移式实现（多站点并列判定思路 → 多对象状态并行采集）。
- 每阶段独立 commit；AI 开发会话快照存 `docs/ai-sessions/`。
- 后端从仓库根目录以 `py -m uvicorn backend.main:app` 启动（backend 内部使用相对导入）。
