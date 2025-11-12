# services/api/app/live_browser.py
"""
实时浏览服务 - 基于Playwright + CDP的流式浏览器
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from pydantic import BaseModel
from typing import Dict, Optional, Any
import asyncio
import sys
import json
import logging
import time
from datetime import datetime

# 🔥 Windows修复：强制使用ProactorEventLoop（支持子进程）
if sys.platform == 'win32':
    # 设置全局策略
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# 导入Cookie管理器
from .cookie_manager import cookie_manager

router = APIRouter(prefix="/api/live", tags=["live-browser"])

logger = logging.getLogger(__name__)

# 配置
MAX_CONCURRENT_SESSIONS = 5  # 最大并发会话数
SESSION_TIMEOUT = 300  # 会话超时时间（秒）


class BrowserSession:
    """浏览器会话 - 管理单个用户的浏览器实例"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.cdp_session = None
        self.playwright = None

        self.is_streaming = False
        self.is_browse_mode = False  # 浏览模式开关
        self.current_url = ""
        self.current_domain = ""

        self.created_at = time.time()
        self.last_activity = time.time()

        logger.info(f"[Session {session_id}] 创建浏览器会话")

    async def start(self, url: str, use_cookies: bool = True):
        """启动浏览器会话"""
        try:
            # 🔥 Windows修复：确保当前协程运行在ProactorEventLoop中
            if sys.platform == 'win32':
                loop = asyncio.get_running_loop()
                loop_type = type(loop).__name__
                if 'Selector' in loop_type:
                    logger.error(f"[Session {self.session_id}] ❌ 检测到SelectorEventLoop，Playwright需要ProactorEventLoop")
                    raise RuntimeError("Windows平台需要ProactorEventLoop才能运行Playwright（支持子进程）")
                logger.info(f"[Session {self.session_id}] ✅ 事件循环类型: {loop_type}")

            self.current_url = url
            self.current_domain = self._extract_domain(url)

            logger.info(f"[Session {self.session_id}] 启动浏览器: {url}")

            # 启动Playwright
            self.playwright = await async_playwright().start()

            # 启动浏览器
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',  # 减少内存使用
                    '--disable-blink-features=AutomationControlled',  # 反检测
                ]
            )

            # 创建浏览器上下文
            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            # 如果需要使用Cookie，注入已保存的Cookie
            if use_cookies:
                await self._inject_cookies()

            # 创建页面
            self.page = await self.context.new_page()

            # 获取CDP会话
            self.cdp_session = await self.context.new_cdp_session(self.page)

            # 导航到URL
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # 等待页面稳定
            await asyncio.sleep(1)

            logger.info(f"[Session {self.session_id}] 浏览器启动成功")
            self.last_activity = time.time()

        except Exception as e:
            logger.error(f"[Session {self.session_id}] 启动失败: {e}", exc_info=True)
            await self.cleanup()
            raise

    async def _inject_cookies(self):
        """注入已保存的Cookie"""
        try:
            cookies = await cookie_manager.get_cookies(self.current_domain)
            if cookies:
                await self.context.add_cookies(cookies)
                logger.info(f"[Session {self.session_id}] 注入 {len(cookies)} 个Cookie")
        except Exception as e:
            logger.warning(f"[Session {self.session_id}] Cookie注入失败: {e}")

    async def start_screencast(self, websocket: WebSocket):
        """开始屏幕录制并流式传输"""
        if not self.cdp_session or not self.page:
            raise RuntimeError("浏览器未初始化")

        self.is_streaming = True

        # 定义帧接收回调
        async def on_screencast_frame(params):
            if not self.is_streaming:
                return

            try:
                frame_data = params.get('data')  # base64 JPEG
                session_id_cdp = params.get('sessionId')
                metadata = params.get('metadata', {})

                # 发送帧到前端
                await websocket.send_json({
                    'type': 'frame',
                    'data': frame_data,
                    'metadata': {
                        'timestamp': time.time(),
                        'url': self.page.url,
                        **metadata
                    }
                })

                # 确认帧接收（重要！否则Chrome会停止发送）
                await self.cdp_session.send('Page.screencastFrameAck', {
                    'sessionId': session_id_cdp
                })

                self.last_activity = time.time()

            except Exception as e:
                logger.error(f"[Session {self.session_id}] 帧处理错误: {e}")

        # 监听screencast帧事件
        self.cdp_session.on('Page.screencastFrame', on_screencast_frame)

        # 启动screencast
        await self.cdp_session.send('Page.startScreencast', {
            'format': 'jpeg',
            'quality': 75,  # JPEG质量 (60-90推荐)
            'everyNthFrame': 1,  # 每帧都发送（可改为2-3降低带宽）
            'maxWidth': 1280,
            'maxHeight': 720
        })

        logger.info(f"[Session {self.session_id}] Screencast已启动")

        # 如果不是浏览模式，注入高亮脚本
        if not self.is_browse_mode:
            await self._inject_highlight_script()

    async def _inject_highlight_script(self):
        """注入高亮脚本（爬取模式）"""
        try:
            highlight_script = """
            (function() {
                if (window.__seenfetch_injected) return;
                window.__seenfetch_injected = true;

                console.log('[SeenFetch] 高亮脚本已注入');

                // 添加高亮样式
                const style = document.createElement('style');
                style.innerHTML = `
                    .seenfetch-highlight {
                        outline: 2px solid #4CAF50 !important;
                        outline-offset: 2px !important;
                        cursor: pointer !important;
                        transition: all 0.2s !important;
                    }
                    .seenfetch-highlight:hover {
                        outline-color: #FF5722 !important;
                        outline-width: 3px !important;
                    }
                `;
                document.head.appendChild(style);

                // 高亮可点击元素
                const selectableElements = document.querySelectorAll('a, button, input, select, textarea, [onclick], [role="button"]');
                selectableElements.forEach(el => {
                    el.classList.add('seenfetch-highlight');
                });

                // 监听点击事件
                document.addEventListener('click', function(e) {
                    const element = e.target;

                    // 收集元素信息
                    const info = {
                        tagName: element.tagName.toLowerCase(),
                        text: (element.innerText || element.textContent || '').substring(0, 200),
                        href: element.href || '',
                        src: element.src || '',
                        id: element.id || '',
                        className: element.className || '',
                        xpath: getXPath(element)
                    };

                    console.log('[SeenFetch] 元素被点击:', info);

                    // 通过CDP发送消息（后端会接收到Runtime.consoleAPICalled事件）
                    window.__seenfetch_clicked = info;

                }, true);

                // 获取XPath的辅助函数
                function getXPath(element) {
                    if (element.id !== '') {
                        return '//*[@id="' + element.id + '"]';
                    }
                    if (element === document.body) {
                        return '/html/body';
                    }
                    let ix = 0;
                    const siblings = element.parentNode.childNodes;
                    for (let i = 0; i < siblings.length; i++) {
                        const sibling = siblings[i];
                        if (sibling === element) {
                            return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        }
                        if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                            ix++;
                        }
                    }
                }
            })();
            """

            await self.page.evaluate(highlight_script)
            logger.info(f"[Session {self.session_id}] 高亮脚本注入成功")

        except Exception as e:
            logger.error(f"[Session {self.session_id}] 高亮脚本注入失败: {e}")

    async def remove_highlight_script(self):
        """移除高亮脚本（切换到浏览模式）"""
        try:
            remove_script = """
            (function() {
                // 移除高亮样式
                document.querySelectorAll('.seenfetch-highlight').forEach(el => {
                    el.classList.remove('seenfetch-highlight');
                });

                console.log('[SeenFetch] 高亮脚本已移除');
            })();
            """
            await self.page.evaluate(remove_script)
            logger.info(f"[Session {self.session_id}] 高亮脚本已移除")

        except Exception as e:
            logger.error(f"[Session {self.session_id}] 移除高亮脚本失败: {e}")

    async def handle_interaction(self, action: dict):
        """处理用户交互"""
        if not self.page:
            return

        try:
            action_type = action.get('type')

            if action_type == 'click':
                x, y = action['x'], action['y']
                await self.page.mouse.click(x, y)
                logger.info(f"[Session {self.session_id}] 点击 ({x}, {y})")

            elif action_type == 'type':
                text = action['text']
                await self.page.keyboard.type(text)
                logger.info(f"[Session {self.session_id}] 输入: {text}")

            elif action_type == 'press':
                key = action['key']
                await self.page.keyboard.press(key)
                logger.info(f"[Session {self.session_id}] 按键: {key}")

            elif action_type == 'scroll':
                delta_y = action.get('deltaY', 0)
                await self.page.mouse.wheel(0, delta_y)
                logger.info(f"[Session {self.session_id}] 滚动: {delta_y}")

            elif action_type == 'navigate':
                url = action['url']
                await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
                self.current_url = url
                self.current_domain = self._extract_domain(url)
                logger.info(f"[Session {self.session_id}] 导航到: {url}")

            elif action_type == 'toggle_browse_mode':
                self.is_browse_mode = action.get('enabled', False)
                if self.is_browse_mode:
                    await self.remove_highlight_script()
                else:
                    await self._inject_highlight_script()
                logger.info(f"[Session {self.session_id}] 浏览模式: {self.is_browse_mode}")

            self.last_activity = time.time()

        except Exception as e:
            logger.error(f"[Session {self.session_id}] 交互处理失败: {e}", exc_info=True)

    async def extract_cookies(self) -> list:
        """提取当前浏览器的Cookie"""
        if not self.context:
            return []

        try:
            cookies = await self.context.cookies()
            logger.info(f"[Session {self.session_id}] 提取到 {len(cookies)} 个Cookie")
            return cookies
        except Exception as e:
            logger.error(f"[Session {self.session_id}] Cookie提取失败: {e}")
            return []

    async def save_cookies(self):
        """保存Cookie到数据库"""
        try:
            cookies = await self.extract_cookies()
            if cookies:
                # 筛选出当前域名的Cookie
                domain_cookies = [c for c in cookies if self.current_domain in c.get('domain', '')]
                if domain_cookies:
                    await cookie_manager.save_cookies(self.current_domain, domain_cookies)
                    logger.info(f"[Session {self.session_id}] 保存 {len(domain_cookies)} 个Cookie到数据库")
                    return len(domain_cookies)
            return 0
        except Exception as e:
            logger.error(f"[Session {self.session_id}] Cookie保存失败: {e}")
            return 0

    async def get_page_info(self) -> dict:
        """获取当前页面信息"""
        if not self.page:
            return {}

        try:
            return {
                'url': self.page.url,
                'title': await self.page.title(),
                'domain': self.current_domain
            }
        except:
            return {}

    def _extract_domain(self, url: str) -> str:
        """提取域名"""
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if ':' in domain:
                domain = domain.split(':')[0]
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ''

    async def stop(self):
        """停止屏幕录制"""
        self.is_streaming = False

        if self.cdp_session:
            try:
                await self.cdp_session.send('Page.stopScreencast')
                logger.info(f"[Session {self.session_id}] Screencast已停止")
            except:
                pass

    async def cleanup(self):
        """清理资源"""
        logger.info(f"[Session {self.session_id}] 开始清理资源")

        self.is_streaming = False

        try:
            if self.cdp_session:
                await self.cdp_session.detach()
        except:
            pass

        try:
            if self.page:
                await self.page.close()
        except:
            pass

        try:
            if self.context:
                await self.context.close()
        except:
            pass

        try:
            if self.browser:
                await self.browser.close()
        except:
            pass

        try:
            if self.playwright:
                await self.playwright.stop()
        except:
            pass

        logger.info(f"[Session {self.session_id}] 资源清理完成")


