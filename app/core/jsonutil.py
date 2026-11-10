"""大模型 JSON 输出的容错解析。

小模型的"只输出 JSON"承诺经常不成立，实际见到过的偏差有：
围栏（```json）、前后带解释文字、单引号、尾逗号、字段被截断。
统一在这里兜一层，避免一次格式抖动就让整条链路走兜底文案。
"""

import json
import re


def _strip_fence(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text[3:]
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip().rstrip("`").strip()
    return text


def loads_object(raw: str) -> dict:
    """从模型输出里抠出一个 JSON 对象；失败抛 ValueError。"""
    text = _strip_fence(raw)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("没有找到 JSON 对象")
    body = text[start : end + 1]
    try:
        return json.loads(body)
    except Exception:
        # 尾逗号：{"a":1,} / [1,2,]
        fixed = re.sub(r",\s*([}\]])", r"\1", body)
        return json.loads(fixed)


def loads_array(raw: str) -> list:
    """从模型输出里抠出一个 JSON 数组；失败抛 ValueError。"""
    text = _strip_fence(raw)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("没有找到 JSON 数组")
    body = text[start : end + 1]
    try:
        return json.loads(body)
    except Exception:
        fixed = re.sub(r",\s*([}\]])", r"\1", body)
        return json.loads(fixed)
