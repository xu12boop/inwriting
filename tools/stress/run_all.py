"""压测统一入口：一条命令跑完（或挑选跑）所有场景。

设计目标：下次复用时不必记住 7 个脚本的名字和先后顺序。

用法：
    python tools/stress/run_all.py                  # 跑全部（A/B/C/D + E 旅程 3 并发）
    python tools/stress/run_all.py api              # 只跑 A/B/C/D 接口维度
    python tools/stress/run_all.py journey 8        # 只跑 E 旅程，8 并发用户
    python tools/stress/run_all.py probe            # 只做阻塞探测（修复验证）
    python tools/stress/run_all.py report           # 只跑 D 组报告专项

环境变量：
    STRESS_BASE   目标地址，默认 http://127.0.0.1:8001
    PROBE_BASE    阻塞探测目标，默认 http://127.0.0.1:8002

前置：
    1. 目标服务已在运行（本地 uvicorn / gunicorn 均可）
    2. 已装依赖：requests、python-docx（仅生成夹具时需要）
    3. 夹具存在：tools/stress/fixtures/stress_resume.docx（缺失会自动生成）
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "stress_resume.docx")

BASE = os.environ.get("STRESS_BASE", "http://127.0.0.1:8001")
PROBE_BASE = os.environ.get("PROBE_BASE", "http://127.0.0.1:8002")


def run(script: str, args: list[str] | None = None) -> int:
    """在子进程里跑一个压测脚本，继承当前环境变量。"""
    cmd = [sys.executable, os.path.join(HERE, script)] + (args or [])
    print(f"\n{'=' * 64}\n▶ {script} {' '.join(args or [])}\n{'=' * 64}", flush=True)
    t0 = time.time()
    code = subprocess.call(cmd)
    print(f"◀ {script} 结束，退出码 {code}，耗时 {time.time() - t0:.1f}s", flush=True)
    return code


def ensure_fixture() -> None:
    """夹具缺失时自动生成，避免新手第一步就报 FileNotFoundError。"""
    if os.path.exists(FIXTURE):
        return
    print("[fixture] 未找到简历夹具，自动生成…", flush=True)
    run("make_fixture_resume.py")


def precheck() -> bool:
    """服务连通性预检查：不通就直接给出提示，而不是让脚本跑到一半到处报错。"""
    import requests

    s = requests.Session()
    s.trust_env = False
    try:
        r = s.get(f"{BASE}/health", timeout=5)
        print(f"[precheck] {BASE}/health -> {r.status_code}", flush=True)
        return r.status_code == 200
    except Exception as e:  # noqa: BLE001
        print(f"[precheck] 无法连接 {BASE}：{e}", flush=True)
        print("[precheck] 请先启动服务，例如：", flush=True)
        print("  .\\venv\\Scripts\\python -m uvicorn app.main:app --port 8001", flush=True)
        return False


def main() -> int:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    users = sys.argv[2] if len(sys.argv) > 2 else "3"

    print(f"目标 STRESS_BASE={BASE}  PROBE_BASE={PROBE_BASE}", flush=True)
    ensure_fixture()

    if mode == "probe":
        print(f"[note] 阻塞探测将打 PROBE_BASE={PROBE_BASE}", flush=True)
        return run("probe_blocking.py")

    if not precheck():
        return 2

    if mode == "api":
        return run("stress_test.py")

    if mode == "journey":
        code = run("stress_journey.py", [users])
        if code == 0:
            run("summarize_journey.py")
        return code

    if mode == "report":
        return run("stress_report.py")

    # all：接口维度 → 旅程 → 汇总
    codes = [run("stress_test.py"), run("stress_journey.py", [users])]
    if codes[-1] == 0:
        run("summarize_journey.py")

    print("\n" + "=" * 64)
    print(f"全部结束。失败组数 {sum(1 for c in codes if c != 0)}/{len(codes)}")
    print(f"结果目录：{os.path.join(HERE, 'results')}")
    print("=" * 64, flush=True)
    return 0 if all(c == 0 for c in codes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
