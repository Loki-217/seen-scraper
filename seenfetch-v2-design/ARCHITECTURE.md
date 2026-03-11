# SeenFetch V2 架构设计文档

## 1. 核心架构变更

### 1.1 问题诊断

当前架构的致命问题：

```
【现状】
用户输入URL → 后端Playwright渲染 → 返回HTML → 前端iframe显示

问题：
- iframe里的HTML是"死页面"，JavaScript上下文在后端Playwright里
- 用户点击iframe里的元素 → 无响应 / 跳转失效
- 翻页、滚动加载、展开详情等交互全部失效
- CORS/CSP/X-Frame-Options导致部分网站无法显示
```

### 1.2 目标架构（参考Browse AI Robot Studio）

```
【V2架构】

┌─────────────────────────────────────────────────────────────┐
│                      用户浏览器（前端）                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Canvas/SVG 交互覆盖层                    │   │
│  │  - 显示后端返回的截图                                 │   │
│  │  - 渲染可点击区域高亮                                 │   │
│  │  - 捕获用户点击坐标 → 发送给后端                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              配置面板 & 字段管理                       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ WebSocket / HTTP
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI 后端                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Session Manager                         │   │
│  │  - 管理多个Playwright持久会话                         │   │
│  │  - Session ID → Browser Context 映射                 │   │
│  │  - 会话超时清理                                       │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Playwright Browser Pool                 │   │
│  │  - 持久化页面状态                                     │   │
│  │  - 执行真实点击/滚动/输入                             │   │
│  │  - 返回截图 + DOM快照 + 可交互元素坐标                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 核心改动点

| 组件 | 现状 | V2 |
|-----|------|-----|
| 页面显示 | iframe嵌入HTML | Canvas显示截图 |
| 用户交互 | 直接操作iframe（失效） | 点击覆盖层 → 坐标发后端 |
| Playwright | 每次请求新建 | 持久Session池 |
| 翻页支持 | ❌ 无 | ✅ 后端执行真实点击 |
| 状态保持 | ❌ 无 | ✅ Session维持页面状态 |

---

## 2. 模块设计

### 2.1 Session Manager（新增）

```python
# services/api/app/session_manager.py

class BrowserSession:
    """单个浏览器会话"""
    session_id: str
    browser_context: BrowserContext
    page: Page
    created_at: datetime
    last_active: datetime
    user_id: Optional[str]  # 未来支持多用户

class SessionManager:
    """会话池管理器"""
    
    sessions: Dict[str, BrowserSession]
    max_sessions: int = 10  # 单实例最大会话数
    session_timeout: int = 1800  # 30分钟超时
    
    async def create_session(self, url: str) -> str:
        """创建新会话，返回session_id"""
        
    async def get_session(self, session_id: str) -> BrowserSession:
        """获取现有会话"""
        
    async def execute_action(self, session_id: str, action: Action) -> ActionResult:
        """在指定会话中执行操作"""
        
    async def cleanup_expired(self):
        """清理过期会话"""
```

### 2.2 Action 类型定义

```python
# services/api/app/models/actions.py

class ActionType(Enum):
    CLICK = "click"
    SCROLL = "scroll"
    INPUT = "input"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"

class Action(BaseModel):
    type: ActionType
    # 点击操作
    x: Optional[int] = None
    y: Optional[int] = None
    selector: Optional[str] = None
    # 滚动操作
    direction: Optional[str] = None  # "up" | "down" | "left" | "right"
    distance: Optional[int] = None
    # 输入操作
    text: Optional[str] = None
    # 等待操作
    wait_ms: Optional[int] = None
    wait_selector: Optional[str] = None

class ActionResult(BaseModel):
    success: bool
    screenshot_base64: str
    url: str  # 当前URL（可能因点击跳转）
    elements: List[InteractiveElement]  # 可交互元素列表
    error: Optional[str] = None

class InteractiveElement(BaseModel):
    selector: str
    rect: Dict[str, float]  # {x, y, width, height}
    tag: str
    text: str
    element_type: str  # "link" | "button" | "input" | "image" | "text"
```

### 2.3 API 端点设计

```python
# services/api/app/routers/browser.py

@router.post("/sessions")
async def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    """
    创建浏览器会话
    
    Request: { url: str }
    Response: { 
        session_id: str, 
        screenshot: str,  # base64
        elements: List[InteractiveElement],
        page_info: { url: str, title: str }
    }
    """

@router.post("/sessions/{session_id}/actions")
async def execute_action(session_id: str, action: Action) -> ActionResult:
    """
    在会话中执行操作
    
    每次操作后返回新的截图和可交互元素列表
    """

