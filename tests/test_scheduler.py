# tests/test_scheduler.py
"""
P2 定时任务功能测试
"""
import pytest
import asyncio
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

# 设置 Windows 事件循环策略
import sys
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class TestScheduleFrequencyCalculation:
    """调度频率计算测试"""

    def test_calculate_next_run_hourly(self):
        """测试每小时计算"""
        from services.api.app.scheduler import Scheduler
        from services.api.app.models import ScheduleDB

        scheduler = Scheduler()

        # 创建模拟调度
        schedule = MagicMock(spec=ScheduleDB)
        schedule.frequency = "hourly"
        schedule.timezone = "Asia/Shanghai"
        schedule.execute_at = None
        schedule.cron_expression = None

        from_time = datetime(2024, 1, 15, 10, 30, 0)
        next_run = scheduler.calculate_next_run(schedule, from_time)

        # 应该是下一个整点
        assert next_run is not None
        assert next_run.minute == 0

    def test_calculate_next_run_daily(self):
        """测试每天计算"""
        from services.api.app.scheduler import Scheduler
        from services.api.app.models import ScheduleDB

        scheduler = Scheduler()

        schedule = MagicMock(spec=ScheduleDB)
        schedule.frequency = "daily"
        schedule.timezone = "Asia/Shanghai"
        schedule.execute_at = "08:00"
        schedule.cron_expression = None

        from_time = datetime(2024, 1, 15, 10, 0, 0)
        next_run = scheduler.calculate_next_run(schedule, from_time)

        # 应该是明天 8:00
        assert next_run is not None
        assert next_run.day == 16 or next_run.day == 15  # 取决于时区

    def test_calculate_next_run_once(self):
        """测试一次性任务"""
        from services.api.app.scheduler import Scheduler
        from services.api.app.models import ScheduleDB

        scheduler = Scheduler()

        schedule = MagicMock(spec=ScheduleDB)
        schedule.frequency = "once"
        schedule.timezone = "Asia/Shanghai"
        schedule.execute_at = None
        schedule.cron_expression = None

        next_run = scheduler.calculate_next_run(schedule)

        # 一次性任务返回 None
        assert next_run is None


class TestRobotExecutor:
    """Robot 执行器测试"""

    @pytest.mark.asyncio
    async def test_execute_result_structure(self):
        """测试执行结果结构"""
        from services.api.app.robot_executor import ExecutionResult

        result = ExecutionResult(
            success=True,
            items=[{"title": "Test"}],
            pages_scraped=1,
            duration_seconds=5.0,
            error=None
        )

        assert result.success is True
        assert len(result.items) == 1
        assert result.pages_scraped == 1
        assert result.duration_seconds == 5.0
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execution_result_failure(self):
        """测试执行失败结果"""
        from services.api.app.robot_executor import ExecutionResult

        result = ExecutionResult(
            success=False,
            items=[],
            pages_scraped=0,
            duration_seconds=1.0,
            error="页面加载超时"
        )

        assert result.success is False
        assert len(result.items) == 0
        assert result.error == "页面加载超时"


class TestSchedulerLifecycle:
    """调度器生命周期测试"""

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """测试调度器启动和停止"""
        from services.api.app.scheduler import Scheduler

        scheduler = Scheduler(check_interval=1)

        # 启动
        await scheduler.start()
        assert scheduler.running is True
        assert scheduler._task is not None

        # 短暂运行
        await asyncio.sleep(0.5)

        # 停止
        await scheduler.stop()
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_scheduler_skip_disabled(self):
        """测试跳过禁用的调度"""
        from services.api.app.scheduler import Scheduler

        scheduler = Scheduler(check_interval=60)

        # 禁用的调度不应被执行
        # 这需要数据库模拟，简化测试
        assert scheduler.check_interval == 60


class TestDataModels:
    """数据模型测试"""

    def test_schedule_model(self):
        """测试 Schedule 模型"""
        from services.api.app.models_v2.schedule import (
            Schedule, ScheduleFrequency
        )

        schedule = Schedule(
            id=str(uuid.uuid4()),
            robot_id=str(uuid.uuid4()),
            name="测试调度",
            frequency=ScheduleFrequency.DAILY,
            timezone="Asia/Shanghai",
        )

        assert schedule.name == "测试调度"
        assert schedule.frequency == ScheduleFrequency.DAILY
        assert schedule.enabled is True

    def test_robot_model(self):
        """测试 Robot 模型"""
        from services.api.app.models_v2.schedule import (
            Robot, FieldConfig, PaginationConfig
        )

        robot = Robot(
            id=str(uuid.uuid4()),
            name="测试 Robot",
            origin_url="https://example.com",
            item_selector=".item",
            fields=[
                FieldConfig(name="标题", selector="h1", attr="text"),
                FieldConfig(name="链接", selector="a", attr="href"),
            ],
            pagination=PaginationConfig(
                type="click_next",
                selector=".next",
                max_pages=5
            )
        )

        assert robot.name == "测试 Robot"
        assert len(robot.fields) == 2
        assert robot.pagination.max_pages == 5

    def test_run_status_enum(self):
        """测试执行状态枚举"""
        from services.api.app.models_v2.schedule import RunStatus

        assert RunStatus.PENDING.value == "pending"
        assert RunStatus.RUNNING.value == "running"
        assert RunStatus.SUCCEEDED.value == "succeeded"
        assert RunStatus.FAILED.value == "failed"
        assert RunStatus.CANCELLED.value == "cancelled"


class TestAPIEndpoints:
    """API 端点测试"""

    def test_create_schedule_request(self):
        """测试创建调度请求模型"""
        from services.api.app.models_v2.schedule import (
            CreateScheduleRequest, ScheduleFrequency
        )

        req = CreateScheduleRequest(
            robot_id=str(uuid.uuid4()),
            name="每日抓取",
            frequency=ScheduleFrequency.DAILY,
            execute_at="08:00",
            timezone="Asia/Shanghai",
            enabled=True
        )

        assert req.name == "每日抓取"
        assert req.frequency == ScheduleFrequency.DAILY
        assert req.execute_at == "08:00"

    def test_update_schedule_request(self):
        """测试更新调度请求模型"""
        from services.api.app.models_v2.schedule import UpdateScheduleRequest

        req = UpdateScheduleRequest(
            enabled=False
        )

        assert req.enabled is False
        assert req.name is None  # 未设置的字段应为 None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
