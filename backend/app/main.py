"""FastAPI 应用入口。"""
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler, sync_remote_domains
from app.settings import settings
from app.routers import domains, popup_rules, rules, stats

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库并启动定时同步。"""
    await init_db()
    start_scheduler()
    if settings.sync_on_startup:
        # 启动时立即触发一次远程同步（不阻塞启动）
        import asyncio
        asyncio.create_task(sync_remote_domains())
    yield
    await stop_scheduler()


app = FastAPI(
    title="AdBlocker Backend",
    description="屏蔽手机APP广告的后端服务：提供广告域名黑名单、弹窗关闭规则、拦截统计",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS：允许 Android 客户端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(domains.router)
app.include_router(popup_rules.router)
app.include_router(rules.router)
app.include_router(stats.router)


@app.get("/", tags=["health"])
async def root():
    return {"service": "AdBlocker Backend", "status": "ok"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "healthy"}

