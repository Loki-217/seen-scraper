# services/api/app/smart_extractor_subprocess.py
from typing import Dict, List, Any
from pydantic import BaseModel
import subprocess
import sys
import os
import json
import re
from bs4 import BeautifulSoup
from collections import Counter

class FieldSuggestion(BaseModel):
    name: str
    selector: str
    type: str
    confidence: float
    sample_data: List[str]
    count: int

class SmartExtractor:
    """智能提取器 - 使用子进程运行 Crawl4AI"""
    
    # 改进的正则模式
    PATTERNS = {
        'price': [
            r'[\$€£¥]\s*[\d,]+\.?\d*',
            r'[\d,]+\.?\d*\s*[\$€£¥元]',
            r'(?:价格|售价|Price|price)[：:]\s*[\d,]+\.?\d*',
            r'\d+\.\d{2}',
        ],
        'date': [
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?',
            r'\d{1,2}[-/]\d{1,2}[-/]\d{4}',
            r'\d+\s*(?:天前|小时前|分钟前|days?\s*ago|hours?\s*ago)',
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}',
        ],
        'email': [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        ],
        'phone': [
            r'1[3-9]\d{9}',
            r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        ],
        'url': [
            r'https?://[^\s<>"{}|\\^`\[\]]+',
        ]
    }
    
    async def analyze_page(self, url: str, config: dict = None) -> Dict[str, Any]:
        """
        分析页面并返回字段建议
        
        Args:
            url: 目标网址
            config: {
                "auto_scroll": bool,
                "use_stealth": bool,
                "use_markdown": bool,
                "wait_for": str
            }
        """
        try:
            # 使用 V2 爬虫
            runner_path = os.path.join(os.path.dirname(__file__), 'crawler_runner_v2.py')
            
            # 检查文件是否存在
            if not os.path.exists(runner_path):
                # 降级到旧版
                runner_path = os.path.join(os.path.dirname(__file__), 'crawler_runner.py')
                print(f"[SmartExtractor] 使用旧版爬虫: {runner_path}")
                
                result = subprocess.run(
                    [sys.executable, runner_path, url],
                    capture_output=True,
                    timeout=60
                )
            else:
                # 新版支持配置
                crawl_config = {
                    "auto_scroll": config.get('auto_scroll', True) if config else True,
                    "use_stealth": config.get('use_stealth', False) if config else False,
                    "wait_for": config.get('wait_for') if config else None
                }
                
                print(f"[SmartExtractor] 使用新版爬虫，配置: {crawl_config}")
                
                params = json.dumps({
                    "url": url,
                    "config": crawl_config
                })
                
                result = subprocess.run(
                    [sys.executable, runner_path, params],
                    capture_output=True,
                    timeout=60
                )
            
            if result.returncode != 0:
                error_msg = result.stderr.decode('utf-8', errors='ignore') if result.stderr else "Unknown error"
                print(f"[SmartExtractor] 爬虫错误:\n{error_msg}")
            
            if not result.stdout:
                return {
                    "success": False,
                    "error": f"爬虫失败，返回码 {result.returncode}",
                    "suggestions": []
                }
            
            # 解析输出
            try:
                output_text = result.stdout.decode('utf-8')
            except UnicodeDecodeError:
                try:
                    output_text = result.stdout.decode('gbk')
                except:
                    output_text = result.stdout.decode('utf-8', errors='ignore')
            
            try:
                data = json.loads(output_text)
            except json.JSONDecodeError as e:
                print(f"[SmartExtractor] JSON解析错误: {e}")
                print(f"[SmartExtractor] 输出内容: {output_text[:500]}")
                return {
                    "success": False,
                    "error": f"JSON解析错误: {str(e)}",
                    "suggestions": []
                }
            
            if not data.get('success'):
                return {
                    "success": False,
                    "error": data.get('error', '爬取失败'),
                    "suggestions": []
                }
            
            # 多维度分析
            suggestions = []
            
            # 选择分析模式
            use_markdown = config.get('use_markdown', False) if config else False
            
            if use_markdown and data.get('fit_markdown'):
                print("[SmartExtractor] 使用 Markdown 分析模式")
                suggestions.extend(self._analyze_markdown_advanced(data['fit_markdown']))
            else:
                # HTML 模式（默认）
                if data.get('html'):
                    soup = BeautifulSoup(data['html'], 'lxml')
                    suggestions.extend(self._analyze_structure(soup))
            
            # 其他分析维度
            if data.get('markdown'):
                suggestions.extend(self._analyze_markdown(data['markdown']))
            
            if data.get('text'):
                suggestions.extend(self._analyze_patterns(data['text']))
            
            if data.get('links'):
                suggestions.extend(self._analyze_links(data['links']))
            
            if data.get('media'):
                suggestions.extend(self._analyze_media(data['media']))
            
            # 去重和排序
            suggestions = self._deduplicate_suggestions(suggestions)
            suggestions = sorted(suggestions, key=lambda x: x.confidence, reverse=True)
            
            return {
                "success": True,
                "url": url,
                "title": self._extract_title(data),
                "suggestions": [s.dict() for s in suggestions],
                "stats": self._extract_stats(data),
                "config_used": crawl_config if os.path.exists(os.path.join(os.path.dirname(__file__), 'crawler_runner_v2.py')) else {}
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Timeout (60s)",
                "suggestions": []
            }
        except Exception as e:
            print(f"[SmartExtractor] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "suggestions": []
            }
    
    def _analyze_structure(self, soup: BeautifulSoup) -> List[FieldSuggestion]:
        """结构化数据分析 - 最核心的功能"""
        suggestions = []
        
        # 检测列表项（最常见的采集目标）
        for list_container in ['ul', 'ol', 'div[class*="list"]', 'table tbody']:
            items = soup.select(f'{list_container} > li, {list_container} > tr, {list_container} > div')
            
            if len(items) >= 3:
                first_item = items[0]
                
                # 标题
                for title_tag in ['h1', 'h2', 'h3', 'h4', 'a', '.title', '[class*="title"]']:
                    titles = [item.select_one(title_tag) for item in items[:5]]
                    titles = [t for t in titles if t and t.get_text(strip=True)]
                    
                    if len(titles) >= 2:
                        suggestions.append(FieldSuggestion(
                            name="标题",
                            selector=f"{list_container} > * {title_tag}",
                            type="text",
                            confidence=0.9,
                            sample_data=[t.get_text(strip=True)[:50] for t in titles[:3]],
                            count=len(items)
                        ))
                        break
                
                # 链接
                links = [item.select_one('a[href]') for item in items[:5]]
                links = [l for l in links if l and l.get('href')]
                if len(links) >= 2:
                    suggestions.append(FieldSuggestion(
                        name="链接",
                        selector=f"{list_container} > * a[href]",
                        type="link",
                        confidence=0.85,
                        sample_data=[l.get('href')[:50] for l in links[:3]],
                        count=len(items)
                    ))
                
                # 图片
                images = [item.select_one('img[src]') for item in items[:5]]
                images = [img for img in images if img and img.get('src')]
                if len(images) >= 2:
                    suggestions.append(FieldSuggestion(
                        name="图片",
                        selector=f"{list_container} > * img[src]",
                        type="image",
                        confidence=0.85,
                        sample_data=[img.get('src')[:50] for img in images[:3]],
                        count=len(items)
                    ))
        
        # 表格数据
        tables = soup.select('table')
        for table in tables:
            rows = table.select('tr')
            if len(rows) >= 3:
                headers = table.select('th')
                if headers:
                    for idx, header in enumerate(headers[:5]):
                        header_text = header.get_text(strip=True)
                        if header_text:
                            col_data = []
                            for row in rows[1:4]:
                                cells = row.select('td')
                                if idx < len(cells):
                                    col_data.append(cells[idx].get_text(strip=True)[:50])
                            
                            if col_data:
                                suggestions.append(FieldSuggestion(
                                    name=header_text,
                                    selector=f"table tr td:nth-child({idx+1})",
                                    type="text",
                                    confidence=0.95,
                                    sample_data=col_data,
                                    count=len(rows) - 1
                                ))
        
        return suggestions
    
    def _analyze_markdown(self, markdown: str) -> List[FieldSuggestion]:
        """分析 Markdown 内容"""
        suggestions = []
        
        for level, name in [(1, "主标题"), (2, "副标题"), (3, "三级标题")]:
            pattern = f"^{'#' * level} (.+)$"
            matches = re.findall(pattern, markdown, re.MULTILINE)
            if matches:
                suggestions.append(FieldSuggestion(
                    name=name,
                    selector=f"h{level}",
                    type="text",
                    confidence=0.85 - (level - 1) * 0.05,
                    sample_data=[m.strip()[:50] for m in matches[:3]],
                    count=len(matches)
                ))
        
        return suggestions
    
    def _analyze_markdown_advanced(self, fit_markdown: str) -> List[FieldSuggestion]:
        """基于精简 Markdown 的高级分析"""
        suggestions = []
        
        # 1. 提取所有链接
        links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', fit_markdown)
        if len(links) >= 3:
            link_texts = [link[0] for link in links if link[0].strip()]
            suggestions.append(FieldSuggestion(
                name="链接文本",
                selector="a[href]",
                type="text",
                confidence=0.9,
                sample_data=link_texts[:3],
                count=len(links)
            ))
            
            link_urls = [link[1] for link in links if link[1].strip()]
            suggestions.append(FieldSuggestion(
                name="链接地址",
                selector="a[href]",
                type="link",
                confidence=0.9,
                sample_data=link_urls[:3],
                count=len(links)
            ))
        
        # 2. 提取所有图片
        images = re.findall(r'!\[([^\]]*)\]\(([^\)]+)\)', fit_markdown)
        if len(images) >= 2:
            suggestions.append(FieldSuggestion(
                name="图片",
                selector="img[src]",
                type="image",
                confidence=0.95,
                sample_data=[img[1][:50] for img in images[:3]],
                count=len(images)
            ))
        
        # 3. 提取标题层级
        for level in [1, 2, 3]:
            pattern = f"^{'#' * level} (.+)$"
            headers = re.findall(pattern, fit_markdown, re.MULTILINE)
            if len(headers) >= 2:
                suggestions.append(FieldSuggestion(
                    name=f"H{level}标题",
                    selector=f"h{level}",
                    type="text",
                    confidence=0.85,
                    sample_data=[h.strip()[:50] for h in headers[:3]],
                    count=len(headers)
                ))
        
        # 4. 提取列表项
        list_items = re.findall(r'^[\*\-\+] (.+)$', fit_markdown, re.MULTILINE)
        if len(list_items) >= 3:
            suggestions.append(FieldSuggestion(
                name="列表项",
                selector="li",
                type="text",
                confidence=0.8,
                sample_data=[item.strip()[:50] for item in list_items[:3]],
                count=len(list_items)
            ))
        
        # 5. 提取价格
        prices = re.findall(r'[\$€£¥]\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*元', fit_markdown)
        if len(prices) >= 2:
            suggestions.append(FieldSuggestion(
                name="价格",
                selector="[class*='price'], .price, [class*='money']",
                type="text",
                confidence=0.85,
                sample_data=list(set(prices))[:3],
                count=len(set(prices))
            ))
        
        return suggestions
    
    def _analyze_patterns(self, text: str) -> List[FieldSuggestion]:
        """模式匹配分析"""
        suggestions = []
        
        for pattern_type, patterns in self.PATTERNS.items():
            all_matches = []
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                all_matches.extend(matches)
            
            if all_matches:
                unique_matches = list(set(all_matches))
                if len(unique_matches) >= 2:
                    suggestions.append(FieldSuggestion(
                        name=pattern_type.capitalize(),
                        selector=f"[class*='{pattern_type}'], .{pattern_type}",
                        type=pattern_type,
                        confidence=0.7,
                        sample_data=unique_matches[:5],
                        count=len(unique_matches)
                    ))
        
        return suggestions
    
    def _analyze_links(self, links: Dict) -> List[FieldSuggestion]:
        """分析链接"""
        suggestions = []
        
        internal = links.get('internal', []) if isinstance(links, dict) else []
        if len(internal) > 0:
            samples = []
            for link in internal[:5]:
                if isinstance(link, dict):
                    text = link.get('text', '').strip()
                    if text:
                        samples.append(text[:30])
                elif isinstance(link, str):
                    samples.append(link[:50])
            
            if samples:
                suggestions.append(FieldSuggestion(
                    name="内部链接",
                    selector="a[href^='/'], a[href*='://']",
                    type="link",
                    confidence=0.8,
                    sample_data=samples[:3],
                    count=len(internal)
                ))
        
        return suggestions
    
    def _analyze_media(self, media: Dict) -> List[FieldSuggestion]:
        """分析媒体"""
        suggestions = []
        
        images = media.get('images', []) if isinstance(media, dict) else []
        if images:
            samples = []
            for img in images[:3]:
                if isinstance(img, dict):
                    alt = img.get('alt', '')
                    src = img.get('src', '')
                    sample = alt if alt else src[:50]
                    samples.append(sample)
                elif isinstance(img, str):
                    samples.append(img[:50])
            
            if samples:
                suggestions.append(FieldSuggestion(
                    name="图片",
                    selector="img",
                    type="image",
                    confidence=0.9,
                    sample_data=samples,
                    count=len(images)
                ))
        
        return suggestions
    
    def _deduplicate_suggestions(self, suggestions: List[FieldSuggestion]) -> List[FieldSuggestion]:
        """去重建议"""
        seen = {}
        
        for sug in suggestions:
            key = sug.selector
            if key not in seen or sug.confidence > seen[key].confidence:
                seen[key] = sug
        
        return list(seen.values())
    
    def _extract_title(self, data: Dict) -> str:
        """提取标题"""
        if data.get('metadata') and isinstance(data['metadata'], dict):
            return data['metadata'].get('title', '')
        return ''
    
    def _extract_stats(self, data: Dict) -> Dict[str, int]:
        """提取统计"""
        stats = {
            "total_words": data.get('word_count', 0),
            "total_links": 0,
            "total_images": 0
        }
        
        if data.get('links') and isinstance(data['links'], dict):
            internal = len(data['links'].get('internal', []))
            external = len(data['links'].get('external', []))
            stats['total_links'] = internal + external
        
        if data.get('media') and isinstance(data['media'], dict):
            stats['total_images'] = len(data['media'].get('images', []))
        
        return stats