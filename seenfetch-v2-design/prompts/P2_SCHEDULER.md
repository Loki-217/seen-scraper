# P2 - 定时任务开发提示词

## 功能概述

实现 Robot 的定时执行能力：
- 支持多种调度频率（每小时/每天/每周/自定义）
- 后台自动执行，无需用户在线
- 执行记录和结果存储
- 失败重试和通知

---

## Prompt 1: 调度数据模型

```
定义 SeenFetch 定时任务相关的数据模型。

要求：
1. 创建 services/api/app/models/schedule.py

2. 定义调度频率枚举：
class ScheduleFrequency(str, Enum):
    ONCE = "once"           # 一次性执行
    EVERY_15_MIN = "15min"  # 每15分钟
    HOURLY = "hourly"       # 每小时
    DAILY = "daily"         # 每天
    WEEKLY = "weekly"       # 每周
    MONTHLY = "monthly"     # 每月
    CUSTOM = "custom"       # 自定义cron表达式

3. 定义 Schedule 模型：
class Schedule(BaseModel):
    id: str                              # UUID
    robot_id: str                        # 关联的 Robot
    name: str                            # 调度名称
    frequency: ScheduleFrequency
    cron_expression: Optional[str]       # 仅 CUSTOM 时使用
    timezone: str = "Asia/Shanghai"      # 时区
    next_run_at: datetime                # 下次执行时间
    last_run_at: Optional[datetime]      # 上次执行时间
    enabled: bool = True                 # 是否启用
    retry_count: int = 3                 # 失败重试次数
    retry_delay_seconds: int = 60        # 重试间隔
    created_at: datetime
    updated_at: datetime

4. 定义 ScheduledRun 模型（执行记录）：
class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ScheduledRun(BaseModel):
    id: str
    schedule_id: str
    robot_id: str
    status: RunStatus
    trigger_type: str                    # "scheduled" | "manual"
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    pages_scraped: int = 0
    items_extracted: int = 0
    result_file: Optional[str]           # 结果文件路径
    error_message: Optional[str]
    retry_attempt: int = 0

5. 数据库表 DDL（SQLite）：

CREATE TABLE schedules (
    id TEXT PRIMARY KEY,
    robot_id TEXT NOT NULL REFERENCES robots(id),
    name TEXT NOT NULL,
    frequency TEXT NOT NULL,
    cron_expression TEXT,
    timezone TEXT DEFAULT 'Asia/Shanghai',
    next_run_at TIMESTAMP NOT NULL,
    last_run_at TIMESTAMP,
    enabled INTEGER DEFAULT 1,
    retry_count INTEGER DEFAULT 3,
    retry_delay_seconds INTEGER DEFAULT 60,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE scheduled_runs (
    id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL REFERENCES schedules(id),
    robot_id TEXT NOT NULL,
    status TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds REAL,
    pages_scraped INTEGER DEFAULT 0,
    items_extracted INTEGER DEFAULT 0,
    result_file TEXT,
    error_message TEXT,
    retry_attempt INTEGER DEFAULT 0
);

CREATE INDEX idx_schedules_next_run ON schedules(next_run_at) WHERE enabled = 1;
CREATE INDEX idx_runs_schedule ON scheduled_runs(schedule_id, started_at DESC);

6. 在 services/api/app/db.py 中添加表创建
```

---

## Prompt 2: 调度器核心实现

