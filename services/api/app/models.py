# services/api/app/models.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""
    pass


# -------------------- Job --------------------
class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    start_url: Mapped[str] = mapped_column(String(500), nullable=False)

    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    pager_selector: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    pager_attr: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    max_pages: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 🔥 新增：爬虫配置（JSON 格式）
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # relationships
    selectors: Mapped[List["Selector"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    runs: Mapped[List["Run"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


# -------------------- Selector --------------------
class Selector(Base):
    __tablename__ = "selectors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    css: Mapped[str] = mapped_column(String(500), nullable=False)
    attr: Mapped[str] = mapped_column(String(50), default="text", nullable=False)
    limit: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    regex: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    order_no: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    job: Mapped[Job] = relationship(back_populates="selectors")


# -------------------- Run --------------------
class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="queued", nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 自由统计信息(JSON 字符串)
    stats_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="runs")
    results: Mapped[List["Result"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


# -------------------- Result --------------------
class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)

    # 注意：以下字段名和你的 CRUD 保持一致
    selector: Mapped[str] = mapped_column(String(100), nullable=False)
    row_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    run: Mapped[Run] = relationship(back_populates="results")
