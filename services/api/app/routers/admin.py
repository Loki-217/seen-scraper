# services/api/app/routers/admin.py
"""Admin-only endpoints: activity logs + dashboard stats."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, cast, Date

from ..auth import require_admin
from ..db import session_scope
from ..models import ActivityLogDB, UserDB, RobotDB, ScheduledRunDB

router = APIRouter(prefix="/admin", tags=["admin"])


# ============ GET /admin/activity-logs ============

@router.get("/activity-logs", summary="查询活动日志")
def list_activity_logs(
    user_id: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: UserDB = Depends(require_admin),
):
    with session_scope() as s:
        base = select(ActivityLogDB)
        if user_id:
            base = base.where(ActivityLogDB.user_id == user_id)
        if action:
            base = base.where(ActivityLogDB.action == action)
        if status:
            base = base.where(ActivityLogDB.status == status)

        total = s.scalar(select(func.count()).select_from(base.subquery()))

        stmt = (
            base.order_by(ActivityLogDB.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = s.execute(stmt).scalars().all()

        items = []
        for r in rows:
            items.append({
                "id": r.id,
                "user_id": r.user_id,
                "action": r.action,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "target_url": r.target_url,
                "status": r.status,
                "error_step": r.error_step,
                "error_message": r.error_message,
                "details": r.details,
                "ip_address": r.ip_address,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            })

        return {"total": total, "page": page, "page_size": page_size, "items": items}


# ============ GET /admin/stats ============

@router.get("/stats", summary="管理员统计面板")
def admin_stats(_admin: UserDB = Depends(require_admin)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today_start - timedelta(days=6)

    with session_scope() as s:
        total_users = s.scalar(select(func.count()).select_from(UserDB)) or 0
        total_robots = s.scalar(select(func.count()).select_from(RobotDB)) or 0

        # Today's active users (distinct user_id with any log today)
        today_active = s.scalar(
            select(func.count(func.distinct(ActivityLogDB.user_id)))
            .where(ActivityLogDB.created_at >= today_start)
        ) or 0

        # Today's new robots
        today_robots = s.scalar(
            select(func.count()).select_from(
                select(ActivityLogDB.id)
                .where(and_(
                    ActivityLogDB.action == "robot_create",
                    ActivityLogDB.created_at >= today_start,
                )).subquery()
            )
        ) or 0

        # Execution stats (robot_run_success + robot_run_failed + schedule_run_success + schedule_run_failed)
        run_actions = [
            "robot_run_success", "robot_run_failed",
            "schedule_run_success", "schedule_run_failed",
        ]
        total_runs = s.scalar(
            select(func.count()).select_from(
                select(ActivityLogDB.id)
                .where(ActivityLogDB.action.in_(run_actions))
                .subquery()
            )
        ) or 0

        success_actions = ["robot_run_success", "schedule_run_success"]
        total_success = s.scalar(
            select(func.count()).select_from(
                select(ActivityLogDB.id)
                .where(ActivityLogDB.action.in_(success_actions))
                .subquery()
            )
        ) or 0

        success_rate = round(total_success / total_runs * 100, 1) if total_runs else 0

        # Last 7 days daily run counts
        daily_runs = []
        for i in range(6, -1, -1):
            day_start = today_start - timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            count = s.scalar(
                select(func.count()).select_from(
                    select(ActivityLogDB.id)
                    .where(and_(
                        ActivityLogDB.action.in_(run_actions),
                        ActivityLogDB.created_at >= day_start,
                        ActivityLogDB.created_at < day_end,
                    )).subquery()
                )
            ) or 0
            daily_runs.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "count": count,
            })

        return {
            "total_users": total_users,
            "today_active_users": today_active,
            "total_robots": total_robots,
            "today_new_robots": today_robots,
            "total_runs": total_runs,
            "total_success": total_success,
            "success_rate": success_rate,
            "daily_runs": daily_runs,
        }
