# P0 - 翻页抓取功能开发提示词

## 功能概述

实现 Robot 的多页抓取能力，支持：
- 点击"下一页"按钮翻页
- 无限滚动加载
- URL参数翻页
- 智能检测翻页方式

---

## Prompt 1: Session Manager 基础实现

```
实现 SeenFetch 的 Session Manager，管理 Playwright 浏览器会话池。

要求：
1. 创建 services/api/app/session_manager.py
2. 实现 BrowserSession 类：
   - session_id: str (UUID)
   - page: Playwright Page 对象
   - created_at, last_active: datetime
   - 方法：screenshot(), get_elements(), execute_action()

3. 实现 SessionManager 类：
   - 单例模式
   - 最多10个并发会话
   - 30分钟超时自动清理
   - 方法：
     - create_session(url) -> session_id
     - get_session(session_id) -> BrowserSession
     - execute_action(session_id, action) -> ActionResult
     - cleanup_expired()

4. ActionResult 包含：
   - success: bool
   - screenshot_base64: str (JPEG, quality=80)
   - url: str (当前页面URL)
   - elements: List[InteractiveElement]
   - error: Optional[str]

5. InteractiveElement 包含：
   - selector: str (CSS选择器)
   - rect: {x, y, width, height}
   - tag: str
   - text: str (前50字符)
   - element_type: "link" | "button" | "input" | "image" | "text"

技术要点：
- 使用 playwright.async_api
- 截图用 JPEG 格式减小体积
- 获取可交互元素时注入 JavaScript 遍历 DOM
- 处理 Windows 事件循环策略

现有代码参考 services/api/app/browser_controller.py
```

---

## Prompt 2: Session API 端点

```
为 SeenFetch 创建 Session 相关的 API 端点。

要求：
1. 创建 services/api/app/routers/browser.py
2. 实现以下端点：

POST /sessions
- 请求：{ url: str }
- 响应：{ session_id, screenshot, elements, page_info: {url, title} }
- 创建新的 Playwright 会话，加载页面，返回截图

POST /sessions/{session_id}/actions
- 请求：Action 对象
- 响应：ActionResult
- Action 类型：
  - click: { type: "click", x: int, y: int } 或 { type: "click", selector: str }
  - scroll: { type: "scroll", direction: "down", distance: 500 }
  - input: { type: "input", selector: str, text: str }
  - wait: { type: "wait", ms: int } 或 { type: "wait", selector: str }

GET /sessions/{session_id}/state
- 响应：当前截图和元素列表

DELETE /sessions/{session_id}
- 关闭会话，释放资源

3. 在 main.py 中注册路由：app.include_router(browser_router, prefix="/sessions")

4. 错误处理：
- 会话不存在：404
- 会话过期：410 Gone
- 操作失败：返回 error 字段

参考现有的 services/api/app/routers/jobs.py 风格
```

---

## Prompt 3: 前端 Canvas 交互层

```
将 SeenFetch 前端从 iframe 改为 Canvas 截图显示。

要求：
1. 创建 services/web/js/browser-canvas.js
2. 实现 BrowserCanvas 类：

class BrowserCanvas {
    constructor(containerId)
    
    // 初始化会话
    async initSession(url) 
    
    // 渲染截图到 Canvas
    renderScreenshot(base64Image)
    
    // 渲染可交互元素高亮覆盖层
    renderElementOverlays()
    
    // 处理鼠标悬停（高亮元素）
    handleMouseMove(event)
    
    // 处理点击（发送到后端）
    async handleClick(event)
    
    // 执行操作并更新画布
    async executeAction(action)
    
    // 查找坐标处的元素
    findElementAt(x, y)
}

3. 交互逻辑：
- 鼠标移动时，高亮鼠标下方的元素（半透明蓝色边框）
- 点击时：
  a. 获取点击坐标
  b. 检查是否在某个元素上
  c. 发送 click action 到后端
  d. 后端执行点击，返回新截图
  e. 更新 Canvas 显示

4. 修改 index.html：
- 移除 iframe 相关代码
- 添加 Canvas 容器
- 加载 browser-canvas.js

5. 视觉反馈：
- 加载中显示 loading 动画
- 错误时显示友好提示
- 元素高亮时显示元素信息（标签、文本）

保持与现有 CSS 风格一致（services/web/css/index-v2.css）
```

---

## Prompt 4: 翻页配置模型

```
定义 SeenFetch 的翻页配置数据模型。

要求：
1. 创建 services/api/app/models/pagination.py

2. 定义枚举 PaginationType：
- CLICK_NEXT: 点击"下一页"
- CLICK_NUMBER: 点击页码
- INFINITE_SCROLL: 滚动加载
- LOAD_MORE: 点击"加载更多"
- URL_PATTERN: URL参数变化

3. 定义 PaginationConfig：
@dataclass / Pydantic BaseModel
- type: PaginationType
- next_button_selector: Optional[str]  # 下一页按钮选择器
- scroll_container: Optional[str]      # 滚动容器（默认 window）
- scroll_wait_ms: int = 2000          # 滚动后等待时间
- url_pattern: Optional[str]          # URL模式，如 "?page={n}"
- max_pages: int = 10                 # 最大页数
- stop_condition: Optional[str]       # 停止条件选择器

4. 定义 PaginationResult：
- pages_scraped: int
- total_items: int
- stopped_reason: str  # "max_pages" | "no_more_content" | "stop_condition" | "error"

5. JSON 序列化/反序列化支持

参考现有的 models 风格
```

---

## Prompt 5: 翻页检测器

