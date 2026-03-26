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

        try:
            elements_data = await self._get_elements_evaluate()
        except Exception as e:
            error_msg = str(e)
            if "Execution context was destroyed" in error_msg or "navigation" in error_msg.lower():
                # Page is navigating — return empty list, will refresh after navigation completes
                return []
            raise
        return [InteractiveElement(**el) for el in elements_data]

    async def _get_elements_evaluate(self):
        """Inner evaluate call for get_elements — separated for navigation-safe wrapping"""
        # 注入获取元素的脚本
        return await self.page.evaluate('''
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
                    // If element has a unique ID, use it directly
                    if (el.id && document.querySelectorAll('#' + CSS.escape(el.id)).length === 1) {
                        return '#' + CSS.escape(el.id);
                    }

                    // Try short selector first: class-based, only if globally unique
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ').filter(c => c && !c.includes('hover') && !c.includes('active'));
                        if (classes.length > 0) {
                            const shortSel = el.tagName.toLowerCase() + '.' + classes.slice(0, 2).map(c => CSS.escape(c)).join('.');
                            if (document.querySelectorAll(shortSel).length === 1) {
                                return shortSel;
                            }
                        }
                    }

                    // Build absolute path from element up to body
                    const parts = [];
                    let cur = el;
                    while (cur && cur !== document.body && cur !== document.documentElement) {
                        let seg = cur.tagName.toLowerCase();
                        if (cur.id && document.querySelectorAll('#' + CSS.escape(cur.id)).length === 1) {
                            parts.unshift('#' + CSS.escape(cur.id));
                            break;
                        }
                        if (cur.className && typeof cur.className === 'string' && cur.className.trim()) {
                            const cls = cur.className.trim().split(/\\s+/).filter(c => c && c.length < 30).slice(0, 2);
                            if (cls.length) seg += '.' + cls.map(c => CSS.escape(c)).join('.');
                        }
                        const parent = cur.parentElement;
                        if (parent) {
                            const sibs = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
                            if (sibs.length > 1) {
                                seg += ':nth-of-type(' + (sibs.indexOf(cur) + 1) + ')';
                            }
                        }
                        parts.unshift(seg);
                        cur = cur.parentElement;
                    }
                    return parts.join(' > ');
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
                                value: el.value || null,
                                innerHTML: (el.innerHTML || '').substring(0, 100),
                                hasChildElements: el.children.length > 0
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

        # Listen for page navigation — notify frontend of URL changes
        self.page.on("load", lambda: asyncio.ensure_future(self._on_page_navigated()))

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

    async def _on_page_navigated(self):
        """Called after page navigation completes — notify frontend of new URL"""
        try:
            await asyncio.sleep(0.5)  # Let page stabilize
            url = self.page.url
            title = await self.page.title()
            message = json.dumps({
                "type": "pageInfo",
                "url": url,
                "title": title
            })
            dead_sockets = set()
            for ws in self.websockets:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead_sockets.add(ws)
            self.websockets -= dead_sockets
        except Exception:
            pass  # Page may still be loading — safe to ignore

    # ---------- List Detection Script Injection ----------

    _LIST_DETECTION_SCRIPT = '''
    (() => {
        if (window.__seenfetch_list_detection_active) return;
        window.__seenfetch_list_detection_active = true;
        window.__seenfetch_detected_list = null;

        const STYLE_ID = '__seenfetch_list_style';
        const HIGHLIGHT_ATTR = 'data-seenfetch-list-item';
        const LABEL_CLASS = '__seenfetch_label';

        // Inject highlight styles
        const style = document.createElement('style');
        style.id = STYLE_ID;
        style.textContent = `
            [${HIGHLIGHT_ATTR}] {
                outline: 2px dashed rgba(102, 126, 234, 0.7) !important;
                outline-offset: -1px !important;
            }
            .__seenfetch_label {
                position: absolute;
                top: 0; left: 0;
                background: rgba(102, 126, 234, 0.85);
                color: #fff;
                font-size: 10px;
                padding: 1px 5px;
                border-radius: 0 0 4px 0;
                pointer-events: none;
                z-index: 2147483647;
                font-family: sans-serif;
                line-height: 16px;
            }
        `;
        document.head.appendChild(style);

        // Structure similarity: tagName + first 2 classes
        function structureKey(el) {
            const tag = el.tagName;
            const cls = (el.className || '').toString().split(' ')
                .filter(c => c && !/\\d{3,}/.test(c))
                .sort().slice(0, 2).join(',');
            return tag + ':' + cls;
        }

        // Generate a CSS selector for an element
        function genSelector(el) {
            if (el.id) return '#' + CSS.escape(el.id);
            if (el.className && typeof el.className === 'string') {
                const cls = el.className.split(' ')
                    .filter(c => c && !/\\d{3,}/.test(c) && !c.includes('hover') && !c.includes('active'))
                    .slice(0, 2);
                if (cls.length) {
                    const sel = el.tagName.toLowerCase() + '.' + cls.map(c => CSS.escape(c)).join('.');
                    if (document.querySelectorAll(sel).length >= 1) return sel;
                }
            }
            const parent = el.parentElement;
            if (parent) {
                const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                if (siblings.length === 1) return el.tagName.toLowerCase();
                return el.tagName.toLowerCase() + ':nth-of-type(' + (siblings.indexOf(el) + 1) + ')';
            }
            return el.tagName.toLowerCase();
        }

        // Generate a container-relative selector
        function genContainerSelector(container) {
            const parts = [];
            let el = container;
            while (el && el !== document.body && parts.length < 4) {
                if (el.id) { parts.unshift('#' + CSS.escape(el.id)); break; }
                const parent = el.parentElement;
                if (!parent) break;
                const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
                let sel = el.tagName.toLowerCase();
                if (el.className && typeof el.className === 'string') {
                    const cls = el.className.split(' ')
                        .filter(c => c && !/\\d{3,}/.test(c) && !c.includes('hover') && !c.includes('active'))
                        .slice(0, 2);
                    if (cls.length) sel += '.' + cls.map(c => CSS.escape(c)).join('.');
                } else if (siblings.length > 1) {
                    sel += ':nth-of-type(' + (siblings.indexOf(el) + 1) + ')';
                }
                parts.unshift(sel);
                el = parent;
            }
            return parts.join(' > ');
        }

        function clearHighlights() {
            document.querySelectorAll('[' + HIGHLIGHT_ATTR + ']').forEach(el => {
                el.removeAttribute(HIGHLIGHT_ATTR);
            });
            document.querySelectorAll('.' + LABEL_CLASS).forEach(el => el.remove());
        }

        let lastTarget = null;
        let throttleTimer = null;

        function onMouseMove(e) {
            if (throttleTimer) return;
            throttleTimer = setTimeout(() => { throttleTimer = null; }, 200);

            const target = e.target;
            if (target === lastTarget) return;
            lastTarget = target;

            clearHighlights();
            window.__seenfetch_detected_list = null;

            // Get parent container
            const parent = target.parentElement;
            if (!parent || parent === document.body || parent === document.documentElement) return;

            // Get structure key of target
            const targetKey = structureKey(target);

            // Find siblings with same structure
            const children = Array.from(parent.children);
            const similar = children.filter(c => structureKey(c) === targetKey);

            if (similar.length < 2) return;

            // Highlight similar items
            similar.forEach((el, i) => {
                el.setAttribute(HIGHLIGHT_ATTR, '');
                // Add label
                const rect = el.getBoundingClientRect();
                const label = document.createElement('div');
                label.className = LABEL_CLASS;
                label.textContent = 'Item ' + (i + 1);
                label.style.position = 'fixed';
                label.style.top = rect.top + 'px';
                label.style.left = rect.left + 'px';
                document.body.appendChild(label);
            });

            // Build item selector
            const itemSel = genSelector(similar[0]);
            const containerSel = genContainerSelector(parent);
            const fullItemSelector = containerSel + ' > ' + itemSel.split(':nth-of-type')[0];

            // Detect field selectors from the first item
            const detectedFields = [];
            const firstItem = similar[0];
            const titleSels = ['h1','h2','h3','h4','h5','h6','[class*="title"]','[class*="name"]'];
            for (const sel of titleSels) {
                const el = firstItem.querySelector(sel);
                if (el && el.textContent.trim()) {
                    detectedFields.push({ name: 'title', selector: sel, attr: 'text', type: 'text' });
                    break;
                }
            }
            const linkEl = firstItem.querySelector('a[href]');
            if (linkEl && linkEl.href) {
                detectedFields.push({ name: 'url', selector: 'a[href]', attr: 'href', type: 'link' });
            }
            const imgEl = firstItem.querySelector('img');
            if (imgEl) {
                detectedFields.push({ name: 'image', selector: 'img', attr: 'src', type: 'image' });
            }
            // Price detection
            const priceEl = firstItem.querySelector('[class*="price"],[class*="cost"],[class*="amount"]');
            if (priceEl && priceEl.textContent.trim()) {
                const priceSel = priceEl.className ? '.' + priceEl.className.split(/\s+/).filter(c => /price|cost|amount/i.test(c))[0] : '[class*="price"]';
                detectedFields.push({ name: 'price', selector: priceSel || '[class*="price"]', attr: 'text', type: 'text' });
            }

            // Extract sample data from first 3 items
            const sampleItems = similar.slice(0, 3).map(el => {
                const obj = {};
                const title = el.querySelector('h1,h2,h3,h4,h5,h6,[class*="title"],[class*="name"]');
                if (title) obj.title = (title.innerText || '').substring(0, 100);
                const link = el.querySelector('a[href]');
                if (link) obj.url = link.href;
                const img = el.querySelector('img');
                if (img) obj.image = img.src;
                const text = (el.innerText || '').substring(0, 200);
                if (text) obj.text = text;
                return obj;
            });

            // === rawItemData: extract all valuable nodes from the first item ===
            const rawItemData = { texts: [], links: [], images: [] };
            const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'SVG', 'PATH', 'BR', 'HR']);

            // Generate a CSS selector relative to the item root
            function relativeSelector(el, root) {
                if (el === root) return '';
                const parts = [];
                let cur = el;
                while (cur && cur !== root) {
                    let seg = cur.tagName.toLowerCase();
                    if (cur.id && !/\\d{3,}/.test(cur.id)) {
                        seg = '#' + CSS.escape(cur.id);
                        parts.unshift(seg);
                        break;
                    }
                    const hasClass = cur.className && typeof cur.className === 'string' && cur.className.trim();
                    if (hasClass) {
                        const cls = cur.className.split(' ')
                            .filter(c => c && c.length < 30 && !/\\d{3,}/.test(c))
                            .slice(0, 2);
                        if (cls.length) seg += '.' + cls.map(c => CSS.escape(c)).join('.');
                    }
                    const parent = cur.parentElement;
                    if (parent && parent !== root) {
                        if (hasClass) {
                            // With class: only add nth-of-type if siblings share same tag AND same first class
                            const firstClass = cur.className.trim().split(/\\s+/)[0];
                            const sameSelSibs = Array.from(parent.children).filter(c =>
                                c.tagName === cur.tagName &&
                                c.className && typeof c.className === 'string' &&
                                c.className.trim().split(/\\s+/)[0] === firstClass
                            );
                            if (sameSelSibs.length > 1) {
                                seg += ':nth-of-type(' + (Array.from(parent.children).filter(c => c.tagName === cur.tagName).indexOf(cur) + 1) + ')';
                            }
                        } else {
                            // No class: add nth-of-type if multiple same-tag siblings
                            const sibs = Array.from(parent.children).filter(c => c.tagName === cur.tagName);
                            if (sibs.length > 1) seg += ':nth-of-type(' + (sibs.indexOf(cur) + 1) + ')';
                        }
                    }
                    parts.unshift(seg);
                    cur = cur.parentElement;
                }
                return parts.join(' > ');
            }

            // Collect text nodes
            let textIdx = 0;
            const walker = document.createTreeWalker(firstItem, NodeFilter.SHOW_ELEMENT, {
                acceptNode: (node) => SKIP_TAGS.has(node.tagName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
            });
            let node = walker.currentNode;
            while (node) {
                // Text content: only leaf-ish elements with direct text
                const directText = Array.from(node.childNodes)
                    .filter(n => n.nodeType === 3)
                    .map(n => n.textContent.trim())
                    .filter(t => t)
                    .join(' ');
                if (directText && directText.length > 0) {
                    rawItemData.texts.push({
                        index: textIdx++,
                        text: directText.substring(0, 100),
                        selector: relativeSelector(node, firstItem),
                        tag: node.tagName.toLowerCase()
                    });
                }
                node = walker.nextNode();
            }

            // Collect links
            firstItem.querySelectorAll('a[href]').forEach((a, i) => {
                rawItemData.links.push({
                    index: i,
                    href: a.href || '',
                    text: (a.textContent || '').trim().substring(0, 100),
                    selector: relativeSelector(a, firstItem)
                });
            });

            // Collect images
            firstItem.querySelectorAll('img').forEach((img, i) => {
                rawItemData.images.push({
                    index: i,
                    src: img.src || img.dataset.src || '',
                    alt: (img.alt || '').substring(0, 100),
                    selector: relativeSelector(img, firstItem)
                });
            });

            console.log('[DEBUG] rawItemData:', JSON.stringify(rawItemData).substring(0, 500));

            window.__seenfetch_detected_list = {
                containerSelector: containerSel,
                itemSelector: fullItemSelector,
                itemCount: similar.length,
                sampleItems: sampleItems,
                detectedFields: detectedFields,
                rawItemData: rawItemData
            };
        }

        document.addEventListener('mousemove', onMouseMove, true);

        // Cleanup function
        window.__seenfetch_cleanup_list_detection = () => {
            document.removeEventListener('mousemove', onMouseMove, true);
            clearHighlights();
            const s = document.getElementById(STYLE_ID);
            if (s) s.remove();
            window.__seenfetch_detected_list = null;
            window.__seenfetch_list_detection_active = false;
            delete window.__seenfetch_cleanup_list_detection;
        };
    })();
    '''

    async def inject_list_detection_script(self):
        """Inject the list detection script into the remote page"""
        try:
            await self.page.evaluate(self._LIST_DETECTION_SCRIPT)
            # Re-inject on future navigations within this page
            self._list_detection_handler = lambda: asyncio.ensure_future(
                self.page.evaluate(self._LIST_DETECTION_SCRIPT)
            )
            self.page.on("load", self._list_detection_handler)
        except Exception as e:
            print(f"[BrowserSession] Failed to inject list detection script: {e}")

    async def remove_list_detection_script(self):
        """Remove the list detection script and cleanup highlights"""
        try:
            # Remove load event handler
            if hasattr(self, '_list_detection_handler') and self._list_detection_handler:
                self.page.remove_listener("load", self._list_detection_handler)
                self._list_detection_handler = None
            await self.page.evaluate('''
                () => {
                    if (typeof window.__seenfetch_cleanup_list_detection === 'function') {
                        window.__seenfetch_cleanup_list_detection();
                    }
                }
            ''')
        except Exception as e:
            print(f"[BrowserSession] Failed to remove list detection script: {e}")

    async def get_detected_list(self) -> Optional[dict]:
        """Read the currently detected list from the remote page"""
        try:
            result = await self.page.evaluate('() => window.__seenfetch_detected_list')
            return result
        except Exception:
            return None

    async def inject_input(self, event: dict):
        """Inject mouse/keyboard events via CDP"""
        if not self.cdp_session:
            return
        event_type = event.get("type")
        try:
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
                params = {
                    "type": event_type,
                    "key": event.get("key", ""),
                    "code": event.get("code", ""),
                    "text": event.get("text", ""),
                }
                key_code = event.get("keyCode", 0)
                if key_code:
                    params["windowsVirtualKeyCode"] = key_code
                    params["nativeVirtualKeyCode"] = key_code
                await self.cdp_session.send("Input.dispatchKeyEvent", params)
        except Exception:
            pass  # CDP call may fail during navigation — safe to ignore

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
