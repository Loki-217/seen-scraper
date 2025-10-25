# services/api/app/ai_service.py
"""
AI 服务模块：调用 DeepSeek API 进行智能字段命名
"""
import re
import json
import httpx
from typing import Dict, Optional
from .settings import settings


class AIService:
    """AI 服务：智能字段命名"""
    
    def __init__(self):
        self.api_key = settings.deepseek_api_key
        self.endpoint_id = settings.deepseek_endpoint_id
        self.api_base = settings.deepseek_api_base
        # 只有 API Key 和 Endpoint ID 都存在时才启用
        self.enabled = (
            settings.ai_enabled 
            and bool(self.api_key) 
            and bool(self.endpoint_id)
        )
    
    def suggest_field_name(
        self, 
        element: Dict, 
        context: Optional[Dict] = None
    ) -> Dict:
        """
        智能建议字段名
        
        Args:
            element: 元素信息 {text, tagName, className, id, href, src}
            context: 上下文信息 {previousText, parentClassName, surroundingText}
        
        Returns:
            {
                "success": True,
                "fieldName": "评分",
                "confidence": 0.95,
                "source": "ai" | "rule",
                "reasoning": "判断依据"
            }
        """
        # 1. 先用规则判断
        rule_result = self._rule_based_suggest(element, context or {})
        
        # 2. 如果规则判断置信度高，直接返回
        if rule_result['confidence'] >= 0.8:
            return {
                "success": True,
                **rule_result,
                "source": "rule"
            }
        
        # 3. 规则不确定，尝试调用 AI
        if not self.enabled:
            # AI 未启用，降级到规则结果
            return {
                "success": True,
                **rule_result,
                "source": "rule"
            }
        
        try:
            ai_result = self._ai_suggest(element, context or {})
            return {
                "success": True,
                **ai_result,
                "source": "ai"
            }
        except Exception as e:
            # AI 调用失败，降级到规则结果
            print(f"[AI] Error: {e}, fallback to rule")
            return {
                "success": True,
                **rule_result,
                "source": "rule",
                "ai_error": str(e)
            }
    
    def _rule_based_suggest(self, element: Dict, context: Dict) -> Dict:
        """基于规则的字段名建议"""
        text = (element.get('text') or '').strip().lower()
        tag = (element.get('tagName') or '').lower()
        class_name = (element.get('className') or '').lower()
        prev_text = (context.get('previousText') or '').lower()
        surrounding = (context.get('surroundingText') or '').lower()
        
        # 规则1: 标签名判断
        if tag in ['h1', 'h2', 'h3']:
            return {'fieldName': '标题', 'confidence': 0.9, 'reasoning': '根据标签名判断'}
        if tag == 'h4':
            return {'fieldName': '副标题', 'confidence': 0.85, 'reasoning': '根据标签名判断'}
        if tag == 'a' and element.get('href'):
            return {'fieldName': '链接', 'confidence': 0.9, 'reasoning': '根据标签名判断'}
        if tag == 'img':
            return {'fieldName': '图片', 'confidence': 0.95, 'reasoning': '根据标签名判断'}
        
        # 规则2: 内容特征判断
        # 价格
        if any(symbol in text for symbol in ['￥', '$', '¥', '€', '£']):
            return {'fieldName': '价格', 'confidence': 0.9, 'reasoning': '包含货币符号'}
        if re.search(r'\d+\.?\d*元', text):
            return {'fieldName': '价格', 'confidence': 0.85, 'reasoning': '包含金额格式'}
        
        # 评分
        if re.match(r'^\d+\.?\d*$', text) and any(kw in surrounding for kw in ['评分', '分', '⭐', 'star', 'rating']):
            return {'fieldName': '评分', 'confidence': 0.85, 'reasoning': '数字+评分关键词'}
        
        # 日期
        if re.match(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}', text):
            return {'fieldName': '日期', 'confidence': 0.9, 'reasoning': '日期格式'}
        if any(kw in text for kw in ['年', '月', '日', '时间', '发布']):
            return {'fieldName': '时间', 'confidence': 0.75, 'reasoning': '包含时间关键词'}
        
        # 规则3: Class 名判断
        if 'price' in class_name:
            return {'fieldName': '价格', 'confidence': 0.8, 'reasoning': 'class 名包含 price'}
        if 'title' in class_name:
            return {'fieldName': '标题', 'confidence': 0.75, 'reasoning': 'class 名包含 title'}
        if any(kw in class_name for kw in ['score', 'rating', 'rate']):
            return {'fieldName': '评分', 'confidence': 0.8, 'reasoning': 'class 名包含评分关键词'}
        if 'time' in class_name or 'date' in class_name:
            return {'fieldName': '时间', 'confidence': 0.75, 'reasoning': 'class 名包含时间关键词'}
        if 'tag' in class_name or 'label' in class_name:
            return {'fieldName': '标签', 'confidence': 0.7, 'reasoning': 'class 名包含标签关键词'}
        if 'author' in class_name or 'user' in class_name:
            return {'fieldName': '作者', 'confidence': 0.75, 'reasoning': 'class 名包含作者关键词'}
        
        # 规则4: 前置 label 判断
        if prev_text:
            if '价格' in prev_text or 'price' in prev_text:
                return {'fieldName': '价格', 'confidence': 0.85, 'reasoning': '前置标签为价格'}
            if '标题' in prev_text or 'title' in prev_text:
                return {'fieldName': '标题', 'confidence': 0.85, 'reasoning': '前置标签为标题'}
            if '评分' in prev_text or 'rating' in prev_text:
                return {'fieldName': '评分', 'confidence': 0.85, 'reasoning': '前置标签为评分'}
        
        # 规则5: 内容长度判断
        if len(text) > 100:
            return {'fieldName': '描述', 'confidence': 0.6, 'reasoning': '文本较长'}
        if len(text) > 50:
            return {'fieldName': '简介', 'confidence': 0.55, 'reasoning': '文本中等'}
        
        # 默认
        return {'fieldName': '字段', 'confidence': 0.3, 'reasoning': '无法识别，使用默认名称'}
    
    def _ai_suggest(self, element: Dict, context: Dict) -> Dict:
        """调用 DeepSeek API 进行智能建议"""
        prompt = self._build_prompt(element, context)
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'model': self.endpoint_id,  # 使用接入点 ID
            'messages': [
                {
                    'role': 'system',
                    'content': '你是一个专业的网页数据采集助手，负责为用户的采集字段起一个清晰、易懂的中文名称。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.1,
            'max_tokens': 200
        }
        
        print(f"[AI] Calling DeepSeek API...")
        print(f"[AI] Endpoint: {self.endpoint_id}")
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f'{self.api_base}/chat/completions',
                headers=headers,
                json=payload
            )
            
            print(f"[AI] Response status: {response.status_code}")
            response.raise_for_status()
            
            data = response.json()
            content = data['choices'][0]['message']['content'].strip()
            
            print(f"[AI] Response: {content}")
            
            result = self._parse_ai_response(content)
            return result
    
    def _build_prompt(self, element: Dict, context: Dict) -> str:
        """构建 Prompt"""
        prompt = f"""你是一个网页数据采集专家。用户正在配置采集规则，需要你帮忙给字段起名字。

【元素信息】
- 文本内容: "{element.get('text', '')[:100]}"
- HTML 标签: {element.get('tagName', '')}
- CSS 类名: {element.get('className', '')}
- ID: {element.get('id', '')}
- 链接: {element.get('href', '')}
- 图片: {element.get('src', '')}

【上下文信息】
- 前一个元素文本: "{context.get('previousText', '')}"
- 父元素类名: {context.get('parentClassName', '')}
- 周围文本: "{context.get('surroundingText', '')[:200]}"
- 是否在列表中: {context.get('isInList', False)}

【常见字段名参考】
标题、副标题、价格、评分、链接、图片、作者、时间、日期、标签、描述、简介、类型、分类

【要求】
1. 根据以上信息判断字段名
2. 字段名必须是 2-6 个中文字符
3. 必须清晰易懂，符合用户习惯
4. 只返回 JSON 格式，不要有其他文字

【输出格式】
{{
  "fieldName": "字段名",
  "confidence": 0.95
}}

请开始分析："""
        
        return prompt
    
    def _parse_ai_response(self, content: str) -> Dict:
        """解析 AI 返回的内容"""
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                result = json.loads(json_match.group())
                field_name = result.get('fieldName', '字段')
                confidence = float(result.get('confidence', 0.7))
                
                # 验证字段名合理性
                if not field_name or len(field_name) > 10 or not re.match(r'^[\u4e00-\u9fa5a-zA-Z]+$', field_name):
                    field_name = '字段'
                    confidence = 0.5
                
                return {
                    'fieldName': field_name,
                    'confidence': min(confidence, 0.95),
                    'reasoning': 'AI 分析'
                }
        except Exception as e:
            print(f"[AI] Parse error: {e}, content: {content}")
        
        # 解析失败，返回默认值
        return {
            'fieldName': '字段',
            'confidence': 0.5,
            'reasoning': 'AI 解析失败'
        }


