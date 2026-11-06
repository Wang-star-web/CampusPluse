"""生成参赛材料：02_AI对话快照 八个阶段案例（阶段1-阶段8）。

- 01/02/04/05：来自证据目录（D:/AICording/nova-CampusPluse 证据/阶段N/）的真实截图，复制并按规范重命名
- 03-我发现的问题.png：**先按模板写 Markdown，再用浅色主题渲染成图**（输入/期望/实际 三段式）
- 00-案例说明.png：按模板正文浅色渲染
- 99-完整对话记录.pdf：仓库 docs/ai-sessions/ 对应阶段章节（工具导出的原始会话转录）
"""

import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Table, TableStyle
from reportlab.lib import colors

SRC_EVIDENCE = Path("D:/AICording/nova-CampusPluse 证据")
SNAPSHOT_1105 = Path("D:/AICording/nova-CampusPluse/campuspulse/docs/ai-sessions/2026-11-05.md")
SNAPSHOT_1106 = Path("D:/AICording/nova-CampusPluse/campuspulse/docs/ai-sessions/2026-11-06.md")
PKG = Path("D:/AICording/传智杯-参赛材料-汪语含-12025051186")
CASES = PKG / "02_AI对话快照"
FONT = "C:/Windows/Fonts/simhei.ttf"

# ---------------------------------------------------------------- 八个案例定义

