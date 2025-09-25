# services/api/app/routers/runs.py
from __future__ import annotations

from typing import Dict, List, Optional
import json

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_session
from .. import models, crud, schemas

# 主路由：/runs 开头（查看 run、取结果）
router = APIRouter(prefix="/runs", tags=["runs"])
# 别名路由：/jobs/{id}/run（按你的习惯也能用）
router_jobs = APIRouter(prefix="/jobs", tags=["runs"])


# ---------- 工具：按 selectors 从 HTML 提取 ----------
def _extract_by_selectors(
    html: str,
    selectors: List[models.Selector],
    limit_default: int,
) -> Dict[str, List[str]]:
    soup = BeautifulSoup(html, "lxml")
    out: Dict[str, List[str]] = {}

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


# ---------- 启动一次运行（最小同步版） ----------
@router.post("/jobs/{job_id}/run")
def run_job(job_id: int, req: schemas.JobPreviewReq, s: Session = Depends(get_session)):
    job = s.get(models.Job, job_id)
    if not job:
        raise HTTPException(404, "job not found")

    url = req.url or job.start_url
    run = crud.create_run(s, job_id=job.id, status="running")

    try:
        # 抓取页面
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            r = client.get(url)
            r.raise_for_status()
            html = r.text

        # 解析并提取样本
        samples = _extract_by_selectors(html, job.selectors, limit_default=req.limit)

        # 落库
        rows_max = 0
        for field, arr in samples.items():
            rows_max = max(rows_max, len(arr))
            for idx, val in enumerate(arr):
                crud.add_result(
                    s,
                    run_id=run.id,
                    field=field,
                    row_idx=idx,
                    value=val,
                    url=url,
                )

        stats = {"rows": rows_max, "pages": 1}
        crud.finish_run(s, run.id, status="succeeded", stats_json=json.dumps(stats))
        return {"run_id": run.id, "status": "succeeded"}

    except Exception as e:
        crud.finish_run(s, run.id, status="failed", stats_json=json.dumps({"error": str(e)}))
        raise HTTPException(400, f"run failed: {e}")


# 别名：支持 POST /jobs/{job_id}/run
@router_jobs.post("/{job_id}/run")
def run_job_alias(job_id: int, req: schemas.JobPreviewReq, s: Session = Depends(get_session)):
    return run_job(job_id, req, s)


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

    # 注意：模型里字段名是 ended_at，这里映射到 schemas.RunOut 的 finished_at（若你.schemas里用 ended_at，就相应改名）
    return schemas.RunOut(
        id=run.id,
        job_id=run.job_id,
        status=run.status,
        started_at=run.started_at,
        finished_at=getattr(run, "ended_at", None),
        stats=stats,
    )


# ---------- 取聚合后的结果 ----------
@router.get("/{run_id}/results", response_model=Dict[str, List[str]])
def get_run_results(run_id: int, s: Session = Depends(get_session)):
    return crud.list_results_rows(s, run_id)
