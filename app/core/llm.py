import json
import time
import requests
from app.core.config import settings

def get_llm_response(messages: list, temperature: float = 0.1, retries: int = 3) -> str:
    """
    非流式调用：用于简历解析、报告生成（需要完整 JSON 返回）
    """
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.zhipuai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "glm-4-flash",  # 👈 换成极速免费模型，不排队
        "messages": messages,
        "temperature": temperature
    }
    
    for attempt in range(retries):
        try:
            # 连接超时5秒，读取超时20秒
            response = requests.post(url, json=payload, headers=headers, timeout=(5, 20))
            
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
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.zhipuai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "glm-4-flash", # 👈 流式也用极速模型
        "messages": messages,
        "temperature": 0.7,
        "stream": True
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=(5, 20))
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