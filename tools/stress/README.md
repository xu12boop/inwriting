# InWriting 压测脚本工具箱

本目录集中存放 InWriting 的压力测试与性能诊断脚本，**与业务代码解耦**，可独立复用。
所有脚本只打 HTTP 接口，不 import 业务模块（`run_patched_8003.py` 例外，见下），
因此既能压本地实例，也能直接压线上（把 `STRESS_BASE` 指过去即可）。

---

## 1. 目录结构

```
tools/stress/
├── README.md                  # 本文件
├── run_all.py                 # ★ 统一入口，一条命令跑完全部
├── stress_test.py             # A/B/C/D 四组接口维度压测
├── stress_journey.py          # E 组：真实用户旅程端到端压测
├── stress_report.py           # D 组专项：并发生成报告
├── probe_blocking.py          # 事件循环阻塞探测（修复验证）
├── run_patched_8003.py        # A/B 对照：8003 端口复现「修复前」行为
├── summarize_journey.py       # 旅程结果汇总（输出可写进文档的数字）
├── make_fixture_resume.py     # 生成压测用简历夹具
├── fixtures/
│   └── stress_resume.docx     # 压测用简历（缺失时自动生成）
└── results/                   # 结果 JSON（不入库，见 .gitignore）
    ├── api_result.json
    ├── journey_result.json
    └── report_result.json
```

---

## 2. 各脚本用途

| 脚本 | 覆盖场景 | 判据 |
|---|---|---|
| `stress_test.py` | **A** 并发只读（`/health`、模型列表）<br>**B** 并发面试对话（SSE 流式）<br>**C** 异常输入（空消息/超长/注入/非法轮次/越权）<br>**D** 报告并发生成 | A：错误率 0、吞吐合理<br>B：流式不中断、chunk 数正常<br>C：**不 500**，有可控 4xx 响应<br>D：全部成功且分数非兜底 |
| `stress_journey.py` | **E** 真实用户旅程：注册 → 登录 → 上传简历 → 开面试 → 6 轮对话（每轮并发拉决策面板）→ 出报告 → 回看 | 旅程成功率、各步骤 P95、跨接口数据一致性（雷达五维齐全、逐题点评 ≥2 条、回看分数与生成时一致） |
| `stress_report.py` | D 组专项，3 路并发 × 3 轮问答后同时生成报告 | 成功率 + 单份耗时 + 整体实际耗时 |
| `probe_blocking.py` | 上传进行中每 0.5s 探一次 `/health` | **修复生效 → 全部 < 1s**；未修复 → 至少一个被拖到数十秒 |
| `run_patched_8003.py` | 启动一个 8003 实例，运行时把 `run_in_threadpool` 换成同步内联（**不改源文件**） | 用于和 8002（已修复）做 A/B 因果对照 |
| `summarize_journey.py` | 读 `results/journey_result.json`，打印注册/登录/上传/对话/首字/报告的均值-P95-最长 | 直接把数字抄进技术文档 |
| `make_fixture_resume.py` | 生成 `fixtures/stress_resume.docx` | 幂等，可重复执行 |

---

## 3. 运行方式

### 3.1 前置

1. 目标服务已在运行（本地或线上）
2. 依赖：`requests`、`python-docx`（模板已在 `requirements*.txt` 中）
3. Python 用项目 venv：

```bash
# Windows
.\venv\Scripts\python tools\stress\run_all.py

# Linux / macOS
./venv/bin/python tools/stress/run_all.py
```

### 3.2 一条命令跑全部（推荐）

```bash
python tools/stress/run_all.py
```

会依次执行：夹具自检 → 连通性预检查 → A/B/C/D → E 旅程（3 并发）→ 汇总，
最后打印结果目录。任一组失败会体现在退出码上。

### 3.3 按需挑一组

```bash
python tools/stress/run_all.py api              # 只跑 A/B/C/D
python tools/stress/run_all.py journey 8        # 只跑 E 旅程，8 并发
python tools/stress/run_all.py report           # 只跑报告专项
python tools/stress/run_all.py probe            # 只做阻塞探测
```

### 3.4 不改入口、直接单跑（压线上时用）

```bash
STRESS_BASE=http://47.94.196.39 python tools/stress/stress_journey.py 5
```

Windows PowerShell：

```powershell
$env:STRESS_BASE="http://47.94.196.39"; python tools\stress\stress_journey.py 5
```

---

## 4. 环境变量

| 变量 | 默认值 | 作用 |
|---|---|---|
| `STRESS_BASE` | `http://127.0.0.1:8001` | 压测目标地址（`stress_test` / `stress_journey` / `stress_report`） |
| `PROBE_BASE` | `http://127.0.0.1:8002` | 阻塞探测目标（`probe_blocking`） |

> 默认端口 `8001` 与线上 gunicorn 一致；本地 `uvicorn --port 8001` 即可对齐。

---

## 5. 结果文件

均写入 `results/`，UTF-8 JSON，可直接被脚本或文档读取：

- `api_result.json` —— `{ "results": [{name, ok, cost, note}], "elapsed": 秒 }`
- `journey_result.json` —— `{ "users", "ok_users", "wall", "results": [{iid, ok, steps[], chat_costs[], first_costs[], plan_ok, report{}}] }`
- `report_result.json` —— `{ "results": [{iid, ok, cost, note}], "wall" }`

`results/` 已加入 `.gitignore`，压测产物不入库。

---

## 6. 阻塞缺陷诊断流程（可复用的排障套路）

背景：`resume.py` 曾是 `async def` 路由内联三段同步阻塞调用（docx 解析 + 向量化 + LLM 匹配），
独占事件循环 20~105 秒，导致**同 worker 的 `/health`、登录全部排队**。
前端表现为「简历上传卡住、登录超时」。

**识别特征**：耗时集中在 21s / 99s / 104s 这类固定档位 + 毫秒级接口被拉到数十秒
⇒ 瓶颈是**队列等待**，不是自身计算。

**三步定位与证明因果**：

```bash
# ① 启动已修复实例（8002）
uvicorn app.main:app --port 8002

# ② 启动「修复前」对照实例（8003，运行时打补丁，不改源文件）
python tools/stress/run_patched_8003.py

# ③ 分别探测两边上传期间的 /health 延迟
PROBE_BASE=http://127.0.0.1:8002 python tools/stress/probe_blocking.py
PROBE_BASE=http://127.0.0.1:8003 python tools/stress/probe_blocking.py
```

**实测结论（本项目真实数据）**：

| 实例 | 上传耗时 | 上传期间 `/health` 最大延迟 |
|---|---|---|
| 8003（模拟修复前） | 22.54s | **20.543s** |
| 8002（已修复） | 20.37s | **0.022s** |

差三个数量级 ⇒ 因果成立。修复方式：`await run_in_threadpool(_parse_and_match, ...)`，
把同步 CPU/IO 让渡给线程池。

---

## 7. 注意事项

- `run_patched_8003.py` 是**唯一**会 import 业务代码的脚本（要改模块属性）。它通过
  向上三级定位项目根并 `os.chdir(ROOT)`，保证 `.env` / `inwriting.db` / `.chroma` 读取路径与正常启动一致。
- 压测会产生真实用户与面试记录，写入 `inwriting.db`。压线上实例前请确认数据可丢弃。
- 报告生成接口耗时 20~60s 属正常（多轮 LLM 调用），脚本超时已设 240s，勿误判为失败。
- 所有脚本 `SESSION.trust_env = False`，**绕过系统代理**，避免压测流量走到加速器上。