# 全局实例
ai_service = AIService()


# ========== 网站配置分析功能 ==========

def suggest_website_config(url: str, page_info: Dict) -> Dict[str, any]:
    """
    调用 DeepSeek 分析网站类型并推荐配置

    Args:
        url: 网站 URL
        page_info: 页面信息摘要 {title, image_count, article_count, has_pagination, has_lazy_load, ...}

    Returns:
        {
            "site_name": "网站名称",
            "site_type": "photo_sharing|ecommerce|news|...",
            "load_type": "infinite_scroll|pagination|static",
            "config": {...},
            "confidence": 0.95,
            "reasoning": "判断依据"
        }
    """
    if not ai_service.enabled:
        raise Exception("AI 服务未启用")

    # 构建 prompt
    prompt = f"""请分析这个网页的数据加载方式，并推荐爬虫配置。

【网站信息】
- URL: {url}
- 标题: {page_info.get('title', 'N/A')}
- 图片数量: {page_info.get('image_count', 0)}
- 文章数量: {page_info.get('article_count', 0)}
- 列表项数量: {page_info.get('item_count', 0)}
- 是否有翻页: {page_info.get('has_pagination', False)}
- 是否有懒加载: {page_info.get('has_lazy_load', False)}

【判断要求】
1. 网站类型 (site_type)：
   - photo_sharing: 图片分享网站 (Unsplash, Pinterest等)
   - ecommerce: 电商平台
   - news: 新闻网站
   - social_media: 社交媒体
   - video_platform: 视频平台
   - general: 其他类型

2. 加载方式 (load_type)：
   - infinite_scroll: 无限滚动（滚动到底部自动加载新内容）
   - pagination: 翻页（有"下一页"按钮）
   - static: 静态单页（所有内容一次性加载）

3. 推荐配置 (config)：
   - use_stealth: 是否需要隐身模式（避免反爬虫）
   - auto_scroll: 是否自动滚动
   - max_scrolls: 最大滚动次数（10-50）
   - scroll_delay: 每次滚动等待时间（毫秒，1000-5000）
   - stable_checks: 稳定性检查次数（2-5）

【配置建议】
- 图片网站：scroll_delay 应该更长（3000-4000ms）
- 反爬虫严格的网站：use_stealth 必须为 true
- 内容多的网站：max_scrolls 增加（30-50）

【输出格式】
只返回 JSON，不要有其他内容：
{{
    "site_name": "网站名称",
    "site_type": "photo_sharing",
    "load_type": "infinite_scroll",
    "config": {{
        "use_stealth": true,
        "auto_scroll": true,
        "max_scrolls": 30,
        "scroll_delay": 3000,
        "stable_checks": 5
    }},
    "confidence": 0.95,
    "reasoning": "简要说明判断依据（50字以内）"
}}

请开始分析："""

    try:
        headers = {
            'Authorization': f'Bearer {ai_service.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': ai_service.endpoint_id,
            'messages': [
                {
                    'role': 'system',
                    'content': '你是一个专业的网页爬虫配置专家，负责分析网站特征并推荐最优的爬虫参数。'
                },
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.1,
            'max_tokens': 500
        }

        print(f"[AI] 调用 DeepSeek 分析网站: {url}")

        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f'{ai_service.api_base}/chat/completions',
                headers=headers,
                json=payload
            )

            print(f"[AI] 响应状态: {response.status_code}")
            response.raise_for_status()

            data = response.json()
            content = data['choices'][0]['message']['content'].strip()

            print(f"[AI] 响应内容: {content[:200]}...")

            # 解析 JSON
            result = _parse_website_config_response(content)
            return result

    except Exception as e:
        print(f"[AI] 网站分析失败: {e}")
        raise