CASES_DEF = [
    {
        "name": "01_数据链初联调_MQTT订阅静默失败",
        "stage": "阶段1",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "解决问题.png": "05-验证结果.png",
            "切换人数900.png": "05b-验证结果-改值传播.png",
        },
        "snapshot": SNAPSHOT_1105, "marker": None,
        "time": "2026-11-05", "commit": "0731b0f", "doc": "4.2",
        "cover_title": "数据链初联调：MQTT 订阅静默失败",
        "cover_module": "backend/mqtt_bridge.py（paho-mqtt 2.x 订阅桥）",
        "cover_conclusion": "证明了我在 AI 第一版订阅代码静默失败时，能用\"端到端数据验证\"定位到 paho-mqtt 2.x 的 API 变化，并用实测 API 的方式纠正，而不是凭旧经验猜。",
        "cover_steps": [
            ("提要求", "搭通 模拟器→MQTT→FastAPI→WebSocket 数据链"),
            ("检查", "查 /api/current 是否出现四个对象"),
            ("发现问题", "订阅\"成功\"但后端收不到任何消息，看板永远空数据"),
            ("纠偏", "实测 paho 2.x API：subscribe() 返回 MQTTErrorCode 无 is_failure，按 1.x 习惯判断导致订阅中断"),
            ("结果", "改为与 MQTT_ERR_SUCCESS 比较；四对象 2 秒内到达，改值 ≤2s 传播"),
        ],
        "cover_learn": "库升级后的 API 变化是静默陷阱。\"代码能跑\"不等于\"链路通了\"——用端到端的真实数据验证每个环节，比读文档更快找到断点。",
        "issue_found": "全链路启动后，浏览器看板四张卡片一直是\"等待数据\"。",
        "issue_input": "模拟器每 2 秒向 MQTT 发布合法信封消息。",
        "issue_expect": "后端订阅后收到消息，/api/current 出现四个对象的实时状态。",
        "issue_actual": "后端日志显示订阅完成，但 /api/current 的 objects 始终为空，消息石沉大海。",
        "issue_why": "数据链断在最前端，后续所有阶段（证据、约束、态势）都无从谈起，必须立刻定位。",
        "issue_reason": "paho-mqtt 2.x 的 subscribe() 返回 MQTTErrorCode（无 is_failure 属性），AI 按 1.x 习惯写 err.is_failure，回调抛 AttributeError 导致订阅被中断。",
    },
    {
        "name": "02_证据层失败语义_不伪造业务值",
        "stage": "阶段2",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "05验证结果（测试正常OK模式）.png": "05-验证结果.png",
            "05 验证结果（500人unavailable）.png": "05b-验证结果-降级.png",
        },
        "snapshot": SNAPSHOT_1106, "marker": "同日第二次任务：A00 阶段02",
        "time": "2026-11-06", "commit": "b6df3ac", "doc": "3.3",
        "cover_title": "证据层失败语义：取证失败不等于业务异常",
        "cover_module": "backend/schemas.py、backend/mqtt_bridge.py（证据信封与双写）",
        "cover_conclusion": "证明了我在证据层引入 ok/unavailable/error 时，能把\"未知≠异常\"从口头约定升级为结构校验：失败证据 value_json=null、不写伪造观测、页面绝不显示\"入口=0/2\"或\"入口异常\"。",
        "cover_steps": [
            ("提要求", "实现证据层：成功双写、失败只记 evidence 且 value_json=null"),
            ("检查", "手工注入失败模式，查数据库行数与页面文案"),
            ("发现问题", "失败信封存在携带业务值的路径，取证失败可能被改写成业务异常"),
            ("纠偏", "pydantic 校验器强制：失败信封 observed_at/data 必须为 null；error 必带 error_message"),
            ("结果", "unavailable 模式下 observations 冻结、页面保持最后成功值、无\"入口异常\"字样"),
        ],
        "cover_learn": "系统\"不知道\"时必须诚实说\"不知道\"。把边界写进数据校验器（而不是靠调用方自觉），才能保证任何来源的失败都不会变成假事实。",
        "issue_found": "注入 entrance 取证失败模式后，检查数据库与页面表现。",
        "issue_input": "entrance 取证模式 = unavailable（模拟数据源主动上报失败）。",
        "issue_expect": "只新增一条 evidence（value_json=null、observed_at=null），observations 冻结，页面保留最后成功值 2/2。",
        "issue_actual": "早期方案的信封校验允许失败信封同时携带 data，存在把\"没取到\"改写成\"入口=0/2\"的风险路径。",
        "issue_why": "取证失败一旦被展示成业务异常，指挥人员会基于假事实做判断，违背系统\"未知≠异常\"的底线。",
        "issue_reason": "信封校验器只在语义上约定失败不带值，没有在结构上强制 data/observed_at 为 null。",
    },
    {
        "name": "03_约束计算接口_热加载失效405",
        "stage": "阶段3",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "终端执行自动化测试77 通过.png": "05-验证结果.png",
            "现场验证值.png": "05b-验证结果-现场值.png",
        },
        "snapshot": SNAPSHOT_1106, "marker": "同日第三次任务：A00 阶段03",
        "time": "2026-11-06", "commit": "20d6b03", "doc": "2.1",
        "cover_title": "约束计算接口：热加载静默失效返回 405",
        "cover_module": "backend/main.py、backend/constraints.py（compute-derived 接口）",
        "cover_conclusion": "证明了我在接口返回 405 时，能用\"进程状态排查\"定位到 uvicorn --reload 的 WatchFiles 对新增文件静默失效，并以干净重启纠正——不把环境问题误判为代码问题。",
        "cover_steps": [
            ("提要求", "实现 POST /api/compute-derived 约束计算接口 + S1/S2 测试"),
            ("检查", "curl 调用新接口看响应"),
            ("发现问题", "返回 405 Method Not Allowed，新路由根本没生效"),
            ("纠偏", "查后端日志：reloader 只响应了一次文件变更后罢工，worker 一直在服务旧路由"),
            ("结果", "改为不带 --reload 的干净实例重启；S1/S2/现场验证值全对、422 四连测通过"),
        ],
        "cover_learn": "开发环境的\"热加载\"会静默吞掉新代码。遇到\"我明明加了路由\"类问题，先验证进程实际加载的是哪份代码，再怀疑业务逻辑。",
        "issue_found": "新增约束计算接口后，用 curl 做冒烟测试。",
        "issue_input": "POST /api/compute-derived，body 为 S1 的合法输入。",
        "issue_expect": "200，返回 config/states/derived 分层结果。",
        "issue_actual": "405 Method Not Allowed——请求命中了旧的 catch-all 路由（GET-only）。",
        "issue_why": "新接口完全不可用，S1/S2 场景验收无法进行。",
        "issue_reason": "后端以 --reload 启动，WatchFiles 只响应了一次文件变更后静默失效，worker 进程一直在服务旧代码。",
    },
    {
        "name": "04_态势聚合落库_旧表结构冲突",
        "stage": "阶段4",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "跑 S2（750 人），拿到新 run_id.png": "05-验证结果.png",
            "S1（300 人），拿到 run_id.png": "05b-验证结果-S1.png",
        },
        "snapshot": SNAPSHOT_1106, "marker": "同日第四次任务：A00 阶段04",
        "time": "2026-11-06", "commit": "9d4a2c0", "doc": "3.4",
        "cover_title": "态势聚合落库：旧 runs 表结构冲突",
        "cover_module": "backend/db.py、backend/main.py（runs 表与 run_id 落库）",
        "cover_conclusion": "证明了我在 run 落库 500 时，能定位到 Day1 旧表 NOT NULL 列与 datetime.now 传类而非实例两个真实缺陷，并用\"旧表整体改名保留 + 新结构重建\"的无损迁移方案纠正。",
        "cover_steps": [
            ("提要求", "影响/态势聚合 + run_id 落库（runs 表 13 字段）"),
            ("检查", "POST /api/runs 跑 S1 全链路"),
            ("发现问题", "500：runs.scene_json NOT NULL 冲突；另有 datetime.now(_tz) 误传 timezone 类"),
            ("纠偏", "旧表改名 runs_legacy 保留数据，新结构重建 runs；_tz.utc 修正"),
            ("结果", "S1/S2/620 三个 run_id 互异落库，父快照可重查，不可覆盖纪律生效"),
        ],
        "cover_learn": "存量数据的迁移要\"先保留后重建\"，宁可多一张 legacy 表，不可丢一行历史；Python 里 datetime.now() 要传 timezone 实例（timezone.utc）而不是类。",
        "issue_found": "提交 S1 完整运行请求，观察落库结果。",
        "issue_input": "POST /api/runs（S1 状态 + 证据引用）。",
        "issue_expect": "生成 run_id 并写入 runs 表 13 个字段。",
        "issue_actual": "500 IntegrityError：runs.scene_json NOT NULL 约束失败；另一次 500 为 TypeError（tzinfo 收到 type）。",
        "issue_why": "run 记录无法写入，run_id 不可覆盖审计这一核心能力完全不可用。",
        "issue_reason": "Day1 旧 runs 表（scene_json/level NOT NULL）与新结构不兼容；且 now(_tz) 传了 timezone 类而非 timezone.utc 实例。",
    },
    {
        "name": "05_多源证据接口_模块导入缺失",
        "stage": "阶段5",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "运行 S3 场景.png": "05-验证结果.png",
            "前端证据页面.png": "05b-验证结果-证据页.png",
        },
        "snapshot": SNAPSHOT_1106, "marker": "同日第五次任务：A00 阶段05",
        "time": "2026-11-06", "commit": "f6289f7", "doc": "2.2",
        "cover_title": "多源证据接口：跨块引用模块导入缺失",
        "cover_module": "backend/main.py、backend/sources.py（天气/工具/RAG 端点）",
        "cover_conclusion": "证明了我在天气工具 500 时，能根据 NameError 栈快速定位到\"阶段05 块引用 sources 而阶段04 块只导入了 _sources 别名\"的跨块引用缺陷，并补齐导入。",
        "cover_steps": [
            ("提要求", "接入天气/路线工具/RAG 三类证据 + S3 场景"),
            ("检查", "POST /api/tools/weather 冒烟"),
            ("发现问题", "500 NameError: name 'sources' is not defined"),
            ("纠偏", "在阶段05 块显式 from . import sources（与 _sources 别名并存）"),
            ("结果", "三类证据各自入库（future_condition/web_api、current_fact/tool、knowledge_basis/rag），S3 未来条件不改写当前路线"),
        ],
        "cover_learn": "追加式开发的\"跨代码块引用\"是静默雷区：模块导入是全局的，但别名不是。报 NameError 时先看 import 区，别急着改业务逻辑。",
        "issue_found": "冒烟测试天气工具端点。",
        "issue_input": "POST /api/tools/weather（无请求体）。",
        "issue_expect": "返回 future_condition 证据行（web_api，含 forecast_window_min/condition）。",
        "issue_actual": "500 NameError: name 'sources' is not defined（后端日志栈顶）。",
        "issue_why": "多源证据三个接口全部不可用，阶段05 验收（S3）无法进行。",
        "issue_reason": "阶段05 代码块引用 sources 模块，但模块只在阶段04 块以 _sources 别名导入过，新块未导入。",
    },
    {
        "name": "06_LLM解释层_判定权边界",
        "stage": "阶段6",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "关闭 LLM 服务，重新访问态势页面，确认态势计算功能完全正常.png": "05-验证结果.png",
            "S4（取证据→提交运行→显示结果，零手工组装）.png": "05b-验证结果-S4.png",
        },
        "snapshot": SNAPSHOT_1106, "marker": "同日第六次任务：A00 阶段06",
        "time": "2026-11-06", "commit": "f134689", "doc": "3.2",
        "cover_title": "LLM 解释层：判定权边界（只解释，不判定）",
        "cover_module": "backend/explain.py、backend/situation.py（LLM 解释层与规则引擎）",
        "cover_conclusion": "证明了我在 AI 试图让 LLM 直接生成整体态势时，用\"先计算，再解释\"的红线把它纠正为：态势全部由 Python 规则计算，LLM 只输出对已有结果的解释文本，且服务关闭时核心功能不受影响。",
        "cover_steps": [
            ("提要求", "接入 LLM 解释层，把运行结果交给大模型生成说明"),
            ("检查", "核对官方规范与代码：LLM 是否可能改写态势"),
            ("发现问题", "AI 第一版方案把 LLM 输出作为态势生成的一部分，违反\"态势由规则计算\"红线"),
            ("纠偏", "LLM 只解释已有计算结果，不发明事实/不改态势/不发明约束，解释单独存表"),
            ("结果", "explain 五条硬边界生效；关闭 LLM 后态势/影响/run_id 全部照常（503 明确提示）"),
        ],
        "cover_learn": "大模型适合做\"表达层\"，不适合做\"判定层\"。把判定权留在显式规则里，LLM 服务挂了系统也不会降级成摆设——这条边界本身就是作品的差异化。",
        "issue_found": "审查 AI 的 LLM 解释层设计方案。",
        "issue_input": "一个 run 的完整结构化结果（状态/派生/影响/态势/未知项）。",
        "issue_expect": "summary/impact 完全由规则产生，LLM 文本仅作附加展示，删除后结果不变。",
        "issue_actual": "AI 方案把 LLM 输出设计成态势生成链的一环，服务下线时态势展示受损。",
        "issue_why": "违反\"态势由规则计算\"红线；LLM 输出不可审计，会让整体结论失去可追溯性，服务故障还会拖垮核心链路。",
        "issue_reason": "AI 没有把\"判定权\"和\"表达权\"分开设计。",
    },
    {
        "name": "07_推演与降级_环境注入残留",
        "stage": "阶段7",
        "files": {
            "01 AI的.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "视图四.png": "05-验证结果.png",
            "前端视图三.png": "05b-验证结果-视图三.png",
        },
        "snapshot": SNAPSHOT_1106, "marker": "同日第七次任务：A00 阶段07",
        "time": "2026-11-06", "commit": "11a89c8", "doc": "3.4",
        "cover_title": "推演与降级：教学注入残留与配置编码损坏",
        "cover_module": "backend/envloader.py、backend/sources.py（what-if 与 S5 降级）",
        "cover_conclusion": "证明了我在回归测试出现 7/8 时，能定位到两个真实缺陷——S5 演示后 .env 只恢复了天气行、路线注入标志残留，以及 sed/PowerShell 写坏 .env 编码——并分别用\"注入用完即恢复并验证\"与\"双编码容错\"纠正。",
        "cover_steps": [
            ("提要求", "实现 what-if 推演、父子 run、S5 可信降级"),
            ("检查", "全量单元测试 + S4-D/S5 线上验证"),
            ("发现问题", "test_sources 7/8：路线注入标志残留；.env 被写成 GBK 导致 envloader 崩溃"),
            ("纠偏", "恢复 .env 全部教学注入；envloader 改字节读取 + UTF-8/GBK 双编码容错"),
            ("结果", "36/36 全过；S4-D 推演父快照原样；S5 unknown/affected/partial 与官方冻结逐项一致"),
        ],
        "cover_learn": "教学注入类环境变量是\"一次性开关\"，用完必须恢复并验证，否则它会污染下一次正常回归；Windows 上被多种工具写过的配置文件必须做编码容错。",
        "issue_found": "阶段07 完成后跑全量测试。",
        "issue_input": "py -m tests.test_sources（8 条）。",
        "issue_expect": "8/8 通过。",
        "issue_actual": "7/8：test_route_tool_ok 失败（路线工具被注入成 unavailable）；另 envloader 读 .env 报 UnicodeDecodeError。",
        "issue_why": "教学注入污染正常回归结论；配置加载崩溃会让后端在任意启动方式下都可能失败。",
        "issue_reason": "S5 演示后只恢复了天气行、ROUTE_TOOL_TEACHING_UNAVAILABLE=1 残留；.env 被 sed/PowerShell 写入了 GBK 字节。",
    },
    {
        "name": "08_回归组装_环境状态排查",
        "stage": "阶段8",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "回归脚本输出（S1~S5 全部通过）.png": "05-验证结果.png",
            "4 个视图页面.png": "05b-验证结果-四视图.png",
        },
        "snapshot": SNAPSHOT_1106, "marker": "同日第八次任务：A00 阶段08",
        "time": "2026-11-06", "commit": "eea90e7", "doc": "4.1",
        "cover_title": "回归组装：在线回归的假失败排查",
        "cover_module": "tests/regression.py、backend/pipeline.py（S1-S5 回归）",
        "cover_conclusion": "证明了我在在线回归 S1-S4 假失败时，能分辨\"环境状态问题\"与\"代码缺陷\"：.env 残留 unavailable 导致天气引用失败，且脚本无条件注入天气引用——通过\"按场景组装引用\"让回归对环境鲁棒，并修正了 GBK 控制台崩溃。",
        "cover_steps": [
            ("提要求", "四视图同底座 + S1-S5 回归脚本 + README 完善"),
            ("检查", "py -m tests.regression --live 跑真实 API 链路"),
            ("发现问题", "S1-S4 全 FAIL（weather unknown 污染）；离线模式又报字段名不一致与 GBK 打印崩溃"),
            ("纠偏", "在线模式按场景组装天气引用（S3/S4 才带 ok、S5 才带 unavailable）；离线映射为 run 快照形态；ASCII 输出"),
            ("结果", "回归离线 5/5、在线 S1-S4 4/4（S5 按注入状态跳过并计入报告）；36/36 单元测试"),
        ],
        "cover_learn": "回归脚本必须对环境状态鲁棒：引用哪个证据应由场景定义而不是\"有什么拿什么\"；控制台输出要避开平台编码差异（GBK 不认 ✗）。",
        "issue_found": "跑在线回归，对比离线结果。",
        "issue_input": "py -m tests.regression --live（真实 API 证据+运行链）。",
        "issue_expect": "S1-S4 通过（S5 按教学注入状态跳过并说明）。",
        "issue_actual": "S1-S4 全 FAIL：每场景 unknown 都带 weather_future_condition；离线模式另有字段名不匹配与 GBK 打印 UnicodeEncodeError。",
        "issue_why": "回归给出错误的失败结论，交付前不可接受；打印崩溃使报告无法输出。",
        "issue_reason": ".env 残留 WEATHER_TEACHING_CONDITION=unavailable（环境问题），且脚本无条件注入天气引用；离线结果字段名与 run 快照不一致；✗ 字符无法用 GBK 编码。",
    },
]


