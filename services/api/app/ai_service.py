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
        
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                f'{self.api_base}/chat/completions',
                headers=headers,
                json=payload
            )
            
            response.raise_for_status()
            
            data = response.json()
            content = data['choices'][0]['message']['content'].strip()

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
        except Exception:
            pass

        # 解析失败，返回默认值
        return {
            'fieldName': '字段',
            'confidence': 0.5,
            'reasoning': 'AI 解析失败'
        }


# 全局实例
ai_service = AIService()