import json
import requests
import time
from app.core.config import settings

def get_llm_response(messages: list, temperature: float = 0.1, retries: int = 3) -> str:
    """
    直接通过 HTTP 请求调用智谱大模型 API，并加入重试机制
    """
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {settings.zhipuai_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "glm-4.7-flash",
        "messages": messages,
        "temperature": temperature
    }
    
    for attempt in range(retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            # 如果是 429（人太多限流），就等 2 秒后重试
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
            
        except Exception as e:
            print(f"❌ 请求发生异常: {e}")
            if attempt == retries - 1: # 最后一次也失败了
                return ""
            time.sleep(2)
            
    print("❌ 重试次数用尽，依然被限流。")
    return ""
def get_llm_stream(messages: list, retries: int = 2):
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.zhipuai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "glm-4.7-flash",
        "messages": messages,
        "temperature": 0.7,
        "stream": True
    }
    
    for attempt in range(retries):
        try:
            # timeout=(连接超时5秒, 读取超时15秒)
            response = requests.post(url, json=payload, headers=headers, stream=True, timeout=(5, 15))
            
            if response.status_code == 429:
                print(f"⚠️ 面试官思考中（触发限流），尝试重试...")
                time.sleep(2)
                continue
                
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
            return # 正常结束就返回，不再重试

        except requests.exceptions.Timeout:
            print("⚠️ 智谱服务器迟迟不响应，触发超时...")
            if attempt == retries - 1:
                yield "系统检测到网络不稳定，让我稍微整理一下思路。" # 给前端的兜底提示
        except Exception as e:
            print(f"流式请求异常: {e}")
            if attempt == retries - 1:
                yield "网络连接出现波动。"