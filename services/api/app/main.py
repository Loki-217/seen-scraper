# services/api/app/main.py
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .settings import settings
from .logging_conf import setup_logging

# 任务路由 & DB
from .db import init_db
from .routers.jobs import router as jobs_router

# 远程页预览（Playwright 封装）
from .runner import run_preview, RunnerError

# 本地 HTML 解析预览
from bs4 import BeautifulSoup
import soupsieve as sv
from .routers.runs import router as runs_router, router_jobs as runs_jobs_router

# ---------- 应用生命周期 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    init_db()   # 确保表已创建
    yield
    # shutdown（需要清理时可在此处补充）


# ---------- 创建应用 ----------
setup_logging()
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 业务路由
app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
app.include_router(runs_jobs_router)                        # /jobs/{id}/run
app.include_router(runs_router)




# ---------- 健康检查 ----------
@app.get("/health")
def health():
    return {"ok": True, "version": settings.api_version}


# ---------- Playwright 远程页面预览 ----------
class PlayPreviewReq(BaseModel):
    url: str = Field(..., description="页面 URL")
    selector: str = Field(..., description="CSS 选择器")
    attr: str = Field(default="text", description="text 或属性名：href/src/…")
    wait_selector: Optional[str] = Field(default=None, description="进入页面后等待的选择器（可选）")
    timeout_ms: int = Field(default=10000, ge=1000, le=60000)
    limit: int = Field(default=20, ge=1, le=100)

class PlayPreviewResp(BaseModel):
    url: str
    selector: str
    attr: str
    count: int
    samples: List[str]

@app.post("/play/preview", response_model=PlayPreviewResp)
def play_preview(req: PlayPreviewReq):
    try:
        data = run_preview(
            url=req.url,
            selector=req.selector,
            attr=req.attr,
            wait_selector=req.wait_selector,
            timeout_ms=req.timeout_ms,
            limit=req.limit,
        )
        return PlayPreviewResp(
            url=req.url,
            selector=req.selector,
            attr=data["attr"],
            count=int(data["count"]),
            samples=data["samples"],
        )
    except RunnerError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- 本地 HTML + 选择器预览 ----------
class TemplatePreviewReq(BaseModel):
    html: str = Field(..., description="原始 HTML 文本（片段/示例均可）")
    selector: str = Field(..., description="CSS 选择器，如 'article h1'")
    attr: str = Field(default="text", description="text 或属性名：href/src/…")
    limit: int = Field(default=50, ge=1, le=200)
    strip: bool = Field(default=True, description="提取文本是否 strip()")

class TemplatePreviewResp(BaseModel):
    selector: str
    attr: str
    count: int
    samples: List[str]

@app.post("/templates/preview", response_model=TemplatePreviewResp)
def templates_preview(req: TemplatePreviewReq):
    # 先校验选择器语法，报错更友好
    try:
        sv.compile(req.selector)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的 CSS 选择器: {e}")

    try:
        soup = BeautifulSoup(req.html, "lxml")
        nodes = soup.select(req.selector)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析/匹配失败: {e}")

    samples: List[str] = []
    attr = (req.attr or "text").lower()
    for el in nodes[: req.limit]:
        if attr == "text":
            samples.append(el.get_text(strip=req.strip))
        else:
            samples.append((el.get(attr) or "").strip())

    return TemplatePreviewResp(
        selector=req.selector,
        attr=attr,
        count=len(nodes),
        samples=samples,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.uvicorn_host, port=settings.uvicorn_port, reload=True)
