"""汇总旅程压测结果：便于写入技术文档的精确数字。

用法（先跑过 stress_journey.py 生成 results/journey_result.json）：
    python tools/stress/summarize_journey.py
"""
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(HERE, "results", "journey_result.json")
d = json.load(open(p, encoding="utf-8"))

res = d["results"]
ok = [r for r in res if r["ok"]]
chat, first = [], []
plan_ok = plan_total = 0
up, reg, login, rep = [], [], [], []
reviews_min = 99
for r in res:
    chat += r.get("chat_costs", [])
    first += r.get("first_costs", [])
    plan_ok += r.get("plan_ok", 0)
    for s in r["steps"]:
        c = s["cost"]
        if s["step"].startswith("3 "):
            up.append(c)
        elif s["step"].startswith("1 "):
            reg.append(c)
        elif s["step"].startswith("2 "):
            login.append(c)
        elif s["step"].startswith("6 "):
            rep.append(c)
    if r.get("report"):
        reviews_min = min(reviews_min, r["report"].get("reviews") or 0)


def s(arr):
    if not arr:
        return "n/a"
    a = sorted(arr)
    p95 = a[min(len(a) - 1, int(round(0.95 * (len(a) - 1))))]
    return f"均值 {st.mean(a):.2f}s / P95 {p95:.2f}s / 最长 {max(a):.2f}s"


print(f"用户数 {d['users']}  成功 {d['ok_users']}/{len(res)}  墙钟 {d['wall']}s")
print(f"注册   {min(reg):.2f}~{max(reg):.2f}s  {s(reg)}")
print(f"登录   {min(login):.2f}~{max(login):.2f}s  {s(login)}")
print(f"上传   {min(up):.2f}~{max(up):.2f}s  {s(up)}")
print(f"对话({len(chat)}轮)  {s(chat)}")
print(f"首字({len(first)}轮)  {s(first)}")
print(f"报告   {min(rep):.2f}~{max(rep):.2f}s  {s(rep)}")
print(f"决策面板 {plan_ok}/48  逐题点评最少 {reviews_min} 条")
print(f"报告分数 {[r['report']['score'] for r in res if r.get('report')]}")