@router.get("/sessions/{session_id}/state")
async def get_session_state(session_id: str) -> SessionState:
    """获取当前会话状态（截图、URL、元素）"""

@router.delete("/sessions/{session_id}")
async def close_session(session_id: str):
    """关闭会话，释放资源"""

@router.post("/sessions/{session_id}/robot")
async def save_as_robot(session_id: str, config: RobotConfig) -> Robot:
    """
    将当前配置保存为Robot
    
    RobotConfig: {
        name: str,
        fields: List[FieldConfig],
        pagination: Optional[PaginationConfig],
        actions: List[Action]  # 录制的操作序列
    }
    """
```

### 2.4 前端交互层设计

```javascript
// services/web/js/browser-canvas.js

class BrowserCanvas {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.canvas = document.createElement('canvas');
        this.ctx = this.canvas.getContext('2d');
        this.elements = [];  // 可交互元素
        this.sessionId = null;
    }
    
    // 渲染截图
    renderScreenshot(base64Image) {
        const img = new Image();
        img.onload = () => {
            this.canvas.width = img.width;
            this.canvas.height = img.height;
            this.ctx.drawImage(img, 0, 0);
            this.renderElementOverlays();
        };
        img.src = `data:image/png;base64,${base64Image}`;
    }
    
    // 渲染可交互元素高亮
    renderElementOverlays() {
        this.elements.forEach(el => {
            this.ctx.strokeStyle = 'rgba(102, 126, 234, 0.5)';
            this.ctx.lineWidth = 2;
            this.ctx.strokeRect(el.rect.x, el.rect.y, el.rect.width, el.rect.height);
        });
    }
    
    // 处理点击
    handleClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        
        // 检查是否点击在某个元素上
        const clickedElement = this.findElementAt(x, y);
        
        // 发送到后端执行
        this.executeAction({
            type: 'click',
            x: Math.round(x),
            y: Math.round(y),
            selector: clickedElement?.selector
        });
    }
    
    // 执行操作
    async executeAction(action) {
        const response = await fetch(`/api/sessions/${this.sessionId}/actions`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(action)
        });
        const result = await response.json();
        
        // 更新画布
        this.renderScreenshot(result.screenshot_base64);
        this.elements = result.elements;
    }
}
```

---

## 3. 翻页抓取设计（P0）

### 3.1 翻页类型

```python
class PaginationType(Enum):
    CLICK_NEXT = "click_next"      # 点击"下一页"按钮
    CLICK_NUMBER = "click_number"  # 点击页码
    INFINITE_SCROLL = "infinite_scroll"  # 滚动加载
    LOAD_MORE = "load_more"        # 点击"加载更多"
    URL_PATTERN = "url_pattern"    # URL参数变化（如 ?page=1, ?page=2）

class PaginationConfig(BaseModel):
    type: PaginationType
    # 点击类
    next_button_selector: Optional[str] = None
    # 滚动类
    scroll_container: Optional[str] = None  # 默认window
    scroll_wait_ms: int = 2000
    # URL类
    url_pattern: Optional[str] = None  # 如 "?page={n}"
    # 通用
    max_pages: int = 10
    stop_condition: Optional[str] = None  # 停止条件选择器（如"没有更多"）
```

### 3.2 翻页执行流程

```
【Robot执行翻页抓取】

1. 打开起始URL
2. 等待页面加载
3. 提取当前页数据（按fields配置）
4. 检查停止条件
   - 达到max_pages → 停止
   - stop_condition元素出现 → 停止
   - next_button不存在/disabled → 停止
5. 执行翻页操作
   - CLICK_NEXT: 点击next_button_selector
   - INFINITE_SCROLL: 滚动到底部，等待加载
   - URL_PATTERN: 构造下一页URL，导航
6. 等待新内容加载
7. 回到步骤3

