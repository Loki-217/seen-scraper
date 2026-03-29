# services/api/app/routers/schedules.py
"""
定时任务 API 路由

端点：
- GET    /schedules              列出所有调度
- POST   /schedules              创建调度
- GET    /schedules/{id}         获取调度详情
- PUT    /schedules/{id}         更新调度
- DELETE /schedules/{id}         删除调度
- POST   /schedules/{id}/run     立即执行一次
- GET    /schedules/{id}/runs    获取执行历史
- GET    /runs/{run_id}          获取执行详情
- POST   /runs/{run_id}/cancel   取消执行
"""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func

from ..activity_log import log_activity
from ..auth import get_current_user
from ..db import session_scope
from ..models import RobotDB, ScheduleDB, ScheduledRunDB, UserDB
from ..models_v2.schedule import (
    ScheduleFrequency,
    RunStatus,
    CreateScheduleRequest,
    UpdateScheduleRequest,
    ScheduleResponse,
    ScheduleListResponse,
    RunResponse,
    RunListResponse,
)
from ..scheduler import scheduler


router = APIRouter(prefix="/schedules", tags=["schedules"])
runs_router = APIRouter(prefix="/runs", tags=["runs"])


# ============ 辅助函数 ============

def db_to_schedule_response(schedule_db: ScheduleDB, robot_name: str = None, last_run_status: str = None) -> ScheduleResponse:
    """将数据库模型转换为响应"""
    return ScheduleResponse(
        id=schedule_db.id,
        robot_id=schedule_db.robot_id,
        name=schedule_db.name,
        frequency=ScheduleFrequency(schedule_db.frequency),
        cron_expression=schedule_db.cron_expression,
        timezone=schedule_db.timezone,
        execute_at=schedule_db.execute_at,
        next_run_at=schedule_db.next_run_at,
        last_run_at=schedule_db.last_run_at,
        enabled=schedule_db.enabled,
        retry_count=schedule_db.retry_count,
        retry_delay_seconds=schedule_db.retry_delay_seconds,
        created_at=schedule_db.created_at,
        updated_at=schedule_db.updated_at,
        robot_name=robot_name,
        last_run_status=last_run_status,
    )


def db_to_run_response(run_db: ScheduledRunDB) -> RunResponse:
    """将数据库模型转换为响应"""
    return RunResponse(
        id=run_db.id,
        schedule_id=run_db.schedule_id,
        robot_id=run_db.robot_id,
        status=RunStatus(run_db.status),
        trigger_type=run_db.trigger_type,
        started_at=run_db.started_at,
        completed_at=run_db.completed_at,
        duration_seconds=run_db.duration_seconds,
        pages_scraped=run_db.pages_scraped,
        items_extracted=run_db.items_extracted,
        result_file=run_db.result_file,
        error_message=run_db.error_message,
        retry_attempt=run_db.retry_attempt,
    )


# ============ 归属检查 ============

def _check_schedule_ownership(schedule_db: ScheduleDB, current_user: UserDB):
    if current_user.role == "admin":
        return
    if schedule_db.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"调度不存在: {schedule_db.id}")


# ============ Schedule API 端点 ============

@router.get("", response_model=ScheduleListResponse, summary="列出所有调度")
def list_schedules(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    robot_id: Optional[str] = Query(None, description="按 Robot 筛选"),
    enabled: Optional[bool] = Query(None, description="按启用状态筛选"),
    current_user: UserDB = Depends(get_current_user),
):
    """获取调度列表"""
    with session_scope() as s:
        # 构建查询条件
        conditions = []
        if current_user.role != "admin":
            conditions.append(ScheduleDB.user_id == current_user.id)
        if robot_id:
            conditions.append(ScheduleDB.robot_id == robot_id)
        if enabled is not None:
            conditions.append(ScheduleDB.enabled == enabled)

        # 统计总数
        total_stmt = select(func.count(ScheduleDB.id))
        if conditions:
            total_stmt = total_stmt.where(and_(*conditions))
        total = s.execute(total_stmt).scalar() or 0

        # 分页查询
        stmt = select(ScheduleDB).offset(offset).limit(limit).order_by(ScheduleDB.next_run_at.asc())
        if conditions:
            stmt = stmt.where(and_(*conditions))
        schedules = s.execute(stmt).scalars().all()

        # 获取关联信息
        items = []
        for schedule_db in schedules:
            robot_db = s.get(RobotDB, schedule_db.robot_id)
            robot_name = robot_db.name if robot_db else None

            # 获取最近一次执行状态
            last_run_stmt = (
                select(ScheduledRunDB)
                .where(ScheduledRunDB.schedule_id == schedule_db.id)
                .order_by(ScheduledRunDB.started_at.desc())
                .limit(1)
            )
            last_run = s.execute(last_run_stmt).scalar_one_or_none()
            last_run_status = last_run.status if last_run else None

            items.append(db_to_schedule_response(schedule_db, robot_name, last_run_status))

        return ScheduleListResponse(total=total, items=items)


