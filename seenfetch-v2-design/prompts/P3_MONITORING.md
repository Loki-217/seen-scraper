# P3 - 数据变化监控开发提示词

## 功能概述

在定时任务基础上，增加数据变化检测和通知：
- 对比历史数据，检测新增/删除/修改
- 支持自定义监控字段
- 变化时触发通知

---

## Prompt 1: 变化检测模型

```
定义 SeenFetch 数据变化检测的数据模型。

要求：
1. 修改 services/api/app/models/schedule.py，添加监控配置

2. 定义监控配置：
class MonitorConfig(BaseModel):
    enabled: bool = False
    # 用于识别同一条记录的字段（如"电影名称"）
    identity_fields: List[str] = []
    # 需要监控变化的字段（如"价格", "评分"）
    watch_fields: List[str] = []
    # 变化类型
    detect_new: bool = True      # 检测新增
    detect_removed: bool = True  # 检测删除
    detect_changed: bool = True  # 检测修改

3. 定义变化记录：
class ChangeType(str, Enum):
    NEW = "new"           # 新增记录
    REMOVED = "removed"   # 删除记录
    CHANGED = "changed"   # 字段变化

class DataChange(BaseModel):
    change_type: ChangeType
    identity: Dict[str, str]  # 记录标识
    old_values: Optional[Dict[str, Any]]  # 变化前（REMOVED/CHANGED）
    new_values: Optional[Dict[str, Any]]  # 变化后（NEW/CHANGED）
    changed_fields: List[str]             # 变化的字段名（CHANGED）

class ChangeReport(BaseModel):
    run_id: str
    compared_with_run_id: str
    total_current: int
    total_previous: int
    new_count: int
    removed_count: int
    changed_count: int
    changes: List[DataChange]

4. 数据库表（存储历史快照）：

CREATE TABLE data_snapshots (
    id TEXT PRIMARY KEY,
    schedule_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    data_hash TEXT NOT NULL,        -- 整体数据hash
    item_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (schedule_id) REFERENCES schedules(id),
    FOREIGN KEY (run_id) REFERENCES scheduled_runs(id)
);

CREATE TABLE snapshot_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,
    identity_hash TEXT NOT NULL,    -- 标识字段的hash
    identity_json TEXT NOT NULL,    -- 标识字段JSON
    data_hash TEXT NOT NULL,        -- 监控字段的hash
    data_json TEXT NOT NULL,        -- 完整数据JSON
    FOREIGN KEY (snapshot_id) REFERENCES data_snapshots(id)
);

CREATE INDEX idx_snapshot_items_identity ON snapshot_items(snapshot_id, identity_hash);
```

---

## Prompt 2: 变化检测器

```
实现 SeenFetch 的数据变化检测逻辑。

要求：
1. 创建 services/api/app/services/change_detector.py

2. 实现 ChangeDetector 类：

class ChangeDetector:
    def __init__(self, config: MonitorConfig):
        self.config = config
    
    def detect_changes(
        self, 
        current_data: List[Dict], 
        previous_data: List[Dict]
    ) -> ChangeReport:
        """对比两次数据，返回变化报告"""
    
    def _build_identity(self, item: Dict) -> str:
        """根据 identity_fields 生成记录标识"""
        # 提取标识字段值，生成hash
    
    def _build_watch_hash(self, item: Dict) -> str:
        """根据 watch_fields 生成监控字段hash"""
    
    def _compare_items(
        self, 
        old_item: Dict, 
        new_item: Dict
    ) -> Optional[DataChange]:
        """对比两条记录，返回变化（如果有）"""

3. 检测算法：

def detect_changes(self, current_data, previous_data):
    # 1. 为每条记录生成身份标识
    current_map = {self._build_identity(item): item for item in current_data}
    previous_map = {self._build_identity(item): item for item in previous_data}
    
    changes = []
    
    # 2. 检测新增（在current但不在previous）
    if self.config.detect_new:
        for identity, item in current_map.items():
            if identity not in previous_map:
                changes.append(DataChange(
                    change_type=ChangeType.NEW,
                    identity=self._extract_identity_fields(item),
                    new_values=item
                ))
    
    # 3. 检测删除（在previous但不在current）
    if self.config.detect_removed:
        for identity, item in previous_map.items():
            if identity not in current_map:
                changes.append(DataChange(
                    change_type=ChangeType.REMOVED,
                    identity=self._extract_identity_fields(item),
                    old_values=item
                ))
    
    # 4. 检测修改（都存在但watch_fields有变化）
    if self.config.detect_changed:
        for identity in current_map.keys() & previous_map.keys():
            change = self._compare_items(previous_map[identity], current_map[identity])
            if change:
                changes.append(change)
    
    return ChangeReport(...)

4. 性能优化：
   - 使用 hash 快速判断是否有变化
   - 大数据集分批处理
   - 只在 hash 变化时才详细对比
```

