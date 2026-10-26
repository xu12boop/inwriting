from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models
from app.core.config import settings
from app.db.database import Base, engine
from app.api.routers import auth, resume # 引入刚才写的路由

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="智聘引擎 InWriting API", lifespan=lifespan)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(auth.router)
app.include_router(resume.router)

@app.get("/health")
def health():
    return {"status": "ok", "service": "inwriting-api"}
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
def root():
    # 访问根路径时，自动重定向到 API 文档
    return RedirectResponse(url="/docs")
# ...
from app.api.routers import auth, resume, interview, report # 加上 interview
app.include_router(report.router)
app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(interview.router) # 加上这行

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)