@router.post("", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED, summary="创建调度")
def create_schedule(req: CreateScheduleRequest, current_user: UserDB = Depends(get_current_user)):
    """创建新的定时任务"""
    with session_scope() as s:
        # 检查 Robot 是否存在且属于当前用户
        robot_db = s.get(RobotDB, req.robot_id)
        if not robot_db:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Robot 不存在: {req.robot_id}")
        if current_user.role != "admin" and robot_db.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Robot 不存在: {req.robot_id}")

        # 验证 cron 表达式
        if req.frequency == ScheduleFrequency.CUSTOM:
            if not req.cron_expression:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="自定义频率必须提供 cron_expression"
                )
            # 验证 cron 语法
            try:
                from croniter import croniter
                croniter(req.cron_expression)
            except ImportError:
                pass  # croniter 未安装，跳过验证
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的 cron 表达式: {e}"
                )

        # 创建调度
        schedule_db = ScheduleDB(
            id=str(uuid.uuid4()),
            robot_id=req.robot_id,
            name=req.name,
            frequency=req.frequency.value,
            cron_expression=req.cron_expression,
            timezone=req.timezone,
            execute_at=req.execute_at,
            enabled=req.enabled,
            retry_count=req.retry_count,
            retry_delay_seconds=req.retry_delay_seconds,
            user_id=current_user.id,
        )

        # 计算下次执行时间
        schedule_db.next_run_at = scheduler.calculate_next_run(schedule_db)

        s.add(schedule_db)
        s.commit()
        s.refresh(schedule_db)

        log_activity(
            "schedule_create",
            user_id=current_user.id,
            target_type="schedule",
            target_id=schedule_db.id,
        )
        return db_to_schedule_response(schedule_db, robot_db.name)


@router.get("/{schedule_id}", response_model=ScheduleResponse, summary="获取调度详情")
def get_schedule(schedule_id: str, current_user: UserDB = Depends(get_current_user)):
    """获取调度详情（包含最近10次执行记录）"""
    with session_scope() as s:
        schedule_db = s.get(ScheduleDB, schedule_id)
        if not schedule_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"调度不存在: {schedule_id}")
        _check_schedule_ownership(schedule_db, current_user)

        robot_db = s.get(RobotDB, schedule_db.robot_id)
        robot_name = robot_db.name if robot_db else None

        # 获取最近执行状态
        last_run_stmt = (
            select(ScheduledRunDB)
            .where(ScheduledRunDB.schedule_id == schedule_id)
            .order_by(ScheduledRunDB.started_at.desc())
            .limit(1)
        )
        last_run = s.execute(last_run_stmt).scalar_one_or_none()
        last_run_status = last_run.status if last_run else None

        return db_to_schedule_response(schedule_db, robot_name, last_run_status)


@router.put("/{schedule_id}", response_model=ScheduleResponse, summary="更新调度")
def update_schedule(schedule_id: str, req: UpdateScheduleRequest, current_user: UserDB = Depends(get_current_user)):
    """更新调度配置"""
    with session_scope() as s:
        schedule_db = s.get(ScheduleDB, schedule_id)
        if not schedule_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"调度不存在: {schedule_id}")
        _check_schedule_ownership(schedule_db, current_user)

        # 更新字段
        if req.name is not None:
            schedule_db.name = req.name
        if req.frequency is not None:
            schedule_db.frequency = req.frequency.value
        if req.cron_expression is not None:
            schedule_db.cron_expression = req.cron_expression
        if req.timezone is not None:
            schedule_db.timezone = req.timezone
        if req.execute_at is not None:
            schedule_db.execute_at = req.execute_at
        if req.enabled is not None:
            schedule_db.enabled = req.enabled
        if req.retry_count is not None:
            schedule_db.retry_count = req.retry_count
        if req.retry_delay_seconds is not None:
            schedule_db.retry_delay_seconds = req.retry_delay_seconds

        # 重新计算下次执行时间
        schedule_db.next_run_at = scheduler.calculate_next_run(schedule_db)
        schedule_db.updated_at = datetime.utcnow()

        s.commit()
        s.refresh(schedule_db)

        robot_db = s.get(RobotDB, schedule_db.robot_id)
        robot_name = robot_db.name if robot_db else None

        log_activity(
            "schedule_update",
            user_id=current_user.id,
            target_type="schedule",
            target_id=schedule_id,
        )
        return db_to_schedule_response(schedule_db, robot_name)