```
实现 SeenFetch 的任务调度器。

要求：
1. 创建 services/api/app/scheduler.py

2. 实现 Scheduler 类：

class Scheduler:
    """任务调度器 - 管理定时任务的执行"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval  # 检查间隔（秒）
        self.running = False
        self._task = None
    
    async def start(self):
        """启动调度器"""
    
    async def stop(self):
        """停止调度器"""
    
    async def _scheduler_loop(self):
        """调度主循环"""
        while self.running:
            await self._check_and_execute()
            await asyncio.sleep(self.check_interval)
    
    async def _check_and_execute(self):
        """检查并执行到期的任务"""
        # 1. 查询所有 enabled=True 且 next_run_at <= now 的 schedule
        # 2. 对每个到期的 schedule，创建 ScheduledRun 并执行
        # 3. 更新 schedule.next_run_at
    
    async def execute_schedule(self, schedule: Schedule) -> ScheduledRun:
        """执行单个调度任务"""
        # 1. 创建 ScheduledRun 记录（状态 PENDING）
        # 2. 更新状态为 RUNNING
        # 3. 调用 RobotExecutor 执行 Robot
        # 4. 保存结果，更新状态
        # 5. 失败时根据 retry_count 决定是否重试
    
    def calculate_next_run(self, schedule: Schedule, from_time: datetime = None) -> datetime:
        """计算下次执行时间"""
        # ONCE: 不再执行，返回 None 或远未来时间
        # HOURLY: from_time + 1 hour
        # DAILY: from_time + 1 day，保持同一时刻
        # WEEKLY: from_time + 7 days
        # MONTHLY: 下个月同一天
        # CUSTOM: 使用 croniter 解析 cron_expression

3. 依赖：
   - pip install croniter  # cron表达式解析

4. 在 main.py 的 lifespan 中启动/停止调度器：

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    init_db()
    scheduler = Scheduler()
    asyncio.create_task(scheduler.start())
    app.state.scheduler = scheduler
    yield
    # shutdown
    await scheduler.stop()

5. 并发控制：
   - 同一 schedule 不能并发执行
   - 使用简单的内存锁或数据库状态控制
```

---

## Prompt 3: Robot 执行器

```
实现 SeenFetch 的 Robot 执行逻辑。

要求：
1. 创建 services/api/app/robot_executor.py

2. 实现 RobotExecutor 类：

class RobotExecutor:
    """Robot 执行器 - 负责执行 Robot 配置，抓取数据"""
    
    def __init__(self, robot: Robot):
        self.robot = robot
        self.browser = None
        self.page = None
        self.results = []
    
    async def execute(self) -> ExecutionResult:
        """执行 Robot，返回结果"""
        try:
            await self._init_browser()
            await self._navigate_to_origin()
            await self._replay_actions()
            await self._extract_data()
            if self.robot.pagination:
                await self._handle_pagination()
            return self._build_result()
        finally:
            await self._cleanup()
    
    async def _init_browser(self):
        """初始化浏览器"""
        # 使用 Playwright，配置反检测选项
    
    async def _navigate_to_origin(self):
        """导航到起始URL"""
        await self.page.goto(self.robot.origin_url)
        await self.page.wait_for_load_state('networkidle')
    
    async def _replay_actions(self):
        """重放录制的操作序列"""
        for action in self.robot.actions:
            await self._execute_action(action)
    
    async def _extract_data(self) -> List[Dict]:
        """根据字段配置提取数据"""
        # 遍历 robot.fields
        # 使用选择器提取数据
        # 返回结构化数据
    
    async def _handle_pagination(self):
        """处理翻页"""
        # 使用 PaginationExecutor
        # 循环提取直到停止条件
    
    async def _execute_action(self, action: Action):
        """执行单个操作"""
        # click, scroll, input, wait 等
    
    def _build_result(self) -> ExecutionResult:
        """构建执行结果"""

@dataclass
class ExecutionResult:
    success: bool
    items: List[Dict]
    pages_scraped: int
    duration_seconds: float
    error: Optional[str]

3. 反检测配置：
   - 使用真实 User-Agent
   - 禁用 webdriver 标识
   - 随机延迟
   - 参考现有 proxy.py 的反检测代码

4. 超时处理：
   - 页面加载超时：30秒
   - 单页提取超时：10秒
   - 总执行超时：10分钟

5. 结果存储：
   - 小数据：直接存数据库 JSON 字段
   - 大数据：存文件，数据库记录文件路径
```

---

## Prompt 4: 调度 API 端点