【数据合并】
- 每页数据追加到results数组
- 自动去重（基于配置的唯一字段）
- 返回合并后的完整数据集
```

### 3.3 智能翻页检测

```python
class PaginationDetector:
    """自动检测页面翻页方式"""
    
    NEXT_BUTTON_PATTERNS = [
        'a:has-text("下一页")',
        'a:has-text("Next")',
        'button:has-text("下一页")',
        '[class*="next"]',
        '[class*="pagination"] a:last-child',
        '.ant-pagination-next',
        '.el-pagination__next',
    ]
    
    LOAD_MORE_PATTERNS = [
        'button:has-text("加载更多")',
        'button:has-text("Load More")',
        '[class*="load-more"]',
    ]
    
    async def detect(self, page: Page) -> PaginationConfig:
        """分析页面，返回推荐的翻页配置"""
        
        # 1. 检测"下一页"按钮
        for pattern in self.NEXT_BUTTON_PATTERNS:
            if await page.locator(pattern).count() > 0:
                return PaginationConfig(
                    type=PaginationType.CLICK_NEXT,
                    next_button_selector=pattern
                )
        
        # 2. 检测"加载更多"
        for pattern in self.LOAD_MORE_PATTERNS:
            if await page.locator(pattern).count() > 0:
                return PaginationConfig(
                    type=PaginationType.LOAD_MORE,
                    next_button_selector=pattern
                )
        
        # 3. 检测无限滚动（页面高度 > 视口高度 * 2）
        body_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")
        if body_height > viewport_height * 2:
            return PaginationConfig(
                type=PaginationType.INFINITE_SCROLL,
                scroll_wait_ms=2000
            )
        
        # 4. 检测URL分页模式
        url = page.url
        if re.search(r'[?&](page|p|pn)=\d+', url):
            return PaginationConfig(
                type=PaginationType.URL_PATTERN,
                url_pattern=re.sub(r'([?&])(page|p|pn)=\d+', r'\1\2={n}', url)
            )
        
        return None  # 未检测到翻页
```

---

## 4. 智能识别增强设计（P1）

### 4.1 列表结构检测

```python
class ListDetector:
    """检测页面中的重复列表结构"""
    
    async def detect_lists(self, page: Page) -> List[DetectedList]:
        """
        检测所有可能的列表结构
        
        算法：
        1. 获取所有容器元素（ul, ol, div, table, section）
        2. 分析子元素结构相似度
        3. 过滤：子元素 >= 3 且结构相似度 >= 0.8
        4. 排序：按元素数量和置信度
        """
        
        lists = await page.evaluate('''
            () => {
                const containers = document.querySelectorAll('ul, ol, div, table, section, main');
                const results = [];
                
                containers.forEach(container => {
                    const children = Array.from(container.children);
                    if (children.length < 3) return;
                    
                    // 计算结构相似度
                    const structures = children.map(getStructure);
                    const similarity = calculateSimilarity(structures);
                    
                    if (similarity >= 0.8) {
                        results.push({
                            selector: generateSelector(container),
                            itemSelector: generateSelector(children[0]),
                            count: children.length,
                            similarity: similarity,
                            sampleItems: children.slice(0, 3).map(extractPreview)
                        });
                    }
                });
                
                return results.sort((a, b) => b.count - a.count);
            }
        ''')
        
        return [DetectedList(**l) for l in lists]
```

### 4.2 字段类型推断

```python
class FieldTypeInferrer:
    """推断字段类型和提取属性"""
    
    PATTERNS = {
        'price': [
            r'[\$€£¥]\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*元',
            r'[\d,]+\.?\d*\s*(USD|CNY|EUR)',
        ],
        'date': [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}',
        ],
        'email': [r'[\w\.-]+@[\w\.-]+\.\w+'],
        'phone': [
            r'1[3-9]\d{9}',  # 中国手机
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # 国际格式
        ],
        'url': [r'https?://[^\s<>"\']+'],
        'rating': [
            r'[\d.]+\s*/\s*[\d.]+',  # 8.5/10
            r'★+',
            r'\d+(\.\d+)?\s*分',
        ],
    }
    
    def infer_type(self, text: str, tag: str, classes: str) -> FieldType:
        """根据文本内容和元素特征推断字段类型"""
        
        # 基于内容匹配
        for field_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return FieldType(field_type)
        
        # 基于标签
        if tag == 'img':
            return FieldType.IMAGE
        if tag == 'a':
            return FieldType.LINK
        if tag in ['h1', 'h2', 'h3', 'h4']:
            return FieldType.TITLE
        
        # 基于class名
        class_hints = {
            'price': FieldType.PRICE,
            'title': FieldType.TITLE,
            'name': FieldType.TITLE,
            'date': FieldType.DATE,
            'time': FieldType.DATE,
            'desc': FieldType.TEXT,
            'rating': FieldType.RATING,
            'score': FieldType.RATING,
        }
        for hint, ftype in class_hints.items():
            if hint in classes.lower():
                return ftype
        
        return FieldType.TEXT
```

---

## 5. 定时任务设计（P2）

### 5.1 数据模型

```python
# services/api/app/models/schedule.py

