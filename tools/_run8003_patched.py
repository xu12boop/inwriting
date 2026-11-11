"""对照实验：在 8003 端口复现「修复前」的阻塞行为。

做法：不改任何源文件，只在启动 uvicorn **之前**对 `app.api.routers.resume`
模块里的 `run_in_threadpool` 打运行时补丁，把它替换成「同线程直接 await」，
从而把 `_parse_and_match` 的同步阻塞重新放回事件循环 —— 等价于修复前的内联写法。

这样 8002（已修复）与 8003（模拟修复前）跑同一份压测，即可给出因果对照。
"""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.api.routers import resume as resume_mod  # noqa: E402


def _blocking_run_in_threadpool(func, *args, **kwargs):
    """替换品：不腾出线程，直接在事件循环里同步执行，复现修复前的独占行为。"""

    async def _inner():
        return func(*args, **kwargs)

    return _inner()


resume_mod.run_in_threadpool = _blocking_run_in_threadpool
print("[patch] run_in_threadpool -> inline (模拟修复前阻塞行为)", flush=True)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8003)
