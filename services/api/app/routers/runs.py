# services/api/app/routers/runs.py
from __future__ import annotations

from typing import Dict, List, Optional
import json

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from ..db import get_session, session_scope
from .. import models, crud, schemas

# 主路由：/runs 开头（查看 run、取结果、列表）
router = APIRouter(prefix="/runs", tags=["runs"])
# 别名路由：/jobs/{id}/run（启动运行）
router_jobs = APIRouter(prefix="/jobs", tags=["runs"])


# ---------- 工具：按 selectors 从 HTML 提取 ----------
def _extract_by_selectors(
    html: str,
    selectors: List[models.Selector],
    limit_default: int,
) -> Dict[str, List[str]]:
    soup = BeautifulSoup(html, "lxml")
    out: Dict[str, List[str]] = {}

    # 确保按 order_no 稳定顺序
    for sel in sorted(selectors, key=lambda x: x.order_no or 0):
        css = sel.css or ""
        attr = (sel.attr or "text").lower()
        limit = sel.limit or limit_default

        nodes = soup.select(css)
        vals: List[str] = []
        for el in nodes[:limit]:
            if attr == "text":
                vals.append(el.get_text(strip=True))
            else:
                vals.append((el.get(attr) or "").strip())
        out[sel.name] = vals

    return out


# ---------- 后台任务主体 ----------
def _run_job_task(run_id: int, job_id: int, url: str, limit: int) -> None:
    # 自己管理会话，避免使用请求线程的 Session
    with session_scope() as s:
        # 预加载 selectors，避免懒加载
        stmt = (
            select(models.Job)
            .options(selectinload(models.Job.selectors))
            .where(models.Job.id == job_id)
        )
        job = s.execute(stmt).scalar_one_or_none()
        if not job:
            crud.finish_run(s, run_id, status="failed", stats_json=json.dumps({"error": "job not found"}))
            return

        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()
                html = r.text

            samples = _extract_by_selectors(html, job.selectors, limit_default=limit)

            rows_max = 0
            for field, arr in samples.items():
                rows_max = max(rows_max, len(arr))
                for idx, val in enumerate(arr):
                    crud.add_result(
                        s,
                        run_id=run_id,
                        field=field,
                        row_idx=idx,
                        value=val,
                        url=url,
                    )

            stats = {"rows": rows_max, "pages": 1}
            crud.finish_run(s, run_id, status="succeeded", stats_json=json.dumps(stats))
        except Exception as e:
            crud.finish_run(s, run_id, status="failed", stats_json=json.dumps({"error": str(e)}))


# ---------- 启动一次运行（后台任务版） ----------
@router.post("/jobs/{job_id}/run", status_code=202)
def run_job_async(
    job_id: int,
    req: schemas.JobPreviewReq,
    background: BackgroundTasks,
    s: Session = Depends(get_session),
):
    job = s.get(models.Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")

    url = req.url or job.start_url
    # 立刻创建 run（标记为 running 或 queued 都可以；为了简单，这里直接 running）
    run = crud.create_run(s, job_id=job.id, status="running")

    # 丢给后台跑，不阻塞请求
    background.add_task(_run_job_task, run.id, job.id, url, req.limit)

    return {"run_id": run.id, "status": "queued"}


# 别名：支持 POST /jobs/{job_id}/run
@router_jobs.post("/{job_id}/run", status_code=202)
def run_job_alias(job_id: int, req: schemas.JobPreviewReq, background: BackgroundTasks, s: Session = Depends(get_session)):
    return run_job_async(job_id, req, background, s)


# ---------- 查看一次运行 ----------
@router.get("/{run_id}", response_model=schemas.RunOut)
def get_run(run_id: int, s: Session = Depends(get_session)):
    run = s.get(models.Run, run_id)
    if not run:
        raise HTTPException(404, "run not found")

    stats: Optional[dict] = None
    if getattr(run, "stats_json", None):
        try:
            stats = json.loads(run.stats_json)
        except Exception:
            stats = None

    return schemas.RunOut(
        id=run.id,
        job_id=run.job_id,
        status=run.status,
        started_at=getattr(run, "started_at", None),
        finished_at=getattr(run, "ended_at", None),
        stats=stats,
    )


# ---------- 取聚合后的结果 ----------
@router.get("/{run_id}/results", response_model=Dict[str, List[str]])
def get_run_results(run_id: int, s: Session = Depends(get_session)):
    return crud.list_results_rows(s, run_id)


# ---------- 运行列表 ----------
from typing import List as _List
from sqlalchemy import select as _select, desc as _desc
import json as _json

@router.get("", response_model=_List[schemas.RunOut])
def list_runs(
    job_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
    s: Session = Depends(get_session),
):
    stmt = _select(models.Run).order_by(_desc(models.Run.id)).offset(offset).limit(limit)
    if job_id is not None:
        stmt = stmt.where(models.Run.job_id == job_id)

    items = s.execute(stmt).scalars().all()

    out: list[schemas.RunOut] = []
    for r in items:
        stats = None
        if getattr(r, "stats_json", None):
            try:
                stats = _json.loads(r.stats_json)
            except Exception:
                stats = None
        out.append(
            schemas.RunOut(
                id=r.id,
                job_id=r.job_id,
                status=r.status,
                started_at=getattr(r, "started_at", None),
                finished_at=getattr(r, "ended_at", None),
                stats=stats,
            )
        )
    return out
