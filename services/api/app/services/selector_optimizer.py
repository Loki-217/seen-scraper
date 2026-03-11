# services/api/app/services/selector_optimizer.py
"""
CSS 选择器优化器

功能:
- 生成稳定的 CSS 选择器
- 评估选择器稳定性
- 提供备选选择器
- 验证选择器有效性
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from playwright.async_api import Page, ElementHandle

from ..models_v2.smart import OptimizedSelector


class SelectorOptimizer:
    """选择器优化器"""

    # 动态类名模式（应该避免）
    DYNAMIC_CLASS_PATTERNS = [
        r'[a-z]+_[a-zA-Z0-9]{5,}',  # BEM 哈希 e.g., styles_abc123
        r'css-[a-zA-Z0-9]+',        # CSS-in-JS
        r'sc-[a-zA-Z0-9]+',         # styled-components
        r'emotion-[a-zA-Z0-9]+',    # emotion
        r'[A-Z][a-z]+_[a-z0-9]{6,}', # CSS Modules
        r'\d{10,}',                 # 长数字
        r'[a-f0-9]{8,}',            # 哈希值
    ]

    # 稳定性评分权重
    STABILITY_WEIGHTS = {
        'data_attr': 0.3,
        'semantic_id': 0.25,
        'semantic_class': 0.2,
        'tag_name': 0.1,
        'nth_child': -0.1,
        'dynamic_class': -0.2,
        'long_path': -0.1,
    }

    async def optimize(self, element: ElementHandle, page: Page) -> OptimizedSelector:
        """
        为元素生成优化的选择器

        Args:
            element: Playwright 元素句柄
            page: 页面对象

        Returns:
            OptimizedSelector
        """
        # 获取元素信息
        element_info = await self._get_element_info(element)

        # 生成候选选择器
        candidates = await self._generate_candidates(element, element_info, page)

        # 评估每个选择器
        evaluated = []
        for selector in candidates:
            score = self._calculate_stability_score(selector)
            match_count = await self._count_matches(page, selector)
            evaluated.append({
                'selector': selector,
                'score': score,
                'match_count': match_count
            })

        # 按稳定性和匹配数排序
        # 优先选择稳定性高且匹配数适中的
        evaluated.sort(key=lambda x: (
            -x['score'],
            abs(x['match_count'] - 1)  # 尽量匹配1个或少量
        ))

        best = evaluated[0] if evaluated else {
            'selector': element_info.get('tag', 'div'),
            'score': 0.3,
            'match_count': 0
        }

        return OptimizedSelector(
            selector=best['selector'],
            stability_score=best['score'],
            specificity=self._calculate_specificity(best['selector']),
            match_count=best['match_count'],
            alternatives=[e['selector'] for e in evaluated[1:4]]  # 前3个备选
        )

    async def generate_alternatives(self, element: ElementHandle, page: Page) -> List[str]:
        """生成备选选择器列表"""
        element_info = await self._get_element_info(element)
        return await self._generate_candidates(element, element_info, page)

    async def validate_selector(self, selector: str, page: Page, expected_count: int = None) -> Dict:
        """
        验证选择器有效性

        Args:
            selector: CSS 选择器
            page: 页面对象
            expected_count: 期望匹配数（可选）

        Returns:
            {valid: bool, match_count: int, sample_texts: List[str]}
        """
        try:
            elements = await page.query_selector_all(selector)
            match_count = len(elements)

            # 获取示例文本
            sample_texts = []
            for el in elements[:5]:
                text = await el.text_content()
                if text:
                    sample_texts.append(text.strip()[:100])

            valid = match_count > 0
            if expected_count is not None:
                valid = match_count == expected_count

            return {
                'valid': valid,
                'match_count': match_count,
                'sample_texts': sample_texts
            }
        except Exception as e:
            return {
                'valid': False,
                'match_count': 0,
                'sample_texts': [],
                'error': str(e)
            }

    async def generate_batch_selector(self, sample_element: ElementHandle, page: Page) -> str:
        """
        根据单个列表项生成能匹配所有同类项的选择器

        Args:
            sample_element: 示例元素
            page: 页面对象

        Returns:
            能匹配所有同类元素的选择器
        """
        element_info = await self._get_element_info(sample_element)

        # 获取父元素选择器
        parent_selector = await page.evaluate('''
            (el) => {
                const parent = el.parentElement;
                if (!parent) return null;

                // 生成父元素选择器
                if (parent.id && !parent.id.match(/\\d{5,}/)) {
                    return '#' + CSS.escape(parent.id);
                }

                if (parent.className && typeof parent.className === 'string') {
                    const classes = parent.className.split(' ')
                        .filter(c => c && !c.match(/\\d{5,}/) && c.length < 30);
                    if (classes.length > 0) {
                        return '.' + classes.slice(0, 2).map(c => CSS.escape(c)).join('.');
                    }
                }

                return parent.tagName.toLowerCase();
            }
        ''', sample_element)

        # 生成子元素选择器（不包含位置信息）
        tag = element_info.get('tag', 'div').lower()

        # 优先使用稳定的类名
        class_name = element_info.get('className', '')
        if class_name:
            stable_classes = self._filter_stable_classes(class_name)
            if stable_classes:
                child_selector = '.' + '.'.join(stable_classes[:2])
            else:
                child_selector = tag
        else:
            child_selector = tag

        if parent_selector:
            return f"{parent_selector} > {child_selector}"

        return child_selector

    async def _get_element_info(self, element: ElementHandle) -> Dict:
        """获取元素详细信息"""
        return await element.evaluate('''
            (el) => ({
                tag: el.tagName.toLowerCase(),
                id: el.id,
                className: el.className,
                dataAttrs: Object.fromEntries(
                    Array.from(el.attributes)
                        .filter(a => a.name.startsWith('data-'))
                        .map(a => [a.name, a.value])
                ),
                text: (el.textContent || '').trim().substring(0, 50),
                href: el.href || null,
                src: el.src || null
            })
        ''')

    async def _generate_candidates(
        self,
        element: ElementHandle,
        element_info: Dict,
        page: Page
    ) -> List[str]:
        """生成候选选择器"""
        candidates = []
        tag = element_info.get('tag', 'div')

        # 1. data-* 属性选择器（最稳定）
        data_attrs = element_info.get('dataAttrs', {})
        for attr_name, attr_value in data_attrs.items():
            if attr_value and not re.match(r'^\d+$', attr_value):
                selector = f'[{attr_name}="{attr_value}"]'
                candidates.append(selector)

        # 2. ID 选择器（如果是语义化的）
        elem_id = element_info.get('id', '')
        if elem_id and not self._is_dynamic_value(elem_id):
            candidates.append(f'#{elem_id}')

        # 3. 类名选择器
        class_name = element_info.get('className', '')
        if class_name:
            stable_classes = self._filter_stable_classes(class_name)
            if stable_classes:
                # 单类名
                for cls in stable_classes[:3]:
                    candidates.append(f'.{cls}')
                # 组合类名
                if len(stable_classes) >= 2:
                    candidates.append('.' + '.'.join(stable_classes[:2]))

        # 4. 标签 + 类名组合
        if class_name:
            stable_classes = self._filter_stable_classes(class_name)
            if stable_classes:
                candidates.append(f'{tag}.{stable_classes[0]}')

        # 5. 路径选择器（通过 JS 获取）
        path_selector = await page.evaluate('''
            (el) => {
                const parts = [];
                let current = el;
                let depth = 0;

                while (current && current !== document.body && depth < 3) {
                    let part = current.tagName.toLowerCase();

                    // 添加类名
                    if (current.className && typeof current.className === 'string') {
                        const classes = current.className.split(' ')
                            .filter(c => c && !c.match(/\\d{5,}/) && c.length < 25);
                        if (classes.length > 0) {
                            part += '.' + classes[0];
                        }
                    }

                    parts.unshift(part);

                    // 如果有 ID 就停止
                    if (current.id && !current.id.match(/\\d{5,}/)) {
                        parts[0] = '#' + CSS.escape(current.id);
                        break;
                    }

                    current = current.parentElement;
                    depth++;
                }

                return parts.join(' > ');
            }
        ''', element)

        if path_selector:
            candidates.append(path_selector)

        # 6. 纯标签（最后手段）
        candidates.append(tag)

        # 去重并保持顺序
        seen = set()
        unique = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        return unique

    def _filter_stable_classes(self, class_name: str) -> List[str]:
        """过滤出稳定的类名"""
        if not class_name or not isinstance(class_name, str):
            return []

        classes = class_name.split()
        stable = []

        for cls in classes:
            if not cls:
                continue
            # 检查是否是动态类名
            is_dynamic = any(
                re.match(pattern, cls)
                for pattern in self.DYNAMIC_CLASS_PATTERNS
            )
            if not is_dynamic and len(cls) < 30:
                stable.append(cls)

        return stable

    def _is_dynamic_value(self, value: str) -> bool:
        """检查值是否是动态生成的"""
        return any(
            re.search(pattern, value)
            for pattern in self.DYNAMIC_CLASS_PATTERNS
        )

    def _calculate_stability_score(self, selector: str) -> float:
        """计算选择器稳定性评分"""
        score = 0.5  # 基础分

        # data-* 属性
        if re.search(r'\[data-[^=]+=[^\]]+\]', selector):
            score += self.STABILITY_WEIGHTS['data_attr']

        # 语义化 ID
        if '#' in selector and not re.search(r'#[a-z]*\d{3,}', selector):
            score += self.STABILITY_WEIGHTS['semantic_id']

        # 语义化 class
        if '.' in selector:
            classes = re.findall(r'\.([a-zA-Z][a-zA-Z0-9_-]*)', selector)
            if classes and all(not self._is_dynamic_value(c) for c in classes):
                score += self.STABILITY_WEIGHTS['semantic_class']

        # 标签名
        if re.match(r'^[a-z]+', selector):
            score += self.STABILITY_WEIGHTS['tag_name']

        # nth-child 扣分
        if ':nth' in selector:
            score += self.STABILITY_WEIGHTS['nth_child']

        # 动态类名扣分
        if any(re.search(pattern, selector) for pattern in self.DYNAMIC_CLASS_PATTERNS):
            score += self.STABILITY_WEIGHTS['dynamic_class']

        # 路径过长扣分
        if selector.count('>') > 3 or selector.count(' ') > 4:
            score += self.STABILITY_WEIGHTS['long_path']

        return max(0, min(1, score))

    def _calculate_specificity(self, selector: str) -> int:
        """计算 CSS 特异性（简化版）"""
        # ID 选择器
        id_count = selector.count('#')
        # 类选择器和属性选择器
        class_count = selector.count('.') + selector.count('[')
        # 标签选择器
        tag_count = len(re.findall(r'(?:^|[\s>+~])([a-z]+)', selector))

        return id_count * 100 + class_count * 10 + tag_count

    async def _count_matches(self, page: Page, selector: str) -> int:
        """统计选择器匹配的元素数"""
        try:
            count = await page.evaluate(f'''
                () => document.querySelectorAll("{selector.replace('"', '\\"')}").length
            ''')
            return count
        except:
            return 0