def _parse_website_config_response(content: str) -> Dict:
    """解析网站配置分析的响应"""
    try:
        # 提取 JSON（可能有 markdown 代码块）
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())

            # 验证必需字段
            required_fields = ['site_type', 'load_type', 'config']
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"缺少必需字段: {field}")

            # 设置默认值
            result.setdefault('site_name', 'Unknown')
            result.setdefault('confidence', 0.8)
            result.setdefault('reasoning', '')

            # 验证 config 字段
            config = result['config']
            config.setdefault('use_stealth', True)
            config.setdefault('auto_scroll', True)
            config.setdefault('max_scrolls', 20)
            config.setdefault('scroll_delay', 2500)
            config.setdefault('stable_checks', 3)

            return result

        raise ValueError("未找到有效的 JSON 内容")

    except Exception as e:
        print(f"[AI] 解析失败: {e}, content: {content}")

        # 降级返回默认配置
        return {
            'site_name': 'Unknown',
            'site_type': 'general',
            'load_type': 'infinite_scroll',
            'config': {
                'use_stealth': True,
                'auto_scroll': True,
                'max_scrolls': 20,
                'scroll_delay': 2500,
                'stable_checks': 3
            },
            'confidence': 0.5,
            'reasoning': 'AI 分析失败，使用默认配置'
        }