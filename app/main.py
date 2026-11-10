"""FastAPI 应用入口。

启动方式：
  开发：uvicorn app.main:app --reload --port 8001
  生产：gunicorn -k uvicorn.workers.UvicornWorker -c deploy/gunicorn.conf.py app.main:app
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app import models  # noqa: F401  确保模型在 create_all 前完成注册
from app.core.config import settings
from app.db.database import Base, engine
from app.db.migrations import ensure_extra_columns
from app.api.routers import auth, resume, interview, report


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 首次启动自动建表（SQLite 场景足够；迁移到 MySQL/PostgreSQL 时改用 Alembic）
    Base.metadata.create_all(bind=engine)
    # 已存在的表补新增字段（幂等、失败不阻断启动）
    ensure_extra_columns(engine)

    # 向量库预热：库里条目过少时补一批真实岗位 JD，让"检索依据"有可比对的候选。
    # 失败只告警，不阻断启动（无外网/无 Key 时仍可跑通主流程）。
    try:
        from app.core.rag import collection, get_embedding
        from app.core.seed_jds import seed_if_empty

        seed_if_empty(collection, get_embedding)
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  向量库预热跳过: {e}")

    # 部署自检提示：保留默认密钥 / 未配置 API Key 时给出醒目告警
    if settings.is_default_secret:
        print("⚠️  安全告警：SECRET_KEY 仍为示例值，请在生产环境更换为随机字符串！")
    if not settings.zhipuai_api_key:
        print("⚠️  配置告警：ZHIPUAI_API_KEY 为空，AI 相关功能将走兜底文案。")
    print(
        f"✅ {settings.app_name} v{settings.app_version} 启动完成 | "
        f"LLM={settings.llm_model} | Planner={'on' if settings.enable_planner else 'off'} | "
        f"DB={settings.database_url}"
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# 跨域：同域部署（Nginx 反代 /api）时该配置不生效也不会报错
origins = settings.cors_origin_list
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 业务路由（每个 router 只注册一次）
app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(report.router)


@app.get("/health", tags=["系统"])
def health():
    """健康检查：用于部署验收、Nginx upstream 探活、云监控告警。"""
    return {
        "status": "ok",
        "service": "inwriting-api",
        "version": settings.app_version,
        "planner": settings.enable_planner,
        "llm": settings.llm_model,
    }


@app.get("/", include_in_schema=False)
def root():
    # 访问根路径时自动跳转到交互式 API 文档
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
