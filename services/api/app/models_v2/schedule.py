# services/api/app/models_v2/schedule.py
"""
定时任务相关数据模型
"""
from enum import Enum
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ScheduleFrequency(str, Enum):
    """调度频率"""
    ONCE = "once"           # 一次性执行
    EVERY_15_MIN = "15min"  # 每15分钟
    HOURLY = "hourly"       # 每小时
    DAILY = "daily"         # 每天
    WEEKLY = "weekly"       # 每周
    MONTHLY = "monthly"     # 每月
    CUSTOM = "custom"       # 自定义cron表达式


class RunStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Schedule(BaseModel):
    """调度任务配置"""
    id: str = Field(..., description="调度ID (UUID)")
    robot_id: str = Field(..., description="关联的 Robot ID")
    name: str = Field(..., description="调度名称")
    frequency: ScheduleFrequency = Field(..., description="执行频率")
    cron_expression: Optional[str] = Field(None, description="自定义cron表达式 (仅 CUSTOM 时使用)")
    timezone: str = Field("Asia/Shanghai", description="时区")
    execute_at: Optional[str] = Field(None, description="执行时间 (HH:MM 格式，用于 DAILY/WEEKLY)")
    next_run_at: Optional[datetime] = Field(None, description="下次执行时间")
    last_run_at: Optional[datetime] = Field(None, description="上次执行时间")
    enabled: bool = Field(True, description="是否启用")
    retry_count: int = Field(3, description="失败重试次数")
    retry_delay_seconds: int = Field(60, description="重试间隔(秒)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ScheduledRun(BaseModel):
    """调度执行记录"""
    id: str = Field(..., description="执行记录ID (UUID)")
    schedule_id: str = Field(..., description="调度ID")
    robot_id: str = Field(..., description="Robot ID")
    status: RunStatus = Field(RunStatus.PENDING, description="执行状态")
    trigger_type: str = Field("scheduled", description="触发类型: scheduled | manual")
    started_at: Optional[datetime] = Field(None, description="开始时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行耗时(秒)")
    pages_scraped: int = Field(0, description="抓取页数")
    items_extracted: int = Field(0, description="提取条目数")
    result_file: Optional[str] = Field(None, description="结果文件路径")
    error_message: Optional[str] = Field(None, description="错误信息")
    retry_attempt: int = Field(0, description="重试次数")

    class Config:
        from_attributes = True


# ============ Robot 模型 (V2) ============

class ActionType(str, Enum):
    """操作类型"""
    CLICK = "click"
    SCROLL = "scroll"
    INPUT = "input"
    WAIT = "wait"
    HOVER = "hover"
    SELECT = "select"


class Action(BaseModel):
    """录制的操作"""
    type: ActionType
    selector: Optional[str] = None
    value: Optional[str] = None  # input 的值
    x: Optional[int] = None      # 点击坐标
    y: Optional[int] = None
    delay_ms: int = Field(500, description="操作后延迟(毫秒)")


class FieldConfig(BaseModel):
    """字段提取配置"""
    name: str = Field(..., description="字段名")
    selector: str = Field(..., description="CSS选择器")
    attr: str = Field("text", description="提取属性: text | href | src | ...")
    required: bool = Field(False, description="是否必需")
    regex: Optional[str] = Field(None, description="正则提取")


class PaginationConfig(BaseModel):
    """翻页配置"""
    type: str = Field(..., description="翻页类型: click_next | scroll | url_pattern")
    selector: Optional[str] = Field(None, description="翻页按钮选择器")
    max_pages: int = Field(10, description="最大页数")
    max_rows: Optional[int] = Field(None, description="最大数据行数，None 表示不限制")
    wait_ms: int = Field(1000, description="翻页后等待时间")
    stop_selector: Optional[str] = Field(None, description="停止条件选择器")


class Robot(BaseModel):
    """Robot 配置 (V2 版本)

    Robot 是一个完整的抓取配置，包含：
    - 起始URL
    - 录制的操作序列
    - 字段提取规则
    - 翻页配置
    """
    id: str = Field(..., description="Robot ID (UUID)")
    name: str = Field(..., description="Robot 名称")
    description: str = Field("", description="描述")
    origin_url: str = Field(..., description="起始URL")

    # 操作序列
    actions: List[Action] = Field(default_factory=list, description="录制的操作序列")

    # 数据提取
    item_selector: str = Field(..., description="列表项选择器")
    fields: List[FieldConfig] = Field(default_factory=list, description="字段配置")

    # 翻页
    pagination: Optional[PaginationConfig] = Field(None, description="翻页配置")

    # 元信息
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_run_at: Optional[datetime] = Field(None, description="上次执行时间")
    run_count: int = Field(0, description="执行次数")

    class Config:
        from_attributes = True


# ============ API 请求/响应模型 ============

class CreateScheduleRequest(BaseModel):
    """创建调度请求"""
    robot_id: str
    name: str
    frequency: ScheduleFrequency
    cron_expression: Optional[str] = None
    timezone: str = "Asia/Shanghai"
    execute_at: Optional[str] = None  # HH:MM
    enabled: bool = True
    retry_count: int = 3
    retry_delay_seconds: int = 60


class UpdateScheduleRequest(BaseModel):
    """更新调度请求"""
    name: Optional[str] = None
    frequency: Optional[ScheduleFrequency] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    execute_at: Optional[str] = None
    enabled: Optional[bool] = None
    retry_count: Optional[int] = None
    retry_delay_seconds: Optional[int] = None


class ScheduleResponse(BaseModel):
    """调度响应"""
    id: str
    robot_id: str
    name: str
    frequency: ScheduleFrequency
    cron_expression: Optional[str]
    timezone: str
    execute_at: Optional[str]
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    enabled: bool
    retry_count: int
    retry_delay_seconds: int
    created_at: datetime
    updated_at: datetime
    # 额外信息
    robot_name: Optional[str] = None
    last_run_status: Optional[str] = None


class ScheduleListResponse(BaseModel):
    """调度列表响应"""
    total: int
    items: List[ScheduleResponse]


class RunResponse(BaseModel):
    """执行记录响应"""
    id: str
    schedule_id: str
    robot_id: str
    status: RunStatus
    trigger_type: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    pages_scraped: int
    items_extracted: int
    result_file: Optional[str]
    error_message: Optional[str]
    retry_attempt: int


class RunListResponse(BaseModel):
    """执行记录列表响应"""
    total: int
    items: List[RunResponse]
