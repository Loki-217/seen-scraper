# SeenFetch 重构计划书 — Claude Code 专用

> **放置位置**：项目根目录 `CLAUDE_CODE_PLAN.md`
> **引用方式**：在 Claude Code 中用 `@CLAUDE_CODE_PLAN.md` 引用
> **语言约定**：代码和注释用英文，文档说明用中文

---

## 一、项目概述

**SeenFetch** 是一个类 Browse.ai 的可视化网页数据提取工具。

**核心用户流程**：
```
输入 URL → 实时预览页面 → 点选/AI识别数据字段 → 配置翻页 → 预览数据
→ 保存为 Robot → 手动执行或定时调度 → 导出 CSV/JSON
```

**竞品参照**：Browse.ai (https://browse.ai)
- Browse.ai 的 Robot Studio 用 CDP Screencast 实现高清实时页面预览
- 用户在实时画面上点选元素训练 Robot
- AI 自动识别列表结构并推荐字段

---

## 二、技术栈

| 层           | 技术                          | 说明                          |
|--------------|-------------------------------|-------------------------------|
| 后端         | Python 3.11 + FastAPI         | 异步 API + WebSocket          |
| 浏览器引擎   | Playwright + CDP Screencast   | 实时页面渲染和帧推送 ★ 核心升级 |
| 数据库       | SQLite + SQLAlchemy 2.0       | 本地存储                      |
| 前端         | 原生 HTML/CSS/JS              | 无框架，单一入口               |
| AI 辅助      | DeepSeek API (火山引擎)       | 字段命名建议                   |
| 开发工具     | VSCode + Claude Code          | AI 辅助开发                   |

**运行方式**：
- 后端：`uvicorn services.api.app.main:app --reload`（端口 8000）
- 前端：`python -m http.server 3000`（在 services/web/ 目录）

### ★ 关键技术升级：CDP Screencast

当前方案（截图模式）的问题：每次操作后 Playwright 截一张静态图 → base64 传输 → 模糊且有 1-2 秒延迟。

新方案（CDP Screencast）：通过 Playwright 的 CDP Session 启动 `Page.startScreencast`，以 WebSocket 持续推送 JPEG 帧到前端，实现 Browse.ai 同等的高清实时预览体验。用户的鼠标/键盘事件通过 WebSocket 回传，用 CDP `Input.dispatch*Event` 注入浏览器。

CDP Screencast 的技术要点：
```python
# Playwright 中获取 CDP Session
cdp = await page.context.new_cdp_session(page)

# 启动 screencast（持续推帧）
await cdp.send("Page.startScreencast", {
    "format": "jpeg",
    "quality": 80,
    "maxWidth": 1280,
    "maxHeight": 800,
    "everyNthFrame": 1
})

# 监听帧事件
cdp.on("Page.screencastFrame", handler)

# handler 中必须确认收到帧（否则不会推下一帧）
await cdp.send("Page.screencastFrameAck", {"sessionId": frame_session_id})

# 注入鼠标事件
await cdp.send("Input.dispatchMouseEvent", {
    "type": "mousePressed", "x": 100, "y": 200,
    "button": "left", "clickCount": 1
})

# 注入滚动
await cdp.send("Input.dispatchMouseEvent", {
    "type": "mouseWheel", "x": 640, "y": 400,
    "deltaX": 0, "deltaY": 300
})
```

前端接收帧：
```javascript
const ws = new WebSocket(`ws://127.0.0.1:8000/sessions/ws/${sessionId}`);
ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "frame") {
        img.src = "data:image/jpeg;base64," + msg.data;
    }
};
// 发送输入
ws.send(JSON.stringify({ type: "mousePressed", x: 100, y: 200, button: "left" }));
```

---

## 三、现有项目结构（★ 标记的是 V2 核心代码，要保留）

```
seen-scraper/
├── services/api/app/
│   ├── main.py               # FastAPI 入口
│   ├── session_manager.py    # ★ Playwright 会话池（需改造为 CDP）
│   ├── robot_executor.py     # ★ Robot 执行器
│   ├── scheduler.py          # ★ 定时调度器
│   ├── ai_service.py         # ★ AI 字段命名
│   ├── models.py             # ★ ORM 模型
│   ├── db.py                 # ★ 数据库引擎
│   ├── settings.py           # ★ 配置
│   ├── models_v2/            # ★ Pydantic 数据模型
│   ├── routers/
│   │   ├── browser.py        # ★ Session API
│   │   ├── smart.py          # ★ 智能分析 API
│   │   ├── robots.py         # ★ Robot CRUD
│   │   ├── schedules.py      # ★ Schedule CRUD
│   │   └── ai.py             # ★ AI 服务 API
│   └── services/
│       ├── list_detector.py      # ★ 列表检测
│       ├── field_inferrer.py     # ★ 字段推断
│       ├── pagination_detector.py # ★ 翻页检测
│       ├── pagination_executor.py # ★ 翻页执行
│       └── selector_optimizer.py  # ★ 选择器优化
├── services/web/
│   ├── index.html            # 前端入口（将被替换）
│   ├── css/                  # 样式（将被替换）
│   └── js/
│       ├── browser-canvas.js     # Canvas 交互（需改造）
│       └── schedule-manager.js   # 调度管理（可复用）
```

---

## 四、需要清理的文件

```
删除：
- services/api/app/browser_controller.py（已废弃）
- services/api/app/crawler_sync.py（旧版）
- services/api/app/crawler_runner_v2.py（V1 子进程方案）
- services/api/app/smart_extractor_subprocess.py（V1 方案）
- services/api/app/smart_matcher.py（未完成）
- services/api/app/test_playwright.py
- services/api/app/test_proxy_debug.py
- services/api/app/proxy.py（V1 iframe 代理）
- services/api/app/runner.py（V1 同步预览）
- services/web/css/*.bak
- services/web/archive/
- web/devui.html

清理后从 main.py 中移除相关 import 和路由注册。
```

---

## 五、MVP 功能范围

### 必须有
1. URL → CDP Screencast 高清实时预览
2. 点选元素 → 自动识别相似项高亮
3. AI 智能推荐字段 + 手动调整
4. 翻页配置 + 多页抓取
5. 数据预览表格
6. 导出 CSV / JSON
7. 保存为 Robot
8. Robot 执行 + 定时调度
9. 执行历史和结果下载

### 不做
- 用户系统、Credit 计费、网页监控、第三方集成、Workflow、模板市场

---

## 六、UI 设计规范

### 配色系统
```css
:root {
    --primary: #667eea;
    --primary-dark: #5a6fd6;
    --primary-light: #8b9cf7;
    --primary-bg: #f0f3ff;
    --gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    --success: #10b981;
    --success-bg: #ecfdf5;
    --warning: #f59e0b;
    --danger: #ef4444;
    --gray-50: #f9fafb;  --gray-100: #f3f4f6;  --gray-200: #e5e7eb;
    --gray-300: #d1d5db;  --gray-400: #9ca3af;  --gray-500: #6b7280;
    --gray-600: #4b5563;  --gray-700: #374151;  --gray-800: #1f2937;
    --text-primary: #111827;  --text-secondary: #6b7280;  --text-muted: #9ca3af;
    --bg-page: #f8f9fb;  --bg-card: #ffffff;
    --border: #e5e7eb;  --border-hover: #d1d5db;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -2px rgba(0,0,0,0.05);
    --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.08);
    --radius-sm: 6px;  --radius-md: 8px;  --radius-lg: 12px;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
    --font-mono: 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
}
```

### 组件规范

**按钮**：padding 8px 16px, border-radius 8px, font-weight 500, font-size 14px, transition 0.15s
- .btn-primary: bg var(--primary), color white; hover: darker + translateY(-1px) + shadow
- .btn-secondary: bg white, border 1px solid var(--border), color var(--text-primary)
- .btn-success: bg var(--success), color white
- .btn-danger: bg white, color var(--danger), border 1px solid var(--danger)
- .btn-sm: padding 4px 10px, font-size 12px

**卡片**：bg white, border 1px solid var(--border), border-radius 12px
- .card-header: padding 12px 16px, border-bottom, font-weight 600, font-size 14px
- .card-body: padding 16px

**输入框**：padding 8px 12px, border 1px solid var(--border), border-radius 8px, font-size 14px
- :focus: border-color var(--primary), box-shadow 0 0 0 3px var(--primary-bg)

**Badge**：padding 2px 8px, border-radius 9999px, font-size 11px, font-weight 600

---

## 七、分阶段实施计划

### Phase 0：清理和基础整合（1 天）

#### 任务 0.1：删除废弃文件

```
Claude Code 指令：

请删除以下废弃文件：
- services/api/app/browser_controller.py
- services/api/app/crawler_sync.py
- services/api/app/crawler_runner_v2.py
- services/api/app/smart_extractor_subprocess.py
- services/api/app/smart_matcher.py
- services/api/app/test_playwright.py
- services/api/app/test_proxy_debug.py
- services/api/app/proxy.py
- services/api/app/runner.py
- services/web/css/components.css.bak
- services/web/css/layout.css.bak
- services/web/css/utilities.css.bak
- services/web/css/variables.css.bak
- services/web/archive/（整个目录）
- web/devui.html

然后打开 services/api/app/main.py，移除所有引用这些文件的 import 语句和路由注册。
具体要移除的：
- from .proxy import router as proxy_router 和 app.include_router(proxy_router)
- from .runner import run_preview, RunnerError
- from .smart_extractor_subprocess import SmartExtractor
- from bs4 import BeautifulSoup / import soupsieve as sv
- PlayPreviewReq/PlayPreviewResp 类和 /play/preview 端点
- TemplatePreviewReq/TemplatePreviewResp 类和 /templates/preview 端点
- SmartAnalyzeRequest 类和 /api/smart/analyze 端点
- 重复的 from pydantic import BaseModel, Field

保留所有 V2 路由（browser_router, smart_router, robots_router, schedules_router, ai_router）。
保留 session_manager 和 scheduler 的生命周期管理。

清理后运行 uvicorn services.api.app.main:app --reload 确认启动无错误。
```

#### 任务 0.2：移动 API Key 到 .env

```
Claude Code 指令：

1. 在项目根目录创建 .env 文件，添加：
   SEENFETCH_DEEPSEEK_API_KEY=9cda15b4-30a6-42c3-9a49-c8edff7e86d9
   SEENFETCH_DEEPSEEK_ENDPOINT_ID=ep-20251010011104-trprx

2. 修改 services/api/app/settings.py：
   - deepseek_api_key 的 default 改为 ""
   - deepseek_endpoint_id 的 default 改为 ""
   - 移除文件中重复的 model_config 定义（有两个，删掉第一个）

3. 确认 .env 在 .gitignore 中
```

---

### Phase 1：CDP Screencast 实时预览（3-4 天）

#### 任务 1.1：改造 SessionManager 添加 CDP Screencast

```
Claude Code 指令：

改造 services/api/app/session_manager.py 的 BrowserSession 类。

新增属性：
- self.cdp_session = None          # CDP session 实例
- self.screencast_active = False   # 是否正在推帧
- self.websockets = set()          # 连接的 WebSocket 客户端
- self.frame_count = 0             # 帧计数

新增方法 1 - start_screencast：
async def start_screencast(self, quality=80, max_width=1280, max_height=800):
    """启动 CDP Screencast 帧推送"""
    self.cdp_session = await self.page.context.new_cdp_session(self.page)
    self.cdp_session.on("Page.screencastFrame", self._on_screencast_frame)
    await self.cdp_session.send("Page.startScreencast", {
        "format": "jpeg",
        "quality": quality,
        "maxWidth": max_width,
        "maxHeight": max_height,
        "everyNthFrame": 1
    })
    self.screencast_active = True

新增方法 2 - _on_screencast_frame：
async def _on_screencast_frame(self, params):
    """收到帧后广播给所有 WebSocket 客户端"""
    # 必须 ack 确认帧
    await self.cdp_session.send("Page.screencastFrameAck", {
        "sessionId": params["sessionId"]
    })
    self.frame_count += 1
    # 广播帧数据
    message = json.dumps({
        "type": "frame",
        "data": params["data"],
        "metadata": params.get("metadata", {})
    })
    dead_sockets = set()
    for ws in self.websockets:
        try:
            await ws.send_text(message)
        except Exception:
            dead_sockets.add(ws)
    self.websockets -= dead_sockets

新增方法 3 - stop_screencast：
async def stop_screencast(self):
    if self.cdp_session and self.screencast_active:
        await self.cdp_session.send("Page.stopScreencast")
        self.screencast_active = False

新增方法 4 - inject_input：
async def inject_input(self, event: dict):
    """通过 CDP 注入鼠标/键盘事件到浏览器"""
    if not self.cdp_session:
        return
    event_type = event.get("type")
    if event_type in ("mousePressed", "mouseReleased", "mouseMoved"):
        await self.cdp_session.send("Input.dispatchMouseEvent", {
            "type": event_type,
            "x": event["x"],
            "y": event["y"],
            "button": event.get("button", "left"),
            "clickCount": event.get("clickCount", 1)
        })
    elif event_type == "mouseWheel":
        await self.cdp_session.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": event.get("x", 0),
            "y": event.get("y", 0),
            "deltaX": event.get("deltaX", 0),
            "deltaY": event.get("deltaY", 300)
        })
    elif event_type in ("keyDown", "keyUp"):
        await self.cdp_session.send("Input.dispatchKeyEvent", {
            "type": event_type,
            "key": event.get("key", ""),
            "code": event.get("code", ""),
            "text": event.get("text", "")
        })

新增方法 5 - add_websocket / remove_websocket：
async def add_websocket(self, ws):
    self.websockets.add(ws)
async def remove_websocket(self, ws):
    self.websockets.discard(ws)

修改 create_session：
在页面 goto 成功后，调用 session.start_screencast()。
返回值中仍包含 elements 和 page_info，但 screenshot 字段改为空字符串（帧通过 WebSocket 推送）。

注意：
- CDP session 绑定到特定 page，页面导航后可能需要重建
- Windows 下事件循环策略保持现有的 WindowsSelectorEventLoopPolicy
- 现有的 execute_action 方法保留作为高级操作备选
- 现有的 get_elements 方法保留，通过 WebSocket 按需调用
```

#### 任务 1.2：新增 WebSocket 端点

```
Claude Code 指令：

在 services/api/app/routers/browser.py 中新增 WebSocket 路由。

在文件顶部添加：
from fastapi import WebSocket, WebSocketDisconnect

新增端点：
@router.websocket("/ws/{session_id}")
async def websocket_screencast(websocket: WebSocket, session_id: str):
    """
    双向 WebSocket：
    服务端→客户端：frame(帧数据), elements(元素列表), pageInfo(页面信息), analyzeResult(分析结果)
    客户端→服务端：mousePressed/mouseReleased/mouseMoved/mouseWheel(鼠标), keyDown/keyUp(键盘),
                   getElements(请求元素), analyze(请求智能分析), findSimilar(查找相似元素)
    """
    await websocket.accept()

    session = session_manager.get_session(session_id)
    if not session:
        await websocket.close(code=4004, reason="Session not found")
        return

    await session.add_websocket(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            # 鼠标和键盘事件 → 注入浏览器
            if event_type in ("mousePressed", "mouseReleased", "mouseMoved", "mouseWheel", "keyDown", "keyUp"):
                await session.inject_input(data)

            # 请求元素列表
            elif event_type == "getElements":
                elements = await session.get_elements()
                await websocket.send_json({
                    "type": "elements",
                    "elements": [el.dict() for el in elements]
                })

            # 智能分析
            elif event_type == "analyze":
                from ..services.list_detector import ListDetector
                from ..services.pagination_detector import PaginationDetector
                detector = ListDetector()
                lists = await detector.detect_lists(session.page)
                pg_detector = PaginationDetector()
                pg_results = await pg_detector.detect(session.page)
                await websocket.send_json({
                    "type": "analyzeResult",
                    "lists": [lst.dict() for lst in lists],
                    "pagination": [p.dict() for p in pg_results]
                })

            # 查找相似元素
            elif event_type == "findSimilar":
                selector = data.get("selector", "")
                result = await session.page.evaluate('''(selector) => {
                    try {
                        const els = document.querySelectorAll(selector);
                        return Array.from(els).map(el => {
                            const rect = el.getBoundingClientRect();
                            return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
                        });
                    } catch(e) { return []; }
                }''', selector)
                await websocket.send_json({
                    "type": "similarElements",
                    "selector": selector,
                    "rects": result,
                    "count": len(result)
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
    finally:
        await session.remove_websocket(websocket)
```

#### 任务 1.3：重建前端 BrowserCanvas

```
Claude Code 指令：

重写 services/web/js/browser-canvas.js，从截图模式改为 CDP Screencast 实时帧模式。

保持类名 BrowserCanvas，构造函数签名不变。

核心变化：
1. 旧版：每次操作 → fetch POST → 等待 → 拿到截图 → 更新 img.src
2. 新版：WebSocket 持续推帧 → img.src 实时刷新 → 操作通过 ws.send → 无需等待

属性：
- this.ws = null               // WebSocket 连接
- this.sessionId = null
- this.elements = []           // 后端返回的可交互元素列表
- this.selectedElements = []   // 用户选中的元素
- this.hoveredElement = null   // 鼠标悬停的元素
- this.scale = 1

DOM 结构（在 _createDOM 中创建）：
- this.frameImg: <img> 显示帧，style: width 100%, height 100%, object-fit contain
- this.overlay: <canvas> 绘制高亮框，absolute 定位，pointer-events none
- this.interactionLayer: <div> 捕获事件，absolute 定位，cursor crosshair
- this.tooltip: <div> fixed 定位，显示元素信息
- this.loadingOverlay: <div> 加载遮罩

事件绑定（在 _bindEvents 中）：
- mousemove → 查找 hoveredElement → 更新 overlay + tooltip
- click (左键) → 选中/取消元素（纯前端，不发给浏览器）
- contextmenu (右键) → 通过 ws.send 发送 mousePressed + mouseReleased 给浏览器
- wheel → 通过 ws.send 发送 mouseWheel 给浏览器
- keydown Esc → clearSelection

initSession(url, options) 流程：
1. fetch POST /sessions 创建 session
2. new WebSocket 连接 /sessions/ws/{sessionId}
3. ws.onmessage 处理 frame/elements/pageInfo/analyzeResult/similarElements
4. 触发 sessionReady 自定义事件

坐标转换 _getCoords(e)：
- 获取 frameImg 的 boundingClientRect
- 计算 scaleX = img.naturalWidth / rect.width
- 计算 scaleY = img.naturalHeight / rect.height
- 返回 { x: (clientX - left) * scaleX, y: (clientY - top) * scaleY }

_renderOverlay()：
- 淡蓝色细框：所有 elements
- 绿色粗框 + 浅绿填充：selectedElements
- 蓝色粗框 + 浅蓝填充：hoveredElement

公共 API（供 studio.js 调用）：
- initSession(url, options) → Promise
- closeSession()
- clearSelection()
- getSelectedElements() → array
- requestElements() → 通过 ws.send({type:"getElements"})
- requestAnalyze() → 通过 ws.send({type:"analyze"})
- findSimilar(selector) → 通过 ws.send({type:"findSimilar", selector})
- destroy()

请从现有 browser-canvas.js 迁移 _findElementAt、tooltip 逻辑等可复用代码。
```

---

### Phase 2：Robot Studio 主界面（3-4 天）

#### 任务 2.1：创建单一入口 HTML

```
Claude Code 指令：

删除 services/web/index.html 和 services/web/index-v2.html。
创建新的 services/web/index.html。

整体布局：
┌─────────────────────────────────────────────────────────────────┐
│ [👁️ SeenFetch Studio]  [🔗___URL输入框(flex:1)___] [Load] [End] │ ← 顶栏 56px
├────────────────────────────────────┬────────────────────────────┤
│                                    │ [🔍Detect][📋Fields][📄Pages][👁Preview] │ ← Tab 44px
│                                    ├────────────────────────────┤
│    Browser Canvas                  │                            │
│    (65% 宽)                        │    Tab 内容区               │
│                                    │    (可滚动)                 │
│    - 顶部工具条(40px)              │                            │
│    - 中间帧显示+覆盖层              │                            │
│    - 底部状态栏(28px)               │                            │
│                                    ├────────────────────────────┤
│                                    │ [💾Save Robot] [📥Export]   │ ← 操作栏
└────────────────────────────────────┴────────────────────────────┘

详细的 HTML 结构请参考计划书第六节的配色系统生成。

HTML 要引用：
- css/studio.css
- js/browser-canvas.js
- js/studio.js

关键 ID：
- urlInput, loadBtn, closeBtn, sessionStatus（顶栏）
- browserContainer, currentUrl, elementCount, selectionCount, frameRate（浏览器区）
- tab-detect, tab-fields, tab-pagination, tab-preview（Tab 面板）
- detectResults, fieldsList, paginationConfig, previewTable（Tab 内容）
- saveRobotBtn, exportBtn（操作按钮）
```

#### 任务 2.2：创建 Studio CSS

```
Claude Code 指令：

创建 services/web/css/studio.css。删除旧的 index-v2.css。

使用计划书第六节的配色系统（所有 CSS 变量定义在 :root 中）。

关键布局规格：

顶栏 .topbar：
- height: 56px, background: var(--gradient), padding: 0 24px
- flex 横向, align-items center, gap 16px
- .brand-name: font-size 18px, font-weight 700, color white
- .brand-badge: font-size 11px, bg rgba(255,255,255,0.2), padding 2px 8px, border-radius 4px
- .url-input-wrapper: flex 1, position relative
- .url-input: height 36px, border-radius 8px, border none, padding 0 12px 0 36px, font-size 14px, width 100%
- .url-prefix: position absolute, left 12px, top 50%, transform translateY(-50%), font-size 14px

主工作区 .workspace：
- height: calc(100vh - 56px), display flex, padding 12px, gap 12px, background var(--bg-page)

浏览器面板 .browser-pane：
- flex: 65, display flex, flex-direction column, bg white, border-radius 12px, box-shadow var(--shadow-md), overflow hidden
- .browser-toolbar: height 40px, padding 0 12px, border-bottom 1px solid var(--border), bg var(--gray-50), flex横向, align-items center
- .toolbar-url: flex 1, font-size 13px, color var(--text-secondary), font-family var(--font-mono), overflow hidden, text-overflow ellipsis
- .browser-container: flex 1, position relative, background #1a1a1a, overflow hidden
- .browser-statusbar: height 28px, padding 0 12px, font-size 12px, color var(--text-muted), bg var(--gray-50), border-top 1px solid var(--border), flex, align-items center, gap 16px

配置面板 .config-pane：
- flex: 35, min-width 360px, display flex, flex-direction column, bg white, border-radius 12px, box-shadow var(--shadow-md), overflow hidden
- .config-tabs: height 44px, display flex, border-bottom 1px solid var(--border)
- .tab-btn: flex 1, border none, bg transparent, font-size 13px, font-weight 500, color var(--text-secondary), cursor pointer, position relative
- .tab-btn.active: color var(--primary)
- .tab-btn.active::after: content '', position absolute, bottom 0, left 8px, right 8px, height 2px, bg var(--primary), border-radius 1px
- .config-content: flex 1, overflow-y auto
- .panel-header: padding 12px 16px, flex, justify-content space-between, align-items center, border-bottom 1px solid var(--border), sticky top 0, bg white, z-index 1
- .panel-body: padding 12px 16px
- .config-actions: padding 12px 16px, border-top 1px solid var(--border), flex, gap 8px（两个按钮各 flex 1）

空状态 .empty-state：position absolute 居中, text-align center
- .empty-icon: font-size 48px, margin-bottom 16px

隐藏类：.hidden { display: none !important; }

body：margin 0, font-family var(--font-sans), bg var(--bg-page), overflow hidden

响应式 @media (max-width: 1200px)：.workspace flex-direction column，两个 pane 各 height 50%

所有组件（按钮、卡片、输入框、Badge）样式请参考第六节组件规范生成。
```

#### 任务 2.3：创建 Studio 主逻辑 JS

```
Claude Code 指令：

创建 services/web/js/studio.js。删除旧的 index-v2.js。

全局状态：
const API_BASE = 'http://127.0.0.1:8000';
let canvas = null;               // BrowserCanvas 实例
let currentSession = null;       // {sessionId, pageInfo}
let configuredFields = [];       // [{name, selector, attr, type, confidence, sampleValues}]
let paginationConfig = null;     // 翻页配置对象
let smartResult = null;          // 智能分析结果
let currentTab = 'detect';

主要函数：

1. startSession()：
   - 获取 urlInput.value
   - 创建 BrowserCanvas 实例
   - 绑定 sessionReady / pageChange / elementSelect 事件
   - 调用 canvas.initSession(url)
   - 更新 UI（隐藏 loadBtn 显示 closeBtn，更新状态指示器）

2. closeSession()：
   - 调用 canvas.closeSession() 和 canvas.destroy()
   - 重置所有 UI

3. switchTab(tabName)：
   - 隐藏所有 .tab-panel
   - 显示对应的 tab
   - 更新 .tab-btn 的 active 状态

4. runSmartAnalyze()：
   - 调用 canvas.requestAnalyze()
   - 监听 WebSocket 返回的 analyzeResult
   - 调用 displayDetectResults(data)

5. displayDetectResults(data)：
   渲染到 #detectResults 中。每个检测到的列表渲染为一个卡片：
   ┌──────────────────────────────────────────┐
   │ 📋 商品列表                  25 items    │ ← card-header
   ├──────────────────────────────────────────┤
   │ item_selector: .grid > li               │ ← 浅灰 code 字体
   │                                          │
   │  📝 标题    text    "肖申克的救赎..."  [+]│ ← 每个字段一行
   │  🖼️ 图片    src     "https://..."     [+]│
   │  🔗 链接    href    "/subject/..."    [+]│
   │  💰 价格    text    "¥39.50"          [+]│
   │                                          │
   │  [Add All Fields]                        │
   └──────────────────────────────────────────┘

   [+] 按钮点击 → addField(field) → 自动切到 Fields tab
   [Add All Fields] → 添加所有字段

6. addField(field) / removeField(index) / updateField(index, changes)：
   管理 configuredFields 数组，每次变更后调用 renderFieldsList()

7. renderFieldsList()：
   渲染到 #fieldsList。每个字段一个可编辑卡片：
   ┌──────────────────────────────────────────┐
   │ [输入框:字段名____]  [类型badge]  [🗑️]  │
   │ selector: .price-tag                     │
   │ attr: [text ▼]   示例: "¥39.50..."       │
   └──────────────────────────────────────────┘
   字段名输入框 onchange → updateField
   attr 下拉框选项：text, href, src, data-*, innerHTML
   删除按钮 → removeField

8. detectPagination()：
   调用 canvas.requestAnalyze() 获取翻页信息
   或直接调用 REST API: POST /sessions/{id}/detect-pagination
   渲染翻页配置表单

9. renderPaginationForm(detected)：
   渲染到 #paginationConfig。
   类型选择按钮组（单选）：None / Next Button / Load More / Scroll / URL Pattern
   根据类型显示不同配置字段
   底部 [Test Pagination] 按钮

10. runPreview()：
    调用 REST API: POST /smart/extract-preview?session_id=xxx
    body: { item_selector: smartResult.lists[0].item_selector, fields: configuredFields }
    渲染表格到 #previewTable

11. saveAsRobot()：
    弹出模态框输入 Robot 名称
    调用 POST /robots
    成功后提示是否立即执行或设定时任务

12. exportData()：
    先执行一次提取
    提供 CSV 和 JSON 两种下载选项

13. showToast(message, type) / showModal(title, content)：
    Toast：fixed 定位右上角，自动消失
    Modal：半透明遮罩 + 白色居中卡片

请从现有 index-v2.js 中迁移以下可复用逻辑：
- escapeHtml, escapeAttribute 函数
- showToast 函数的实现
- highlightElements / clearHighlight 函数概念（改为通过 WebSocket findSimilar）
```

---

### Phase 3：交互模式改造 + 操作录制（预计 2-3 天）

**目标**：将当前的"左键选元素/右键导航"改为 Browse.ai 风格的模式切换机制，并实现操作步骤录制。

#### 任务 3.1：交互模式状态机

```
Claude Code 指令：

重构 browser-canvas.js 的鼠标事件处理逻辑，引入交互模式状态机。

⚠️ 不要删除或修改现有的 WebSocket 通信逻辑、帧渲染逻辑、元素数据结构。只修改鼠标事件的处理分支。

当前行为：左键 = 选中元素，右键 = 真实点击导航
改为：根据 interactionMode 变量决定鼠标行为

在 BrowserCanvas 中新增属性：
- this.interactionMode = 'navigate'  // 'navigate' | 'capture_list' | 'capture_text'

模式行为定义：

【navigate 模式（默认）】
- 所有鼠标点击通过 WebSocket 发送 CDP Input 事件给浏览器（即现在的"右键点击"逻辑）
- 不显示元素高亮框
- 不拦截链接跳转
- 滚轮事件正常转发

【capture_list 模式】
- 鼠标点击被前端拦截，不发送给浏览器
- mousemove 时在 overlay canvas 上高亮鼠标下的元素（复用现有的 hoveredElement 逻辑）
- 点击 = 确认选择当前悬停的列表（后续任务 3.4 会增强为动态列表检测）
- 链接跳转被禁用
- 滚轮事件仍然转发给浏览器（允许滚动查看页面）

【capture_text 模式】
- 鼠标点击被前端拦截
- mousemove 时高亮鼠标下的单个元素
- 点击 = 将该元素添加到 selectedElements 数组
- 链接跳转被禁用
- 滚轮事件仍然转发

新增公共方法：
- setMode(mode)：切换模式，清除当前高亮状态
- getMode()：返回当前模式

新增事件派发：
- 模式切换时派发 'modeChange' 事件
- capture_list 模式下用户点击确认列表时派发 'listCaptured' 事件（detail 包含 selector 和 item count）
- capture_text 模式下用户点击元素时派发 'textCaptured' 事件（detail 包含 element 信息）

在 studio.js 中：
- 引导面板的 "From a list" 按钮 onclick → canvas.setMode('capture_list') + setGuideState('smartDetect')
- "Just text" 按钮 onclick → canvas.setMode('capture_text') + setGuideState('manualSelect')
- 用户完成选取（Confirm/Save）后 → canvas.setMode('navigate')
- Discard 按钮 → canvas.setMode('navigate') + 重置引导状态

保留现有的 elements 数组和 get_elements WebSocket 请求逻辑不变——这些在 capture 模式下仍然需要用来做 hitTest（判断鼠标下是哪个元素）。
```

#### 任务 3.2：Step 操作录制与展示

```
Claude Code 指令：

在 studio.js 中实现操作步骤录制系统。

⚠️ 不要修改现有的引导面板状态机逻辑（renderGuidePanel 等函数），只在其基础上追加录制功能。录制的步骤列表显示在右侧面板的引导内容下方（引导按钮和选项之下，Discard/Finish 之上），随着用户操作实时追加。

新增数据结构：
let recordedSteps = [];  // 录制的步骤数组

每个步骤对象的结构：
{
    type: 'navigation' | 'interaction' | 'captured_list' | 'captured_text' | 'captured_screenshot',
    timestamp: ISO string,
    details: {
        // navigation: { url: string }
        // interaction: { action: 'click' | 'scroll' | 'input', selector?: string, x?: number, y?: number }
        // captured_list: { name: string, selector: string, itemCount: number, fields: [...] }
        // captured_text: { name: string, selector: string, sampleValue: string }
    }
}

录制触发点：
1. WebSocket 收到 pageInfo 消息（URL 变化）→ 追加 navigation 步骤
2. navigate 模式下用户点击被转发给浏览器 → 追加 interaction 步骤（记录 click 坐标和目标元素 selector）
3. capture_list 模式下用户完成列表选取 → 追加 captured_list 步骤
4. capture_text 模式下用户确认文本选取 → 追加 captured_text 步骤

步骤列表的 UI 渲染：
- 调用 renderRecordedSteps() 函数将 recordedSteps 渲染为 HTML
- 每个步骤显示为一个小卡片，包含步骤类型图标、简短描述
- 步骤类型图标：navigation = ▶，interaction = ↗，captured_list = ≡，captured_text = T
- 步骤描述从 details 中动态生成（如 "Navigating to https://..." 截断显示）
- 新步骤追加时滚动到底部

保存 Robot 时的数据转换：
- 将 recordedSteps 转换为后端 Robot 模型的 actions 格式
- navigation 和 interaction 步骤 → 转为 actions 数组中的 {type: "click"/"scroll"/"navigate", ...}
- captured_list 和 captured_text 步骤 → 转为 fields 配置
- 在 saveAsRobot() 函数中组装这些数据

为未来 Monitor 功能预留接口：
- recordedSteps 数组设计为可序列化的（纯 JSON，无 DOM 引用）
- 新增函数 getRecordingData() 返回完整的录制数据（steps + fields + pagination config）
- 新增函数 loadRecordingData(data) 从已有数据恢复录制状态（未来 Monitor 重新训练时用）
- 新增事件 'recordingComplete' 在用户点击 Finish 时派发，detail 包含完整的录制数据
```

#### 任务 3.3：翻页/行数配置仅在 List 模式下显示

```
Claude Code 指令：

修改 studio.js 中翻页配置区域的显示逻辑。

⚠️ 不要修改翻页检测和翻页执行的后端逻辑（pagination_detector.py、pagination_executor.py），只修改前端的显示条件。

当前行为：所有模式都显示 Step 3: Pagination 配置区域
改为：

1. 仅当 interactionMode === 'capture_list' 且用户已选中一个列表（captured list 的 itemCount >= 2）时，
   才显示翻页相关配置

2. 翻页配置区域包含两部分（在列表选取确认后显示）：
   - 行数选择：让用户选择最大抓取行数（提供 10 / 100 / Custom 三个选项，Custom 允许输入自定义数字）
   - 翻页设置：一个 "Select Pagination Setting" 按钮，点击后调用现有的翻页检测 API，
     展示检测结果并让用户确认

3. 在 capture_text 模式下，完全不显示翻页配置

4. 行数选择和翻页配置的值保存到 paginationConfig 对象中，供保存 Robot 时使用

在 renderConfiguringGuide() 或对应的引导面板渲染函数中实现此条件判断。
```

#### 任务 3.4：鼠标跟随动态列表检测（CDP 注入方案）

```
Claude Code 指令：

实现 Browse.ai 风格的动态列表检测：在 capture_list 模式下，鼠标悬停时实时识别当前层级的重复结构。

⚠️ 这是技术难度最高的任务。核心原则：检测和高亮逻辑必须在远程浏览器端运行（通过 CDP 注入 JS），不能每次 mousemove 都通过 WebSocket 往返。只有用户"点击确认选择"时才通过 WebSocket 回传结果。

实现方案分两层：

【浏览器端注入脚本】
通过 CDP Runtime.evaluate 向远程页面注入一段 JS 脚本（在 session_manager.py 中实现）。
这段脚本的功能：
- 监听 mousemove 事件（自带 200ms 节流 throttle）
- 获取鼠标下的 DOM 元素 E
- 获取 E 的父元素 P
- 遍历 P 的所有直接子元素，计算与 E 的结构相似度（比较 tagName + className 组合）
- 如果相似子元素 >= 2 个，认为这是一个列表
- 用 CSS outline（虚线框）标记所有相似的列表项（不使用 box-shadow 或 border，避免影响布局）
- 在每个列表项左上角叠加一个小的 "List Item N" 标签（用 ::before 伪元素或绝对定位 div）
- 鼠标移走时清除上一次的高亮
- 将当前检测到的列表信息（container selector、item selector、item count）暂存在 window.__seenfetch_detected_list 变量中

注入脚本的管理：
- 在 session_manager.py 的 BrowserSession 中新增方法 inject_list_detection_script()
- 进入 capture_list 模式时调用此方法注入脚本
- 退出 capture_list 模式时调用 remove_list_detection_script() 清除注入的脚本和样式
- 页面导航后需要重新注入（监听 page 的 'load' 事件）

【用户确认选择时的回传】
用户在 capture_list 模式下点击页面：
1. 前端通过 WebSocket 发送 {type: "confirmListSelection"} 给后端
2. 后端通过 CDP Runtime.evaluate 读取 window.__seenfetch_detected_list 的值
3. 返回给前端：{type: "listCaptured", selector: "...", itemCount: N, sampleItems: [...]}
4. 前端接收后追加到 recordedSteps，更新引导面板显示

在 routers/browser.py 的 WebSocket handler 中新增 "confirmListSelection" 消息类型的处理。

现有的 list_detector.py 保留不动——它仍然用于 "Smart detect" 模式（全局一次性扫描）。
新的动态检测是额外的功能，用于 "From a list" 模式。

注入脚本中的列表结构相似度算法可以参考 list_detector.py 中的 getStructureHash 逻辑，
简化为：两个元素的 tagName 相同且 className 的前两个 class 相同即认为结构相似。
```

---

### Phase 4：Robot 保存 + 执行 + 导出完善（预计 1-2 天）

**目标**：完善 Robot 保存流程，修复执行和导出功能，确保 Studio → 保存 → 执行 → 查看结果 的完整链路可用。

#### 任务 4.1：完善 Robot 保存流程

```
Claude Code 指令：

检查并修复 studio.js 中 saveAsRobot() 函数的完整流程。

⚠️ 不要修改后端 API（routers/robots.py 的 POST /robots 和 POST /robots/{id}/run）。只修复前端逻辑。

保存时需要收集的数据：
- name 和 description：从保存对话框的输入框获取
- origin_url：从当前 session 的 pageInfo.url 获取
- actions：从 recordedSteps 中提取 navigation 和 interaction 类型的步骤，
  转换为后端 Action 模型格式（参考 models_v2/schedule.py 中的 Action 类）
- item_selector：从 captured_list 步骤中获取，或从 smartResult 中获取
- fields：从 configuredFields 数组转换，每个字段包含 name、selector、attr
- pagination：从 paginationConfig 转换，包含 type、selector、max_pages、wait_ms

调用 POST /robots 后的三个按钮行为（确认现有逻辑正确）：
- Run Now → window.location.href = 'robot.html?id=' + robot.id + '&autorun=true'
- Set Schedule → 调用现有的 showScheduleDialogDirect(robot)
- Later → window.location.href = 'index.html'

检查保存对话框中 robot.id 是否正确传递到三个按钮的 onclick 中。
如果发现 robot.id 为 undefined，检查 POST /robots 的响应解析逻辑。
```

#### 任务 4.2：Robot 详情页执行和导出修复

```
Claude Code 指令：

检查 robot.html 和 robot.js 的执行与导出功能。

⚠️ 不要修改 robot.html 的页面布局和样式，只修复 JS 逻辑。

需要确认和修复的点：

1. autorun 流程：
   - URL 参数包含 autorun=true 时，页面加载后自动调用 POST /robots/{id}/run
   - 显示 loading 遮罩，等待 API 返回（这个 API 是同步等待执行完成的）
   - 执行成功后，从响应中获取 result.items 数组
   - 用 items 渲染数据表格（表头从 items[0] 的 keys 生成）
   - 将 items 存入 JS 变量供 Download 使用

2. 手动 Run Task 按钮：
   - 点击后显示 loading 遮罩
   - 调用 POST /robots/{id}/run
   - 逻辑同上

3. Download 功能：
   - CSV 下载：在前端将 items 数组转为 CSV 格式
     - 使用 BOM (\uFEFF) 开头确保中文在 Excel 中正确显示
     - 字段值中的逗号和引号需要正确转义
     - 创建 Blob 对象，用临时 <a> 标签触发下载
   - JSON 下载：JSON.stringify(items, null, 2) → Blob → 下载

4. 错误处理：
   - 如果 POST /robots/{id}/run 返回 success: false，显示错误信息和重试按钮
   - 如果网络请求失败，显示友好提示
```

---

### Phase 5：打磨、测试与 Monitor 接口预留（预计 1-2 天）

**目标**：完善错误处理，预留 Monitor 扩展接口，验证完整流程。

#### 任务 5.1：错误处理完善

```
Claude Code 指令：

为以下场景添加友好的错误处理。

⚠️ 使用 Toast 通知显示错误信息，不要用 alert()。不要修改后端 API 的错误返回格式。

1. WebSocket 断连自动重连：
   - 在 browser-canvas.js 中，WebSocket onclose 事件触发后，3 秒后自动尝试重连
   - 最多重连 3 次
   - 重连期间在状态栏显示 "Reconnecting..."
   - 全部失败后显示 Toast "Connection lost. Please reload the page."

2. Session 过期处理：
   - 后端返回 410 Gone 时（session 已过期），显示 Toast "Session expired"
   - 自动清理前端状态并显示空状态页面

3. 智能分析失败降级：
   - Smart detect 失败时，显示 Toast 提示并建议用户使用 "From a list" 手动选取
   - 不阻塞其他功能

4. Robot 执行失败：
   - robot.html 中执行失败时，显示错误详情 + 重试按钮
   - 不要隐藏 loading 后显示空白，确保用户知道发生了什么

5. 页面加载超时：
   - Studio 中 session 创建超时（30 秒），显示提示建议检查 URL 或网络
```

#### 任务 5.2：Monitor 接口预留

```
Claude Code 指令：

在现有代码中预留 Monitor 功能的扩展接口。

⚠️ 不需要实现 Monitor 的任何功能逻辑，只是确保数据结构和代码架构不会阻碍未来添加 Monitor。

1. Robot 模型扩展预留：
   - 在 models.py 的 RobotDB 中，添加一个注释标记未来 Monitor 字段的位置：
     # === Future: Monitor fields ===
     # monitor_enabled: bool
     # monitor_frequency: str (cron expression)
     # monitor_diff_mode: str ('visual' | 'content' | 'data')
     # last_monitor_at: datetime
     # === End Future ===
   - 不要真的添加这些列，只留注释占位

2. 录制数据的可复用性：
   - 确认 getRecordingData() 返回的数据结构包含足够信息，
     使得未来 Monitor 可以：
     a) 重新执行同样的导航路径
     b) 在同样的页面上提取同样的数据
     c) 与上次结果做 diff 对比
   - 具体来说，确保 recordedSteps 中的每个 navigation 步骤都包含完整 URL，
     每个 captured_list/captured_text 步骤都包含完整的 selector 信息

3. robot.html 页面预留：
   - 在 Tab 栏中，Quick Setup 旁边添加一个灰色不可点击的 "Monitor" tab
   - 样式：color: #d1d5db, cursor: default, 旁边加一个小的 "Coming soon" badge
   - 点击无反应

4. home.html 主页预留：
   - Robot 卡片中，如果未来 robot 有 monitor_enabled 属性，可以显示一个小的监控状态图标
   - 现在不需要实现，但在渲染 Robot 卡片的代码中留一个注释标记：
     // Future: if (robot.monitor_enabled) { show monitor status icon }
```

#### 任务 5.3：端到端测试验证

```
Claude Code 指令：

创建 services/web/TEST_GUIDE.md，包含以下端到端测试用例。

⚠️ 测试用例中的 URL 和数据都是建议值，测试者可以用任何网站替代。

测试 1 - 完整的 Smart Detect 流程：
- 打开主页 → 点击 Build New Robot → 进入 Studio
- 输入 URL → Load → 等待实时预览出现
- 点击 Capture text → Smart detect
- 验证右侧面板显示检测到的列表和字段
- 添加字段 → 验证底栏数据预览可以展开并显示数据
- 点击 Finish → 命名 Robot → Save
- 选择 Run Now → 跳转到 Robot 详情页 → 验证数据表格显示
- 下载 CSV 和 JSON → 验证文件内容正确

测试 2 - From a list 手动选取流程：
- 进入 Studio → 加载页面
- 点击 Capture text → From a list
- 验证鼠标悬停时页面上出现列表高亮框
- 点击确认列表 → 验证翻页配置区域出现
- 设置最大行数 → 选择翻页方式
- Finish → Save → Later → 验证跳转到主页 → 验证 Robot 卡片出现

测试 3 - Just text 手动选取流程：
- 进入 Studio → 加载页面
- 点击 Capture text → Just text
- 在页面上点击多个元素 → 验证右侧面板显示已选字段列表
- 验证翻页配置不显示
- Finish → Save

测试 4 - 导航模式操作录制：
- 进入 Studio → 加载一个包含链接的页面
- 在导航模式下点击一个链接 → 验证页面跳转
- 验证右侧面板的步骤列表显示 Step 1: Navigation 和 Step 2: Page Interaction
- 在新页面上进行数据选取 → 验证步骤列表追加新步骤

测试 5 - 错误场景：
- 输入无效 URL → 验证错误提示
- 在 Robot 详情页点击 Run Task 后断网 → 验证错误提示和重试按钮
- 等待 session 过期（30 分钟不操作）→ 验证过期提示
```

---

## 八、工作规范

### 代码风格
- Python：snake_case 变量/函数，PascalCase 类名
- JavaScript：camelCase 变量/函数，PascalCase 类名
- CSS：kebab-case 类名
- 注释英文，用户可见文字中文

### 开发约定
- 每次修改前说明影响范围
- 前端修改后提醒 Ctrl+Shift+R
- 数据库模型变更提醒删除旧 .db
- API Key 只放 .env

### 推进节奏
- 每个任务一次 Claude Code 对话
- 完成一个任务后 git commit
- 每完成一个 Phase 推送 GitHub
