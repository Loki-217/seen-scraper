# services/api/app/crud.py
from __future__ import annotations

from typing import Optional, Dict, List, Any, Iterable
from datetime import datetime
import json

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from . import models, schemas


# ---------------------------------------------------------------------
# 小工具：兼容不同模型字段命名（如 selector/name, row_idx/row 等）
# ---------------------------------------------------------------------
def _col(cls, *candidates: str) -> str:
    """返回 ORM 类上第一个存在的字段名"""
    for name in candidates:
        if hasattr(cls, name):
            return name
    # 兜底：用第一个候选，避免 AttributeError（后续 getattr 会报错）
    return candidates[0]


def _set(obj: Any, **pairs: Any) -> None:
    """
    宽容地给 obj 赋值：对同一语义的多个候选名尝试设置（遇到存在的就设置）
    例：_set(r, selector=("selector","name"), value=("value","text"), ...)
    """
    for logical_name, value in pairs.items():
        if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], (list, tuple)):
            # 兼容旧版本调用：_set(obj, selector=(("selector","name"), "title"))
            candidates, val = value
        else:
            candidates, val = logical_name, value  # 不走这里，保留兼容
        # 如果 candidates 不是可迭代字段名列表，就跳过
        if not isinstance(candidates, (list, tuple)):
            continue
        for name in candidates:
            if hasattr(obj, name):
                setattr(obj, name, val)
                break


# 预先解析 Result 字段名，避免每次调用都查
_RESULT_SELECTOR = _col(models.Result, "selector", "name")
_RESULT_ROW      = _col(models.Result, "row_idx", "row", "index", "idx")
_RESULT_VALUE    = _col(models.Result, "value", "text", "content", "val")
_RESULT_URL      = _col(models.Result, "url", "href", "link")


# ---------------------------------------------------------------------
# Job
# ---------------------------------------------------------------------
def list_jobs(s: Session, limit: int = 100, offset: int = 0) -> List[models.Job]:
    stmt = select(models.Job).order_by(models.Job.id.asc()).limit(limit).offset(offset)
    return list(s.execute(stmt).scalars())


def get_job(s: Session, job_id: int) -> Optional[models.Job]:
    return s.get(models.Job, job_id)


def get_job_by_name(s: Session, name: str) -> Optional[models.Job]:
    stmt = select(models.Job).where(models.Job.name == name)
    return s.scalar(stmt)