```
实现 SeenFetch 的智能翻页方式检测。

要求：
1. 创建 services/api/app/services/pagination_detector.py

2. 实现 PaginationDetector 类：
- detect(page: Page) -> Optional[PaginationConfig]

3. 检测逻辑（按优先级）：

a. 检测"下一页"按钮：
   选择器模式列表：
   - 'a:has-text("下一页")', 'a:has-text("Next")'
   - 'button:has-text("下一页")', 'button:has-text("Next")'
   - '[class*="next"]:not([class*="prev"])'
   - '.pagination a:last-child'
   - '.ant-pagination-next', '.el-pagination__next'
   
b. 检测"加载更多"按钮：
   - 'button:has-text("加载更多")', 'button:has-text("Load More")'
   - '[class*="load-more"]', '[class*="loadmore"]'

c. 检测无限滚动：
   - 页面高度 > 视口高度 * 2
   - 存在 [data-infinite-scroll] 或 .infinite-scroll 元素

d. 检测 URL 分页：
   - URL 包含 page=, p=, pn=, offset= 等参数
   - 提取模式并生成 url_pattern

4. 返回检测结果时包含置信度：
   - PaginationConfig + confidence: float

5. 如果检测到多种方式，返回置信度最高的

测试用例：
- 豆瓣 Top250（点击下一页）
- 微博（无限滚动）
- 知乎（加载更多）
```

---

## Prompt 6: 翻页执行器

```
实现 SeenFetch 的翻页执行逻辑。

要求：
1. 创建 services/api/app/services/pagination_executor.py

2. 实现 PaginationExecutor 类：

class PaginationExecutor:
    def __init__(self, page: Page, config: PaginationConfig):
        ...
    
    async def has_next_page(self) -> bool:
        """检查是否还有下一页"""
    
    async def go_to_next_page(self) -> bool:
        """执行翻页，返回是否成功"""
    
    async def extract_all_pages(self, field_configs: List[FieldConfig]) -> List[Dict]:
        """循环翻页并提取所有数据"""

3. 各类型翻页实现：

CLICK_NEXT:
- 查找 next_button_selector
- 检查是否 disabled / hidden
- 点击并等待页面更新（监听 network idle 或新内容出现）

INFINITE_SCROLL:
- 滚动到底部
- 等待 scroll_wait_ms
- 检查是否有新内容加载（对比前后高度/元素数量）

LOAD_MORE:
- 类似 CLICK_NEXT，但通常不会跳转页面

URL_PATTERN:
- 解析当前页码
- 构造下一页 URL
- 导航到新 URL

4. 停止条件检查：
- 达到 max_pages
- stop_condition 选择器出现
- next_button 不存在或 disabled
- 连续2次无新内容

5. 数据合并：
- 每页数据追加到结果数组
- 可选：基于指定字段去重

6. 错误处理：
- 翻页失败时记录当前进度
- 返回已抓取的数据 + 错误信息
```

---

## Prompt 7: 前端翻页配置UI

```
为 SeenFetch 前端添加翻页配置界面。

要求：
1. 修改 services/web/index.html，在字段配置区域下方添加翻页配置区

2. 翻页配置UI包含：
- 翻页方式选择（下拉框）：
  - 不翻页
  - 点击下一页
  - 无限滚动
  - 加载更多
  - URL参数

- 根据选择显示不同配置：
  点击下一页：
  - "下一页按钮" 选择器输入框
  - "选择元素" 按钮（进入选择模式）
  
  无限滚动：
  - 等待时间（毫秒）
  
  URL参数：
  - URL模式输入框（带 {n} 占位符提示）

- 通用配置：
  - 最大页数（数字输入，默认10）
  - 停止条件选择器（可选）

3. 智能检测按钮：
- 点击后调用 /api/detect-pagination
- 自动填充检测到的配置
- 显示检测结果和置信度

4. 预览功能：
- "测试翻页" 按钮
- 执行一次翻页，显示结果
- 帮助用户验证配置正确

5. 保存配置：
- 翻页配置作为 Robot 的一部分保存

样式保持与现有设计一致，使用紫色主题色 #667eea
```

---

## Prompt 8: 集成测试

```
为 SeenFetch 翻页功能编写集成测试。

要求：
1. 创建 tests/test_pagination.py

2. 测试用例：

a. 翻页检测测试：
- test_detect_click_next: 测试检测点击下一页（用豆瓣Top250）
- test_detect_infinite_scroll: 测试检测无限滚动
- test_detect_url_pattern: 测试检测URL参数翻页

b. 翻页执行测试：
- test_click_next_pagination: 执行点击下一页，验证获取多页数据
- test_max_pages_limit: 验证达到最大页数时停止
- test_stop_condition: 验证停止条件生效

c. Session API 测试：
- test_create_session: 创建会话并获取截图
- test_execute_click: 执行点击操作
- test_session_timeout: 验证超时清理

3. 使用 pytest + pytest-asyncio
4. 使用实际网站测试（豆瓣 Top250 作为默认测试目标）
5. 测试失败时保存截图便于调试

示例：
```python
@pytest.mark.asyncio
async def test_detect_click_next():
    detector = PaginationDetector()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://movie.douban.com/top250")
        
        config = await detector.detect(page)
        
        assert config is not None
        assert config.type == PaginationType.CLICK_NEXT
        assert "下一页" in config.next_button_selector or "next" in config.next_button_selector.lower()
        
        await browser.close()
```
```

---

## 开发顺序建议

1. **Prompt 1 + 2**: Session Manager + API（后端基础）
2. **Prompt 3**: 前端 Canvas 改造（前后端打通）
3. **Prompt 4 + 5**: 翻页模型 + 检测器
4. **Prompt 6**: 翻页执行器
5. **Prompt 7**: 前端翻页配置UI
6. **Prompt 8**: 集成测试

每完成一步，先手动测试确认功能正常，再进行下一步。
