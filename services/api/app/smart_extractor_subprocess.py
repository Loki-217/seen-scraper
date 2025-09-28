# services/api/app/smart_extractor_subprocess.py
from typing import Dict, List, Any
from pydantic import BaseModel
import subprocess
import sys
import os
import json
import re

class FieldSuggestion(BaseModel):
    name: str
    selector: str
    type: str
    confidence: float
    sample_data: List[str]
    count: int

class SmartExtractor:
    """使用子进程运行 Crawl4AI 的智能提取器"""
    
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
        ],
        'email': [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        ]
    }
    
    async def analyze_page(self, url: str) -> Dict[str, Any]:
        """分析页面并返回字段建议"""
        try:
            # 获取 crawler_runner.py 的路径
            runner_path = os.path.join(
                os.path.dirname(__file__), 
                'crawler_runner.py'
            )
            
            print(f"Running crawler for: {url}")
            
            # 替换成这段
            result = subprocess.run(
                [sys.executable, runner_path, url],
                capture_output=True,
                timeout=60
            ) 
            
            # 替换成这段
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
               # 日志会在 stderr 中，这是正常的
                print(f"Crawler stderr output:\n{error_msg}")  # 这会显示在服务器终端
    
            # 但如果没有 stdout，才是真的错误
            if not result.stdout:
                return {
                    "success": False,
                    "error": f"Crawler failed with code {result.returncode}",
                    "suggestions": []
                         }
            
            # 替换成这段
            # 处理输出编码
            if result.stdout:
                try:
                    output_text = result.stdout.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        output_text = result.stdout.decode('gbk')
                    except:
                        output_text = result.stdout.decode('utf-8', errors='ignore')
            else:
                output_text = ""

            try:
                data = json.loads(output_text) if output_text else {}
            except json.JSONDecodeError as e:                                                                            

                print(f"Failed to parse JSON: {result.stdout[:500]}")
                return {
                    "success": False,
                    "error": f"JSON parse error: {str(e)}",
                    "suggestions": []
                }
            
            # 检查爬取是否成功                   
            if not data.get('success'):
                return {
                    "success": False,
                    "error": data.get('error', 'Crawl failed'),
                    "suggestions": []
                }
            
            # 分析爬取的数据
            suggestions = self._analyze_crawl_data(data)
            
            # 构建响应
            return {
                "success": True,
                "url": url,
                "title": self._extract_title(data),
                "suggestions": [s.dict() for s in suggestions],
                "stats": self._extract_stats(data)
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Page loading timeout (60s)",
                "suggestions": []
            }
        except Exception as e:
            print(f"Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "suggestions": []
            }
    
    def _analyze_crawl_data(self, data: Dict) -> List[FieldSuggestion]:
        """分析爬取的数据并生成字段建议"""
        suggestions = []
        
        # 1. 分析 Markdown 内容（标题）
        if data.get('markdown'):
            markdown_suggestions = self._analyze_markdown(data['markdown'])
            suggestions.extend(markdown_suggestions)
        
        # 2. 分析 HTML 结构
        if data.get('html'):
            html_suggestions = self._analyze_html(data['html'])
            suggestions.extend(html_suggestions)
        
        # 3. 分析纯文本（价格、日期等）
        if data.get('text'):
            text_suggestions = self._analyze_text(data['text'])
            suggestions.extend(text_suggestions)
        
        # 4. 分析链接
        if data.get('links'):
            link_suggestions = self._analyze_links(data['links'])
            suggestions.extend(link_suggestions)
        
        # 5. 分析媒体
        if data.get('media'):
            media_suggestions = self._analyze_media(data['media'])
            suggestions.extend(media_suggestions)
        
        return suggestions
    
    def _analyze_markdown(self, markdown: str) -> List[FieldSuggestion]:
        """分析 Markdown 内容"""
        suggestions = []
        
        # H1 标题
        h1_matches = re.findall(r'^# (.+)$', markdown, re.MULTILINE)
        if h1_matches:
            suggestions.append(FieldSuggestion(
                name="主标题",
                selector="h1",
                type="text",
                confidence=0.9,
                sample_data=[m.strip() for m in h1_matches[:3]],
                count=len(h1_matches)
            ))
        
        # H2 标题
        h2_matches = re.findall(r'^## (.+)$', markdown, re.MULTILINE)
        if h2_matches:
            suggestions.append(FieldSuggestion(
                name="副标题",
                selector="h2",
                type="text",
                confidence=0.85,
                sample_data=[m.strip() for m in h2_matches[:3]],
                count=len(h2_matches)
            ))
        
        # H3 标题
        h3_matches = re.findall(r'^### (.+)$', markdown, re.MULTILINE)
        if h3_matches:
            suggestions.append(FieldSuggestion(
                name="三级标题",
                selector="h3",
                type="text",
                confidence=0.8,
                sample_data=[m.strip() for m in h3_matches[:3]],
                count=len(h3_matches)
            ))
        
        return suggestions
    
    def _analyze_html(self, html: str) -> List[FieldSuggestion]:
        """分析 HTML 结构"""
        suggestions = []
        
        # 列表项
        list_items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL | re.IGNORECASE)
        if len(list_items) >= 3:  # 至少3个列表项
            clean_items = []
            for item in list_items[:5]:
                # 清理 HTML 标签
                clean_text = re.sub(r'<[^>]+>', '', item).strip()
                clean_text = re.sub(r'\s+', ' ', clean_text)  # 压缩空白
                if clean_text and len(clean_text) > 2:
                    clean_items.append(clean_text[:100])
            
            if clean_items:
                suggestions.append(FieldSuggestion(
                    name="列表项",
                    selector="li",
                    type="text",
                    confidence=0.85,
                    sample_data=clean_items[:3],
                    count=len(list_items)
                ))
        
        # 段落
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.IGNORECASE)
        if paragraphs:
            clean_paragraphs = []
            for p in paragraphs[:3]:
                clean_text = re.sub(r'<[^>]+>', '', p).strip()
                clean_text = re.sub(r'\s+', ' ', clean_text)
                if clean_text and len(clean_text) > 10:
                    clean_paragraphs.append(clean_text[:150])
            
            if clean_paragraphs:
                suggestions.append(FieldSuggestion(
                    name="段落",
                    selector="p",
                    type="text",
                    confidence=0.75,
                    sample_data=clean_paragraphs,
                    count=len(paragraphs)
                ))
        
        # 表格
        tables = re.findall(r'<table[^>]*>.*?</table>', html, re.DOTALL | re.IGNORECASE)
        if tables:
            suggestions.append(FieldSuggestion(
                name="表格",
                selector="table",
                type="table",
                confidence=0.8,
                sample_data=[f"表格 {i+1}" for i in range(min(3, len(tables)))],
                count=len(tables)
            ))
        
        return suggestions
    
    def _analyze_text(self, text: str) -> List[FieldSuggestion]:
        """分析纯文本内容"""
        suggestions = []
        
        # 价格
        price_matches = []
        for pattern in self.PATTERNS['price']:
            matches = re.findall(pattern, text, re.IGNORECASE)
            price_matches.extend(matches)
        
        if price_matches:
            unique_prices = list(set(price_matches))[:5]
            suggestions.append(FieldSuggestion(
                name="价格",
                selector=".price, [class*='price'], [class*='cost']",
                type="price",
                confidence=0.7,
                sample_data=unique_prices,
                count=len(price_matches)
            ))
        
        # 日期
        date_matches = []
        for pattern in self.PATTERNS['date']:
            matches = re.findall(pattern, text)
            date_matches.extend(matches)
        
        if date_matches:
            unique_dates = list(set(date_matches))[:5]
            suggestions.append(FieldSuggestion(
                name="日期",
                selector=".date, [class*='date'], time",
                type="date",
                confidence=0.65,
                sample_data=unique_dates,
                count=len(date_matches)
            ))
        
        # 邮箱
        email_matches = []
        for pattern in self.PATTERNS['email']:
            matches = re.findall(pattern, text)
            email_matches.extend(matches)
        
        if email_matches:
            unique_emails = list(set(email_matches))[:3]
            suggestions.append(FieldSuggestion(
                name="邮箱",
                selector="a[href^='mailto:']",
                type="email",
                confidence=0.9,
                sample_data=unique_emails,
                count=len(email_matches)
            ))
        
        return suggestions
    
    def _analyze_links(self, links: Dict) -> List[FieldSuggestion]:
        """分析链接"""
        suggestions = []
        
        # 内部链接
        internal_links = links.get('internal', []) if isinstance(links, dict) else []
        if len(internal_links) > 0:
            link_samples = []
            for link in internal_links[:5]:
                if isinstance(link, dict):
                    text = link.get('text', '').strip()
                    href = link.get('href', '')
                    if text:
                        link_samples.append(f"{text[:30]}")
                elif isinstance(link, str):
                    link_samples.append(link[:50])
            
            if link_samples:
                suggestions.append(FieldSuggestion(
                    name="内部链接",
                    selector="a[href^='/'], a[href*='://']",
                    type="link",
                    confidence=0.8,
                    sample_data=link_samples[:3],
                    count=len(internal_links)
                ))
        
        # 外部链接
        external_links = links.get('external', []) if isinstance(links, dict) else []
        if len(external_links) > 0:
            ext_samples = []
            for link in external_links[:3]:
                if isinstance(link, dict):
                    text = link.get('text', '').strip()
                    if text:
                        ext_samples.append(text[:30])
                elif isinstance(link, str):
                    ext_samples.append(link[:50])
            
            if ext_samples:
                suggestions.append(FieldSuggestion(
                    name="外部链接",
                    selector="a[href^='http']",
                    type="link",
                    confidence=0.75,
                    sample_data=ext_samples,
                    count=len(external_links)
                ))
        
        return suggestions
    
    def _analyze_media(self, media: Dict) -> List[FieldSuggestion]:
        """分析媒体内容"""
        suggestions = []
        
        # 图片
        images = media.get('images', []) if isinstance(media, dict) else []
        if images:
            img_samples = []
            for img in images[:3]:
                if isinstance(img, dict):
                    alt = img.get('alt', '')
                    src = img.get('src', '')
                    sample = alt if alt else src[:50]
                    img_samples.append(sample)
                elif isinstance(img, str):
                    img_samples.append(img[:50])
            
            if img_samples:
                suggestions.append(FieldSuggestion(
                    name="图片",
                    selector="img",
                    type="image",
                    confidence=0.9,
                    sample_data=img_samples,
                    count=len(images)
                ))
        
        # 视频
        videos = media.get('videos', []) if isinstance(media, dict) else []
        if videos:
            suggestions.append(FieldSuggestion(
                name="视频",
                selector="video, iframe[src*='youtube'], iframe[src*='vimeo']",
                type="video",
                confidence=0.85,
                sample_data=[f"视频 {i+1}" for i in range(min(3, len(videos)))],
                count=len(videos)
            ))
        
        return suggestions
    
    def _extract_title(self, data: Dict) -> str:
        """提取页面标题"""
        if data.get('metadata') and isinstance(data['metadata'], dict):
            return data['metadata'].get('title', '')
        return ''
    
    def _extract_stats(self, data: Dict) -> Dict[str, int]:
        """提取统计信息"""
        stats = {
            "total_words": data.get('word_count', 0),
            "total_links": 0,
            "total_images": 0
        }
        
        # 统计链接
        if data.get('links') and isinstance(data['links'], dict):
            internal = len(data['links'].get('internal', []))
            external = len(data['links'].get('external', []))
            stats['total_links'] = internal + external
        
        # 统计图片
        if data.get('media') and isinstance(data['media'], dict):
            stats['total_images'] = len(data['media'].get('images', []))
        
        return stats