---

## Prompt 3: 快照存储服务

```
实现 SeenFetch 的数据快照存储和检索。

要求：
1. 创建 services/api/app/services/snapshot_service.py

2. 实现 SnapshotService 类：

class SnapshotService:
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def save_snapshot(
        self, 
        schedule_id: str, 
        run_id: str, 
        data: List[Dict],
        config: MonitorConfig
    ) -> str:
        """保存数据快照，返回 snapshot_id"""
        # 1. 计算整体 data_hash
        # 2. 创建 data_snapshots 记录
        # 3. 为每条数据创建 snapshot_items 记录
    
    async def get_latest_snapshot(
        self, 
        schedule_id: str
    ) -> Optional[DataSnapshot]:
        """获取最新的快照"""
    
    async def get_snapshot_data(
        self, 
        snapshot_id: str
    ) -> List[Dict]:
        """获取快照的完整数据"""
    
    async def cleanup_old_snapshots(
        self, 
        schedule_id: str, 
        keep_count: int = 10
    ):
        """清理旧快照，只保留最近N个"""

3. 整合到执行流程：

# 在 RobotExecutor 或 Scheduler 中
async def execute_with_monitoring(schedule, run):
    # 1. 执行 Robot，获取数据
    result = await executor.execute()
    
    # 2. 如果启用了监控
    if schedule.monitor_config and schedule.monitor_config.enabled:
        # 获取上次快照
        previous = await snapshot_service.get_latest_snapshot(schedule.id)
        
        if previous:
            # 检测变化
            detector = ChangeDetector(schedule.monitor_config)
            previous_data = await snapshot_service.get_snapshot_data(previous.id)
            changes = detector.detect_changes(result.items, previous_data)
            
            # 保存变化报告
            await save_change_report(run.id, changes)
            
            # 触发通知（如果有变化）
            if changes.changes:
                await notify_changes(schedule, changes)
        
        # 保存本次快照
        await snapshot_service.save_snapshot(
            schedule.id, run.id, result.items, schedule.monitor_config
        )
    
    return result

4. 存储优化：
   - 只存储 identity_fields + watch_fields，不存完整数据
   - 或者存储完整数据但用压缩
```

---

## Prompt 4: 监控 API 端点

```
为 SeenFetch 监控功能创建 API 端点。

要求：
1. 修改 services/api/app/routers/schedules.py

2. 新增端点：

PUT /schedules/{id}/monitor
- 配置监控选项
- 请求：
{
  "enabled": true,
  "identity_fields": ["电影名称"],
  "watch_fields": ["评分", "评价人数"],
  "detect_new": true,
  "detect_removed": true,
  "detect_changed": true
}

GET /schedules/{id}/monitor
- 获取监控配置

GET /schedules/{id}/changes
- 获取变化历史
- 支持分页
- 响应：变化报告列表

GET /runs/{run_id}/changes
- 获取单次执行的变化详情
- 响应：ChangeReport

GET /schedules/{id}/changes/summary
- 获取变化统计摘要
- 响应：
{
  "total_runs_with_changes": 15,
  "total_new": 42,
  "total_removed": 5,
  "total_changed": 128,
  "recent_changes": [...]  // 最近10条变化
}

3. 在 Robot 保存时提供监控配置建议：

POST /robots/{id}/suggest-monitor
- 根据字段类型建议监控配置
- 响应：
{
  "suggested_identity_fields": ["标题"],  // 通常是 TITLE 类型
  "suggested_watch_fields": ["价格", "评分"],  // 通常是 PRICE/RATING 类型
}
```

---

## Prompt 5: 前端监控配置UI

