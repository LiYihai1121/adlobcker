"""FastAPI 应用入口。"""
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler
from app.routers import domains, popup_rules, stats

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库并启动定时同步。"""
    await init_db()
    start_scheduler()
    yield
    await stop_scheduler()


app = FastAPI(
    title="AdBlocker Backend",
    description="屏蔽手机APP广告的后端服务：提供广告域名黑名单、弹窗关闭规则、拦截统计",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(domains.router)
app.include_router(popup_rules.router)
app.include_router(stats.router)


@app.get("/", tags=["health"])
async def root():
    return {"service": "AdBlocker Backend", "status": "ok"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy"}