```
创建 SeenFetch 定时任务的 API 端点。

要求：
1. 创建 services/api/app/routers/schedules.py

2. 实现以下端点：

GET /schedules
- 列出所有调度任务
- 支持分页、筛选（robot_id, enabled）
- 响应包含下次执行时间、上次执行状态

POST /schedules
- 创建新调度
- 请求：
{
  "robot_id": "xxx",
  "name": "每日抓取豆瓣",
  "frequency": "daily",
  "cron_expression": null,  // 仅 custom 时需要
  "timezone": "Asia/Shanghai",
  "enabled": true
}
- 自动计算 next_run_at

GET /schedules/{id}
- 获取调度详情
- 包含最近10次执行记录

PUT /schedules/{id}
- 更新调度配置
- 支持启用/禁用

DELETE /schedules/{id}
- 删除调度（保留历史执行记录）

POST /schedules/{id}/run
- 立即执行一次（不影响定时计划）
- 返回 run_id

GET /schedules/{id}/runs
- 获取执行历史
- 支持分页、状态筛选

GET /runs/{run_id}
- 获取单次执行详情
- 包含结果数据或下载链接

POST /runs/{run_id}/cancel
- 取消正在执行的任务

3. 在 main.py 中注册路由

4. 错误处理：
- Robot 不存在：400
- cron 表达式无效：400
- 调度不存在：404
```

---

## Prompt 5: 前端调度配置UI

```
为 SeenFetch 前端添加定时任务配置界面。

要求：
1. 创建 services/web/js/schedule-manager.js

2. 调度配置对话框：

┌────────────────────────────────────────────┐
│ ⏰ 设置定时任务                        [×] │
├────────────────────────────────────────────┤
│                                            │
│ 任务名称：[豆瓣Top250每日更新        ]    │
│                                            │
│ 执行频率：                                 │
│   ○ 仅执行一次                             │
│   ○ 每15分钟                               │
│   ○ 每小时                                 │
│   ● 每天                                   │
│   ○ 每周                                   │
│   ○ 自定义 (Cron)                          │
│                                            │
│ 执行时间：[08:00]  时区：[Asia/Shanghai▼] │
│                                            │
│ 失败重试：[3] 次，间隔 [60] 秒            │
│                                            │
│ 下次执行：2024-01-15 08:00 (明天)         │
│                                            │
│        [取消]            [保存并启用]      │
└────────────────────────────────────────────┘

3. 调度列表页面：

┌────────────────────────────────────────────────────────────┐
│ 我的定时任务                                    [+ 新建] │
├────────────────────────────────────────────────────────────┤
│ ┌────────────────────────────────────────────────────────┐│
│ │ ✅ 豆瓣Top250每日更新                                  ││
│ │    Robot: 豆瓣电影Top250                               ││
│ │    频率: 每天 08:00                                    ││
│ │    下次: 2024-01-15 08:00  上次: 成功 (2024-01-14)    ││
│ │                        [立即执行] [编辑] [暂停] [删除]  ││
│ └────────────────────────────────────────────────────────┘│
│ ┌────────────────────────────────────────────────────────┐│
│ │ ⏸️ 竞品价格监控                                        ││
│ │    Robot: 京东商品价格                                 ││
│ │    频率: 每小时                                        ││
│ │    状态: 已暂停                                        ││
│ │                        [立即执行] [编辑] [启用] [删除]  ││
│ └────────────────────────────────────────────────────────┘│
└────────────────────────────────────────────────────────────┘

4. 执行历史弹窗：

┌────────────────────────────────────────────────────────────┐
│ 执行历史 - 豆瓣Top250每日更新                              │
├────────────────────────────────────────────────────────────┤
│ 2024-01-14 08:00  ✅ 成功  3页/75条  12秒    [查看] [下载] │
│ 2024-01-13 08:00  ✅ 成功  3页/75条  15秒    [查看] [下载] │
│ 2024-01-12 08:00  ❌ 失败  超时              [详情]        │
│ 2024-01-11 08:00  ✅ 成功  3页/75条  11秒    [查看] [下载] │
└────────────────────────────────────────────────────────────┘

5. 状态自动刷新：
   - WebSocket 或轮询（每30秒）
   - 正在执行的任务显示进度

6. 样式保持与现有设计一致
```

