# services/api/app/browser_controller.py（已废弃）
from typing import Dict, Any, Optional
import asyncio
import json
import uuid
from playwright.async_api import async_playwright, Page, Browser
from fastapi import WebSocket
import base64

class BrowserSession:
    """管理单个用户的浏览器会话"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        
    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--disable-web-security', '--disable-features=IsolateOrigins,site-per-process']
        )
        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        self.page = await context.new_page()
        
    async def goto(self, url: str) -> Dict[str, Any]:
        """导航到URL并返回页面信息"""
        await self.page.goto(url, wait_until="networkidle")
        
        # 注入标记脚本
        await self.page.add_script_tag(content="""
            window.__seenfetch__ = {
                highlightElement: function(selector) {
                    document.querySelectorAll('.seenfetch-highlight').forEach(el => {
                        el.classList.remove('seenfetch-highlight');
                    });
                    document.querySelectorAll(selector).forEach(el => {
                        el.classList.add('seenfetch-highlight');
                    });
                },
                getElementInfo: function(x, y) {
                    const element = document.elementFromPoint(x, y);
                    if (!element) return null;
                    
                    const rect = element.getBoundingClientRect();
                    return {
                        tagName: element.tagName,
                        className: element.className,
                        id: element.id,
                        text: element.innerText?.substring(0, 100),
                        rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                        selector: this.generateSelector(element)
                    };
                },
                generateSelector: function(el) {
                    // 智能生成选择器
                    if (el.id) return '#' + el.id;
                    if (el.className) {
                        const classes = el.className.split(' ').filter(c => c && !c.includes('seenfetch'));
                        if (classes.length) return '.' + classes[0];
                    }
                    return el.tagName.toLowerCase();
                },
                findSimilar: function(selector) {
                    const elements = document.querySelectorAll(selector);
                    return Array.from(elements).map(el => {
                        const rect = el.getBoundingClientRect();
                        return {
                            text: el.innerText?.substring(0, 50),
                            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                        };
                    });
                }
            };
            
            // 添加高亮样式
            if (!document.querySelector('#seenfetch-styles')) {
                const style = document.createElement('style');
                style.id = 'seenfetch-styles';
                style.innerHTML = `
                    .seenfetch-highlight {
                        outline: 3px solid #4CAF50 !important;
                        outline-offset: 2px;
                        background: rgba(76, 175, 80, 0.1) !important;
                    }
                `;
                document.head.appendChild(style);
            }
        """)
        
        # 获取页面截图和DOM信息
        screenshot = await self.page.screenshot(full_page=False)
        
        # 获取可交互元素
        elements = await self.page.evaluate("""
            () => {
                const interactables = [];
                const selectors = ['a', 'button', 'input', 'select', 'textarea', '[onclick]', '[role="button"]'];
                
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            interactables.push({
                                selector: window.__seenfetch__.generateSelector(el),
                                rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                                type: el.tagName.toLowerCase(),
                                text: el.innerText?.substring(0, 50) || el.value || ''
                            });
                        }
                    });
                });
                return interactables;
            }
        """)
        
        return {
            "screenshot": base64.b64encode(screenshot).decode(),
            "url": self.page.url,
            "title": await self.page.title(),
            "elements": elements,
            "viewport": {'width': 1920, 'height': 1080}
        }
    
    async def click(self, x: int, y: int) -> Dict[str, Any]:
        """处理点击事件"""
        # 获取点击位置的元素信息
        element_info = await self.page.evaluate(f"""
            window.__seenfetch__.getElementInfo({x}, {y})
        """)
        
        if not element_info:
            return {"error": "No element at position"}
        
        # 查找相似元素
        similar = await self.page.evaluate(f"""
            window.__seenfetch__.findSimilar('{element_info['selector']}')
        """)
        
        # 高亮所有相似元素
        await self.page.evaluate(f"""
            window.__seenfetch__.highlightElement('{element_info['selector']}')
        """)
        
        # 截图显示高亮效果
        screenshot = await self.page.screenshot(full_page=False)
        
        return {
            "element": element_info,
            "similar_count": len(similar),
            "similar_elements": similar[:10],  # 最多返回10个示例
            "screenshot": base64.b64encode(screenshot).decode(),
            "suggested_selector": element_info['selector']
        }
    
    async def extract_data(self, selector: str, attr: str = "text") -> list:
        """提取数据"""
        data = await self.page.evaluate(f"""
            Array.from(document.querySelectorAll('{selector}')).map(el => {{
                if ('{attr}' === 'text') return el.innerText;
                return el.getAttribute('{attr}');
            }})
        """)
        return data
    
    async def close(self):
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


class BrowserManager:
    """管理所有浏览器会话"""
    
    def __init__(self):
        self.sessions: Dict[str, BrowserSession] = {}
        
    async def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        session = BrowserSession(session_id)
        await session.start()
        self.sessions[session_id] = session
        return session_id
    
    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        return self.sessions.get(session_id)
    
    async def close_session(self, session_id: str):
        session = self.sessions.pop(session_id, None)
        if session:
            await session.close()

# 全局实例
browser_manager = BrowserManager()