# services/api/app/services/pagination_executor.py
"""
翻页执行器

功能:
- 根据配置执行翻页操作
- 支持多种翻页类型
- 数据去重和合并
"""

from typing import List, Dict, Any, Optional, Callable
import asyncio
import re
from playwright.async_api import Page

from ..models_v2.pagination import (
    PaginationType,
    PaginationConfig,
    PaginationResult,
)


class PaginationExecutor:
    """翻页执行器"""

    def __init__(self, page: Page, config: PaginationConfig):
        self.page = page
        self.config = config
        self.current_page = config.start_page
        self.consecutive_no_new_content = 0
        self._last_content_hash = None

    async def has_next_page(self) -> bool:
        """检查是否还有下一页"""
        # 检查页数限制
        if self.current_page >= self.config.start_page + self.config.max_pages:
            return False

        # 检查停止条件选择器
        if self.config.stop_condition:
            try:
                count = await self.page.locator(self.config.stop_condition).count()
                if count > 0:
                    return False
            except:
                pass

        # 根据类型检查
        if self.config.type == PaginationType.CLICK_NEXT:
            return await self._check_next_button_available()

        if self.config.type == PaginationType.LOAD_MORE:
            return await self._check_load_more_available()

        if self.config.type == PaginationType.INFINITE_SCROLL:
            return self.consecutive_no_new_content < 2

        if self.config.type == PaginationType.URL_PATTERN:
            return True  # URL 模式由页数控制

        return False

    async def go_to_next_page(self) -> bool:
        """执行翻页，返回是否成功"""
        try:
            if self.config.type == PaginationType.CLICK_NEXT:
                return await self._click_next_button()

            if self.config.type == PaginationType.LOAD_MORE:
                return await self._click_load_more()

            if self.config.type == PaginationType.INFINITE_SCROLL:
                return await self._scroll_to_load()

            if self.config.type == PaginationType.URL_PATTERN:
                return await self._navigate_to_next_url()

            return False

        except Exception as e:
            print(f"[PaginationExecutor] 翻页失败: {e}")
            return False

    async def extract_all_pages(
        self,
        extract_fn: Callable[[Page], Any],
        on_page_complete: Optional[Callable[[int, List], None]] = None
    ) -> PaginationResult:
        """
        循环翻页并提取所有数据

        Args:
            extract_fn: 数据提取函数，接收 page 返回数据列表
            on_page_complete: 每页完成回调
        """
        all_data: List[Dict] = []
        pages_scraped = 0
        stopped_reason = ""

        try:
            while True:
                # 提取当前页数据
                page_data = await extract_fn(self.page)
                if isinstance(page_data, list):
                    all_data.extend(page_data)
                elif page_data:
                    all_data.append(page_data)

                pages_scraped += 1

                # 回调
                if on_page_complete:
                    on_page_complete(pages_scraped, page_data)

                print(f"[PaginationExecutor] 第 {pages_scraped} 页完成，累计 {len(all_data)} 条数据")

                # 检查是否达到最大页数
                if pages_scraped >= self.config.max_pages:
                    stopped_reason = "max_pages"
                    break

                # 检查是否有下一页
                if not await self.has_next_page():
                    stopped_reason = "no_more_content"
                    break

                # 翻页
                success = await self.go_to_next_page()
                if not success:
                    stopped_reason = "pagination_failed"
                    break

                self.current_page += 1

                # 等待内容加载
                await self._wait_for_content()

            # 去重
            if self.config.dedup_field and all_data:
                all_data = self._deduplicate(all_data, self.config.dedup_field)

            return PaginationResult(
                success=True,
                pages_scraped=pages_scraped,
                total_items=len(all_data),
                stopped_reason=stopped_reason,
                data=all_data
            )

        except Exception as e:
            return PaginationResult(
                success=False,
                pages_scraped=pages_scraped,
                total_items=len(all_data),
                stopped_reason="error",
                error=str(e),
                data=all_data
            )

    async def _check_next_button_available(self) -> bool:
        """检查下一页按钮是否可用"""
        if not self.config.next_button_selector:
            return False

        try:
            locator = self.page.locator(self.config.next_button_selector)
            count = await locator.count()
            if count == 0:
                return False

            element = locator.first

            # 检查可见性
            is_visible = await element.is_visible()
            if not is_visible:
                return False

            # 检查是否禁用
            disabled = await element.get_attribute('disabled')
            if disabled is not None:
                return False

            class_name = await element.get_attribute('class') or ''
            if 'disabled' in class_name.lower():
                return False

            # 检查停止文本
            if self.config.stop_text:
                text = await element.text_content() or ''
                if self.config.stop_text in text:
                    return False

            return True

        except Exception:
            return False

    async def _check_load_more_available(self) -> bool:
        """检查加载更多按钮是否可用"""
        return await self._check_next_button_available()

    async def _click_next_button(self) -> bool:
        """点击下一页按钮"""
        if not self.config.next_button_selector:
            return False

        try:
            element = self.page.locator(self.config.next_button_selector).first

            # 滚动到元素可见
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)

            # 点击
            await element.click()

            # 等待页面更新
            await self._wait_for_page_update()

            return True

        except Exception as e:
            print(f"[PaginationExecutor] 点击下一页失败: {e}")
            return False

    async def _click_load_more(self) -> bool:
        """点击加载更多按钮"""
        if not self.config.next_button_selector:
            return False

        # 记录当前内容高度
        old_height = await self.page.evaluate('document.body.scrollHeight')

        try:
            element = self.page.locator(self.config.next_button_selector).first
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.3)
            await element.click()

            # 等待新内容加载
            await asyncio.sleep(self.config.scroll_wait_ms / 1000)

            # 检查是否有新内容
            new_height = await self.page.evaluate('document.body.scrollHeight')

            if new_height > old_height:
                self.consecutive_no_new_content = 0
                return True
            else:
                self.consecutive_no_new_content += 1
                return self.consecutive_no_new_content < 2

        except Exception as e:
            print(f"[PaginationExecutor] 点击加载更多失败: {e}")
            return False

    async def _scroll_to_load(self) -> bool:
        """滚动加载更多"""
        # 记录当前状态
        old_height = await self.page.evaluate('document.body.scrollHeight')
        old_items = await self._get_content_hash()

        # 滚动到底部
        if self.config.scroll_container:
            await self.page.evaluate(f'''
                document.querySelector("{self.config.scroll_container}").scrollTo({{
                    top: document.querySelector("{self.config.scroll_container}").scrollHeight,
                    behavior: "smooth"
                }})
            ''')
        else:
            await self.page.evaluate('window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" })')

        # 等待加载
        await asyncio.sleep(self.config.scroll_wait_ms / 1000)

        # 检查是否有新内容
        new_height = await self.page.evaluate('document.body.scrollHeight')
        new_items = await self._get_content_hash()

        if new_height > old_height or new_items != old_items:
            self.consecutive_no_new_content = 0
            self._last_content_hash = new_items
            return True
        else:
            self.consecutive_no_new_content += 1
            return False

    async def _navigate_to_next_url(self) -> bool:
        """导航到下一页 URL"""
        if not self.config.url_pattern:
            return False

        try:
            next_page = self.current_page + self.config.page_step
            next_url = self.config.url_pattern.replace('{n}', str(next_page))

            await self.page.goto(next_url, wait_until='networkidle')
            return True

        except Exception as e:
            print(f"[PaginationExecutor] 导航失败: {e}")
            return False

    async def _wait_for_page_update(self):
        """等待页面更新"""
        try:
            if self.config.wait_for_network:
                await self.page.wait_for_load_state('networkidle', timeout=10000)

            if self.config.wait_for_selector:
                await self.page.wait_for_selector(
                    self.config.wait_for_selector,
                    timeout=10000
                )

            await asyncio.sleep(0.5)

        except Exception:
            await asyncio.sleep(1)

    async def _wait_for_content(self):
        """等待内容加载"""
        try:
            if self.config.wait_for_network:
                await self.page.wait_for_load_state('networkidle', timeout=5000)
            await asyncio.sleep(0.5)
        except:
            await asyncio.sleep(1)

    async def _get_content_hash(self) -> str:
        """获取内容哈希用于检测变化"""
        try:
            # 获取主要内容区域的文本
            text = await self.page.evaluate('''
                () => {
                    const main = document.querySelector('main, article, .content, #content, .list');
                    return (main || document.body).innerText.substring(0, 1000);
                }
            ''')
            return str(hash(text))
        except:
            return ""

    def _deduplicate(self, data: List[Dict], field: str) -> List[Dict]:
        """根据字段去重"""
        seen = set()
        result = []

        for item in data:
            key = item.get(field)
            if key and key not in seen:
                seen.add(key)
                result.append(item)

        return result
