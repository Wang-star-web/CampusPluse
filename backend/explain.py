"""阶段06 LLM 解释层（DeepSeek / OpenAI 兼容 chat/completions）。

硬边界（官方）：
- LLM 只解释已经算好的 run 结构化结果：不发明事实、不新增业务约束、
  不修改整体态势标签、不补齐缺失事实、不出现系统未定义的安全等级；
- 解释单独存 explanations 表，禁止写回 runs 的 situation/impacts 等任何字段；
- LLM 服务不可用时返回 503 并明确说明——核心态势/影响/run_id 链路完全不受影响
  （解释只是附加功能，先计算，再解释）。
"""

import json
import os
import urllib.error
import urllib.request

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_TIMEOUT_S = float(os.getenv("TOOL_TIMEOUT_S", "5")) + 30  # LLM 生成需要更长时间

SYSTEM_PROMPT = """你是 CampusPulse 校园活动脉搏系统的态势解释助手。
你只解释下面已经计算好的结构化运行结果，严格遵守：
1. 只解释已有计算结果，不发明任何新事实、不补充缺失数据；
2. 不新增、不修改任何业务约束或规则；
3. 不修改整体态势标签（summary）、不修改任何 impact 文案；
4. 缺证据时明确说明"当前缺少相关证据"，不得编造；
5. 不出现系统没有定义的专业安全等级（如"高风险""必须疏散"等）。
你的输出只用于帮助人理解系统已经算出的结论，不是新的裁决。"""


def build_context(run: dict, question: str | None) -> dict:
    """组装送给 LLM 的结构化上下文（只送该 run 已形成的结构化结果，不送数据库原文）。"""
    return {
        "run_id": run["run_id"],
        "current_states": run["input_snapshot"]["states"],
        "config": run["input_snapshot"]["config"],
        "derived_results": run["derived_results"],
        "impacts": run["impacts"],
        "situation": run["situation"],
        "unknown_items": run["unknown_items"],
        "situation_completeness": run["situation_completeness"],
        "evidence_refs": run["evidence_refs"],
        "user_question": question or "请解释这次运行的完整态势。",
    }


def build_user_prompt(context: dict) -> str:
    ctx_json = json.dumps(context, ensure_ascii=False, indent=2)
    return (
        "请解释下面这次 CampusPulse 运行的结构化结果。"
        "你的回答至少覆盖四点：1) 当前整体态势是什么；2) 它主要由哪些局部影响形成；"
        "3) 哪些证据属于未来条件/模型预测（不等同于当前事实）；4) 当前还有什么未知/边界。\n\n"
        f"运行结构化结果：\n{ctx_json}"
    )


def call_llm(system: str, user: str) -> str:
    """OpenAI 兼容 chat/completions（DeepSeek）。未配置 key → ValueError。"""
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY not configured")
    body = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 1200,
        "temperature": 0.2,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_S) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]
