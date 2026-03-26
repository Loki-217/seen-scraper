# services/api/app/main.py
from __future__ import annotations
import sys
import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .settings import settings
from .logging_conf import setup_logging

# DB
from .db import init_db

# V1 routers (jobs/runs)
from .routers.jobs import router as jobs_router
from .routers.runs import router as runs_router, router_jobs as runs_jobs_router

# V2 routers
from .routers.ai import router as ai_router
from .routers.browser import router as browser_router
from .routers.smart import router as smart_router
from .routers.robots import router as robots_router
from .routers.schedules import router as schedules_router, runs_router as scheduled_runs_router

# V2: Session Manager and Scheduler
from .session_manager import session_manager
from .scheduler import scheduler


# ---------- App lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    init_db()
    await session_manager.start()
    print("[SeenFetch] Session Manager 已启动")
    await scheduler.start()
    print("[SeenFetch] Scheduler 已启动")
    yield
    # shutdown
    await scheduler.stop()
    print("[SeenFetch] Scheduler 已停止")
    await session_manager.stop()
    print("[SeenFetch] Session Manager 已停止")


# ---------- Create app ----------
setup_logging()
app = FastAPI(
    title="SeenFetch API",
    version="1.0.0",
    description="Visual web scraping made simple - See it, Fetch it!",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_detail = {
        "error": str(exc),
        "type": type(exc).__name__,
        "traceback": traceback.format_exc()
    }
    return JSONResponse(
        status_code=500,
        content=error_detail
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(runs_jobs_router)
app.include_router(runs_router)
app.include_router(ai_router)
app.include_router(browser_router)
app.include_router(smart_router)
app.include_router(robots_router)
app.include_router(schedules_router)
app.include_router(scheduled_runs_router)


# ---------- Root ----------
@app.get("/")
def root():
    return {
        "name": "SeenFetch",
        "version": settings.api_version,
        "tagline": "See it, Fetch it",
        "description": "Visual web data extraction for everyone",
        "api_docs": "/api/docs"
    }

# ---------- Health check ----------
@app.get("/health")
def health():
    return {"ok": True, "version": settings.api_version}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.uvicorn_host, port=settings.uvicorn_port, reload=True)