# 全局会话管理
active_sessions: Dict[str, BrowserSession] = {}
session_lock = asyncio.Lock()


async def cleanup_idle_sessions():
    """清理空闲会话（后台任务）"""
    while True:
        try:
            await asyncio.sleep(60)  # 每分钟检查一次

            current_time = time.time()
            sessions_to_remove = []

            async with session_lock:
                for session_id, session in active_sessions.items():
                    # 超时判断
                    if current_time - session.last_activity > SESSION_TIMEOUT:
                        sessions_to_remove.append(session_id)
                        logger.info(f"[Session {session_id}] 超时，准备清理")

                # 清理超时会话
                for session_id in sessions_to_remove:
                    session = active_sessions.pop(session_id, None)
                    if session:
                        await session.cleanup()

            if sessions_to_remove:
                logger.info(f"清理了 {len(sessions_to_remove)} 个超时会话")

        except Exception as e:
            logger.error(f"清理空闲会话失败: {e}", exc_info=True)


@router.websocket("/ws/browser/{session_id}")
async def live_browser_websocket(websocket: WebSocket, session_id: str):
    """WebSocket端点 - 实时浏览器流"""

    # 检查并发限制
    async with session_lock:
        if len(active_sessions) >= MAX_CONCURRENT_SESSIONS:
            await websocket.close(code=1008, reason='服务器繁忙，请稍后重试')
            logger.warning(f"[Session {session_id}] 拒绝连接：超过最大并发数")
            return

    await websocket.accept()
    logger.info(f"[Session {session_id}] WebSocket连接已接受")

    session = BrowserSession(session_id)

    async with session_lock:
        active_sessions[session_id] = session

    try:
        # 等待前端发送初始化信息
        init_data = await websocket.receive_json()
        url = init_data.get('url', 'https://www.baidu.com')
        use_cookies = init_data.get('use_cookies', True)

        logger.info(f"[Session {session_id}] 收到初始化请求: {url}")

        # 启动浏览器会话
        await session.start(url, use_cookies=use_cookies)

        # 开始屏幕录制
        await session.start_screencast(websocket)

        # 发送就绪信号
        page_info = await session.get_page_info()
        await websocket.send_json({
            'type': 'ready',
            'session_id': session_id,
            'page_info': page_info
        })

        logger.info(f"[Session {session_id}] 就绪信号已发送")

        # 持续监听前端消息（用户交互）
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=1.0  # 1秒超时，用于定期检查会话状态
                )

                msg_type = message.get('type')

                if msg_type == 'action':
                    await session.handle_interaction(message.get('data', {}))

                elif msg_type == 'save_cookies':
                    count = await session.save_cookies()
                    await websocket.send_json({
                        'type': 'cookies_saved',
                        'count': count
                    })

                elif msg_type == 'get_page_info':
                    page_info = await session.get_page_info()
                    await websocket.send_json({
                        'type': 'page_info',
                        'data': page_info
                    })

                elif msg_type == 'close':
                    logger.info(f"[Session {session_id}] 收到关闭请求")
                    break

            except asyncio.TimeoutError:
                # 超时是正常的，继续循环
                continue
            except WebSocketDisconnect:
                logger.info(f"[Session {session_id}] WebSocket断开")
                break

    except Exception as e:
        logger.error(f"[Session {session_id}] WebSocket错误: {e}", exc_info=True)
        try:
            await websocket.send_json({
                'type': 'error',
                'message': str(e)
            })
        except:
            pass

    finally:
        # 清理资源
        logger.info(f"[Session {session_id}] 开始清理会话")

        await session.cleanup()

        async with session_lock:
            if session_id in active_sessions:
                del active_sessions[session_id]

        logger.info(f"[Session {session_id}] 会话已清理，当前活跃会话数: {len(active_sessions)}")


@router.get("/sessions")
async def get_active_sessions():
    """获取当前活跃会话列表（调试用）"""
    sessions_info = []
    async with session_lock:
        for session_id, session in active_sessions.items():
            sessions_info.append({
                'session_id': session_id,
                'url': session.current_url,
                'domain': session.current_domain,
                'is_streaming': session.is_streaming,
                'is_browse_mode': session.is_browse_mode,
                'created_at': datetime.fromtimestamp(session.created_at).isoformat(),
                'last_activity': datetime.fromtimestamp(session.last_activity).isoformat(),
                'idle_seconds': int(time.time() - session.last_activity)
            })

    return {
        'count': len(sessions_info),
        'max_concurrent': MAX_CONCURRENT_SESSIONS,
        'sessions': sessions_info
    }


# 启动清理任务（在应用启动时调用）
cleanup_task = None

async def start_cleanup_task():
    """启动清理任务"""
    global cleanup_task
    if cleanup_task is None:
        cleanup_task = asyncio.create_task(cleanup_idle_sessions())
        logger.info("会话清理任务已启动")
