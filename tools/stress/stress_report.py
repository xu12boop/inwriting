"""D 组专项：真实轮次下的并发生成报告（3 路并发，每路 3 轮问答）。

用法：
    python tools/stress/stress_report.py
    STRESS_BASE=http://127.0.0.1:8002 python tools/stress/stress_report.py

结果：tools/stress/results/report_result.json
"""
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
RESUME_PATH = os.path.join(_HERE, "fixtures", "stress_resume.docx")
import concurrent.futures as cf
import json
import time
import traceback

import requests

BASE = os.environ.get("STRESS_BASE", "http://127.0.0.1:8001")
RESUME_BYTES = open(RESUME_PATH, "rb").read()

ANSWERS = [
    "我用 FastAPI 做流式接口，SSE 推送，单机压测支撑过每秒 200 并发，用连接池和背压控制峰值。",
    "RAG 部分我做了两路召回：向量 Top5 召回后，再用大模型对候选 JD 重排打分，最后把引用一起返回给前端做溯源。",
    "缓存用了两级，进程内 LRU 加 Redis，命中率大概七成，冷启动会预热门岗位的 JD。",
]


def new_session(tag):
    s = requests.Session()
    s.trust_env = False
    u = f"stress_d_{tag}_{int(time.time() * 1000) % 10**8}"
    p = "stress123456"
    s.post(f"{BASE}/auth/register", json={"username": u, "password": p}, timeout=30)
    r = s.post(f"{BASE}/auth/login", data={"username": u, "password": p}, timeout=30)
    if r.status_code != 200:
        return None, f"login {r.status_code}"
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    files = {"file": ("resume.docx", RESUME_BYTES,
                      "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    r = s.post(f"{BASE}/resume/upload", files=files, data={"target_job": "AI应用开发实习生"}, headers=h, timeout=180)
    if r.status_code != 200:
        return None, f"resume {r.status_code}"
    r = s.post(f"{BASE}/interview/start",
               json={"resume_id": r.json()["id"], "target_job": "AI应用开发实习生", "interview_type": "tech"},
               headers=h, timeout=60)
    if r.status_code != 200:
        return None, f"start {r.status_code}"
    return {"s": s, "h": h, "iid": r.json()["id"]}, ""


def chat(sess, msg, rnd):
    r = sess["s"].post(f"{BASE}/interview/chat",
                       json={"interview_id": sess["iid"], "user_message": msg, "round_no": rnd, "max_rounds": 6},
                       headers=sess["h"], stream=True, timeout=150)
    if r.status_code != 200:
        return False
    n = sum(1 for line in r.iter_lines() if line and line.startswith(b"data: "))
    return n > 0


def prepare(tag):
    sess, err = new_session(tag)
    if not sess:
        return None, err
    for i, ans in enumerate(ANSWERS, 1):
        if not chat(sess, ans, i):
            return None, f"第{i}轮对话失败"
    return sess, ""


def gen(sess):
    t = time.time()
    try:
        r = sess["s"].post(f"{BASE}/report/generate/{sess['iid']}?look_away=0", headers=sess["h"], timeout=240)
        if r.status_code != 200:
            return False, time.time() - t, f"HTTP {r.status_code}"
        d = r.json()
        radar = d.get("radar_data") or {}
        reviews = d.get("question_reviews") or []
        degraded = set(radar.values()) == {60} and not reviews
        return (not degraded), time.time() - t, \
            f"综合 {d.get('overall_score')}, 雷达 {list(radar.values())}, 逐题 {len(reviews)} 条"
    except Exception as e:
        return False, time.time() - t, type(e).__name__


if __name__ == "__main__":
    print("=== D 专项：3 路并发 × 3 轮问答 → 并发生成报告 ===")
    print("准备会话（含简历解析 + 3 轮对话，串行并重试）…")
    sessions = []
    for tag in "abc":
        sess, err = None, ""
        for attempt in range(1, 4):
            try:
                sess, err = prepare(f"{tag}{attempt}")
            except Exception as e:  # 回环瞬时 RST 时重试
                sess, err = None, f"{type(e).__name__}"
            if sess:
                break
            time.sleep(2)
        if sess:
            sessions.append(sess)
            print(f"  ✅ 会话{sess['iid']} 就绪")
        else:
            print(f"  ❌ 会话{tag} 准备失败: {err}")

    if not sessions:
        raise SystemExit("无可用会话")

    print(f"\n同时生成 {len(sessions)} 份报告…")
    t0 = time.time()
    results = []
    with cf.ThreadPoolExecutor(max_workers=len(sessions)) as ex:
        for sess, (ok, cost, note) in zip(sessions, ex.map(gen, sessions)):
            results.append({"iid": sess["iid"], "ok": ok, "cost": round(cost, 2), "note": note})
            print(f"  {'✅' if ok else '❌'} 报告{sess['iid']}  {cost:.1f}s  {note}")
    wall = time.time() - t0

    okn = sum(1 for r in results if r["ok"])
    print(f"\n汇总：成功 {okn}/{len(results)}，墙钟 {wall:.1f}s，平均 {sum(r['cost'] for r in results)/len(results):.1f}s/份")
    os.makedirs(os.path.join(_HERE, "results"), exist_ok=True)
    with open(os.path.join(_HERE, "results", "report_result.json"), "w", encoding="utf-8") as fp:
        json.dump({"results": results, "wall": round(wall, 2)}, fp, ensure_ascii=False, indent=2)
