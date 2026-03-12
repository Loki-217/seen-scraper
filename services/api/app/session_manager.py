# services/api/app/session_manager.py
"""
V2 Session Manager - 管理 Playwright 浏览器会话池

核心功能：
- 创建和管理持久化浏览器会话
- 会话超时自动清理
- 执行用户操作（点击、滚动、输入等）
- 返回截图和可交互元素
"""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from .models_v2.actions import (
    Action,
    ActionType,
    ActionResult,
    InteractiveElement,
    CreateSessionResponse,
    PageInfo,
    SessionState,
)

# Windows 事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class BrowserSession:
    """单个浏览器会话"""

    def __init__(
        self,
        session_id: str,
        context: BrowserContext,
        page: Page,
        viewport: Dict[str, int]
    ):
        self.session_id = session_id
        self.context = context
        self.page = page
        self.viewport = viewport
        self.created_at = datetime.utcnow()
        self.last_active = datetime.utcnow()
        # CDP Screencast
        self.cdp_session = None
        self.screencast_active = False
        self.websockets: set = set()
        self.frame_count = 0
        self._last_frame: Optional[str] = None  # Cache latest frame for new WS clients

    def touch(self):
        """更新最后活动时间"""
        self.last_active = datetime.utcnow()

    def is_expired(self, timeout_seconds: int = 1800) -> bool:
        """检查会话是否过期（默认30分钟）"""
        return datetime.utcnow() - self.last_active > timedelta(seconds=timeout_seconds)

    async def screenshot(self, quality: int = 95) -> str:
        """获取页面截图(Base64 JPEG)"""
        self.touch()
        screenshot_bytes = await self.page.screenshot(
            type='jpeg',
            quality=quality,
            full_page=False
        )
        return base64.b64encode(screenshot_bytes).decode('utf-8')

    async def get_elements(self) -> List[InteractiveElement]:
        """获取页面上的所有可选择元素（包括文本、图片等）"""
        self.touch()

        # 注入获取元素的脚本
        elements_data = await self.page.evaluate('''
            () => {
                const elements = [];
                // 扩展选择器 - 包含所有常见内容元素
                const selectors = [
                    // 交互元素
                    'a[href]',
                    'button',
                    'input',
                    'select',
                    'textarea',
                    '[onclick]',
                    '[role="button"]',
                    '[role="link"]',
                    // 内容元素
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',  // 标题
                    'p',                                   // 段落
                    'li',                                  // 列表项
                    'td', 'th',                           // 表格单元格
                    'img',                                // 图片
                    'span',                               // 行内文本
                    'div',                                // 块级容器
                    'article', 'section',                 // 语义化容器
                    'label',                              // 标签
                    'time',                               // 时间
                    '[class*="price"]',                   // 价格相关
                    '[class*="title"]',                   // 标题相关
                    '[class*="name"]',                    // 名称相关
                    '[class*="desc"]',                    // 描述相关
                    '[class*="content"]',                 // 内容相关
                    '[class*="item"]',                    // 列表项相关
                    '[class*="card"]',                    // 卡片相关
                    '[data-*]'                            // data 属性元素
                ];

                // 生成唯一选择器
                function generateSelector(el) {
                    if (el.id) return '#' + CSS.escape(el.id);

                    // 使用 data 属性
                    for (const attr of el.attributes) {
                        if (attr.name.startsWith('data-') && attr.value) {
                            return `[${attr.name}="${CSS.escape(attr.value)}"]`;
                        }
                    }

                    // 使用类名
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ').filter(c => c && !c.includes('hover') && !c.includes('active'));
                        if (classes.length > 0) {
                            const selector = '.' + classes.slice(0, 2).map(c => CSS.escape(c)).join('.');
                            // 检查是否唯一
                            if (document.querySelectorAll(selector).length <= 10) {
                                return selector;
                            }
                        }
                    }

                    // 使用标签 + nth-child
                    const parent = el.parentElement;
                    if (parent) {
                        const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                        const index = siblings.indexOf(el) + 1;
                        const tagSelector = el.tagName.toLowerCase();
                        if (siblings.length === 1) {
                            return tagSelector;
                        }
                        return `${tagSelector}:nth-of-type(${index})`;
                    }

                    return el.tagName.toLowerCase();
                }

                // 获取元素类型
                function getElementType(el) {
                    const tag = el.tagName.toLowerCase();
                    if (tag === 'a') return 'link';
                    if (tag === 'button' || el.getAttribute('role') === 'button') return 'button';
                    if (tag === 'input' || tag === 'textarea' || tag === 'select') return 'input';
                    if (tag === 'img') return 'image';
                    if (['h1','h2','h3','h4','h5','h6'].includes(tag)) return 'heading';
                    if (tag === 'p') return 'paragraph';
                    if (tag === 'li') return 'list-item';
                    if (tag === 'td' || tag === 'th') return 'table-cell';
                    if (tag === 'span') return 'text';
                    if (tag === 'time') return 'time';
                    if (el.className && typeof el.className === 'string') {
                        if (el.className.includes('price')) return 'price';
                        if (el.className.includes('title')) return 'title';
                    }
                    return 'container';
                }

                // 检查元素是否有有意义的内容
                function hasContent(el) {
                    const tag = el.tagName.toLowerCase();
                    // 图片始终有意义
                    if (tag === 'img') return true;
                    // 输入框始终有意义
                    if (['input', 'textarea', 'select'].includes(tag)) return true;
                    // 链接和按钮始终有意义
                    if (tag === 'a' || tag === 'button') return true;
                    // 其他元素需要有文本内容
                    const text = (el.innerText || '').trim();
                    // 对于容器元素，要求直接文本内容（避免选中整个页面的大容器）
                    if (tag === 'div' || tag === 'section' || tag === 'article') {
                        // 只选择文本内容较短的 div（可能是具体数据）
                        return text.length > 0 && text.length < 200;
                    }
                    return text.length > 0;
                }

                const seen = new Set();

                selectors.forEach(selector => {
                    try {
                        document.querySelectorAll(selector).forEach(el => {
                            const rect = el.getBoundingClientRect();

                            // 过滤不可见元素
                            if (rect.width < 5 || rect.height < 5) return;
                            if (rect.top > window.innerHeight || rect.bottom < 0) return;
                            if (rect.left > window.innerWidth || rect.right < 0) return;

                            // 检查可见性
                            const style = window.getComputedStyle(el);
                            if (style.display === 'none' || style.visibility === 'hidden') return;
                            if (parseFloat(style.opacity) < 0.1) return;

                            // 检查是否有内容
                            if (!hasContent(el)) return;

                            const elSelector = generateSelector(el);

                            // 避免重复
                            const key = `${Math.round(rect.x)},${Math.round(rect.y)},${rect.width},${rect.height}`;
                            if (seen.has(key)) return;
                            seen.add(key);

                            elements.push({
                                selector: elSelector,
                                rect: {
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height
                                },
                                tag: el.tagName.toLowerCase(),
                                text: (el.innerText || el.value || el.alt || el.title || '').substring(0, 50).trim(),
                                element_type: getElementType(el),
                                href: el.href || null,
                                src: el.src || null,
                                placeholder: el.placeholder || null,
                                value: el.value || null
                            });
                        });
                    } catch(e) {
                        // 忽略无效选择器
                    }
                });

                // 按位置排序（从上到下，从左到右）
                elements.sort((a, b) => {
                    if (Math.abs(a.rect.y - b.rect.y) > 20) return a.rect.y - b.rect.y;
                    return a.rect.x - b.rect.x;
                });

                return elements.slice(0, 1000);  // 最多返回1000个元素
            }
        ''')

        return [InteractiveElement(**el) for el in elements_data]

    async def execute_action(self, action: Action) -> ActionResult:
        """执行操作"""
        self.touch()

        try:
            if action.type == ActionType.CLICK:
                await self._do_click(action)
            elif action.type == ActionType.SCROLL:
                await self._do_scroll(action)
            elif action.type == ActionType.INPUT:
                await self._do_input(action)
            elif action.type == ActionType.WAIT:
                await self._do_wait(action)
            elif action.type == ActionType.HOVER:
                await self._do_hover(action)
            elif action.type == ActionType.NAVIGATE:
                await self._do_navigate(action)
            elif action.type == ActionType.SCREENSHOT:
                pass  # 只截图，无其他操作

            # 等待页面稳定
            await asyncio.sleep(0.3)

            # 返回结果
            screenshot = await self.screenshot()
            elements = await self.get_elements()

            return ActionResult(
                success=True,
                screenshot_base64=screenshot,
                url=self.page.url,
                title=await self.page.title(),
                elements=elements,
                action_type=action.type.value
            )

        except Exception as e:
            # 即使出错也尝试返回截图
            try:
                screenshot = await self.screenshot()
            except:
                screenshot = ""

            return ActionResult(
                success=False,
                screenshot_base64=screenshot,
                url=self.page.url,
                title="",
                elements=[],
                error=f"操作失败: {str(e)}",
                action_type=action.type.value if action.type else None
            )

    async def _do_click(self, action: Action):
        """执行点击"""
        if action.selector:
            await self.page.click(action.selector, timeout=5000)
        elif action.x is not None and action.y is not None:
            await self.page.mouse.click(action.x, action.y)
        else:
            raise ValueError("点击操作需要提供 selector 或 x/y 坐标")

        # 等待可能的导航或动画
        try:
            await self.page.wait_for_load_state("networkidle", timeout=3000)
        except:
            pass

    async def _do_scroll(self, action: Action):
        """执行滚动"""
        distance = action.distance or 300
        direction = action.direction or "down"

        if direction == "down":
            await self.page.mouse.wheel(0, distance)
        elif direction == "up":
            await self.page.mouse.wheel(0, -distance)
        elif direction == "right":
            await self.page.mouse.wheel(distance, 0)
        elif direction == "left":
            await self.page.mouse.wheel(-distance, 0)

        await asyncio.sleep(0.5)  # 等待滚动动画

    async def _do_input(self, action: Action):
        """执行输入"""
        if not action.selector:
            raise ValueError("输入操作需要提供 selector")

        if action.clear_first:
            await self.page.fill(action.selector, action.text or "")
        else:
            await self.page.type(action.selector, action.text or "")

    async def _do_wait(self, action: Action):
        """执行等待"""
        if action.wait_selector:
            await self.page.wait_for_selector(action.wait_selector, timeout=action.wait_ms or 10000)
        elif action.wait_ms:
            await asyncio.sleep(action.wait_ms / 1000)

    async def _do_hover(self, action: Action):
        """执行悬停"""
        if action.selector:
            await self.page.hover(action.selector)
        elif action.x is not None and action.y is not None:
            await self.page.mouse.move(action.x, action.y)

    async def _do_navigate(self, action: Action):
        """执行导航"""
        if not action.url:
            raise ValueError("导航操作需要提供 url")
        await self.page.goto(action.url, wait_until="networkidle", timeout=30000)

    # ---------- CDP Screencast ----------

    async def start_screencast(self, quality: int = 80, max_width: int = 1280, max_height: int = 800):
        """Start CDP Screencast frame push"""
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

    async def _on_screencast_frame(self, params: dict):
        """Broadcast frame to all connected WebSocket clients"""
        await self.cdp_session.send("Page.screencastFrameAck", {
            "sessionId": params["sessionId"]
        })
        self.frame_count += 1
        self.touch()

        message = json.dumps({
            "type": "frame",
            "data": params["data"],
            "metadata": params.get("metadata", {})
        })
        self._last_frame = message  # Cache for new clients

        dead_sockets = set()
        for ws in self.websockets:
            try:
                await ws.send_text(message)
            except Exception:
                dead_sockets.add(ws)
        self.websockets -= dead_sockets

    async def stop_screencast(self):
        """Stop CDP Screencast"""
        if self.cdp_session and self.screencast_active:
            try:
                await self.cdp_session.send("Page.stopScreencast")
            except Exception:
                pass
            self.screencast_active = False

    async def inject_input(self, event: dict):
        """Inject mouse/keyboard events via CDP"""
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

    async def add_websocket(self, ws):
        self.websockets.add(ws)
        # Send cached last frame so the client sees something immediately
        if self._last_frame:
            try:
                await ws.send_text(self._last_frame)
            except Exception:
                pass

    async def remove_websocket(self, ws):
        self.websockets.discard(ws)

    async def close(self):
        """关闭会话"""
        await self.stop_screencast()
        try:
            if self.cdp_session:
                await self.cdp_session.detach()
        except:
            pass
        try:
            await self.page.close()
        except:
            pass
        try:
            await self.context.close()
        except:
            pass


