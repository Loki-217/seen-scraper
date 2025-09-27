# services/api/app/smart_extractor.py
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import re
import json
import subprocess
import sys
import os

class FieldSuggestion(BaseModel):
    """字段建议"""
    name: str
    selector: str
    type: str
    confidence: float
    sample_data: List[str]
    count: int

class SmartExtractor:
    """智能页面分析器 - 使用子进程运行 Crawl4AI"""
    
    # 常见字段模式
    PATTERNS = {
        'price': [
            r'[\$€£¥]\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*[\$€£¥元]',
            r'(?:价格|售价|Price)[：:]\s*[\d,]+\.?\d*'
        ],
        'date': [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',
            r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',
            r'\d+\s*(?:天前|小时前|分钟前|days?\s*ago|hours?\s*ago)'
        ]
    }
    
    async def analyze_page(self, url: str) -> Dict[str, Any]:
        """智能分析页面，返回字段建议"""
        try:
            # 使用子进程运行 crawler_runner.py
            runner_path = os.path.join(
                os.path.dirname(__file__), 
                'crawler_runner.py'
            )
            
            # 运行子进程
            process = await asyncio.create_subprocess_exec(
                sys.executable, 
                runner_path, 
                url,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore')
                print(f"Crawler error: {error_msg}")
                return {
                    "success": False,
                    "error": f"Crawler failed: {error_msg}",
                    "suggestions": []
                }
            
            # 解析结果
            try:
                result = json.loads(stdout.decode('utf-8'))
            except json.JSONDecodeError as e:
                print(f"Failed to parse crawler output: {stdout.decode('utf-8', errors='ignore')}")
                return {
                    "success": False,
                    "error": f"Failed to parse result: {str(e)}",
                    "suggestions": []
                }
            
            if not result.get('success'):
                return {
                    "success": False,
                    "error": result.get('error', 'Unknown error'),
                    "suggestions": []
                }
            
            # 分析页面结构
            suggestions = []
            
            # 1. 分析标题
            if result.get('markdown'):
                titles = self._analyze_titles_from_markdown(result['markdown'])
                suggestions.extend(titles)
            
            # 2. 分析列表
            if result.get('html'):
                lists = self._analyze_lists_from_html(result['html'])
                suggestions.extend(lists)
            
            # 3. 分析特殊字段
            if result.get('text'):
                special = self._analyze_special_fields_from_text(result['text'])
                suggestions.extend(special)
            
            # 4. 分析链接
            if result.get('links'):
                links = self._analyze_links(result['links'])
                suggestions.extend(links)
            
            # 5. 分析图片
            if result.get('media', {}).get('images'):
                images = self._analyze_images(result['media']['images'])
                suggestions.extend(images)
            
            # 转换为字典
            suggestions_dict = [
                {
                    "name": s.name,
                    "selector": s.selector,
                    "type": s.type,
                    "confidence": s.confidence,
                    "sample_data": s.sample_data,
                    "count": s.count
                } for s in suggestions
            ]
            
            return {
                "success": True,
                "url": url,
                "title": result.get('metadata', {}).get('title', ''),
                "suggestions": suggestions_dict,
                "stats": {
                    "total_words": result.get('word_count', 0),
                    "total_links": self._count_links(result.get('links', {})),
                    "total_images": len(result.get('media', {}).get('images', []))
                }
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "suggestions": []
            }
    
    def _analyze_titles_from_markdown(self, markdown: str) -> List[FieldSuggestion]:
        """从 Markdown 分析标题"""
        suggestions = []
        
        # 查找 # 标题
        h1_matches = re.findall(r'^# (.+)$', markdown, re.MULTILINE)
        if h1_matches:
            suggestions.append(FieldSuggestion(
                name="主标题",
                selector="h1",
                type="text",
                confidence=0.9,
                sample_data=h1_matches[:3],
                count=len(h1_matches)
            ))
        
        # 查找 ## 副标题
        h2_matches = re.findall(r'^## (.+)$', markdown, re.MULTILINE)
        if h2_matches:
            suggestions.append(FieldSuggestion(
                name="副标题",
                selector="h2",
                type="text",
                confidence=0.8,
                sample_data=h2_matches[:3],
                count=len(h2_matches)
            ))
        
        return suggestions
    
    def _analyze_lists_from_html(self, html: str) -> List[FieldSuggestion]:
        """从 HTML 分析列表"""
        suggestions = []
        
        # 查找列表项
        list_items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
        if len(list_items) > 3:
            clean_items = []
            for item in list_items[:5]:
                clean_text = re.sub(r'<.*?>', '', item).strip()[:100]
                if clean_text:
                    clean_items.append(clean_text)
            
            if clean_items:
                suggestions.append(FieldSuggestion(
                    name="列表项",
                    selector="li",
                    type="text",
                    confidence=0.85,
                    sample_data=clean_items[:3],
                    count=len(list_items)
                ))
        
        return suggestions
    
    def _analyze_special_fields_from_text(self, text: str) -> List[FieldSuggestion]:
        """分析特殊字段"""
        suggestions = []
        
        # 检测价格
        for pattern in self.PATTERNS['price']:
            matches = re.findall(pattern, text)
            if matches:
                suggestions.append(FieldSuggestion(
                    name="价格",
                    selector=".price, [class*='price']",
                    type="price",
                    confidence=0.75,
                    sample_data=list(set(matches[:5])),
                    count=len(matches)
                ))
                break
        
        return suggestions
    
    def _analyze_links(self, links: Dict) -> List[FieldSuggestion]:
        """分析链接"""
        suggestions = []
        
        internal_links = links.get("internal", []) if isinstance(links, dict) else []
        if internal_links:
            link_texts = []
            for link in internal_links[:10]:
                if isinstance(link, dict):
                    text = link.get('text', '')
                    if text:
                        link_texts.append(text[:50])
            
            if link_texts:
                suggestions.append(FieldSuggestion(
                    name="内部链接",
                    selector="a[href]",
                    type="link",
                    confidence=0.8,
                    sample_data=link_texts[:3],
                    count=len(internal_links)
                ))
        
        return suggestions
    
    def _analyze_images(self, images: List) -> List[FieldSuggestion]:
        """分析图片"""
        suggestions = []
        
        if images:
            image_samples = []
            for img in images[:5]:
                if isinstance(img, dict):
                    sample = img.get('alt', img.get('src', 'image'))[:50]
                else:
                    sample = str(img)[:50]
                image_samples.append(sample)
            
            if image_samples:
                suggestions.append(FieldSuggestion(
                    name="图片",
                    selector="img",
                    type="image",
                    confidence=0.9,
                    sample_data=image_samples[:3],
                    count=len(images)
                ))
        
        return suggestions
    
    def _count_links(self, links: Dict) -> int:
        """统计链接数量"""
        if not isinstance(links, dict):
            return 0
        internal = len(links.get("internal", []))
        external = len(links.get("external", []))
        return internal + external

# 需要导入 asyncio
import asyncio