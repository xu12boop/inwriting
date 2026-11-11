import json
import time
import requests
from app.core.config import settings

def get_llm_response(
    messages: list,
    temperature: float = 0.1,
    retries: int = 3,
    timeout: tuple | None = None,
) -> str:
    """
    非流式调用：用于简历解析、报告生成（需要完整 JSON 返回）

    timeout 为 (连接秒, 读取秒)；不传则用默认值。生成评估报告这类长输出
    必须显式传长超时，否则会在 20 秒处被掐断、退化为兜底文案。
    """
    url = f"{settings.llm_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.zhipuai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.llm_model,  # 默认 glm-4-flash，可通过 LLM_MODEL 覆盖
        "messages": messages,
        "temperature": temperature
    }
    req_timeout = timeout or (settings.llm_timeout_connect, settings.llm_timeout_read)

    for attempt in range(retries):
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=req_timeout,
            )
            
            if response.status_code == 429:
                print(f"⚠️ 触发限流（429），{2 * (attempt + 1)} 秒后尝试第 {attempt + 1} 次重试...")
                time.sleep(2 * (attempt + 1))
                continue
                
            if response.status_code != 200:
                print(f"❌ API 请求失败，状态码: {response.status_code}")
                print(f"错误详情: {response.text}")
                return ""
                
            result = response.json()
            return result["choices"][0]["message"]["content"]
            
        except requests.exceptions.Timeout:
            print("⚠️ 智谱服务器响应超时...")
        except Exception as e:
            print(f"❌ 请求发生异常: {e}")
            
        if attempt == retries - 1:
            return ""
        time.sleep(1)
    return ""

def get_llm_stream(messages: list):
    """
    流式调用：用于面试对话（打字机效果）
    """
    url = f"{settings.llm_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.zhipuai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.llm_model, # 流式与非流式共用同一模型配置
        "messages": messages,
        "temperature": 0.7,
        "stream": True
    }
    
    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=(settings.llm_timeout_connect, settings.llm_timeout_read),
        )
        if response.status_code != 200:
            yield "抱歉，AI 服务器当前繁忙，请稍后再试。"
            return

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"]
                        if "content" in delta and delta["content"]:
                            yield delta["content"]
                    except Exception:
                        continue
    except Exception as e:
        print(f"流式请求异常: {e}")
        yield "抱歉，网络连接出现问题。"


def chat_with_tools(
    messages: list,
    tools: list,
    temperature: float = 0.3,
    max_tool_rounds: int = 2,
    timeout: tuple | None = None,
):
    """
    带工具（Function Calling / MCP）的非流式调用：用于规划 Agent。
    若模型返回 tool_calls，则执行工具并把结果回填，最多迭代 max_tool_rounds 轮，
    最终返回 (assistant_content, tool_calls_log)。
    tool_calls_log 形如 [{"name": ..., "arguments": ..., "result": ...}, ...]

    timeout 用于给规划类调用单独设置更短的超时（避免拖慢主对话首字延迟）。
    """
    url = f"{settings.llm_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.zhipuai_api_key}",
        "Content-Type": "application/json"
    }
    req_timeout = timeout or (settings.llm_timeout_connect, settings.llm_timeout_read)
    tool_log = []
    working_messages = [dict(m) for m in messages]

    for _ in range(max_tool_rounds + 1):
        payload = {
            "model": settings.llm_model,
            "messages": working_messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": temperature,
        }
        try:
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=req_timeout,
            )
            if response.status_code == 429:
                print("⚠️ 规划 Agent 触发限流（429），返回空规划")
                return "", tool_log
            if response.status_code != 200:
                print(f"❌ 规划 Agent 请求失败: {response.status_code} {response.text}")
                return "", tool_log
            data = response.json()
            msg = data["choices"][0]["message"]
            if msg.get("tool_calls"):
                from app.core.tools import execute_tool  # 懒加载，避免循环依赖
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    name = fn["name"]
                    try:
                        args = json.loads(fn.get("arguments", "{}") or "{}")
                    except Exception:
                        args = {}
                    result = execute_tool(name, args)
                    tool_log.append({"name": name, "arguments": args, "result": result})
                    working_messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": tc.get("id", name),
                            "type": "function",
                            "function": {"name": name, "arguments": fn.get("arguments", "{}")}
                        }]
                    })
                    working_messages.append({
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tc.get("id", name)
                    })
                continue  # 继续下一轮，让模型基于工具结果给出最终内容
            return msg.get("content", ""), tool_log
        except Exception as e:
            print(f"❌ 规划 Agent 异常: {e}")
            return "", tool_log
    return "", tool_log