@router.delete("/{schedule_id}", summary="删除调度")
def delete_schedule(schedule_id: str, current_user: UserDB = Depends(get_current_user)):
    """删除调度（保留历史执行记录）"""
    with session_scope() as s:
        schedule_db = s.get(ScheduleDB, schedule_id)
        if not schedule_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"调度不存在: {schedule_id}")
        _check_schedule_ownership(schedule_db, current_user)

        s.delete(schedule_db)
        s.commit()

        log_activity(
            "schedule_delete",
            user_id=current_user.id,
            target_type="schedule",
            target_id=schedule_id,
        )
        return {"ok": True, "message": f"调度 {schedule_id} 已删除"}


@router.post("/{schedule_id}/run", summary="立即执行一次")
async def run_schedule_now(schedule_id: str, current_user: UserDB = Depends(get_current_user)):
    """立即执行一次（不影响定时计划）"""
    with session_scope() as s:
        schedule_db = s.get(ScheduleDB, schedule_id)
        if not schedule_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"调度不存在: {schedule_id}")
        _check_schedule_ownership(schedule_db, current_user)

    run_id = await scheduler.execute_schedule_by_id(schedule_id, trigger_type="manual")

    if not run_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="执行失败"
        )

    return {"ok": True, "run_id": run_id, "message": "执行已开始"}


@router.get("/{schedule_id}/runs", response_model=RunListResponse, summary="获取执行历史")
def get_schedule_runs(
    schedule_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status", description="按状态筛选"),
    current_user: UserDB = Depends(get_current_user),
):
    """获取调度的执行历史"""
    with session_scope() as s:
        schedule_db = s.get(ScheduleDB, schedule_id)
        if not schedule_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"调度不存在: {schedule_id}")
        _check_schedule_ownership(schedule_db, current_user)

        # 构建查询
        conditions = [ScheduledRunDB.schedule_id == schedule_id]
        if status_filter:
            conditions.append(ScheduledRunDB.status == status_filter)

        # 统计总数
        total_stmt = select(func.count(ScheduledRunDB.id)).where(and_(*conditions))
        total = s.execute(total_stmt).scalar() or 0

        # 分页查询
        stmt = (
            select(ScheduledRunDB)
            .where(and_(*conditions))
            .order_by(ScheduledRunDB.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        runs = s.execute(stmt).scalars().all()

        return RunListResponse(
            total=total,
            items=[db_to_run_response(r) for r in runs]
        )


# ============ Run API 端点 ============

@runs_router.get("/{run_id}", response_model=RunResponse, summary="获取执行详情")
def get_run(run_id: str, current_user: UserDB = Depends(get_current_user)):
    """获取单次执行详情"""
    with session_scope() as s:
        run_db = s.get(ScheduledRunDB, run_id)
        if not run_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在: {run_id}")
        if current_user.role != "admin" and run_db.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在: {run_id}")
        return db_to_run_response(run_db)


@runs_router.post("/{run_id}/cancel", summary="取消执行")
def cancel_run(run_id: str, current_user: UserDB = Depends(get_current_user)):
    """取消正在执行的任务"""
    with session_scope() as s:
        run_db = s.get(ScheduledRunDB, run_id)
        if not run_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在: {run_id}")
        if current_user.role != "admin" and run_db.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在: {run_id}")

        if run_db.status not in [RunStatus.PENDING.value, RunStatus.RUNNING.value]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无法取消状态为 {run_db.status} 的任务"
            )

        run_db.status = RunStatus.CANCELLED.value
        run_db.completed_at = datetime.utcnow()
        s.commit()

        return {"ok": True, "message": f"执行 {run_id} 已取消"}


@runs_router.get("/{run_id}/result", summary="获取执行结果")
def get_run_result(run_id: str, current_user: UserDB = Depends(get_current_user)):
    """获取执行结果数据"""
    import json
    from pathlib import Path

    with session_scope() as s:
        run_db = s.get(ScheduledRunDB, run_id)
        if not run_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在: {run_id}")
        if current_user.role != "admin" and run_db.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在: {run_id}")

        if not run_db.result_file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="无结果文件")

        result_path = Path(run_db.result_file)
        if not result_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结果文件不存在")

        with open(result_path, 'r', encoding='utf-8') as f:
            return json.load(f)


@runs_router.get("/{run_id}/download", summary="下载执行结果文件")
def download_run_result(run_id: str, current_user: UserDB = Depends(get_current_user)):
    """直接下载执行结果 CSV 文件"""
    from pathlib import Path
    from fastapi.responses import FileResponse

    with session_scope() as s:
        run_db = s.get(ScheduledRunDB, run_id)
        if not run_db:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在: {run_id}")
        if current_user.role != "admin" and run_db.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"执行记录不存在: {run_id}")

        if not run_db.result_file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="无结果文件")

        result_path = Path(run_db.result_file)
        if not result_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="结果文件不存在")

        # 返回文件下载
        return FileResponse(
            path=str(result_path),
            filename=result_path.name,
            media_type='text/csv'
        )
