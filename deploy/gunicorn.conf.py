"""Gunicorn 生产配置（Linux）。

启动：
    /opt/inwriting/venv/bin/gunicorn -c deploy/gunicorn.conf.py app.main:app

为什么 worker 数默认是 1：
  本机为 2 核 2G 的入门级实例，AI 调用属于 IO 等待型任务，
  单进程 + asyncio 事件循环即可支撑演示并发；
  而 SQLite 在多进程写入时容易出现 "database is locked"，
  单 worker 可彻底规避该问题。需要更高并发时通过环境变量 WEB_CONCURRENCY 调整，
  同时建议把 DATABASE_URL 换成 MySQL/PostgreSQL。
"""

import os

# 监听地址：仅本机，由 Nginx 反向代理对外提供服务
bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8001")

# 工作进程数（默认 1，理由见文件头说明）
workers = int(os.getenv("WEB_CONCURRENCY", "1"))

# 使用 uvicorn 的异步 worker，兼容 FastAPI 的 async/SSE
worker_class = "uvicorn.workers.UvicornWorker"

# SSE 流式面试是长连接，超时需放宽，否则对话进行到一半会被杀掉
timeout = 180
graceful_timeout = 30
keepalive = 5

# 不在 master 中预加载应用：chromadb / sqlite 连接在 fork 后共享易出问题
preload_app = False

# 日志输出到 stdout/stderr，由 systemd journal 统一收集
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# 进程名便于 ps / htop 识别
proc_name = "inwriting-api"

# 每个 worker 处理多少请求后重启，缓解潜在内存增长
max_requests = 1000
max_requests_jitter = 100