```
为 SeenFetch 前端添加监控配置界面。

要求：
1. 在调度配置对话框中添加监控选项卡

2. 监控配置 UI：

┌────────────────────────────────────────────────────────────┐
│ ⏰ 设置定时任务                                            │
├─────────┬─────────┬────────────────────────────────────────┤
│ 基本设置 │ 数据监控 │                                        │
├─────────┴─────────┴────────────────────────────────────────┤
│                                                            │
│ [✓] 启用数据变化监控                                       │
│                                                            │
│ 记录标识字段（用于识别同一条数据）：                        │
│ ┌──────────────────────────────────────────┐              │
│ │ [✓] 电影名称                             │              │
│ │ [ ] 封面图片                             │              │
│ │ [ ] 评分                                 │              │
│ │ [ ] 简介                                 │              │
│ └──────────────────────────────────────────┘              │
│                                                            │
│ 监控变化的字段：                                           │
│ ┌──────────────────────────────────────────┐              │
│ │ [ ] 电影名称                             │              │
│ │ [ ] 封面图片                             │              │
│ │ [✓] 评分                                 │              │
│ │ [✓] 简介                                 │              │
│ └──────────────────────────────────────────┘              │
│                                                            │
│ 检测类型：                                                 │
│ [✓] 新增数据  [✓] 删除数据  [✓] 数据变化                  │
│                                                            │
└────────────────────────────────────────────────────────────┘

3. 变化报告展示：

┌────────────────────────────────────────────────────────────┐
│ 📊 数据变化报告 - 2024-01-15 08:00                         │
├────────────────────────────────────────────────────────────┤
│ 对比: 2024-01-14 08:00 → 2024-01-15 08:00                 │
│ 总记录: 75 → 76 (+1)                                      │
├────────────────────────────────────────────────────────────┤
│ ➕ 新增 (1)                                                │
│ ┌────────────────────────────────────────────────────────┐│
│ │ 电影名称: 奥本海默                                      ││
│ │ 评分: 8.9  评价人数: 123456                            ││
│ └────────────────────────────────────────────────────────┘│
│                                                            │
│ 📝 变化 (3)                                                │
│ ┌────────────────────────────────────────────────────────┐│
│ │ 电影名称: 肖申克的救赎                                  ││
│ │ 评分: 9.6 → 9.7 (+0.1)                                 ││
│ │ 评价人数: 2345678 → 2350000 (+4322)                    ││
│ └────────────────────────────────────────────────────────┘│
│ ┌────────────────────────────────────────────────────────┐│
│ │ 电影名称: 霸王别姬                                      ││
│ │ 评分: 9.5 → 9.6 (+0.1)                                 ││
│ └────────────────────────────────────────────────────────┘│
│                                                            │
│ ➖ 删除 (0)                                                │
│ 无                                                         │
└────────────────────────────────────────────────────────────┘

4. 变化趋势图表（可选）：
   - 使用 Chart.js 或简单的 CSS 柱状图
   - 显示最近7次执行的新增/删除/变化数量

5. 交互功能：
   - 点击变化记录展开详情
   - 下载变化报告 (CSV)
   - 筛选变化类型
```

---

## Prompt 6: 变化通知

```
为 SeenFetch 添加数据变化通知。

要求：
1. 扩展 services/api/app/notifier.py

2. 变化通知配置：
class ChangeNotificationConfig(BaseModel):
    notify_on_new: bool = True
    notify_on_removed: bool = True
    notify_on_changed: bool = True
    min_changes_threshold: int = 1  # 至少N条变化才通知
    channels: List[str]  # ["browser", "email"]

3. 通知内容模板：

【浏览器/站内通知】
标题: "📊 豆瓣Top250 数据变化"
内容: "检测到 1 条新增, 3 条变化。点击查看详情。"

【邮件通知】
主题: [SeenFetch] 豆瓣Top250 数据变化报告
正文:
---
您的定时任务"豆瓣Top250每日更新"检测到数据变化：

执行时间: 2024-01-15 08:00
对比时间: 2024-01-14 08:00

变化摘要:
- 新增: 1 条
- 变化: 3 条
- 删除: 0 条

新增数据:
1. 奥本海默 (评分: 8.9)

主要变化:
1. 肖申克的救赎: 评分 9.6 → 9.7
2. 霸王别姬: 评分 9.5 → 9.6
...

查看完整报告: https://seenfetch.com/runs/xxx

---
SeenFetch - 可视化网页数据提取
---

4. 实现通知触发：

async def notify_changes(schedule, change_report, config):
    if not should_notify(change_report, config):
        return
    
    message = build_notification_message(schedule, change_report)
    
    for channel in config.channels:
        if channel == "browser":
            await send_browser_notification(schedule.user_id, message)
        elif channel == "email":
            await send_email_notification(schedule.user_email, message)

5. 浏览器通知实现（简化版）：
   - 存储通知到数据库
   - 前端轮询获取未读通知
   - 显示通知气泡
```

---

## 开发顺序建议

1. **Prompt 1**: 数据模型
2. **Prompt 2**: 变化检测器
3. **Prompt 3**: 快照存储
4. **Prompt 4**: API 端点
5. **Prompt 5**: 前端 UI
6. **Prompt 6**: 通知

P3 依赖 P2（定时任务）完成后才能开发。
