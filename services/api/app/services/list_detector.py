# services/api/app/services/list_detector.py
"""
列表结构自动检测器

功能:
- 检测页面中的列表/表格结构
- 分析列表项内部字段
- 生成字段建议
"""

from typing import List, Dict, Any, Optional, Tuple
import hashlib
import re
from playwright.async_api import Page

from ..models_v2.smart import (
    DetectedList,
    SuggestedField,
    FieldType,
)


class ListDetector:
    """列表结构检测器"""

    # 常见列表容器标签
    CONTAINER_TAGS = ['ul', 'ol', 'tbody', 'div', 'section', 'main', 'article']

    # 列表项标签
    ITEM_TAGS = ['li', 'tr', 'div', 'article', 'section']

    # 最小子元素数
    MIN_CHILDREN = 3

    # 结构相似度阈值
    SIMILARITY_THRESHOLD = 0.7

    async def detect_lists(self, page: Page) -> List[DetectedList]:
        """
        检测页面中的列表结构

        Returns:
            按置信度降序排列的检测结果列表
        """
        results: List[DetectedList] = []

        # 在页面中执行检测脚本
        candidates = await page.evaluate('''
            () => {
                const results = [];
                const containerTags = ['ul', 'ol', 'tbody', 'div', 'section', 'main', 'article'];
                const itemTags = ['li', 'tr', 'div', 'article', 'section'];
                const minChildren = 3;

                // 生成元素结构哈希
                function getStructureHash(element) {
                    const tags = Array.from(element.children).map(c => c.tagName).join(',');
                    const classes = (element.className || '').toString().split(' ')
                        .filter(c => c && !c.match(/\\d{3,}/))  // 过滤含长数字的类
                        .sort().slice(0, 3).join(',');
                    return `${element.tagName}:${tags}:${classes}`;
                }

                // 生成选择器
                function generateSelector(el) {
                    // 优先使用 data 属性
                    for (const attr of el.attributes || []) {
                        if (attr.name.startsWith('data-') && attr.value && !attr.value.match(/^\\d+$/)) {
                            return `[${attr.name}="${attr.value}"]`;
                        }
                    }

                    // 使用 ID
                    if (el.id && !el.id.match(/\\d{3,}/)) {
                        return '#' + CSS.escape(el.id);
                    }

                    // 使用 class
                    if (el.className && typeof el.className === 'string') {
                        const classes = el.className.split(' ')
                            .filter(c => c && !c.match(/\\d{3,}/) && c.length < 30);
                        if (classes.length > 0) {
                            return '.' + classes.slice(0, 2).map(c => CSS.escape(c)).join('.');
                        }
                    }

                    // 使用标签
                    return el.tagName.toLowerCase();
                }

                // 获取元素的完整选择器路径
                function getFullSelector(el, maxDepth = 3) {
                    const parts = [];
                    let current = el;
                    let depth = 0;

                    while (current && current !== document.body && depth < maxDepth) {
                        const selector = generateSelector(current);
                        parts.unshift(selector);

                        // 如果有 ID 或唯一 class，就停止
                        if (selector.startsWith('#') || selector.startsWith('[data-')) {
                            break;
                        }

                        current = current.parentElement;
                        depth++;
                    }

                    return parts.join(' > ');
                }

                // 检查元素是否在视口内
                function isInViewport(el) {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 &&
                           rect.top < window.innerHeight * 2 &&
                           rect.bottom > -window.innerHeight;
                }

                // 遍历容器
                containerTags.forEach(tag => {
                    document.querySelectorAll(tag).forEach(container => {
                        // 过滤隐藏和太小的容器
                        if (!isInViewport(container)) return;

                        // 获取直接子元素
                        const children = Array.from(container.children)
                            .filter(c => itemTags.includes(c.tagName.toLowerCase()))
                            .filter(c => isInViewport(c));

                        if (children.length < minChildren) return;

                        // 计算结构相似度
                        const hashes = children.map(c => getStructureHash(c));
                        const hashCounts = {};
                        hashes.forEach(h => { hashCounts[h] = (hashCounts[h] || 0) + 1; });

                        const maxCount = Math.max(...Object.values(hashCounts));
                        const similarity = maxCount / children.length;

                        if (similarity < 0.7) return;

                        // 找出最常见的结构
                        const dominantHash = Object.entries(hashCounts)
                            .sort((a, b) => b[1] - a[1])[0][0];

                        // 获取具有该结构的子元素
                        const matchingChildren = children.filter((c, i) => hashes[i] === dominantHash);

                        if (matchingChildren.length < minChildren) return;

                        // 生成选择器
                        const containerSelector = getFullSelector(container);
                        const itemSelector = containerSelector + ' > ' + matchingChildren[0].tagName.toLowerCase();

                        // 分析列表项结构
                        const sampleItems = matchingChildren.slice(0, 3).map(item => {
                            const data = {};

                            // 提取标题
                            const titleEl = item.querySelector('h1, h2, h3, h4, h5, h6, [class*="title"], [class*="name"], a');
                            if (titleEl) {
                                data.title = (titleEl.textContent || '').trim().substring(0, 100);
                            }

                            // 提取图片
                            const imgEl = item.querySelector('img');
                            if (imgEl) {
                                data.image = imgEl.src || imgEl.dataset.src || '';
                            }

                            // 提取链接
                            const linkEl = item.querySelector('a[href]');
                            if (linkEl) {
                                data.link = linkEl.href;
                            }

                            // 提取文本内容
                            data.text = (item.textContent || '').trim().substring(0, 200);

                            return data;
                        });

                        // 分析字段结构
                        const firstItem = matchingChildren[0];
                        const fields = [];

                        // 检测标题
                        const titleSelectors = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', '[class*="title"]', '[class*="name"]'];
                        for (const sel of titleSelectors) {
                            const el = firstItem.querySelector(sel);
                            if (el && el.textContent.trim()) {
                                fields.push({
                                    name: '标题',
                                    selector: sel,
                                    type: 'title',
                                    attr: 'text',
                                    sample: el.textContent.trim().substring(0, 50)
                                });
                                break;
                            }
                        }

                        // 检测图片
                        const imgEl = firstItem.querySelector('img');
                        if (imgEl) {
                            fields.push({
                                name: '图片',
                                selector: 'img',
                                type: 'image',
                                attr: 'src',
                                sample: imgEl.src || imgEl.dataset.src || ''
                            });
                        }

                        // 检测链接
                        const linkEl = firstItem.querySelector('a[href]');
                        if (linkEl && linkEl.href) {
                            fields.push({
                                name: '链接',
                                selector: 'a',
                                type: 'url',
                                attr: 'href',
                                sample: linkEl.href
                            });
                        }

                        // 检测价格
                        const pricePattern = /[¥$€£]\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*元/;
                        const allText = firstItem.textContent || '';
                        if (pricePattern.test(allText)) {
                            // 尝试找到包含价格的元素
                            const priceEl = Array.from(firstItem.querySelectorAll('*'))
                                .find(el => el.children.length === 0 && pricePattern.test(el.textContent || ''));
                            if (priceEl) {
                                const priceSelector = generateSelector(priceEl);
                                fields.push({
                                    name: '价格',
                                    selector: priceSelector,
                                    type: 'price',
                                    attr: 'text',
                                    sample: (priceEl.textContent || '').trim()
                                });
                            }
                        }

                        // 检测评分
                        const ratingPattern = /[\d.]+\s*[/分]|★+/;
                        if (ratingPattern.test(allText)) {
                            const ratingEl = Array.from(firstItem.querySelectorAll('*'))
                                .find(el => el.children.length === 0 && ratingPattern.test(el.textContent || ''));
                            if (ratingEl) {
                                const ratingSelector = generateSelector(ratingEl);
                                fields.push({
                                    name: '评分',
                                    selector: ratingSelector,
                                    type: 'rating',
                                    attr: 'text',
                                    sample: (ratingEl.textContent || '').trim()
                                });
                            }
                        }

                        results.push({
                            containerSelector,
                            itemSelector,
                            itemCount: matchingChildren.length,
                            similarity,
                            structureHash: dominantHash,
                            sampleItems,
                            fields,
                            // 计算置信度
                            confidence: similarity * 0.5 +
                                       Math.min(matchingChildren.length / 10, 1) * 0.3 +
                                       (fields.length > 0 ? 0.2 : 0)
                        });
                    });
                });

                // 按置信度排序，去重
                results.sort((a, b) => b.confidence - a.confidence);

                // 过滤嵌套的重复结果
                const filtered = [];
                const seen = new Set();

                for (const r of results) {
                    const key = r.containerSelector;
                    let isDuplicate = false;

                    for (const seenKey of seen) {
                        if (key.includes(seenKey) || seenKey.includes(key)) {
                            isDuplicate = true;
                            break;
                        }
                    }

                    if (!isDuplicate) {
                        seen.add(key);
                        filtered.push(r);
                    }
                }

                return filtered.slice(0, 5);  // 最多返回5个结果
            }
        ''')

        # 转换为数据模型
        for candidate in candidates:
            suggested_fields = []
            for field in candidate.get('fields', []):
                field_type_map = {
                    'title': FieldType.TITLE,
                    'image': FieldType.IMAGE,
                    'url': FieldType.URL,
                    'price': FieldType.PRICE,
                    'rating': FieldType.RATING,
                    'text': FieldType.TEXT,
                }

                suggested_fields.append(SuggestedField(
                    name=field['name'],
                    selector=field['selector'],
                    field_type=field_type_map.get(field['type'], FieldType.TEXT),
                    attr=field['attr'],
                    confidence=0.8,
                    sample_values=[field.get('sample', '')] if field.get('sample') else []
                ))

            # 生成列表名称
            list_name = self._generate_list_name(candidate, suggested_fields)

            results.append(DetectedList(
                name=list_name,
                container_selector=candidate['containerSelector'],
                item_selector=candidate['itemSelector'],
                item_count=candidate['itemCount'],
                confidence=candidate['confidence'],
                structure_hash=candidate['structureHash'],
                sample_items=candidate.get('sampleItems', []),
                suggested_fields=suggested_fields
            ))

        return results

    def _generate_list_name(self, candidate: Dict, fields: List[SuggestedField]) -> str:
        """根据检测结果生成列表名称"""
        # 检查示例数据
        sample = candidate.get('sampleItems', [{}])[0] if candidate.get('sampleItems') else {}

        # 根据字段类型推断
        has_image = any(f.field_type == FieldType.IMAGE for f in fields)
        has_price = any(f.field_type == FieldType.PRICE for f in fields)
        has_rating = any(f.field_type == FieldType.RATING for f in fields)

        if has_price and has_image:
            return "商品列表"
        if has_rating:
            return "评分列表"
        if has_image:
            return "图文列表"

        # 根据容器选择器推断
        selector = candidate.get('containerSelector', '').lower()
        if 'product' in selector or 'goods' in selector:
            return "商品列表"
        if 'movie' in selector or 'film' in selector:
            return "电影列表"
        if 'news' in selector or 'article' in selector:
            return "文章列表"
        if 'user' in selector or 'member' in selector:
            return "用户列表"

        return "数据列表"

    async def get_best_list(self, page: Page) -> Optional[DetectedList]:
        """获取置信度最高的列表"""
        results = await self.detect_lists(page)
        return results[0] if results else None