def create_or_update_job(s: Session, payload: schemas.JobCreate, overwrite: bool = False) -> models.Job:
    """
    依据 name 存在则更新；不存在则创建。
    overwrite=True 会清空并重建 selectors。
    """
    job = get_job_by_name(s, payload.name)

    # 🔥 处理配置：将字典转换为 JSON 字符串
    config_json = None
    if payload.config:
        config_json = json.dumps(payload.config, ensure_ascii=False)

    if not job:
        job = models.Job(
            name=payload.name,
            start_url=payload.start_url,
            description=payload.description or "",
            status=payload.status or "active",
            pager_selector=(payload.pager.selector if payload.pager else None),
            pager_attr=(payload.pager.attr if payload.pager else None),
            max_pages=(payload.pager.max_pages if payload.pager else None),
            config_json=config_json,  # 🔥 新增
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        s.add(job)
        s.flush()
    else:
        job.start_url = payload.start_url
        job.description = payload.description or job.description
        job.status = payload.status or job.status
        if payload.pager:
            job.pager_selector = payload.pager.selector
            job.pager_attr = payload.pager.attr
            job.max_pages = payload.pager.max_pages
        if config_json is not None:  # 🔥 新增
            job.config_json = config_json
        job.updated_at = datetime.utcnow()
        s.add(job)
        s.flush()

    # selectors
    if overwrite:
        s.execute(delete(models.Selector).where(models.Selector.job_id == job.id))
        s.flush()

    # 去重：name 唯一
    existed = {sel.name for sel in job.selectors} if getattr(job, "selectors", None) else set()
    order_no = 0
    for sel_in in payload.selectors or []:
        if sel_in.name in existed and not overwrite:
            continue
        sel = models.Selector(
            job_id=job.id,
            name=sel_in.name,
            css=sel_in.css,
            attr=sel_in.attr or "text",
            limit=sel_in.limit or 20,
            required=bool(sel_in.required),
            regex=sel_in.regex,
            order_no=order_no,
            created_at=datetime.utcnow(),
        )
        order_no += 1
        s.add(sel)

    s.flush()
    return job


def delete_job(s: Session, job_id: int) -> None:
    subq_runs = select(models.Run.id).where(models.Run.job_id == job_id).subquery()
    s.execute(delete(models.Result).where(models.Result.run_id.in_(select(subq_runs.c.id))))
    s.execute(delete(models.Run).where(models.Run.job_id == job_id))
    s.execute(delete(models.Selector).where(models.Selector.job_id == job_id))
    s.execute(delete(models.Job).where(models.Job.id == job_id))

# ---------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------
def list_runs(
    s: Session,
    job_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
) -> List[models.Run]:
    stmt = select(models.Run).order_by(models.Run.id.desc())
    if job_id is not None:
        stmt = stmt.where(models.Run.job_id == job_id)
    stmt = stmt.limit(limit).offset(offset)
    return list(s.execute(stmt).scalars())


def get_run(s: Session, run_id: int) -> Optional[models.Run]:
    return s.get(models.Run, run_id)


def create_run(s: Session, job_id: int, status: str = "queued") -> models.Run:
    run = models.Run(
        job_id=job_id,
        status=status,
        started_at=None,
        finished_at=None,
        stats_json=None,
    )
    s.add(run)
    s.flush()
    return run


def set_run_running(s: Session, run_id: int) -> None:
    run = get_run(s, run_id)
    if run:
        run.status = "running"
        run.started_at = datetime.utcnow()
        s.add(run)


def finish_run(s: Session, run_id: int, status: str, stats: Optional[Dict[str, Any]] = None) -> None:
    run = get_run(s, run_id)
    if run:
        run.status = status
        run.finished_at = datetime.utcnow()
        run.stats_json = json.dumps(stats or {}, ensure_ascii=False)
        s.add(run)


# ---------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------
def add_result(
    s: Session,
    run_id: int,
    selector_name: str,
    row_idx: int,
    value: str,
    url: Optional[str] = None,
) -> models.Result:
    r = models.Result(run_id=run_id)
    # 兼容不同字段名
    setattr(r, _RESULT_SELECTOR, selector_name)
    setattr(r, _RESULT_ROW, row_idx)
    setattr(r, _RESULT_VALUE, value)
    setattr(r, _RESULT_URL, url or "")
    s.add(r)
    s.flush()
    return r


def list_results_raw(s: Session, run_id: int) -> List[models.Result]:
    """
    返回 Result ORM 对象列表；调用方可自行序列化/导出。
    """
    stmt = (
        select(models.Result)
        .where(models.Result.run_id == run_id)
        .order_by(
            getattr(models.Result, _RESULT_SELECTOR).asc(),
            getattr(models.Result, _RESULT_ROW).asc(),
            models.Result.id.asc(),
        )
    )
    return list(s.execute(stmt).scalars())


def list_results_rows(s: Session, run_id: int) -> Dict[str, List[str]]:
    """
    返回聚合后的 {"selector_name": ["v1","v2",...], ...}
    自动兼容不同字段名。
    """
    stmt = (
        select(models.Result)
        .where(models.Result.run_id == run_id)
        .order_by(
            getattr(models.Result, _RESULT_SELECTOR).asc(),
            getattr(models.Result, _RESULT_ROW).asc(),
            models.Result.id.asc(),
        )
    )
    out: Dict[str, List[str]] = {}
    for r in s.execute(stmt).scalars():
        key = getattr(r, _RESULT_SELECTOR) or ""
        val = getattr(r, _RESULT_VALUE) or ""
        out.setdefault(key, []).append(val)
    return out