# ---------------------------------------------------------------- 渲染函数

def render_png(blocks, out: Path, width=1200):
    """blocks: [(kind, text)] kind ∈ title/h/k/b/n；浅色主题渲染，宽度 1200。"""
    sizes = {"title": 34, "h": 26, "k": 22, "b": 22, "n": 22}
    line_gaps = {"title": 52, "h": 42, "k": 36, "b": 36, "n": 36}
    H = 120
    items = []
    for kind, text in blocks:
        items.append((kind, text, sizes[kind]))
    for kind, text, size in items:
        H += line_gaps[kind] + (len(text) // (width // (size + 4)) + 1) * int(size * 1.6)
    img = Image.new("RGB", (width, H), "#ffffff")
    d = ImageDraw.Draw(img)
    fonts = {k: ImageFont.truetype(FONT, sizes[k]) for k in sizes}
    y = 60
    for kind, text, size in items:
        color = {"title": "#1f2328", "h": "#0969da", "k": "#59636e", "b": "#1f2328", "n": "#1f2328"}[kind]
        d.text((60, y), text, font=fonts[kind], fill=color)
        y += line_gaps[kind]
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print("  [PNG]", out.name)


def render_issue_png(case: dict, out: Path):
    blocks = [
        ("title", "我发现的问题"),
        ("k", f"案例：{case['name']}　时间：{case['time']}"),
        ("h", "怎么发现的"),
        ("b", case["issue_found"]),
        ("h", "具体现象（输入 → 期望 → 实际）"),
        ("k", "输入：" + case["issue_input"]),
        ("k", "期望：" + case["issue_expect"]),
        ("k", "实际：" + case["issue_actual"]),
        ("h", "为什么不能接受"),
        ("b", case["issue_why"]),
        ("h", "我当时判断的原因"),
        ("b", case["issue_reason"]),
    ]
    render_png(blocks, out)


def render_cover_png(case: dict, out: Path):
    blocks = [
        ("title", case["cover_title"]),
        ("k", f"时间：{case['time']}　涉及模块：{case['cover_module']}"),
        ("k", f"对应提交：{case['commit']}　对应技术文档：{case['doc']}"),
        ("h", "一句话结论"),
        ("b", case["cover_conclusion"]),
        ("h", "过程概要"),
    ]
    for k, v in case["cover_steps"]:
        blocks.append(("k", f"{k}：{v}"))
    blocks.append(("h", "我从这件事上学到什么"))
    blocks.append(("b", case["cover_learn"]))
    render_png(blocks, out)


def extract_snapshot(snapshot: Path, marker: str | None) -> str:
    text = snapshot.read_text(encoding="utf-8")
    if marker is None:
        return text.strip()
    start = text.find(marker)
    assert start > 0, f"marker not found: {marker}"
    end = text.find("\n---\n", start)
    if end < 0:
        end = len(text)
    return text[start:end].strip()


def build_pdf(text: str, out: Path):
    pdfmetrics.registerFont(TTFont("SimHei", FONT))
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54,
                            title=out.stem)
    h1 = ParagraphStyle("h1", fontName="SimHei", fontSize=15, leading=21, spaceAfter=8, textColor="#1f2328")
    h2 = ParagraphStyle("h2", fontName="SimHei", fontSize=12, leading=18, spaceBefore=10, spaceAfter=4, textColor="#0969da")
    body = ParagraphStyle("b", fontName="SimHei", fontSize=9.5, leading=15, textColor="#1f2328")
    cell = ParagraphStyle("c", fontName="SimHei", fontSize=8.5, leading=12, textColor="#1f2328")

    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    story = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("|"):
            tbl_rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                l = lines[i].strip()
                if set(l.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
                    i += 1
                    continue
                cells = [c.strip() for c in l.strip("|").split("|")]
                tbl_rows.append([Paragraph(esc(c), cell) for c in cells])
                i += 1
            if tbl_rows:
                t = Table(tbl_rows)
                t.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d9e0")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f8")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))
            continue
        if line.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            story.append(Preformatted("\n".join(buf), ParagraphStyle("pre", fontName="SimHei", fontSize=8, leading=11, textColor="#59636e")))
            story.append(Spacer(1, 6))
            continue
        if line.startswith("### ") or line.startswith("## "):
            story.append(Paragraph(esc(line.lstrip("# ").strip()), h2))
        elif line.startswith("# "):
            story.append(Paragraph(esc(line.lstrip("# ").strip()), h1))
        elif line.startswith("- ") or (len(line) > 2 and line[0].isdigit() and line[1] == "."):
            story.append(Paragraph("• " + esc(line.lstrip("- 0123456789. ")), body))
        elif line.startswith(">"):
            story.append(Paragraph(esc(line.lstrip("> ")), ParagraphStyle("q", parent=body, textColor="#59636e")))
        else:
            story.append(Paragraph(esc(line), body))
        i += 1
    doc.build(story)
    print("  [PDF]", out.name)


def build_case(case: dict):
    cdir = CASES / case["name"]
    cdir.mkdir(parents=True, exist_ok=True)
    src_stage = SRC_EVIDENCE / case["stage"]
    for src_name, dst_name in case["files"].items():
        src = src_stage / src_name
        assert src.exists(), f"missing evidence: {src}"
        shutil.copyfile(src, cdir / dst_name)
        print("  [copy]", dst_name, "<-", case["stage"] + "/" + src_name)

    render_cover_png(case, cdir / "00-案例说明.png")
    # 03-我发现的问题.png：按模板先写 Markdown 再浅色渲染成图（不贴对话截图）
    render_issue_png(case, cdir / "03-我发现的问题.png")
    section = extract_snapshot(case["snapshot"], case["marker"])
    build_pdf(section, cdir / "99-完整对话记录.pdf")


def main():
    for case in CASES_DEF:
        print("=" * 50)
        print("案例:", case["name"])
        build_case(case)
    print("done")


if __name__ == "__main__":
    main()
