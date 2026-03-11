# SeenFetch V2 - Claude Code 主提示词

## 项目身份

你正在开发 **SeenFetch**，一个面向非程序员的网页端可视化爬虫工具。

核心定位：
- **即开即用**：网页端，不需要下载安装
- **可视化配置**：点击选择，不需要写代码
- **一次性用户**：服务于偶尔需要抓数据的普通人，不是专业爬虫用户

竞品参考：Browse AI（目标）、Octoparse（需下载，对标）

## 技术栈

```
前端：原生 HTML/CSS/JavaScript（无框架）
后端：FastAPI + Python 3.11+
浏览器引擎：Playwright（服务端渲染和交互）
数据库：SQLite（开发）/ PostgreSQL（生产）
AI：火山引擎 DeepSeek API（字段名建议等）
```

## 核心架构原则

### 1. 服务端浏览器架构

```
用户浏览器                     SeenFetch 服务端
     │                              │
     │ 1. 输入URL                   │
     ├─────────────────────────────►│ Playwright 加载页面
     │                              │
     │ 2. 返回截图 + 可交互元素     │
     │◄─────────────────────────────┤
     │                              │
     │ 3. 用户点击（坐标/选择器）   │
     ├─────────────────────────────►│ Playwright 执行真实点击
     │                              │
     │ 4. 返回新截图 + 新状态       │
     │◄─────────────────────────────┤
```

**关键点**：
- 前端**不显示**目标网页的 HTML/iframe
- 前端显示的是**截图**（Canvas/Image）
- 所有交互由**后端 Playwright 执行**
- 这样完全绕过 CORS/CSP/X-Frame-Options

### 2. Session 持久化

每个用户的"训练"过程对应一个 Playwright Session：
- Session 保持页面状态（已登录、已滚动、已展开等）
- Session 超时自动清理（默认30分钟）
- Session ID 返回给前端，后续请求携带

### 3. Robot = 可重放的操作序列

用户训练完成后保存为 Robot：
```python
Robot = {
    name: "豆瓣Top250",
    origin_url: "https://movie.douban.com/top250",
    fields: [...],        # 要提取的字段
    pagination: {...},    # 翻页配置
    actions: [...]        # 录制的操作序列（点击、滚动、等待）
}
```

Robot 可以：
- 立即执行（一次性抓取）
- 定时执行（每天/每周）
- 批量执行（多个URL）

## 代码规范

### Python 后端

```python
# 使用 Pydantic 定义所有请求/响应模型
class CreateSessionRequest(BaseModel):
    url: str = Field(..., description="目标页面URL")

class CreateSessionResponse(BaseModel):
    session_id: str
    screenshot: str  # base64
    elements: List[InteractiveElement]

# 使用 async/await
async def create_session(req: CreateSessionRequest) -> CreateSessionResponse:
    ...

# 错误处理返回结构化响应
@app.exception_handler(Exception)
async def handle_exception(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__}
    )
```

### JavaScript 前端

```javascript
// 使用 ES6+ 语法
// 不使用框架，保持简单
// 所有 API 调用封装到单独函数

const API_BASE = 'http://127.0.0.1:8000';

async function createSession(url) {
    const response = await fetch(`${API_BASE}/sessions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
    });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
}
```

## 文件结构

```
seenfetch/
├── services/
│   ├── api/
│   │   └── app/
│   │       ├── main.py              # FastAPI 应用入口
│   │       ├── settings.py          # 配置
│   │       ├── session_manager.py   # 【新】Session 池管理
│   │       ├── models/
│   │       │   ├── actions.py       # 【新】操作类型定义
│   │       │   ├── robot.py         # 【新】Robot 模型
│   │       │   └── schedule.py      # 【新】定时任务模型
│   │       ├── routers/
│   │       │   ├── browser.py       # 【新】/sessions API
│   │       │   ├── robots.py        # 【新】/robots API
│   │       │   ├── jobs.py          # 现有
│   │       │   └── runs.py          # 现有
│   │       ├── services/
│   │       │   ├── pagination.py    # 【新】翻页检测与执行
│   │       │   ├── list_detector.py # 【新】列表结构检测
│   │       │   └── field_inferrer.py# 【新】字段类型推断
│   │       └── db.py                # 数据库
│   └── web/
│       ├── index.html
│       ├── css/
│       │   └── index-v2.css
│       └── js/
│           ├── index-v2.js
│           ├── browser-canvas.js    # 【新】Canvas 交互层
│           └── robot-config.js      # 【新】Robot 配置面板
└── tests/
```

## 当前优先级

1. **P0 - 翻页抓取**：用户能配置翻页，Robot 能执行多页抓取
2. **P1 - 智能识别增强**：更准确地检测列表和字段类型
3. **P2 - 定时任务**：Robot 能按计划自动执行
4. **P3 - 数据变化监控**：检测数据变化并通知

## 开发原则

1. **先跑通再优化**：先实现最小可用版本，再迭代改进
2. **保持向后兼容**：新功能不破坏现有功能
3. **用户体验优先**：每个交互都要考虑普通用户能否理解
4. **错误要可理解**：错误信息用中文，告诉用户怎么做

## 调试技巧

```bash
# 启动后端（开发模式）
cd services/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端（简单HTTP服务器）
cd services/web
python -m http.server 3000

# 测试 Playwright
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=False); b.close()"
```

## 注意事项

- Playwright 在 Windows 上需要 `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())`
- 截图传输大，考虑压缩（JPEG quality 80）或增量更新
- Session 超时要及时清理，避免内存泄漏
- 目标网站可能有反爬，要有重试和降级策略