class SessionManager:
    """
    会话池管理器 - 单例模式

    功能：
    - 管理多个 Playwright 浏览器会话
    - 自动清理过期会话
    - 限制最大并发会话数
    """

    _instance: Optional['SessionManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.sessions: Dict[str, BrowserSession] = {}
        self.max_sessions: int = 10
        self.session_timeout: int = 1800  # 30分钟
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._initialized = True

    async def start(self):
        """启动 Session Manager"""
        if self.playwright is not None:
            return

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
            ]
        )

        # 启动清理任务
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        print(f"[SessionManager] 启动完成，最大会话数: {self.max_sessions}")

    async def stop(self):
        """停止 Session Manager"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 关闭所有会话
        for session in list(self.sessions.values()):
            await session.close()
        self.sessions.clear()

        # 关闭浏览器
        if self.browser:
            await self.browser.close()
            self.browser = None

        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        print("[SessionManager] 已停止")

    async def create_session(
        self,
        url: str,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        wait_for: Optional[str] = None,
        timeout_ms: int = 30000
    ) -> CreateSessionResponse:
        """创建新会话"""
        await self.start()

        # 检查会话数量限制
        if len(self.sessions) >= self.max_sessions:
            # 清理最旧的过期会话
            await self.cleanup_expired()
            if len(self.sessions) >= self.max_sessions:
                # 强制关闭最旧的会话
                oldest = min(self.sessions.values(), key=lambda s: s.last_active)
                await self.close_session(oldest.session_id)

        session_id = str(uuid.uuid4())
        viewport = {"width": viewport_width, "height": viewport_height}

        # 创建新的浏览器上下文
        context = await self.browser.new_context(
            viewport=viewport,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )

        page = await context.new_page()

        # 注入反检测脚本
        await page.add_init_script('''
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
        ''')

        # 导航到目标页面
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)

            # 等待特定选择器
            if wait_for:
                await page.wait_for_selector(wait_for, timeout=10000)

        except Exception as e:
            await context.close()
            raise RuntimeError(f"页面加载失败: {str(e)}")

        # 创建会话对象
        session = BrowserSession(
            session_id=session_id,
            context=context,
            page=page,
            viewport=viewport
        )

        self.sessions[session_id] = session

        # Start CDP Screencast
        await session.start_screencast(
            quality=80,
            max_width=viewport_width,
            max_height=viewport_height
        )

        # Get initial state
        elements = await session.get_elements()
        title = await page.title()

        print(f"[SessionManager] 创建会话 {session_id[:8]}... URL: {url} (CDP Screencast)")

        return CreateSessionResponse(
            session_id=session_id,
            screenshot="",  # Frames are pushed via WebSocket now
            elements=elements,
            page_info=PageInfo(
                url=page.url,
                title=title,
                viewport=viewport
            )
        )

    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """获取会话"""
        session = self.sessions.get(session_id)
        if session:
            session.touch()
        return session

    async def execute_action(self, session_id: str, action: Action) -> ActionResult:
        """在指定会话中执行操作"""
        session = self.get_session(session_id)
        if not session:
            return ActionResult(
                success=False,
                screenshot_base64="",
                url="",
                title="",
                elements=[],
                error=f"会话不存在或已过期: {session_id}"
            )

        return await session.execute_action(action)

    async def get_state(self, session_id: str) -> Optional[SessionState]:
        """获取会话状态"""
        session = self.get_session(session_id)
        if not session:
            return None

        try:
            screenshot = await session.screenshot()
            elements = await session.get_elements()
            title = await session.page.title()

            return SessionState(
                session_id=session_id,
                url=session.page.url,
                title=title,
                screenshot=screenshot,
                elements=elements,
                created_at=session.created_at.isoformat(),
                last_active=session.last_active.isoformat(),
                is_active=True
            )
        except Exception as e:
            return SessionState(
                session_id=session_id,
                url="",
                title="",
                screenshot="",
                elements=[],
                created_at=session.created_at.isoformat(),
                last_active=session.last_active.isoformat(),
                is_active=False
            )

    async def close_session(self, session_id: str) -> bool:
        """关闭指定会话"""
        session = self.sessions.pop(session_id, None)
        if session:
            await session.close()
            print(f"[SessionManager] 关闭会话 {session_id[:8]}...")
            return True
        return False

    async def cleanup_expired(self) -> int:
        """清理过期会话"""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.session_timeout)
        ]

        for sid in expired:
            await self.close_session(sid)

        if expired:
            print(f"[SessionManager] 清理了 {len(expired)} 个过期会话")

        return len(expired)

    async def _cleanup_loop(self):
        """定期清理过期会话"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[SessionManager] 清理任务出错: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "active_sessions": len(self.sessions),
            "max_sessions": self.max_sessions,
            "session_timeout": self.session_timeout,
            "sessions": [
                {
                    "id": sid[:8] + "...",
                    "created_at": s.created_at.isoformat(),
                    "last_active": s.last_active.isoformat(),
                    "url": s.page.url[:50] + "..." if len(s.page.url) > 50 else s.page.url
                }
                for sid, s in self.sessions.items()
            ]
        }


# 全局单例
session_manager = SessionManager()


# 便捷的上下文管理器
@asynccontextmanager
async def get_session_manager():
    """获取 Session Manager 实例"""
    await session_manager.start()
    try:
        yield session_manager
    finally:
        pass  # 不在这里停止，让应用生命周期管理
