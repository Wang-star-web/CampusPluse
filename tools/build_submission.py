"""生成参赛材料：02_AI对话快照 三个案例的目录、封面图（PNG）与完整对话记录（PDF）。

- 截图来源：D:/AICording/nova-CampusPluse 证据/阶段N/（真实开发过程截图，复制并按规范重命名）
- 99 PDF 来源：仓库 docs/ai-sessions/2026-11-06.md 的对应阶段章节（工具导出的原始会话转录）
- 00 封面图与 03 文字图：本脚本按模板正文渲染（浅色主题、SimHei 字体）
"""

import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted

SRC_EVIDENCE = Path("D:/AICording/nova-CampusPluse 证据")
SNAPSHOT = Path("D:/AICording/nova-CampusPluse/campuspulse/docs/ai-sessions/2026-11-06.md")
PKG = Path("D:/AICording/传智杯-参赛材料-汪语含-12025051186")
CASES = PKG / "02_AI对话快照"
FONT = "C:/Windows/Fonts/simhei.ttf"

# 案例定义：证据文件 → 规范文件名（同目录多张验证图用 a/b 编号）
CASES_DEF = [
    {
        "name": "01_态势判定权边界_LLM只解释不判定",
        "stage": "阶段6",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "关闭 LLM 服务，重新访问态势页面，确认态势计算功能完全正常.png": "05-验证结果.png",
        },
        "snapshot_marker": "同日第六次任务：A00 阶段06",
    },
    {
        "name": "02_取证失败不等于业务异常",
        "stage": "阶段2",
        "files": {
            "01 我的原始提问.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "05验证结果（测试正常OK模式）.png": "05-验证结果.png",
            "05 验证结果（500人unavailable）.png": "05b-验证结果-降级.png",
        },
        "snapshot_marker": "同日第二次任务：A00 阶段02",
    },
    {
        "name": "03_条件推演不得覆盖现实运行",
        "stage": "阶段7",
        "files": {
            "01 AI的.png": "01-我的原始提问.png",
            "02 AI第一次的方案.png": "02-AI第一次的方案.png",
            "03 我发现的问题.png": "03-我发现的问题.png",
            "04 我的纠编指令.png": "04-我的纠偏指令.png",
            "视图四.png": "05-验证结果.png",
        },
        "snapshot_marker": "同日第七次任务：A00 阶段07",
    },
]

COVER_TEXT = {
    "01_态势判定权边界_LLM只解释不判定": {
        "title": "态势判定权边界：LLM 只解释，不判定",
        "time": "2026-11-06",
        "module": "backend/explain.py、backend/situation.py（LLM 解释层与规则引擎）",
        "commit": "f134689",
        "doc": "3.2",
        "conclusion": "证明了我在 AI 试图让 LLM 直接生成整体态势时，用\"先计算，再解释\"的红线把它纠正为：态势全部由 Python 规则计算，LLM 只输出对已有结果的解释文本，且服务关闭时核心功能不受影响。",
        "summary": [
            ("提要求", "接入 LLM 解释层，把运行结果交给大模型生成说明"),
            ("检查", "核对官方规范与代码：LLM 是否可能改写态势"),
            ("发现问题", "AI 第一版方案把 LLM 输出作为态势来源之一，违反\"态势由规则计算\"红线"),
            ("纠偏", "明确约束：LLM 只解释已有计算结果，不发明事实/不改态势/不发明约束，解释单独存表"),
            ("结果", "explain 接口五条硬边界生效；关闭 LLM 后态势/影响/run_id 全部照常（503 明确提示）"),
        ],
        "learn": "大模型适合做\"表达层\"，不适合做\"判定层\"。把判定权留在显式规则里，LLM 服务挂了系统也不会降级成摆设——这条边界本身就是作品的差异化。",
    },
    "02_取证失败不等于业务异常": {
        "title": "取证失败不等于业务异常：unavailable 的边界",
        "time": "2026-11-06",
        "module": "backend/schemas.py、backend/mqtt_bridge.py（证据信封与双写）",
        "commit": "b6df3ac",
        "doc": "3.3",
        "conclusion": "证明了我在证据层引入 ok/unavailable/error 状态时，能用\"取证失败≠业务异常\"的规则约束 AI：失败证据 value_json=null、不写伪造观测、页面绝不显示\"入口=0/2\"或\"入口异常\"。",
        "summary": [
            ("提要求", "实现证据层：成功双写、失败只记 evidence 且 value_json=null"),
            ("检查", "用手工注入失败模式验证：observations 是否被伪造、页面是否误报业务异常"),
            ("发现问题", "需要把失败语义和业务状态彻底切开，防止取证失败被改写为业务异常"),
            ("纠偏", "在信封校验器里强制：失败信封 observed_at/data 必须为 null；status 只表示本次取证是否成功"),
            ("结果", "unavailable 模式下 observations 冻结、页面保持最后成功值、无\"入口异常\"字样（回归断言）"),
        ],
        "learn": "系统\"不知道\"时必须诚实说\"不知道\"。用结构校验（而不是口头约定）把\"未知≠异常\"钉进数据层，比任何提示词都可靠。",
    },
    "03_条件推演不得覆盖现实运行": {
        "title": "条件推演不得覆盖现实运行：what-if 与父子 run_id",
        "time": "2026-11-06",
        "module": "backend/main.py、backend/db.py（what-if 接口与 runs 表）",
        "commit": "11a89c8",
        "doc": "3.4",
        "conclusion": "证明了我在实现条件推演时，用\"只 INSERT 不 UPDATE\"的纪律约束 AI：what-if 生成全新 run_id 并携带 parent_run_id，原 reality 快照逐字节保留，S5 证据退化时系统主动降级为 partial 而不编造业务异常。",
        "summary": [
            ("提要求", "实现 what-if 推演、父子 run 关系、S5 可信降级"),
            ("检查", "推演后重查父 run 快照、比较输入/派生/影响/态势五维差异"),
            ("发现问题", "推演结果绝不能污染现实运行记录，unknown 也绝不能转成业务异常"),
            ("纠偏", "约束：what-if 必须携带 parent_run_id/input_overrides/assumptions；runs 表只有 INSERT/SELECT 路径"),
            ("结果", "S4-D 推演后父快照原样（入口仍 1/2）；S5 run unknown_items/affected_impacts/partial 全部符合官方预期"),
        ],
        "learn": "改条件要新运行，丢证据要收缩判断边界——两条链不能混。把\"不可覆盖\"做成代码里不存在 UPDATE 路径，而不是靠人自觉。",
    },
}