class ScheduleFrequency(Enum):
    ONCE = "once"           # 一次性
    HOURLY = "hourly"       # 每小时
    DAILY = "daily"         # 每天
    WEEKLY = "weekly"       # 每周
    CUSTOM = "custom"       # 自定义cron

class Schedule(BaseModel):
    id: str
    robot_id: str
    frequency: ScheduleFrequency
    cron_expression: Optional[str] = None  # 仅CUSTOM时使用
    next_run: datetime
    last_run: Optional[datetime] = None
    enabled: bool = True
    
class ScheduledRun(BaseModel):
    id: str
    schedule_id: str
    robot_id: str
    status: RunStatus  # pending | running | succeeded | failed
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result_count: int = 0
    error: Optional[str] = None
```

### 5.2 调度器设计

```python
# services/api/app/scheduler.py

class Scheduler:
    """简单的内存调度器（生产环境建议用Celery/APScheduler）"""
    
    def __init__(self):
        self.schedules: Dict[str, Schedule] = {}
        self.running = False
        
    async def start(self):
        """启动调度循环"""
        self.running = True
        while self.running:
            await self.check_and_run()
            await asyncio.sleep(60)  # 每分钟检查一次
    
    async def check_and_run(self):
        """检查并执行到期的任务"""
        now = datetime.utcnow()
        for schedule in self.schedules.values():
            if schedule.enabled and schedule.next_run <= now:
                await self.execute_robot(schedule)
                schedule.last_run = now
                schedule.next_run = self.calculate_next_run(schedule)
    
    def calculate_next_run(self, schedule: Schedule) -> datetime:
        """计算下次执行时间"""
        now = datetime.utcnow()
        if schedule.frequency == ScheduleFrequency.HOURLY:
            return now + timedelta(hours=1)
        elif schedule.frequency == ScheduleFrequency.DAILY:
            return now + timedelta(days=1)
        elif schedule.frequency == ScheduleFrequency.WEEKLY:
            return now + timedelta(weeks=1)
        elif schedule.frequency == ScheduleFrequency.CUSTOM:
            return croniter(schedule.cron_expression, now).get_next(datetime)
        return None  # ONCE不重复
```

---

## 6. 数据库设计

### 6.1 表结构

```sql
-- 会话表（临时，用于训练模式）
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    state JSON  -- 页面状态快照
);

-- Robot表（保存的爬虫配置）
CREATE TABLE robots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    origin_url TEXT NOT NULL,
    fields JSON NOT NULL,        -- 字段配置
    pagination JSON,             -- 翻页配置
    actions JSON,                -- 录制的操作序列
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 定时任务表
CREATE TABLE schedules (
    id TEXT PRIMARY KEY,
    robot_id TEXT REFERENCES robots(id),
    frequency TEXT NOT NULL,
    cron_expression TEXT,
    next_run TIMESTAMP NOT NULL,
    last_run TIMESTAMP,
    enabled BOOLEAN DEFAULT TRUE
);

-- 执行记录表
CREATE TABLE runs (
    id TEXT PRIMARY KEY,
    robot_id TEXT REFERENCES robots(id),
    schedule_id TEXT REFERENCES schedules(id),
    status TEXT NOT NULL,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result_count INTEGER DEFAULT 0,
    result_data JSON,
    error TEXT
);
```

---

## 7. 迁移路径

### Phase 1: Session Manager（1周）
1. 实现 SessionManager 类
2. 实现 /sessions API端点
3. 保持现有功能可用

### Phase 2: 前端Canvas化（1周）
1. 实现 BrowserCanvas 类
2. 替换 iframe 为 Canvas
3. 实现点击 → 后端执行 → 更新画布 循环

### Phase 3: 翻页支持（1-2周）
1. 实现 PaginationDetector
2. 实现翻页执行逻辑
3. UI支持翻页配置

### Phase 4: 智能识别增强（1周）
1. 实现 ListDetector
2. 实现 FieldTypeInferrer
3. 集成到训练流程

### Phase 5: 定时任务（1周）
1. 实现 Scheduler
2. 实现调度API
3. UI支持定时配置

---

## 8. 风险与应对

| 风险 | 影响 | 应对措施 |
|-----|------|---------|
| Playwright内存占用大 | 服务器资源紧张 | 限制并发会话数，设置超时清理 |
| 会话状态丢失 | 用户配置丢失 | 定期持久化状态，支持恢复 |
| 截图传输慢 | 交互延迟高 | 压缩截图，增量更新，WebSocket |
| 网站反爬 | 抓取失败 | 代理池，延迟策略，用户提示 |
