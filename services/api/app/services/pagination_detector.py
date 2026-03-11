# services/api/app/services/pagination_detector.py
"""
智能翻页方式检测器

功能:
- 检测页面中的翻页方式
- 支持多种翻页类型识别
- 返回推荐配置和置信度
"""

from typing import List, Optional, Tuple
import re
from playwright.async_api import Page

from ..models_v2.pagination import (
    PaginationType,
    PaginationConfig,
    DetectedPagination,
)


class PaginationDetector:
    """智能翻页检测器"""

    # "下一页"按钮选择器模式
    NEXT_BUTTON_PATTERNS = [
        # 中文
        ('a:has-text("下一页")', 0.95),
        ('button:has-text("下一页")', 0.95),
        ('[class*="next"]:has-text("下一页")', 0.9),
        # 英文
        ('a:has-text("Next")', 0.9),
        ('button:has-text("Next")', 0.9),
        ('a:has-text("next")', 0.85),
        # 箭头图标
        ('a:has-text(">")', 0.6),
        ('a:has-text("»")', 0.7),
        ('a:has-text("›")', 0.65),
        # 类名模式
        ('[class*="next"]:not([class*="prev"])', 0.7),
        ('[class*="pagination"] a:last-child', 0.6),
        ('.pagination-next', 0.85),
        ('.page-next', 0.85),
        # 常见 UI 框架
        ('.ant-pagination-next:not(.ant-pagination-disabled)', 0.9),
        ('.el-pagination__next:not(.disabled)', 0.9),
        ('.van-pagination__next', 0.85),
        ('.ivu-page-next', 0.85),
    ]

    # "加载更多"按钮选择器模式
    LOAD_MORE_PATTERNS = [
        # 中文
        ('button:has-text("加载更多")', 0.95),
        ('a:has-text("加载更多")', 0.9),
        ('button:has-text("查看更多")', 0.85),
        ('a:has-text("查看更多")', 0.8),
        ('button:has-text("显示更多")', 0.8),
        # 英文
        ('button:has-text("Load More")', 0.9),
        ('button:has-text("Show More")', 0.85),
        ('button:has-text("View More")', 0.8),
        # 类名模式
        ('[class*="load-more"]', 0.75),
        ('[class*="loadmore"]', 0.75),
        ('[class*="more-btn"]', 0.7),
        ('.load-more-button', 0.8),
    ]

    # 无限滚动检测模式
    INFINITE_SCROLL_PATTERNS = [
        '[data-infinite-scroll]',
        '[infinite-scroll]',
        '.infinite-scroll',
        '.infinite-scroll-component',
        '[class*="infinite"]',
    ]

    # URL 翻页参数模式
    URL_PAGE_PATTERNS = [
        (r'[?&](page)=(\d+)', 'page'),
        (r'[?&](p)=(\d+)', 'p'),
        (r'[?&](pn)=(\d+)', 'pn'),
        (r'[?&](pageNum)=(\d+)', 'pageNum'),
        (r'[?&](pageNo)=(\d+)', 'pageNo'),
        (r'[?&](offset)=(\d+)', 'offset'),
        (r'[?&](start)=(\d+)', 'start'),
        (r'/page/(\d+)', 'page'),
        (r'/p(\d+)\.html', 'page'),
    ]

    async def detect(self, page: Page) -> List[DetectedPagination]:
        """
        检测页面中的翻页方式

        返回检测到的所有翻页方式，按置信度排序
        """
        results: List[DetectedPagination] = []

        # 1. 检测点击"下一页"按钮
        next_btn_result = await self._detect_next_button(page)
        if next_btn_result:
            results.append(next_btn_result)

        # 2. 检测"加载更多"按钮
        load_more_result = await self._detect_load_more(page)
        if load_more_result:
            results.append(load_more_result)

        # 3. 检测无限滚动
        infinite_result = await self._detect_infinite_scroll(page)
        if infinite_result:
            results.append(infinite_result)

        # 4. 检测 URL 翻页模式
        url_result = await self._detect_url_pattern(page)
        if url_result:
            results.append(url_result)

        # 按置信度排序
        results.sort(key=lambda x: x.confidence, reverse=True)

        return results

    async def get_recommended(self, page: Page) -> Optional[PaginationConfig]:
        """获取推荐的翻页配置"""
        results = await self.detect(page)
        if results:
            return results[0].config
        return None

    async def _detect_next_button(self, page: Page) -> Optional[DetectedPagination]:
        """检测"下一页"按钮"""
        for selector, base_confidence in self.NEXT_BUTTON_PATTERNS:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    # 进一步验证：检查元素是否可见
                    element = page.locator(selector).first
                    is_visible = await element.is_visible()

                    if is_visible:
                        # 检查是否被禁用
                        is_disabled = await self._is_element_disabled(element)
                        if not is_disabled:
                            # 获取实际的选择器文本
                            text = await element.text_content()
                            text = (text or "").strip()[:20]

                            return DetectedPagination(
                                type=PaginationType.CLICK_NEXT,
                                config=PaginationConfig(
                                    type=PaginationType.CLICK_NEXT,
                                    next_button_selector=selector,
                                    max_pages=10,
                                ),
                                confidence=base_confidence,
                                evidence=f"找到下一页按钮: '{text}' ({selector})"
                            )
            except Exception:
                continue

        return None

    async def _detect_load_more(self, page: Page) -> Optional[DetectedPagination]:
        """检测"加载更多"按钮"""
        for selector, base_confidence in self.LOAD_MORE_PATTERNS:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    element = page.locator(selector).first
                    is_visible = await element.is_visible()

                    if is_visible:
                        text = await element.text_content()
                        text = (text or "").strip()[:20]

                        return DetectedPagination(
                            type=PaginationType.LOAD_MORE,
                            config=PaginationConfig(
                                type=PaginationType.LOAD_MORE,
                                next_button_selector=selector,
                                max_pages=10,
                            ),
                            confidence=base_confidence,
                            evidence=f"找到加载更多按钮: '{text}' ({selector})"
                        )
            except Exception:
                continue

        return None

    async def _detect_infinite_scroll(self, page: Page) -> Optional[DetectedPagination]:
        """检测无限滚动"""
        # 方法1: 检测特定标记
        for selector in self.INFINITE_SCROLL_PATTERNS:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    return DetectedPagination(
                        type=PaginationType.INFINITE_SCROLL,
                        config=PaginationConfig(
                            type=PaginationType.INFINITE_SCROLL,
                            scroll_wait_ms=2000,
                            max_pages=10,
                        ),
                        confidence=0.8,
                        evidence=f"找到无限滚动标记: {selector}"
                    )
            except Exception:
                continue

        # 方法2: 检测页面高度是否远大于视口
        try:
            dimensions = await page.evaluate('''
                () => ({
                    bodyHeight: document.body.scrollHeight,
                    viewportHeight: window.innerHeight,
                    hasScrollbar: document.body.scrollHeight > window.innerHeight
                })
            ''')

            body_height = dimensions['bodyHeight']
            viewport_height = dimensions['viewportHeight']

            # 如果页面高度大于视口高度的 2.5 倍，可能是无限滚动
            if body_height > viewport_height * 2.5:
                return DetectedPagination(
                    type=PaginationType.INFINITE_SCROLL,
                    config=PaginationConfig(
                        type=PaginationType.INFINITE_SCROLL,
                        scroll_wait_ms=2000,
                        max_pages=10,
                    ),
                    confidence=0.5,
                    evidence=f"页面高度 ({body_height}px) 远大于视口 ({viewport_height}px)"
                )
        except Exception:
            pass

        return None

    async def _detect_url_pattern(self, page: Page) -> Optional[DetectedPagination]:
        """检测 URL 翻页模式"""
        url = page.url

        for pattern, param_name in self.URL_PAGE_PATTERNS:
            match = re.search(pattern, url)
            if match:
                # 构造 URL 模式
                if param_name == 'offset' or param_name == 'start':
                    # offset 类型，需要步进
                    url_pattern = re.sub(pattern, f'{param_name}={{n}}', url)
                    page_step = 10  # 默认步进
                else:
                    url_pattern = re.sub(pattern, f'{param_name}={{n}}', url)
                    page_step = 1

                current_page = int(match.group(2)) if len(match.groups()) > 1 else int(match.group(1))

                return DetectedPagination(
                    type=PaginationType.URL_PATTERN,
                    config=PaginationConfig(
                        type=PaginationType.URL_PATTERN,
                        url_pattern=url_pattern,
                        start_page=current_page,
                        page_step=page_step,
                        max_pages=10,
                    ),
                    confidence=0.85,
                    evidence=f"URL 包含翻页参数: {param_name}={current_page}"
                )

        return None

    async def _is_element_disabled(self, element) -> bool:
        """检查元素是否被禁用"""
        try:
            # 检查 disabled 属性
            disabled = await element.get_attribute('disabled')
            if disabled is not None:
                return True

            # 检查 aria-disabled
            aria_disabled = await element.get_attribute('aria-disabled')
            if aria_disabled == 'true':
                return True

            # 检查类名
            class_name = await element.get_attribute('class') or ''
            if 'disabled' in class_name.lower():
                return True

            return False
        except Exception:
            return False
