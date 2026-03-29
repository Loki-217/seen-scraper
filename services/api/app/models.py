# services/api/app/models.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Boolean, Float
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


# -------------------- Robot (V2) --------------------
class RobotDB(Base):
    """Robot 配置表 (V2)"""
    __tablename__ = "robots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    origin_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # JSON 存储复杂配置
    actions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    item_selector: Mapped[str] = mapped_column(String(500), nullable=False)
    fields_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pagination_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 归属
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    # 元信息
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # === Future: Monitor fields ===
    # monitor_enabled: bool
    # monitor_frequency: str (cron expression)
    # monitor_diff_mode: str ('visual' | 'content' | 'data')
    # last_monitor_at: datetime
    # === End Future ===

    # 关联
    schedules: Mapped[List["ScheduleDB"]] = relationship(
        back_populates="robot", cascade="all, delete-orphan"
    )


# -------------------- Schedule (V2) --------------------
class ScheduleDB(Base):
    """定时任务配置表"""
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    robot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("robots.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Shanghai", nullable=False)
    execute_at: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # HH:MM

    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    retry_count: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_delay_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # 归属
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 关联
    robot: Mapped["RobotDB"] = relationship(back_populates="schedules")
    runs: Mapped[List["ScheduledRunDB"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )


# -------------------- User (Auth) --------------------
class UserDB(Base):
    """用户表"""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


# -------------------- InviteCode (Auth) --------------------
class InviteCodeDB(Base):
    """邀请码表"""
    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    used_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# -------------------- ScheduledRun (V2) --------------------
class ScheduledRunDB(Base):
    """调度执行记录表"""
    __tablename__ = "scheduled_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("schedules.id"), index=True, nullable=False
    )
    robot_id: Mapped[str] = mapped_column(String(36), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    pages_scraped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_extracted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_file: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 归属
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    # 关联
    schedule: Mapped["ScheduleDB"] = relationship(back_populates="runs")


# -------------------- ActivityLog --------------------
class ActivityLogDB(Base):
    """用户行为日志表"""
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    target_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    error_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