def render_png(text_lines: list[tuple[str, str]], out: Path, title_size=36, body_size=24):
    """把模板正文渲染成浅色主题 PNG（宽度 1200，A4 打印可读）。"""
    W = 1200
    line_h = int(body_size * 1.9)
    head_h = int(title_size * 2.2)
    H = 140 + head_h + len(text_lines) * line_h + 80
    img = Image.new("RGB", (W, H), "#ffffff")
    d = ImageDraw.Draw(img)
    f_title = ImageFont.truetype(FONT, title_size)
    f_body = ImageFont.truetype(FONT, body_size)
    y = 60
    d.text((60, y), text_lines[0][1], font=f_title, fill="#1f2328")
    y += head_h + 30
    for style, line in text_lines[1:]:
        color = {"h": "#0969da", "k": "#59636e", "b": "#1f2328", "n": "#1f2328"}[style]
        d.text((60, y), line, font=f_body, fill=color)
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print("  [PNG]", out.name)


def extract_snapshot_section(marker: str) -> str:
    text = SNAPSHOT.read_text(encoding="utf-8")
    start = text.find(marker)
    assert start > 0, f"snapshot marker not found: {marker}"
    end = text.find("\n---\n", start)
    if end < 0:
        end = len(text)
    return text[start:end].strip()


def build_pdf(text: str, out: Path):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors

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
        raw = lines[i]
        line = raw.strip()
        if not line:
            i += 1
            continue
        # 表格块：连续的 | 行（跳过 |---| 分隔行）
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
                t = Table(tbl_rows, colWidths=None)
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
        if line.startswith("### "):
            story.append(Paragraph(esc(line.lstrip("# ").strip()), h2))
        elif line.startswith("## "):
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

    # 00-案例说明.png（封面）
    t = COVER_TEXT[case["name"]]
    lines = [(None, t["title"]),
             ("k", f"时间：{t['time']}　涉及模块：{t['module']}"),
             ("k", f"对应提交：{t['commit']}　对应技术文档：{t['doc']}"),
             ("h", "一句话结论"),
             ("b", t["conclusion"]),
             ("h", "过程概要")]
    for k, v in t["summary"]:
        lines.append(("k", f"{k}：{v}"))
    lines.append(("h", "我从这件事上学到什么"))
    lines.append(("b", t["learn"]))
    render_png(lines, cdir / "00-案例说明.png")

    # 99-完整对话记录.pdf（工具导出的原始会话转录：当日 AI 会话快照对应章节）
    section = extract_snapshot_section(case["snapshot_marker"])
    build_pdf(section, cdir / "99-完整对话记录.pdf")


def main():
    for case in CASES_DEF:
        print("=" * 50)
        print("案例:", case["name"])
        build_case(case)
    print("done")


if __name__ == "__main__":
    main()
