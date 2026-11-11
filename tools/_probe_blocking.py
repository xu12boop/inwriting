"""验证 run_in_threadpool 修复：上传简历期间 /health 是否仍可毫秒级响应。

修复前现象：resume.py 的 async def 路由内联三段同步阻塞调用，独占事件循环
20~105 秒，期间同 worker 的 /health、登录全部排队，表现为「毫秒级接口等上百秒」。

判据：
  - 修复生效 → 上传期间 /health 全部 < 1s
  - 未修复   → 至少一个 /health 被拖到数十秒
"""
import os
import sys
import threading
import time

import requests

BASE = os.environ.get("PROBE_BASE", "http://127.0.0.1:8002")
SESSION = requests.Session()
SESSION.trust_env = False

HERE = os.path.dirname(os.path.abspath(__file__))
RESUME = os.path.join(HERE, "_stress_resume.docx")


def main():
    # 0. 健康检查
    t = time.time()
    r = SESSION.get(f"{BASE}/health", timeout=10)
    print(f"[health] {r.status_code} {round(time.time()-t,3)}s {r.text[:120]}")

    # 1. 注册 + 登录
    u = f"probe_{int(time.time())}"
    r = SESSION.post(f"{BASE}/auth/register", json={"username": u, "password": "Probe123456"}, timeout=60)
    print(f"[register] {r.status_code}")
    # 登录是 OAuth2 表单（OAuth2PasswordRequestForm），必须 form 提交而非 json
    r = SESSION.post(f"{BASE}/auth/login", data={"username": u, "password": "Probe123456"}, timeout=120)
    print(f"[login] {r.status_code}")
    tok = r.json().get("access_token")
    h = {"Authorization": f"Bearer {tok}"}

    result = {}

    def upload():
        t0 = time.time()
        try:
            with open(RESUME, "rb") as f:
                files = {"file": ("resume.docx", f.read(),
                                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
            t1 = time.time()
            r = SESSION.post(f"{BASE}/resume/upload", headers=h, files=files,
                             data={"target_job": "Python 后端开发"}, timeout=300)
            result["upload"] = (r.status_code, round(time.time() - t1, 2))
            print(f"[upload] {r.status_code} 耗时 {result['upload'][1]}s")
        except Exception as e:
            result["upload"] = ("ERR", str(e)[:120])
            print(f"[upload] ERR {e}")

    th = threading.Thread(target=upload)
    th.start()

    time.sleep(2)  # 等上传进入 LLM 阻塞段

    lat = []
    for i in range(8):
        t = time.time()
        try:
            r = SESSION.get(f"{BASE}/health", timeout=60)
            d = round(time.time() - t, 3)
            lat.append((d, r.status_code))
        except Exception as e:
            lat.append((round(time.time() - t, 3), "ERR"))
        time.sleep(0.5)

    th.join()

    print("\n上传期间 /health 延迟序列（秒 / 状态）:")
    for d, s in lat:
        print(f"  {d:>7.3f}  {s}")
    print(f"\n最大延迟 {max(d for d, _ in lat):.3f}s")
    print("判据：全部 < 1s → 修复生效（事件循环未被独占）")
    print("上传结果:", result.get("upload"))


if __name__ == "__main__":
    main()
