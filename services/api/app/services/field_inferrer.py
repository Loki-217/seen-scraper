# services/api/app/services/field_inferrer.py
"""
字段类型智能推断器

功能:
- 基于元素标签、类名、文本内容推断字段类型
- 提取和格式化值
- 建议字段名称
"""

import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from ..models_v2.smart import FieldType, InferenceResult


class FieldTypeInferrer:
    """字段类型推断器"""

    # 价格模式
    PRICE_PATTERNS = [
        (r'[\$€£¥]\s*[\d,]+\.?\d*', 'currency_prefix'),
        (r'[\d,]+\.?\d*\s*[元円]', 'currency_suffix'),
        (r'[\d,]+\.?\d*\s*(USD|CNY|EUR|RMB|JPY)', 'currency_code'),
        (r'[¥$€£]\d+', 'simple_currency'),
    ]

    # 日期模式
    DATE_PATTERNS = [
        (r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?', 'date_cn'),
        (r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', 'date_slash'),
        (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}', 'date_en'),
        (r'\d{4}-\d{2}-\d{2}', 'date_iso'),
        (r'\d+\s*(天|小时|分钟|秒|周|月|年)前', 'date_relative'),
        (r'(刚刚|今天|昨天|前天)', 'date_relative_cn'),
    ]

    # 评分模式
    RATING_PATTERNS = [
        (r'[\d.]+\s*[/／]\s*[\d.]+', 'rating_fraction'),
        (r'[\d.]+\s*分', 'rating_cn'),
        (r'[★☆]+', 'rating_star'),
        (r'\d+(\.\d+)?\s*stars?', 'rating_en'),
    ]

    # 其他模式
    EMAIL_PATTERN = r'[\w\.-]+@[\w\.-]+\.\w+'
    PHONE_CN_PATTERN = r'1[3-9]\d{9}'
    PHONE_INTL_PATTERN = r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    PERCENTAGE_PATTERN = r'\d+\.?\d*\s*%'
    NUMBER_PATTERN = r'^[\d,]+\.?\d*$'

    # 类名关键词映射
    CLASS_KEYWORDS = {
        FieldType.PRICE: ['price', 'cost', 'money', 'fee', 'amount', '价格', '售价'],
        FieldType.TITLE: ['title', 'name', 'heading', '标题', '名称', '商品名'],
        FieldType.DATE: ['date', 'time', 'created', 'updated', 'publish', '日期', '时间'],
        FieldType.RATING: ['rating', 'score', 'star', 'rate', '评分', '评价', '星级'],
        FieldType.TEXT: ['desc', 'description', 'content', 'summary', 'intro', '描述', '简介'],
        FieldType.IMAGE: ['img', 'image', 'photo', 'pic', 'cover', 'thumb', '图片', '封面'],
    }

    # 字段类型默认名称
    TYPE_DEFAULT_NAMES = {
        FieldType.TEXT: '文本',
        FieldType.TITLE: '标题',
        FieldType.PRICE: '价格',
        FieldType.DATE: '日期',
        FieldType.DATETIME: '时间',
        FieldType.EMAIL: '邮箱',
        FieldType.PHONE: '电话',
        FieldType.URL: '链接',
        FieldType.IMAGE: '图片',
        FieldType.RATING: '评分',
        FieldType.NUMBER: '数值',
        FieldType.PERCENTAGE: '百分比',
    }

    def infer(self, text: str, element_info: Dict[str, Any] = None) -> InferenceResult:
        """
        推断字段类型

        Args:
            text: 文本内容
            element_info: 元素信息 {tag, className, id, href, src, ...}

        Returns:
            InferenceResult
        """
        element_info = element_info or {}
        text = (text or '').strip()

        # 1. 基于元素标签
        tag = (element_info.get('tag') or '').lower()
        result = self._infer_by_tag(tag, element_info)
        if result and result.confidence >= 0.9:
            return result

        # 2. 基于 class/id 名称
        class_result = self._infer_by_class(element_info)
        if class_result and class_result.confidence >= 0.85:
            return class_result

        # 3. 基于文本内容正则匹配
        text_result = self._infer_by_text(text)
        if text_result:
            return text_result

        # 4. 合并判断
        if result and class_result:
            # 两者一致则提高置信度
            if result.field_type == class_result.field_type:
                result.confidence = min(1.0, result.confidence + 0.1)
                return result
            # 不一致则选择置信度高的
            return result if result.confidence >= class_result.confidence else class_result

        # 5. 默认返回文本类型
        return InferenceResult(
            field_type=FieldType.TEXT,
            confidence=0.5,
            extracted_value=text,
            suggested_name='文本',
            extraction_attr='text'
        )

    def _infer_by_tag(self, tag: str, element_info: Dict) -> Optional[InferenceResult]:
        """基于元素标签推断"""

        # 图片
        if tag == 'img':
            src = element_info.get('src') or element_info.get('data-src', '')
            return InferenceResult(
                field_type=FieldType.IMAGE,
                confidence=0.95,
                extracted_value=src,
                suggested_name='图片',
                extraction_attr='src'
            )

        # 链接
        if tag == 'a':
            href = element_info.get('href', '')
            if href:
                return InferenceResult(
                    field_type=FieldType.URL,
                    confidence=0.9,
                    extracted_value=href,
                    suggested_name='链接',
                    extraction_attr='href'
                )

        # 标题
        if tag in ['h1', 'h2', 'h3', 'h4']:
            return InferenceResult(
                field_type=FieldType.TITLE,
                confidence=0.9,
                extracted_value=element_info.get('text', ''),
                suggested_name='标题',
                extraction_attr='text'
            )

        # 时间
        if tag == 'time':
            datetime_attr = element_info.get('datetime', '')
            return InferenceResult(
                field_type=FieldType.DATETIME,
                confidence=0.9,
                extracted_value=datetime_attr or element_info.get('text', ''),
                suggested_name='时间',
                extraction_attr='datetime' if datetime_attr else 'text'
            )

        return None

    def _infer_by_class(self, element_info: Dict) -> Optional[InferenceResult]:
        """基于 class/id 名称推断"""
        class_name = (element_info.get('className') or '').lower()
        element_id = (element_info.get('id') or '').lower()
        combined = f"{class_name} {element_id}"

        for field_type, keywords in self.CLASS_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in combined:
                    # 确定提取属性
                    if field_type == FieldType.IMAGE:
                        attr = 'src'
                        value = element_info.get('src', '')
                    elif field_type == FieldType.URL:
                        attr = 'href'
                        value = element_info.get('href', '')
                    else:
                        attr = 'text'
                        value = element_info.get('text', '')

                    return InferenceResult(
                        field_type=field_type,
                        confidence=0.85,
                        extracted_value=value,
                        suggested_name=self._suggest_name_from_class(keyword, field_type),
                        extraction_attr=attr
                    )

        return None

    def _infer_by_text(self, text: str) -> Optional[InferenceResult]:
        """基于文本内容正则匹配推断"""
        if not text:
            return None

        # 价格
        for pattern, _ in self.PRICE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = self._extract_price(match.group())
                return InferenceResult(
                    field_type=FieldType.PRICE,
                    confidence=0.9,
                    extracted_value=value,
                    suggested_name='价格',
                    extraction_attr='text'
                )

        # 日期
        for pattern, pattern_type in self.DATE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = self._extract_date(match.group(), pattern_type)
                return InferenceResult(
                    field_type=FieldType.DATE,
                    confidence=0.85,
                    extracted_value=value,
                    suggested_name='日期',
                    extraction_attr='text'
                )

        # 评分
        for pattern, pattern_type in self.RATING_PATTERNS:
            match = re.search(pattern, text)
            if match:
                value = self._extract_rating(match.group(), pattern_type)
                return InferenceResult(
                    field_type=FieldType.RATING,
                    confidence=0.85,
                    extracted_value=value,
                    suggested_name='评分',
                    extraction_attr='text'
                )

        # 邮箱
        if re.search(self.EMAIL_PATTERN, text):
            match = re.search(self.EMAIL_PATTERN, text)
            return InferenceResult(
                field_type=FieldType.EMAIL,
                confidence=0.95,
                extracted_value=match.group(),
                suggested_name='邮箱',
                extraction_attr='text'
            )

        # 电话
        phone_match = re.search(self.PHONE_CN_PATTERN, text) or re.search(self.PHONE_INTL_PATTERN, text)
        if phone_match:
            return InferenceResult(
                field_type=FieldType.PHONE,
                confidence=0.85,
                extracted_value=phone_match.group(),
                suggested_name='电话',
                extraction_attr='text'
            )

        # 百分比
        if re.search(self.PERCENTAGE_PATTERN, text):
            match = re.search(self.PERCENTAGE_PATTERN, text)
            value = float(re.sub(r'[^\d.]', '', match.group()))
            return InferenceResult(
                field_type=FieldType.PERCENTAGE,
                confidence=0.9,
                extracted_value=value,
                suggested_name='百分比',
                extraction_attr='text'
            )

        # 纯数字
        clean_text = text.replace(',', '').strip()
        if re.match(self.NUMBER_PATTERN, clean_text):
            try:
                value = float(clean_text)
                return InferenceResult(
                    field_type=FieldType.NUMBER,
                    confidence=0.7,
                    extracted_value=value,
                    suggested_name='数值',
                    extraction_attr='text'
                )
            except:
                pass

        return None

    def _extract_price(self, text: str) -> float:
        """提取价格数值"""
        # 移除货币符号和空格
        cleaned = re.sub(r'[¥$€£元円\s,]', '', text)
        cleaned = re.sub(r'(USD|CNY|EUR|RMB|JPY)', '', cleaned, flags=re.IGNORECASE)
        try:
            return float(cleaned)
        except:
            return 0.0

    def _extract_date(self, text: str, pattern_type: str) -> str:
        """提取日期，尝试标准化"""
        # 相对日期保持原样
        if pattern_type in ['date_relative', 'date_relative_cn']:
            return text

        # 尝试解析为标准格式
        try:
            # 中文日期
            if pattern_type == 'date_cn':
                cleaned = text.replace('年', '-').replace('月', '-').replace('日', '')
                return cleaned

            # ISO 格式
            if pattern_type == 'date_iso':
                return text

            # 其他格式保持原样
            return text
        except:
            return text

    def _extract_rating(self, text: str, pattern_type: str) -> float:
        """提取评分数值"""
        if pattern_type == 'rating_star':
            # 计算星星数
            filled = text.count('★')
            return float(filled)

        if pattern_type == 'rating_fraction':
            # 8.5/10 格式
            parts = re.split(r'[/／]', text)
            if len(parts) == 2:
                try:
                    return float(parts[0].strip())
                except:
                    pass

        if pattern_type == 'rating_cn':
            # 9.2分 格式
            match = re.search(r'[\d.]+', text)
            if match:
                return float(match.group())

        # 默认尝试提取数字
        match = re.search(r'[\d.]+', text)
        if match:
            return float(match.group())

        return 0.0

    def _suggest_name_from_class(self, keyword: str, field_type: FieldType) -> str:
        """根据类名关键词建议字段名"""
        # 中文关键词直接使用
        if any('\u4e00' <= c <= '\u9fff' for c in keyword):
            return keyword

        # 常见英文翻译
        translations = {
            'price': '价格',
            'cost': '成本',
            'title': '标题',
            'name': '名称',
            'date': '日期',
            'time': '时间',
            'rating': '评分',
            'score': '得分',
            'desc': '描述',
            'description': '描述',
            'content': '内容',
            'image': '图片',
            'cover': '封面',
        }

        if keyword.lower() in translations:
            return translations[keyword.lower()]

        # 默认使用类型名
        return self.TYPE_DEFAULT_NAMES.get(field_type, '字段')

    def batch_infer(self, items: List[Dict[str, Any]]) -> List[InferenceResult]:
        """批量推断多个元素"""
        return [self.infer(item.get('text', ''), item) for item in items]
