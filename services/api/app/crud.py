from __future__ import annotations
from typing import Iterable, List, Optional, Dict
from datetime import datetime

from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from .models import Job, Selector, Run, Result


# -------- Jobs --------
def get_job_by_id(s: Session, job_id: int) -> Optional[Job]:
    return s.get(Job, job_id)

def get_job_by_name(s: Session, name: str) -> Optional[Job]:
    return s.scalar(select(Job).where(Job.name == name))

def list_jobs(s: Session, limit: int = 50, offset: int = 0) -> List[Job]:
    return list(s.scalars(select(Job).offset(offset).limit(limit)))

def create_or_update_job(s: Session, payload, overwrite: bool = False) -> Job:
    """
    payload: schemas.JobCreate
    如果 name 已存在：
      - overwrite=False -> ValueError
      - overwrite=True  -> 更新 Job 基本信息 + 覆盖 selectors
    """
    job = get_job_by_name(s, payload.name)
    if job and not overwrite:
        raise ValueError(f"job '{payload.name}' already exists")

    if not job:
        job = Job(name=payload.name, start_url=payload.start_url)
        s.add(job)

    # 基本字段
    job.start_url = payload.start_url
    job.description = payload.description
    job.status = payload.status
    job.pager_selector = payload.pager.selector
    job.pager_attr = payload.pager.attr
    job.max_pages = payload.pager.max_pages
    job.updated_at = datetime.utcnow()

    # 覆盖 selectors
    job.selectors.clear()
    for i, sel in enumerate(payload.selectors):
        job.selectors.append(
            Selector(
                name=sel.name,
                css=sel.css,
                attr=sel.attr,
                limit=sel.limit,
                required=1 if sel.required else 0,
                regex=sel.regex,
                order_no=sel.order_no if sel.order_no else i,
            )
        )
    s.flush()
    return job

def delete_job(s: Session, job_id: int) -> None:
    s.execute(delete(Job).where(Job.id == job_id))


# -------- Runs --------
def create_run(s: Session, job_id: int, status: str = "queued", settings_json: Optional[str] = None) -> Run:
    run = Run(job_id=job_id, status=status, started_at=datetime.utcnow(), settings_json=settings_json)
    s.add(run)
    s.flush()
    return run

def finish_run(s: Session, run_id: int, status: str, error: Optional[str] = None, stats_json: Optional[str] = None) -> Run:
    run = s.get(Run, run_id)
    if not run:
        raise ValueError("run not found")
    run.status = status
    run.ended_at = datetime.utcnow()
    run.error = error
    run.stats_json = stats_json
    s.flush()
    return run


# -------- Results --------
def add_result(s: Session, run_id: int, field: str, row_idx: int, value: Optional[str], url: Optional[str]) -> Result:
    r = Result(run_id=run_id, field=field, row_idx=row_idx, value=value, url=url)
    s.add(r)
    s.flush()
    return r

def list_results_flat(s: Session, run_id: int, field: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Result]:
    stmt = select(Result).where(Result.run_id == run_id)
    if field:
        stmt = stmt.where(Result.field == field)
    stmt = stmt.order_by(Result.row_idx.asc(), Result.id.asc()).offset(offset).limit(limit)
    return list(s.scalars(stmt))

def list_results_rows(s: Session, run_id: int) -> Dict[str, List[str]]:
    """
    将 flat 结果按 row_idx 聚合成行；返回 {field: [v1,v2,...]}
    """
    stmt = select(Result.field, Result.row_idx, Result.value).where(Result.run_id == run_id).order_by(
        Result.row_idx.asc(), Result.field.asc(), Result.id.asc()
    )
    rows = {}
    for field, row_idx, value in s.execute(stmt):
        rows.setdefault(field, [])
        # 简单齐头对齐：确保长度 >= row_idx + 1
        while len(rows[field]) <= row_idx:
            rows[field].append("")
        rows[field][row_idx] = value or ""
    return rows

