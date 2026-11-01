"""规划型 Interview Controller（Multi-Agent 的"大脑"）。

在每一轮候选人作答之后、面试官开口之前，由规划 Agent 基于：
  - 当前面试官角色（技术/HR/压力）
  - 候选人简历画像
  - 最近若干轮问答
  - 上一轮回答质量评估
自主决定下一轮策略（深挖 / 切换话题 / 加压 / 收尾），并可调用工具
（见 tools.py）检索岗位知识、技术考点或薪资带宽，再产出"聚焦点"用于生成提问。

这把原本"固定顺序交接"的多 Agent 升级为"带规划 + 工具调用 + 自主决策"的编排，
直接对应评分项：Agent/工作流设计（8%）、MCP/工具集成（4%）。
"""

import json
from app.core.llm import chat_with_tools
from app.core.tools import TOOL_SCHEMAS

# 各角色的规划侧重点
_ROLE_HINT = {
    "tech": "你是技术面试的总控规划器。请判断候选人上一轮技术回答的质量，决定是继续深挖底层原理、还是切换到新知识点、还是适度加压。",
    "hr": "你是 HR 面试的总控规划器。请判断候选人的沟通与稳定性信号，决定是继续用 STAR 追问行为经历、还是转向职业规划/离职动机、还是温和加压。",
    "stress": "你是压力面试的总控规划器。请判断候选人抗压表现，决定是继续施压追问细节、还是换角度质疑、还是逼近其薄弱环节。",
}

_PLANNER_PROMPT = """你是模拟面试系统的"规划 Agent"（总控大脑），不直接与候选人对话，而是为"面试官 Agent"制定下一轮策略。

{role_hint}

候选人简历画像：
{resume_json}

最近对话记录（最后一条是候选人刚刚的回答）：
{history}

上一轮候选人的回答质量评分（0-100，越高越好）：{quality}

请综合判断，输出严格 JSON（不要 ```包裹）：
{{
  "decision": "deepen(深挖本轮技术点) | switch(切换新话题) | pressure(施加压力/质疑) | close(临近收尾)",
  "focus": "给面试官 Agent 的具体聚焦点（一句话，例如：'候选人答出 Redis 持久化但没说 AOF 重写，继续追问 AOF 重写机制'）",
  "reasoning": "你做出该决策的简要理由（1-2 句，用于系统可解释性展示）",
  "use_tools": true/false  （是否需要调用工具检索岗位知识/技术考点/薪资作为提问依据）
}}

如果 use_tools 为 true，系统会自动为你调用工具，并把结果放入 focus 的参考资料中。
"""


def _estimate_quality(history: list) -> int:
    """极简的回答质量启发式：根据最近一条用户回答的长度/完整性给分。"""
    last_user = ""
    for m in reversed(history):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break
    n = len(last_user)
    if n >= 80:
        return 85
    if n >= 40:
        return 70
    if n >= 15:
        return 55
    return 40


def plan_next_turn(interview_type: str, resume_json: str, history: list) -> dict:
    """返回规划结果 dict: {decision, focus, reasoning, tool_calls}。异常时返回安全默认值。"""
    role = interview_type if interview_type in _ROLE_HINT else "tech"
    quality = _estimate_quality(history)
    recent = history[-6:] if len(history) > 6 else history
    history_str = "\n".join(f"{m.get('role')}: {m.get('content','')}" for m in recent)

    prompt = _PLANNER_PROMPT.format(
        role_hint=_ROLE_HINT[role],
        resume_json=resume_json[:1500],
        history=history_str[:2000],
        quality=quality,
    )
    messages = [{"role": "user", "content": prompt}]

    content, tool_log = chat_with_tools(messages, TOOL_SCHEMAS, temperature=0.3, max_tool_rounds=2)

    tool_calls = [
        {"name": t["name"], "arguments": t["arguments"], "result": t["result"]}
        for t in tool_log
    ]
    tool_text = ""
    for t in tool_calls:
        tool_text += f"\n[工具:{t['name']}] {t['result']}"

    # 解析 JSON
    try:
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:-3].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:-3].strip()
        parsed = json.loads(cleaned)
        decision = parsed.get("decision", "deepen")
        focus = parsed.get("focus", "")
        reasoning = parsed.get("reasoning", "")
    except Exception:
        decision, focus, reasoning = "deepen", "", "（规划 Agent 未返回结构化结果，沿用默认深挖策略）"

    if tool_text:
        focus = (focus + "\n参考资料：" + tool_text).strip()

    return {
        "decision": decision,
        "focus": focus,
        "reasoning": reasoning,
        "tool_calls": tool_calls,
    }
