from __future__ import annotations
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import schemas, crud, models
from ..db import get_session

router = APIRouter()


def _load_job_with_rels(s: Session, job_id: int) -> models.Job | None:
    """带 selectin 预加载的 Job 查询，防止懒加载问题。"""
    stmt = (
        select(models.Job)
        .options(
            selectinload(models.Job.selectors),
            selectinload(models.Job.runs),
        )
        .where(models.Job.id == job_id)
    )
    return s.execute(stmt).scalar_one_or_none()


def _to_job_out(job: models.Job) -> schemas.JobOut:
    """在会话关闭前将 ORM 转成 Pydantic。"""
    _ = list(job.selectors or [])
    _ = list(job.runs or [])
    return schemas.JobOut.model_validate(job, from_attributes=True)


# ---------- CRUD ----------
@router.post("", response_model=schemas.JobOut)
def create_job(
    payload: schemas.JobCreate,
    overwrite: bool = False,
    s: Session = Depends(get_session),
):
    try:
        job = crud.create_or_update_job(s, payload, overwrite=overwrite)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    job = _load_job_with_rels(s, job.id)
    if not job:
        raise HTTPException(status_code=500, detail="created job not found")
    return _to_job_out(job)


@router.get("", response_model=List[schemas.JobOut])
def list_jobs(limit: int = 50, offset: int = 0, s: Session = Depends(get_session)):
    stmt = (
        select(models.Job)
        .options(
            selectinload(models.Job.selectors),
            selectinload(models.Job.runs),
        )
        .offset(offset)
        .limit(limit)
    )
    jobs = s.execute(stmt).scalars().all()
    return [_to_job_out(j) for j in jobs]


@router.get("/{job_id}", response_model=schemas.JobOut)
def get_job(job_id: int, s: Session = Depends(get_session)):
    job = _load_job_with_rels(s, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return _to_job_out(job)


@router.delete("/{job_id}")
def delete_job(job_id: int, s: Session = Depends(get_session)):
    crud.delete_job(s, job_id)
    return {"ok": True}
