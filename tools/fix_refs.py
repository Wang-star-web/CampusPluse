"""修正参赛包各 md 中的案例引用映射（8 案例命名）。"""

from pathlib import Path

PKG = Path("D:/AICording/传智杯-参赛材料-汪语含-12025051186")

C01 = "01_数据链初联调_MQTT订阅静默失败"
C02 = "02_证据层失败语义_不伪造业务值"
C03 = "03_约束计算接口_热加载失效405"
C04 = "04_态势聚合落库_旧表结构冲突"
C05 = "05_多源证据接口_模块导入缺失"
C06 = "06_LLM解释层_判定权边界"
C07 = "07_推演与降级_环境注入残留"
C08 = "08_回归组装_环境状态排查"


def fix_commit_index():
    p = PKG / "01_Git提交日志" / "commit-index.md"
    t = p.read_text(encoding="utf-8")
    pairs = [
        ("阶段01：多对象现场数据链（模拟器→MQTT→FastAPI→WebSocket） | — | 6.1 |",
         f"阶段01：多对象现场数据链（模拟器→MQTT→FastAPI→WebSocket） | `{C01}` | 4.2 |"),
        ("阶段03：显式约束与派生结果（独立教学配置 + compute-derived） | — | 2.1 |",
         f"阶段03：显式约束与派生结果（独立教学配置 + compute-derived） | `{C03}` | 2.1 |"),
        ("阶段04：局部影响→整体态势→run_id（只 INSERT 不 UPDATE） | `07_推演与降级_环境注入残留` | 3.4 |",
         f"阶段04：局部影响→整体态势→run_id（只 INSERT 不 UPDATE） | `{C04}` | 3.4 |"),
        ("阶段08：系统组装回归验证（四视图同底座 + S1-S5 回归） | — | 4.1 / 5.1 |",
         f"阶段08：系统组装回归验证（四视图同底座 + S1-S5 回归） | `{C08}` | 4.1 / 5.1 |"),
    ]
    for old, new in pairs:
        assert old in t, f"commit-index 未找到: {old[:30]}"
        t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    print("commit-index ok")


def fix_tech_doc():
    p = PKG / "05_技术文档" / "技术文档.md"
    t = p.read_text(encoding="utf-8")
    pairs = [
        ("见快照案例 01", f"见快照案例 {C06}"),
        ("案例 01/05-验证结果.png", f"案例 {C06}/05-验证结果.png"),
        ("（案例 01）", f"（案例 {C06}）"),
        ("（案例 02）", f"（案例 {C02}）"),
        ("（案例 03）", f"（案例 {C07}）"),
        ("3.2（案例 01）", f"3.2（案例 {C06}）"),
        ("3.3（案例 02）", f"3.3（案例 {C02}）"),
        ("3.4（案例 03）", f"3.4（案例 {C07}）"),
    ]
    for old, new in pairs:
        t = t.replace(old, new)
    note = f"\n\n> 案例说明：提交包 `02_AI对话快照/` 保留阶段1-8 共 8 个案例的完整快照；本章详述其中 3 个代表性案例（案例 {C02}/{C06}/{C07}，分别对应下文 3.3/3.2/3.4），其余案例的\"我发现的问题\"摘要见各案例目录 03 图。"
    if "### 3.1 我的 AI 协作方法" in t and "保留阶段1-8 共 8 个案例" not in t:
        t = t.replace("### 3.1 我的 AI 协作方法", "### 3.1 我的 AI 协作方法" + note, 1)
    p.write_text(t, encoding="utf-8")
    print("tech doc ok")


def fix_ppt():
    p = PKG / "答辩PPT大纲.md"
    t = p.read_text(encoding="utf-8")
    t = t.replace("AI 对话案例 01（纠正 AI 试图让 LLM 生成态势的完整纠偏链）",
                  f"AI 对话案例 {C06}（纠正 AI 试图让 LLM 生成态势的完整纠偏链）")
    t = t.replace("AI 对话案例 02/03",
                  f"AI 对话案例 {C02} 与 {C07}")
    p.write_text(t, encoding="utf-8")
    print("ppt ok")


if __name__ == "__main__":
    fix_commit_index()
    fix_tech_doc()
    fix_ppt()
