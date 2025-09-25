from __future__ import annotations
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    start_url: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text, default=None)

    status: Mapped[str] = mapped_column(String, default="draft")  # draft/active/paused/disabled
    pager_selector: Mapped[Optional[str]] = mapped_column(String, default=None)
    pager_attr: Mapped[str] = mapped_column(String, default="href")
    max_pages: Mapped[int] = mapped_column(Integer, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    selectors: Mapped[List["Selector"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Selector.order_no"
    )
    runs: Mapped[List["Run"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Run.id.desc()"
    )


class Selector(Base):
    __tablename__ = "selectors"
    __table_args__ = (UniqueConstraint("job_id", "name", name="uix_job_selector_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String)
    css: Mapped[str] = mapped_column(Text)
    attr: Mapped[str] = mapped_column(String, default="text")
    limit: Mapped[int] = mapped_column(Integer, default=50)
    required: Mapped[int] = mapped_column(Integer, default=0)  # 0/1
    regex: Mapped[Optional[str]] = mapped_column(String, default=None)
    order_no: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job: Mapped["Job"] = relationship(back_populates="selectors")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)

    status: Mapped[str] = mapped_column(String, default="queued")  # queued/running/succeeded/failed/cancelled
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)
    error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    settings_json: Mapped[Optional[str]] = mapped_column(Text, default=None)
    stats_json: Mapped[Optional[str]] = mapped_column(Text, default=None)

    job: Mapped["Job"] = relationship(back_populates="runs")
    results: Mapped[List["Result"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="Result.row_idx.asc()"
    )


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)

    field: Mapped[str] = mapped_column(String, index=True)  # 与 Selector.name 对应
    row_idx: Mapped[int] = mapped_column(Integer, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text, default=None)
    url: Mapped[Optional[str]] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    run: Mapped["Run"] = relationship(back_populates="results")
