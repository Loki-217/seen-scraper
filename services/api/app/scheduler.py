# services/api/app/scheduler.py
"""
任务调度器 - 管理定时任务的执行
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Set
from zoneinfo import ZoneInfo

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from .db import session_scope
from .models import RobotDB, ScheduleDB, ScheduledRunDB
from .models_v2.schedule import (
    ScheduleFrequency,
    RunStatus,
    Robot,
    Action,
    FieldConfig,
    PaginationConfig,
)
from .robot_executor import RobotExecutor, save_results_to_file


def get_local_now(timezone: str = "Asia/Shanghai") -> datetime:
    """获取本地时间（不带时区信息）"""
    try:
        tz = ZoneInfo(timezone)
    except:
        tz = ZoneInfo("Asia/Shanghai")
    return datetime.now(tz).replace(tzinfo=None)


class Scheduler:
    """任务调度器 - 管理定时任务的执行"""

    def __init__(self, check_interval: int = 60):
        """
        初始化调度器

        Args:
            check_interval: 检查间隔（秒），默认60秒
        """
        self.check_interval = check_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._running_schedules: Set[str] = set()  # 正在执行的调度ID（防止并发）

    async def start(self):
        """启动调度器"""
        if self.running:
            return

        self.running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        print(f"[Scheduler] 调度器已启动 (检查间隔: {self.check_interval}秒)")

    async def stop(self):
        """停止调度器"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[Scheduler] 调度器已停止")

    async def _scheduler_loop(self):
        """调度主循环"""
        while self.running:
            try:
                await self._check_and_execute()
            except Exception as e:
                print(f"[Scheduler] 循环错误: {e}")

            await asyncio.sleep(self.check_interval)

    async def _check_and_execute(self):
        """检查并执行到期的任务"""
        now = get_local_now()

        with session_scope() as s:
            # 查询所有到期的调度
            stmt = select(ScheduleDB).where(
                and_(
                    ScheduleDB.enabled == True,
                    ScheduleDB.next_run_at <= now
                )
            )
            due_schedules = s.execute(stmt).scalars().all()

            for schedule_db in due_schedules:
                # 跳过正在执行的
                if schedule_db.id in self._running_schedules:
                    continue

                # 标记为正在执行
                self._running_schedules.add(schedule_db.id)

                # 异步执行（不阻塞循环）
                asyncio.create_task(
                    self._execute_schedule_safe(schedule_db.id)
                )

    async def _execute_schedule_safe(self, schedule_id: str):
        """安全执行调度（捕获异常）"""
        try:
            await self.execute_schedule_by_id(schedule_id, trigger_type="scheduled")
        except Exception as e:
            print(f"[Scheduler] 执行调度 {schedule_id} 失败: {e}")
        finally:
            self._running_schedules.discard(schedule_id)

    async def execute_schedule_by_id(
        self,
        schedule_id: str,
        trigger_type: str = "manual"
    ) -> Optional[str]:
        """
        执行指定的调度任务

        Args:
            schedule_id: 调度ID
            trigger_type: 触发类型 "scheduled" | "manual"

        Returns:
            执行记录ID
        """
        with session_scope() as s:
            # 获取调度和 Robot
            schedule_db = s.get(ScheduleDB, schedule_id)
            if not schedule_db:
                print(f"[Scheduler] 调度不存在: {schedule_id}")
                return None

            robot_db = s.get(RobotDB, schedule_db.robot_id)
            if not robot_db:
                print(f"[Scheduler] Robot 不存在: {schedule_db.robot_id}")
                return None

            # 创建执行记录
            run_id = str(uuid.uuid4())
            run_db = ScheduledRunDB(
                id=run_id,
                schedule_id=schedule_id,
                robot_id=schedule_db.robot_id,
                status=RunStatus.PENDING.value,
                trigger_type=trigger_type,
            )
            s.add(run_db)
            s.commit()

            # 转换为 Robot 模型
            robot = self._db_to_robot(robot_db)

        # 读取 retry 配置
        with session_scope() as s:
            sched = s.get(ScheduleDB, schedule_id)
            max_retries = sched.retry_count if sched else 0
            retry_delay = sched.retry_delay_seconds if sched else 60

        # 执行 Robot（在数据库会话外执行）
        run_result = await self._execute_robot(
            run_id, robot,
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

        # 更新执行记录和调度
        with session_scope() as s:
            run_db = s.get(ScheduledRunDB, run_id)
            if run_db:
                run_db.status = run_result['status']
                run_db.started_at = run_result['started_at']
                run_db.completed_at = run_result['completed_at']
                run_db.duration_seconds = run_result['duration_seconds']
                run_db.pages_scraped = run_result['pages_scraped']
                run_db.items_extracted = run_result['items_extracted']
                run_db.result_file = run_result.get('result_file')
                run_db.error_message = run_result.get('error_message')

            # 更新调度
            schedule_db = s.get(ScheduleDB, schedule_id)
            if schedule_db:
                schedule_db.last_run_at = get_local_now()
                # 一次性任务执行后禁用
                if schedule_db.frequency == ScheduleFrequency.ONCE.value:
                    schedule_db.enabled = False
                else:
                    # 计算下次执行时间
                    next_run = self.calculate_next_run(schedule_db)
                    schedule_db.next_run_at = next_run

            # 更新 Robot 统计
            robot_db = s.get(RobotDB, robot.id)
            if robot_db:
                robot_db.last_run_at = get_local_now()
                robot_db.run_count += 1

            s.commit()

        return run_id

    async def _execute_robot(
        self,
        run_id: str,
        robot: Robot,
        max_retries: int = 0,
        retry_delay: int = 60,
    ) -> dict:
        """执行 Robot 并返回结果（支持重试）"""
        started_at = get_local_now()

        # 更新状态为 RUNNING
        with session_scope() as s:
            run_db = s.get(ScheduledRunDB, run_id)
            if run_db:
                run_db.status = RunStatus.RUNNING.value
                run_db.started_at = started_at
                s.commit()

        last_error = None
        result = None

        for attempt in range(max_retries + 1):
            try:
                executor = RobotExecutor(robot)
                result = await executor.execute()

                if result.success:
                    break  # 成功，退出重试

                # 执行返回但标记失败
                last_error = result.error
                if attempt < max_retries:
                    print(f"[Scheduler] 执行失败 (attempt {attempt + 1}/{max_retries + 1}): {last_error}, {retry_delay}s 后重试...")
                    with session_scope() as s:
                        run_db = s.get(ScheduledRunDB, run_id)
                        if run_db:
                            run_db.retry_attempt = attempt + 1
                            s.commit()
                    await asyncio.sleep(retry_delay)
                    continue

            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    print(f"[Scheduler] 执行异常 (attempt {attempt + 1}/{max_retries + 1}): {e}, {retry_delay}s 后重试...")
                    with session_scope() as s:
                        run_db = s.get(ScheduledRunDB, run_id)
                        if run_db:
                            run_db.retry_attempt = attempt + 1
                            s.commit()
                    await asyncio.sleep(retry_delay)
                    continue

        completed_at = get_local_now()

        # 保存结果到文件
        result_file = None
        if result and result.success and result.items:
            try:
                result_file = await save_results_to_file(
                    result.items,
                    robot.name,
                    robot_id=robot.id,
                )
            except Exception as e:
                print(f"[Scheduler] 保存结果失败: {e}")

        success = result.success if result else False
        return {
            'status': RunStatus.SUCCEEDED.value if success else RunStatus.FAILED.value,
            'started_at': started_at,
            'completed_at': completed_at,
            'duration_seconds': result.duration_seconds if result else 0,
            'pages_scraped': result.pages_scraped if result else 0,
            'items_extracted': len(result.items) if result else 0,
            'result_file': result_file,
            'error_message': last_error if not success else None,
        }

    def _db_to_robot(self, robot_db: RobotDB) -> Robot:
        """将数据库模型转换为 Robot 模型"""
        # 解析 JSON 字段
        actions = []
        if robot_db.actions_json:
            actions_data = json.loads(robot_db.actions_json)
            actions = [Action(**a) for a in actions_data]

        fields = []
        if robot_db.fields_json:
            fields_data = json.loads(robot_db.fields_json)
            fields = [FieldConfig(**f) for f in fields_data]

        pagination = None
        if robot_db.pagination_json:
            pagination_data = json.loads(robot_db.pagination_json)
            pagination = PaginationConfig(**pagination_data)

        return Robot(
            id=robot_db.id,
            name=robot_db.name,
            description=robot_db.description,
            origin_url=robot_db.origin_url,
            actions=actions,
            item_selector=robot_db.item_selector,
            fields=fields,
            pagination=pagination,
            created_at=robot_db.created_at,
            updated_at=robot_db.updated_at,
            last_run_at=robot_db.last_run_at,
            run_count=robot_db.run_count,
        )

    def calculate_next_run(
        self,
        schedule: ScheduleDB,
        from_time: Optional[datetime] = None
    ) -> Optional[datetime]:
        """
        计算下次执行时间

        Args:
            schedule: 调度配置
            from_time: 基准时间，默认为当前时间

        Returns:
            下次执行时间，ONCE 类型返回 None
        """
        if from_time is None:
            from_time = get_local_now()

        frequency = ScheduleFrequency(schedule.frequency)

        # from_time 已经是本地时间，直接使用
        local_time = from_time

        # 获取执行时间 (HH:MM)
        execute_hour = 8
        execute_minute = 0
        if schedule.execute_at:
            try:
                parts = schedule.execute_at.split(":")
                execute_hour = int(parts[0])
                execute_minute = int(parts[1]) if len(parts) > 1 else 0
            except:
                pass

        # 一次性任务：返回指定时间
        if frequency == ScheduleFrequency.ONCE:
            next_run = local_time.replace(
                hour=execute_hour,
                minute=execute_minute,
                second=0,
                microsecond=0
            )
            # 如果时间已过，设为明天
            if next_run <= local_time:
                next_run += timedelta(days=1)
            return next_run

        if frequency == ScheduleFrequency.EVERY_15_MIN:
            # 每15分钟
            next_run = local_time + timedelta(minutes=15)

        elif frequency == ScheduleFrequency.HOURLY:
            # 每小时（整点）
            next_run = local_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        elif frequency == ScheduleFrequency.DAILY:
            # 每天指定时间
            next_run = local_time.replace(
                hour=execute_hour,
                minute=execute_minute,
                second=0,
                microsecond=0
            )
            if next_run <= local_time:
                next_run += timedelta(days=1)

        elif frequency == ScheduleFrequency.WEEKLY:
            # 每周（同一天同一时间）
            next_run = local_time.replace(
                hour=execute_hour,
                minute=execute_minute,
                second=0,
                microsecond=0
            )
            if next_run <= local_time:
                next_run += timedelta(weeks=1)

        elif frequency == ScheduleFrequency.MONTHLY:
            # 每月同一天
            next_run = local_time.replace(
                hour=execute_hour,
                minute=execute_minute,
                second=0,
                microsecond=0
            )
            if next_run <= local_time:
                # 下个月
                if local_time.month == 12:
                    next_run = next_run.replace(year=local_time.year + 1, month=1)
                else:
                    next_run = next_run.replace(month=local_time.month + 1)

        elif frequency == ScheduleFrequency.CUSTOM:
            # 自定义 cron 表达式
            if schedule.cron_expression:
                try:
                    from croniter import croniter
                    cron = croniter(schedule.cron_expression, local_time)
                    next_run = cron.get_next(datetime)
                except ImportError:
                    print("[Scheduler] croniter 未安装，使用每天执行")
                    next_run = local_time + timedelta(days=1)
                except Exception as e:
                    print(f"[Scheduler] cron 表达式解析错误: {e}")
                    next_run = local_time + timedelta(days=1)
            else:
                next_run = local_time + timedelta(days=1)
        else:
            next_run = local_time + timedelta(days=1)

        # 返回本地时间（不带时区信息，便于前端显示）
        return next_run.replace(tzinfo=None)


# 全局调度器实例
scheduler = Scheduler()
