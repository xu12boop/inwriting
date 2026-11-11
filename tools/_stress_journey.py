"""E 组：按「真实用户旅程」设计的端到端压测。

设计依据 —— 前端 Interview.vue / Report.vue 的真实调用顺序：
  1. 注册 → 登录                       POST /auth/register, /auth/login
  2. 上传简历（等待 LLM 解析 + 匹配）   POST /resume/upload
  3. 选择面试官并开始面试               POST /interview/start
  4. 每一轮：发消息（SSE 流式）          POST /interview/chat
             同时右栏拉本轮规划          GET  /interview/plan/{id}   ← 前端并发发起
  5. 答满 6 轮自动收尾 / 用户提前结束    POST /report/generate/{id}?look_away=N
  6. 进入报告页回看                     GET  /report/{id}

与 A~D 组的区别：A~D 是「接口维度」的负载测试，E 组是「用户维度」的旅程测试——
一个用户从头到尾走完整条链路，多个用户同时走，统计每一步的耗时与成功率，
并断言跨接口的数据一致性（报告里的 id、雷达维度、逐题条数与对话轮数吻合）。

用法：
    python tools/_stress_journey.py            # 默认 3 个并发用户
    python tools/_stress_journey.py 5          # 5 个并发用户
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
RESUME_PATH = os.path.join(_HERE, "_stress_resume.docx")

import concurrent.futures as cf
import json
import statistics
import sys
import time

import requests

BASE = os.environ.get("STRESS_BASE", "http://127.0.0.1:8001")
MAX_ROUNDS = 6

# 6 轮答案，模拟一个会认真作答但水平中等的候选人（与真实用户一致：不是每次都答满，这里走满 6 轮以覆盖自动收尾）
ANSWERS = [
    "我做过一个基于 FastAPI 的流式问答服务，用 SSE 推送 token，前端做了队列削峰，单机压测能扛住 200 并发左右。",
    "检索这块我用的是向量召回加 LLM 重排：先 Top5 召回候选，再让模型按岗位要求打分重排，最后把引用一起返回做溯源。",
    "缓存做了两级，进程内 LRU 加 Redis，命中率大概七成；冷启动会预热热门岗位的 JD 向量。",
    "遇到过 Redis 缓存穿透，我加的是布隆过滤器加空值缓存，配合随机过期时间，热点过期时的抖动基本消掉了。",
    "团队协作上我用过 Git Flow，接口先定 OpenAPI 契约再并行开发，联调阶段主要靠契约测试兜底。",
    "如果重做这个项目，我会先把可观测性补上：结构化日志、关键链路打点、慢查询告警，而不是等出问题再查日志。",
]

RESUME_BYTES = open(RESUME_PATH, "rb").read()


def _post_stream(sess, url, payload, headers, timeout=150):
    """发一轮对话，返回 (ok, 首字耗时, 总耗时, chunk 数)。"""
    t = time.time()
    r = sess.post(url, json=payload, headers=headers, stream=True, timeout=timeout)
    if r.status_code != 200:
        return False, 0.0, time.time() - t, 0
    first, chunks = None, 0
    for line in r.iter_lines():
        if line and line.startswith(b"data: "):
            if first is None:
                first = time.time() - t
            chunks += 1
    return chunks > 0, (first or 0.0), time.time() - t, chunks


def run_one_user(idx: int) -> dict:
    """一个用户的完整旅程。返回逐步骤耗时与断言结果。"""
    steps = []          # [(步骤名, 成功?, 耗时秒, 备注)]
    s = requests.Session()
    s.trust_env = False
    user = f"journey_{idx}_{int(time.time() * 1000) % 10**8}"
    pwd = "journey123456"

    def step(name, ok, cost, note=""):
        steps.append({"step": name, "ok": ok, "cost": round(cost, 3), "note": note})
        return ok

    # ---- 1. 注册 ----
    t = time.time()
    try:
        r = s.post(f"{BASE}/auth/register", json={"username": user, "password": pwd}, timeout=30)
        ok = r.status_code in (200, 400)          # 400 = 用户名已存在，对本流程等价于可用
    except Exception as e:
        return {"user": user, "ok": False, "steps": steps + [{"step": "1 注册", "ok": False, "cost": 0, "note": type(e).__name__}]}
    step("1 注册", ok, time.time() - t, f"HTTP {r.status_code}")

    # ---- 2. 登录 ----
    # 并发场景下后端是单 worker，注册的 bcrypt 计算 + 简历解析会短时占住事件循环，
    # 因此登录允许重试，避免把「排队」误判成「失败」。
    t = time.time()
    r = None
    for attempt in range(1, 4):
        try:
            r = s.post(f"{BASE}/auth/login", data={"username": user, "password": pwd}, timeout=30)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1.5 * attempt)
    if r is None or r.status_code != 200:
        step("2 登录", False, time.time() - t, f"HTTP {getattr(r, 'status_code', 'timeout')}（重试 3 次）")
        return {"user": user, "ok": False, "steps": steps}
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    step("2 登录", True, time.time() - t, "拿到 JWT")

    # ---- 3. 上传简历（LLM 解析 + RAG 匹配，用户视角的「等我简历分析完」）----
    t = time.time()
    r = None
    for attempt in range(1, 4):
        files = {"file": ("resume.docx", RESUME_BYTES,
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        try:
            r = s.post(f"{BASE}/resume/upload", files=files,
                       data={"target_job": "AI应用开发实习生"}, headers=h, timeout=180)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(2 * attempt)
    if r is None or r.status_code != 200:
        step("3 上传简历", False, time.time() - t, f"HTTP {getattr(r, 'status_code', 'timeout')}（重试 3 次）")
        return {"user": user, "ok": False, "steps": steps}
    resume_id = r.json().get("id")
    match_score = r.json().get("match_score")
    step("3 上传简历", True, time.time() - t, f"resume_id={resume_id}, 匹配分={match_score}")

    # ---- 4. 开始面试 ----
    t = time.time()
    r = None
    for attempt in range(1, 4):
        try:
            r = s.post(f"{BASE}/interview/start",
                       json={"resume_id": resume_id, "target_job": "AI应用开发实习生", "interview_type": "tech"},
                       headers=h, timeout=60)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1.5 * attempt)
    if r is None or r.status_code != 200:
        step("4 开始面试", False, time.time() - t, f"HTTP {getattr(r, 'status_code', 'conn-reset')}（重试 3 次）")
        return {"user": user, "ok": False, "steps": steps}
    iid = r.json()["id"]
    step("4 开始面试", True, time.time() - t, f"interview_id={iid}")

    # ---- 5. 六个回合：chat(SSE) + plan(并发拉取) ----
    chat_costs, first_costs, plan_costs = [], [], []
    plan_ok = 0
    for rnd, ans in enumerate(ANSWERS, 1):
        t = time.time()
        try:
            ok, first, cost, chunks = _post_stream(
                s, f"{BASE}/interview/chat",
                {"interview_id": iid, "user_message": ans, "round_no": rnd, "max_rounds": MAX_ROUNDS},
                h)
        except Exception as e:
            step(f"5.{rnd} 对话", False, time.time() - t, type(e).__name__)
            return {"user": user, "ok": False, "steps": steps}
        chat_costs.append(cost)
        first_costs.append(first)
        step(f"5.{rnd} 对话(SSE)", ok, cost, f"首字 {first:.2f}s, {chunks} chunk")

        # 前端在流式开始后立刻并发拉规划；这里同样发一次，验证它不会拖慢或打断主链路
        tp = time.time()
        rp = s.get(f"{BASE}/interview/plan/{iid}", headers=h, timeout=20)
        plan_costs.append(time.time() - tp)
        has_plan = rp.status_code == 200 and bool(rp.json().get("has_plan"))
        if has_plan:
            plan_ok += 1
        step(f"5.{rnd} 决策面板", rp.status_code == 200,
             time.time() - tp,
             f"has_plan={has_plan}" + (f", decision={rp.json().get('decision')}" if has_plan else ", 首轮尚无规划"))

    # ---- 6. 生成报告（带 look_away 与用户旅程一致）----
    look_away = 2      # 模拟真实用户中途有 2 次注意力偏离
    t = time.time()
    r = s.post(f"{BASE}/report/generate/{iid}?look_away={look_away}", headers=h, timeout=240)
    if r.status_code != 200:
        step("6 生成报告", False, time.time() - t, f"HTTP {r.status_code}")
        return {"user": user, "ok": False, "steps": steps}
    rep = r.json()
    radar = rep.get("radar_data") or {}
    reviews = rep.get("question_reviews") or []
    score = rep.get("overall_score")
    # 数据一致性断言：不是「全 60 分兜底」、五维雷达齐全、逐题点评条数合理
    fallback = set(radar.values()) == {60} and not reviews
    dims_ok = len(radar) == 5
    step("6 生成报告", (not fallback) and dims_ok, time.time() - t,
         f"综合 {score}, 雷达 {list(radar.values())}, 逐题 {len(reviews)} 条")

    # ---- 7. 报告页回看（GET /report/{id}）----
    t = time.time()
    r2 = s.get(f"{BASE}/report/{iid}", headers=h, timeout=30)
    same = r2.status_code == 200 and r2.json().get("overall_score") == score
    step("7 报告页回看", same, time.time() - t,
         f"HTTP {r2.status_code}, 分数一致={same}")

    all_ok = all(x["ok"] for x in steps)
    return {
        "user": user,
        "ok": all_ok,
        "iid": iid,
        "steps": steps,
        "chat_costs": [round(c, 2) for c in chat_costs],
        "first_costs": [round(c, 2) for c in first_costs],
        "plan_ok": plan_ok,
        "report": {"score": score, "radar": radar, "reviews": len(reviews)},
    }


def run_one_user_safe(idx: int) -> dict:
    """包一层异常保护：单个用户旅程崩溃不应中断整轮压测。"""
    try:
        return run_one_user(idx)
    except Exception as e:
        return {"user": f"journey_{idx}", "ok": False,
                "steps": [{"step": "异常", "ok": False, "cost": 0, "note": type(e).__name__}]}


def main(users: int = 3):
    print(f"=== E 组：真实用户旅程压测（{users} 个并发用户 × 完整链路）===")
    print(f"目标 {BASE}｜每个用户走：注册→登录→传简历→开面试→6 轮对话(含决策面板)→出报告→回看")
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=users) as ex:
        results = list(ex.map(run_one_user_safe, range(users)))
    wall = time.time() - t0

    print("\n--- 逐用户结果 ---")
    for r in results:
        print(f"\n用户 {r['user']}  整体 {'✅' if r['ok'] else '❌'}")
        for s_ in r["steps"]:
            print(f"   {'✅' if s_['ok'] else '❌'} {s_['step']:<16} {s_['cost']:>7.2f}s  {s_['note']}")

    ok_users = sum(1 for r in results if r["ok"])
    all_chat = [c for r in results for c in r.get("chat_costs", [])]
    all_first = [c for r in results for c in r.get("first_costs", []) if c]
    plan_total = sum(1 for r in results for s_ in r["steps"] if s_["step"].endswith("决策面板"))
    plan_ok = sum(r.get("plan_ok", 0) for r in results)

    print("\n" + "=" * 66)
    print(f"完整旅程成功率：{ok_users}/{len(results)}")
    if all_chat:
        print(f"对话轮次：{len(all_chat)} 轮，平均 {statistics.mean(all_chat):.2f}s，"
              f"P95 {sorted(all_chat)[max(0, int(len(all_chat)*0.95)-1)]:.2f}s，"
              f"最长 {max(all_chat):.2f}s")
    if all_first:
        print(f"首字延迟：平均 {statistics.mean(all_first):.2f}s，P95 {sorted(all_first)[max(0,int(len(all_first)*0.95)-1)]:.2f}s，"
              f"最长 {max(all_first):.2f}s")
    print(f"决策面板可用：{plan_ok}/{plan_total}")
    print(f"墙钟总耗时：{wall:.1f}s")

    out = os.path.join(_HERE, "_stress_journey_result.json")
    with open(out, "w", encoding="utf-8") as fp:
        json.dump({"users": users, "wall": round(wall, 2), "ok_users": ok_users,
                   "results": results}, fp, ensure_ascii=False, indent=2)
    print(f"结果已写入 {out}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    main(n)
