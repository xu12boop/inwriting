import requests
import json

# 1. 创建一个面试会话（假设你之前通过上传简历拿到了 resume_id = 1）
start_url = "http://127.0.0.1:8001/interview/start"
start_res = requests.post(start_url, json={"resume_id": 1, "target_job": "后端开发"})
print("创建面试:", start_res.json())
interview_id = start_res.json()["id"]

# 2. 发送用户回答，并接收流式数据
chat_url = "http://127.0.0.1:8001/interview/chat"
payload = {
    "interview_id": interview_id,
    "user_message": "面试官您好，我已经准备好了，请开始提问吧。"
}

print("\n=== AI 面试官正在输入 ===")
# 开启 stream=True
response = requests.post(chat_url, json=payload, stream=True)

for line in response.iter_lines():
    if line:
        decoded = line.decode('utf-8')
        if decoded.startswith("data: "):
            data_str = decoded[6:]
            if data_str == "[DONE]":
                print("\n\n=== 面试官回答结束 ===")
                break
            try:
                data = json.loads(data_str)
                # 模拟打字机效果，不换行输出
                print(data["content"], end="", flush=True)
            except:
                pass