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

### Phase 3：元素选择增强 + AI 集成（2-3 天）

#### 任务 3.1：点选元素自动查找相似项

```
Claude Code 指令：

增强 BrowserCanvas 的 click 处理。

当前：左键点击 → 选中单个元素
改为：左键点击 → 查找相同 tag+class 的元素 → 全部高亮 → 提示数量

实现：
1. 在 click handler 中，选中元素后调用 this.findSimilar(element.selector)
2. findSimilar 通过 WebSocket 发送 {type:"findSimilar", selector:"..."}
3. 后端返回 {type:"similarElements", rects:[...], count:N}
4. 前端在 overlay canvas 上用绿色虚线框标记所有相似项
5. 在状态栏显示 "Found 25 similar items"
6. 触发事件：container.dispatchEvent(new CustomEvent('similarFound', {detail: {selector, count, rects}}))

在 studio.js 中监听 similarFound 事件，Toast 提示："Found 25 similar items with selector '.product-card'"
```

#### 任务 3.2：AI 字段命名增强

```
Claude Code 指令：

在 studio.js 的 displayDetectResults 中：
对每个 suggested_field 的 confidence < 0.85 的字段，异步调用 AI 命名：

async function enhanceFieldName(field) {
    try {
        const res = await fetch(`${API_BASE}/api/ai/suggest-field-name`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                element: {
                    text: field.sample_values?.[0] || '',
                    tagName: '', className: field.selector, id: '',
                    href: '', src: ''
                }
            })
        });
        const result = await res.json();
        if (result.confidence > field.confidence) {
            field.name = result.fieldName;
            field.confidence = result.confidence;
        }
    } catch(e) { /* ignore, keep original name */ }
}

在字段卡片上，如果 AI 优化过名称，显示一个小的 "AI" badge。
这里复用现有的 /api/ai/suggest-field-name API，无需修改后端。
```

---

### Phase 4：Robot 保存 + 执行 + 调度（2 天）

#### 任务 4.1：Robot 保存流程

```
Claude Code 指令：

实现 saveAsRobot() 函数。

点击 "Save as Robot" 按钮 → 弹出模态框：
┌──────────────────────────────────────┐
│ 💾 Save Robot            [✕]        │
├──────────────────────────────────────┤
│                                      │
│ Robot Name:                          │
│ [_________________________________] │
│                                      │
│ Description (optional):              │
│ [_________________________________] │
│                                      │
│ Origin URL: https://example.com/...  │ ← 灰色只读
│ Fields: 5 configured                 │ ← 灰色只读
│ Pagination: Next Button              │ ← 灰色只读
│                                      │
├──────────────────────────────────────┤
│              [Cancel]  [Save Robot]  │
└──────────────────────────────────────┘

模态框样式：
- 遮罩：fixed 全屏，bg rgba(0,0,0,0.5)，z-index 1000
- 卡片：bg white，max-width 480px，border-radius 12px，box-shadow var(--shadow-lg)
- 标题栏：padding 16px 20px，border-bottom，font-size 16px font-weight 600
- 表单区：padding 20px
- 底部：padding 16px 20px，border-top，flex，justify-content flex-end，gap 8px

保存时调用 POST /robots，body：
{
    name, description,
    origin_url: currentSession.pageInfo.url,
    item_selector: smartResult?.lists?.[0]?.item_selector || "",
    fields: configuredFields.map(f => ({name: f.name, selector: f.selector, attr: f.attr})),
    pagination: paginationConfig ? { type: paginationConfig.type, selector: paginationConfig.next_button_selector, max_pages: paginationConfig.max_pages, wait_ms: 1000 } : null,
    actions: []
}

成功后：
- Toast "Robot saved!"
- 弹出确认："Run now?" [Run Now] [Set Schedule] [Later]
- Run Now → 调用 POST /robots/{id}/run，显示执行进度
- Set Schedule → 调用 schedule-manager.js 的 showScheduleDialogDirect(robot)
```

#### 任务 4.2：执行进度和结果下载

```
Claude Code 指令：

"Run Now" 点击后显示执行进度弹窗：
┌──────────────────────────────────────┐
│        🔄 Running Robot...           │
│                                      │
│  Status: Extracting page 3/10        │
│  Items: 75                           │
│  Duration: 12.3s                     │
│                                      │
│  ████████████░░░░░░ 30%             │
│                                      │
└──────────────────────────────────────┘

实现：
1. 调用 POST /robots/{id}/run 获取初始响应
2. 由于 robot_executor 是异步的，用 polling 检查 robot 的 last_run_at 变化
   或者更简单的方案：同步等待 API 返回（当前 run_robot 端点是 await executor.execute()）
3. 成功后变为：

┌──────────────────────────────────────┐
│        ✅ Complete!                  │
│                                      │
│  Pages: 10  Items: 250  Time: 45.2s  │
│                                      │
│  [📥 Download CSV] [📥 Download JSON]│
│                                      │
│  [Close]                             │
└──────────────────────────────────────┘

CSV 下载：
- 如果 result_file 存在，直接 window.open /robots/{id}/run 返回的 result_file 路径
- 备选方案：在前端用 result.items 生成 CSV Blob 下载

JSON 下载：
- 前端生成：new Blob([JSON.stringify(items, null, 2)], {type: 'application/json'})
- 创建临时 <a> 标签触发下载
```

---

### Phase 5：打磨和测试（2 天）

#### 任务 5.1：错误处理

```
Claude Code 指令：

为以下场景添加错误处理：

1. URL 加载失败：
   - WebSocket 断开 → 3 秒后自动重连，最多 3 次
   - 重连失败 → Toast "Connection lost. Please reload the page."

2. Session 过期（30 分钟）：
   - 检测到 4xx 响应 → Toast "Session expired" + 自动清理 UI

3. 智能分析无结果：
   - 显示 "No data lists detected. Try selecting elements manually." + 自动切到 Fields tab

4. Robot 执行失败：
   - 显示错误详情 + [Retry] 按钮

5. 导出失败：
   - 降级到前端生成（如果后端文件不可用）
```

#### 任务 5.2：创建测试指南

```
Claude Code 指令：

创建 TEST_GUIDE.md，包含端到端测试用例：

测试 1 - 基础流程：
URL: https://quotes.toscrape.com/
步骤：输入URL → Load → 等待实时预览出现 → Run Analysis → 添加字段 → Preview → Export CSV

测试 2 - 翻页：
URL: https://quotes.toscrape.com/
步骤：Detect pagination → 应该检测到 Next Button → Test → 配置 max_pages=3 → 执行抓取

测试 3 - Robot 流程：
步骤：在测试 1 基础上 → Save Robot → Run Now → 下载结果 → 设置每天执行的定时任务

测试 4 - 异常场景：
- 输入无效 URL → 应显示错误提示
- 输入 localhost → 应显示错误提示
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