---

## Prompt 6: 执行通知（可选）

```
为 SeenFetch 添加任务执行通知功能。

要求：
1. 创建 services/api/app/notifier.py

2. 通知类型：
   - 执行成功
   - 执行失败
   - 数据变化（与上次对比）

3. 通知渠道（选择实现）：

a. 浏览器通知（Web Push）：
   - 需要用户授权
   - 使用 pywebpush
   - 前端注册 Service Worker

b. 邮件通知：
   - 使用 SMTP
   - 配置 EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASS

c. Webhook：
   - 用户配置 webhook URL
   - POST 执行结果 JSON

4. 通知配置模型：
class NotificationConfig(BaseModel):
    schedule_id: str
    on_success: bool = False
    on_failure: bool = True
    on_change: bool = False
    channels: List[str]  # ["browser", "email", "webhook"]
    email: Optional[str]
    webhook_url: Optional[str]

5. 数据变化检测：
   - 保存上次执行结果的 hash
   - 对比本次结果
   - 检测新增/删除/修改的记录

6. API 端点：
   POST /schedules/{id}/notification
   GET /schedules/{id}/notification
   DELETE /schedules/{id}/notification

7. 实现简化版（MVP）：
   - 仅实现浏览器内通知（不需要后端推送）
   - 用户打开页面时检查最新执行状态
   - 显示未读的执行结果通知
```

---

## Prompt 7: 集成测试

```
为 SeenFetch 定时任务功能编写测试。

要求：
1. 创建 tests/test_scheduler.py

2. 调度器测试：
- test_calculate_next_run_hourly: 每小时计算
- test_calculate_next_run_daily: 每天计算
- test_calculate_next_run_weekly: 每周计算
- test_calculate_next_run_cron: 自定义cron
- test_scheduler_executes_due_tasks: 到期任务被执行
- test_scheduler_skips_disabled: 禁用任务被跳过
- test_concurrent_execution_prevented: 同一任务不并发

3. Robot 执行器测试：
- test_execute_simple_robot: 执行简单Robot
- test_execute_with_pagination: 执行带翻页的Robot
- test_execution_timeout: 超时处理
- test_execution_retry: 失败重试

4. API 测试：
- test_create_schedule: 创建调度
- test_update_schedule: 更新调度
- test_manual_run: 手动触发执行
- test_get_run_history: 获取执行历史

5. 使用 pytest-asyncio
6. Mock 时间（使用 freezegun 或手动 mock）
7. Mock Playwright（不真正打开浏览器）

示例：
```python
@pytest.mark.asyncio
async def test_scheduler_executes_due_tasks():
    scheduler = Scheduler(check_interval=1)
    
    # 创建一个已到期的调度
    schedule = create_test_schedule(next_run_at=datetime.utcnow() - timedelta(minutes=1))
    
    # 启动调度器
    await scheduler.start()
    await asyncio.sleep(2)
    await scheduler.stop()
    
    # 验证任务被执行
    runs = get_runs_for_schedule(schedule.id)
    assert len(runs) == 1
    assert runs[0].status in [RunStatus.SUCCEEDED, RunStatus.FAILED]
```
```

---

## 开发顺序建议

1. **Prompt 1**: 数据模型和数据库表
2. **Prompt 3**: Robot 执行器（独立于调度，可单独测试）
3. **Prompt 2**: 调度器核心
4. **Prompt 4**: API 端点
5. **Prompt 5**: 前端 UI
6. **Prompt 7**: 测试
7. **Prompt 6**: 通知（可选）

先确保 Robot 能正确执行，再加入调度功能。
