# services/api/app/website_analyzer.py
"""
智能网站分析模块：识别网站类型并推荐爬虫配置

流程：
1. 查询数据库缓存（最快）
2. 匹配本地规则库（次快）
3. 快速页面分析（中等）
4. DeepSeek AI 分析（最准确但最慢）
5. 缓存结果到数据库
"""
import json
import re
import os
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from datetime import datetime
from sqlalchemy.orm import Session

from .models import WebsiteConfig
from .settings import get_settings


class WebsiteAnalyzer:
    """网站智能分析器"""

    def __init__(self):
        self.rules = self._load_rules()
        self.settings = get_settings()

    def _load_rules(self) -> Dict:
        """加载本地规则库"""
        rules_path = os.path.join(os.path.dirname(__file__), 'website_rules.json')

        if os.path.exists(rules_path):
            with open(rules_path, 'r', encoding='utf-8') as f:
                return json.load(f)

        # 如果文件不存在，返回默认配置
        print("[Analyzer] 警告: website_rules.json 不存在，使用默认配置")
        return {
            "rules": [],
            "default_configs": {
                "infinite_scroll": {
                    "use_stealth": True,
                    "auto_scroll": True,
                    "max_scrolls": 20,
                    "scroll_delay": 2500,
                    "stable_checks": 3
                }
            }
        }

    def analyze(self, url: str, session: Session, force_refresh: bool = False) -> Dict[str, Any]:
        """
        智能分析网站并返回推荐配置

        Args:
            url: 目标网站 URL
            session: 数据库会话
            force_refresh: 是否强制刷新（忽略缓存）

        Returns:
            包含网站信息和推荐配置的字典
        """
        domain = self._extract_domain(url)

        print(f"[Analyzer] 开始分析: {url}")
        print(f"[Analyzer] 域名: {domain}")

        # Step 1: 查询数据库缓存（最快，毫秒级）
        if not force_refresh:
            cached = self._get_cached_config(session, domain, url)
            if cached:
                print(f"[Analyzer] ✓ 使用缓存配置: {cached['site_name']} (置信度: {cached['confidence']})")
                return cached

        # Step 2: 匹配本地规则库（次快，毫秒级）
        rule = self._match_local_rules(url, domain)
        if rule:
            print(f"[Analyzer] ✓ 匹配本地规则: {rule['site_name']} (置信度: {rule['confidence']})")
            result = self._rule_to_result(rule, source='local_rules')
            self._save_to_cache(session, domain, url, result)
            return result

        # Step 3: 快速页面分析（中等，2-5秒）
        print(f"[Analyzer] 本地规则未匹配，进行页面分析...")
        page_info = self._quick_page_analysis(url)
        local_result = self._detect_by_features(page_info)

        print(f"[Analyzer] 本地检测结果: {local_result['load_type']} (置信度: {local_result['confidence']})")

        if local_result['confidence'] > 0.85:
            print(f"[Analyzer] ✓ 本地检测置信度高，直接使用")
            self._save_to_cache(session, domain, url, local_result)
            return local_result

        # Step 4: DeepSeek AI 分析（最慢但最准确，3-5秒）
        if self.settings.ai_enabled:
            print(f"[Analyzer] 调用 DeepSeek AI 分析...")
            try:
                from .ai_service import suggest_website_config

                ai_result = suggest_website_config(url, page_info)

                print(f"[Analyzer] ✓ AI 分析完成: {ai_result['load_type']} (置信度: {ai_result['confidence']})")

                # 合并本地和 AI 结果
                final_result = self._merge_results(local_result, ai_result)

                self._save_to_cache(session, domain, url, final_result)
                return final_result

            except Exception as e:
                print(f"[Analyzer] AI 分析失败: {e}，使用本地检测结果")
                self._save_to_cache(session, domain, url, local_result)
                return local_result

        # 降级：使用本地检测结果
        print(f"[Analyzer] AI 未启用，使用本地检测结果")
        self._save_to_cache(session, domain, url, local_result)
        return local_result

    def _extract_domain(self, url: str) -> str:
        """提取域名"""
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        # 移除 www. 前缀
        domain = re.sub(r'^www\.', '', domain)
        return domain

    def _get_cached_config(self, session: Session, domain: str, url: str) -> Optional[Dict]:
        """从数据库获取缓存配置"""
        # 精确匹配域名
        config = session.query(WebsiteConfig).filter(
            WebsiteConfig.domain == domain
        ).first()

        if not config:
            # 模糊匹配 URL 模式
            configs = session.query(WebsiteConfig).filter(
                WebsiteConfig.url_pattern.isnot(None)
            ).all()

            for c in configs:
                pattern = c.url_pattern.replace('*', '.*')
                if re.search(pattern, url):
                    config = c
                    break

        if not config:
            return None

        # 更新最后使用时间
        config.last_used_at = datetime.utcnow()
        session.commit()

        return {
            'site_name': config.site_name,
            'site_type': config.site_type,
            'load_type': config.load_type,
            'config': json.loads(config.config_json),
            'confidence': config.confidence,
            'source': config.source,
            'reasoning': config.ai_reasoning
        }

    def _match_local_rules(self, url: str, domain: str) -> Optional[Dict]:
        """匹配本地规则库"""
        for rule in self.rules.get('rules', []):
            # 精确匹配域名
            if rule['domain'] == domain:
                return rule

            # 匹配 URL 模式
            if 'url_pattern' in rule:
                pattern = rule['url_pattern'].replace('*', '.*')
                if re.search(pattern, url):
                    return rule

        return None

    def _quick_page_analysis(self, url: str) -> Dict[str, Any]:
        """快速页面分析（使用 requests + BeautifulSoup）"""
        try:
            import requests
            from bs4 import BeautifulSoup

            print(f"[Analyzer] 正在加载页面...")
            response = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })

            html = response.text
            soup = BeautifulSoup(html, 'lxml')

            # 提取关键信息
            title = soup.title.string if soup.title else ''

            # 统计元素
            images = soup.select('img')
            articles = soup.select('article')
            figures = soup.select('figure')
            items = soup.select('.item, .product, .card')

            # 检测特征
            has_lazy_load = bool(soup.select('[loading="lazy"], [data-src], [class*="lazy"]'))
            has_infinite_hints = bool(soup.select('[class*="infinite"], [data-scroll]'))
            has_pagination = bool(soup.select('.pagination, .pager, a[class*="next"]'))

            print(f"[Analyzer] 页面分析完成:")
            print(f"[Analyzer]   - 标题: {title[:50]}...")
            print(f"[Analyzer]   - 图片: {len(images)} 个")
            print(f"[Analyzer]   - 文章: {len(articles)} 个")
            print(f"[Analyzer]   - 列表项: {len(items)} 个")

            return {
                'url': url,
                'title': title,
                'html': html,
                'soup': soup,
                'status_code': response.status_code,
                'image_count': len(images),
                'article_count': len(articles),
                'figure_count': len(figures),
                'item_count': len(items),
                'has_lazy_load': has_lazy_load,
                'has_infinite_hints': has_infinite_hints,
                'has_pagination': has_pagination,
            }

        except Exception as e:
            print(f"[Analyzer] 页面分析失败: {e}")
            return {'url': url, 'html': '', 'soup': None}

    def _detect_by_features(self, page_info: Dict) -> Dict[str, Any]:
        """基于页面特征的本地检测"""
        soup = page_info.get('soup')

        if not soup:
            # 降级：使用默认配置
            return {
                'site_name': 'Unknown',
                'site_type': 'unknown',
                'load_type': 'infinite_scroll',
                'config': self.rules['default_configs']['infinite_scroll'],
                'confidence': 0.5,
                'source': 'local_detection',
                'reasoning': '页面分析失败，使用默认无限滚动配置'
            }

        # 统计元素数量
        total_items = max(
            page_info.get('image_count', 0),
            page_info.get('article_count', 0),
            page_info.get('figure_count', 0),
            page_info.get('item_count', 0)
        )

        has_lazy_load = page_info.get('has_lazy_load', False)
        has_infinite_hints = page_info.get('has_infinite_hints', False)
        has_pagination = page_info.get('has_pagination', False)

        # 判断加载类型
        if has_pagination:
            load_type = 'pagination'
            confidence = 0.75
            reasoning = f"检测到翻页元素"
        elif has_lazy_load or has_infinite_hints or total_items > 30:
            load_type = 'infinite_scroll'
            confidence = 0.7 if total_items > 50 else 0.6
            reasoning = f"检测到 {total_items} 个内容项"
            if has_lazy_load:
                reasoning += "，有懒加载特征"
            if has_infinite_hints:
                reasoning += "，有无限滚动提示"
        else:
            load_type = 'static'
            confidence = 0.6
            reasoning = f"内容较少（{total_items} 项），可能是静态页面"

        # 判断网站类型
        if page_info.get('image_count', 0) > 20:
            site_type = 'photo_sharing'
        elif page_info.get('article_count', 0) > 10:
            site_type = 'news_or_blog'
        elif page_info.get('item_count', 0) > 15:
            site_type = 'ecommerce'
        else:
            site_type = 'general'

        # 选择配置
        config = self.rules['default_configs'].get(
            load_type,
            self.rules['default_configs']['infinite_scroll']
        )

        return {
            'site_name': page_info.get('title', 'Unknown')[:50],
            'site_type': site_type,
            'load_type': load_type,
            'config': config,
            'confidence': confidence,
            'source': 'local_detection',
            'reasoning': reasoning
        }

    def _merge_results(self, local_result: Dict, ai_result: Dict) -> Dict[str, Any]:
        """合并本地检测和 AI 结果"""
        # AI 结果优先，但保留本地检测的高置信度判断
        if ai_result['confidence'] > local_result['confidence']:
            print(f"[Analyzer] 采用 AI 分析结果（置信度更高）")
            return ai_result
        else:
            print(f"[Analyzer] 采用本地检测结果（置信度更高）")
            return local_result

    def _rule_to_result(self, rule: Dict, source: str) -> Dict[str, Any]:
        """将规则转换为结果格式"""
        return {
            'site_name': rule.get('site_name', 'Unknown'),
            'site_type': rule.get('site_type', 'unknown'),
            'load_type': rule.get('load_type', 'infinite_scroll'),
            'config': rule.get('config', {}),
            'confidence': rule.get('confidence', 1.0),
            'source': source,
            'reasoning': rule.get('notes', '')
        }

    def _save_to_cache(self, session: Session, domain: str, url: str, result: Dict):
        """保存分析结果到数据库"""
        try:
            # 查找已存在的配置
            config = session.query(WebsiteConfig).filter(
                WebsiteConfig.domain == domain
            ).first()

            config_json = json.dumps(result['config'], ensure_ascii=False)

            if config:
                # 更新
                config.site_name = result['site_name']
                config.site_type = result['site_type']
                config.load_type = result['load_type']
                config.config_json = config_json
                config.confidence = result['confidence']
                config.source = result['source']
                config.ai_reasoning = result.get('reasoning', '')
                config.updated_at = datetime.utcnow()
                print(f"[Analyzer] 更新缓存: {domain}")
            else:
                # 创建
                config = WebsiteConfig(
                    domain=domain,
                    site_name=result['site_name'],
                    site_type=result['site_type'],
                    load_type=result['load_type'],
                    config_json=config_json,
                    confidence=result['confidence'],
                    source=result['source'],
                    ai_reasoning=result.get('reasoning', '')
                )
                session.add(config)
                print(f"[Analyzer] 创建缓存: {domain}")

            session.commit()

        except Exception as e:
            print(f"[Analyzer] 缓存保存失败: {e}")
            session.rollback()


# 全局单例
_analyzer_instance = None

def get_analyzer() -> WebsiteAnalyzer:
    """获取分析器单例"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = WebsiteAnalyzer()
    return _analyzer_instance
