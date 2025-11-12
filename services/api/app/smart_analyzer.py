# services/api/app/smart_analyzer.py
"""
智能URL分析器 - 自动判断使用静态抓取还是实时浏览
"""

from pydantic import BaseModel
from typing import Optional, List
import httpx
from bs4 import BeautifulSoup
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class QualityScore(BaseModel):
    """HTML质量评分"""
    score: float  # 0.0 - 1.0
    reason: str


class AnalysisResult(BaseModel):
    """分析结果"""
    method: str  # 'static' 或 'realtime'
    reason: str
    confidence: float  # 0.0 - 1.0
    quality_score: Optional[float] = None


class URLAnalyzer:
    """URL智能分析器"""

    # 已知需要实时浏览的域名（JavaScript渲染、复杂交互）
    REALTIME_REQUIRED_DOMAINS = {
        'bilibili.com',
        'youtube.com',
        'twitter.com',
        'x.com',
        'facebook.com',
        'instagram.com',
        'taobao.com',
        'tmall.com',
        'jd.com',
        'pinduoduo.com',
        'xiaohongshu.com',
        'douyin.com',
        'tiktok.com',
        'weibo.com',
    }

    # 已知静态友好的域名（纯HTML或API）
    STATIC_FRIENDLY_DOMAINS = {
        'wikipedia.org',
        'baidu.com',
        'gov.cn',
        'edu.cn',
    }

    async def analyze(self, url: str) -> AnalysisResult:
        """
        分析URL，返回推荐的渲染方式

        分析维度：
        1. 域名黑白名单
        2. URL特征
        3. HEAD请求探测
        4. 快速静态抓取测试
        5. HTML质量检测
        """
        try:
            domain = self._extract_domain(url)

            # 维度1: 域名黑名单检查
            if self._is_in_domain_list(domain, self.REALTIME_REQUIRED_DOMAINS):
                logger.info(f"[Analyzer] {domain} 在实时浏览黑名单中")
                return AnalysisResult(
                    method='realtime',
                    reason=f'已知 {domain} 需要JavaScript渲染',
                    confidence=0.95
                )

            # 维度2: 域名白名单检查
            if self._is_in_domain_list(domain, self.STATIC_FRIENDLY_DOMAINS):
                logger.info(f"[Analyzer] {domain} 在静态友好白名单中")
                return AnalysisResult(
                    method='static',
                    reason=f'已知 {domain} 支持静态抓取',
                    confidence=0.90
                )

            # 维度3: URL特征分析
            if self._is_api_url(url):
                logger.info(f"[Analyzer] {url} 是API接口")
                return AnalysisResult(
                    method='static',
                    reason='API接口，直接请求',
                    confidence=0.85
                )

            # 维度4: 快速HEAD探测
            content_type = await self._quick_head_check(url)
            if content_type:
                if 'json' in content_type or 'xml' in content_type:
                    logger.info(f"[Analyzer] {url} 返回结构化数据")
                    return AnalysisResult(
                        method='static',
                        reason='返回JSON/XML结构化数据',
                        confidence=1.0
                    )

            # 维度5: 快速静态抓取测试
            logger.info(f"[Analyzer] 开始快速静态抓取测试: {url}")
            html = await self._quick_static_fetch(url, timeout=5)

            if html:
                quality = self._check_html_quality(html)
                logger.info(f"[Analyzer] HTML质量分数: {quality.score}, 原因: {quality.reason}")

                if quality.score >= 0.7:
                    return AnalysisResult(
                        method='static',
                        reason=f'静态抓取成功 (质量: {quality.score:.2f})',
                        confidence=quality.score,
                        quality_score=quality.score
                    )
                else:
                    return AnalysisResult(
                        method='realtime',
                        reason=f'静态抓取质量差: {quality.reason}',
                        confidence=0.8,
                        quality_score=quality.score
                    )

            # 默认：探测失败，使用实时模式（更安全）
            logger.warning(f"[Analyzer] 探测失败，默认使用实时模式")
            return AnalysisResult(
                method='realtime',
                reason='探测失败，使用实时模式保证成功',
                confidence=0.6
            )

        except Exception as e:
            logger.error(f"[Analyzer] 分析失败: {e}", exc_info=True)
            # 出错时默认实时（更安全）
            return AnalysisResult(
                method='realtime',
                reason=f'分析异常，使用实时模式: {str(e)[:100]}',
                confidence=0.5
            )

    def _extract_domain(self, url: str) -> str:
        """提取域名"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # 去掉端口
            if ':' in domain:
                domain = domain.split(':')[0]

            # 去掉www前缀
            if domain.startswith('www.'):
                domain = domain[4:]

            return domain
        except:
            return ''

    def _is_in_domain_list(self, domain: str, domain_list: set) -> bool:
        """检查域名是否在列表中（支持子域名）"""
        if domain in domain_list:
            return True

        # 检查是否是子域名
        for known_domain in domain_list:
            if domain.endswith('.' + known_domain) or domain == known_domain:
                return True

        return False

    def _is_api_url(self, url: str) -> bool:
        """判断是否是API接口"""
        api_indicators = ['/api/', '/ajax/', '/json/', '/v1/', '/v2/', '/graphql']
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in api_indicators)

    async def _quick_head_check(self, url: str) -> Optional[str]:
        """快速HEAD请求检测Content-Type"""
        try:
            async with httpx.AsyncClient(timeout=3, follow_redirects=True) as client:
                response = await client.head(url)
                return response.headers.get('content-type', '').lower()
        except Exception as e:
            logger.debug(f"[Analyzer] HEAD请求失败: {e}")
            return None

    async def _quick_static_fetch(self, url: str, timeout: int = 5) -> Optional[str]:
        """快速静态抓取（用于测试）"""
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.debug(f"[Analyzer] 静态抓取失败: {e}")
            return None

    def _check_html_quality(self, html: str) -> QualityScore:
        """检查HTML质量"""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            score = 1.0
            reasons = []

            # 检查1: 内容长度
            text = soup.get_text(strip=True)
            text_length = len(text)
            if text_length < 100:
                score -= 0.5
                reasons.append(f'内容过少({text_length}字符)')
            elif text_length < 500:
                score -= 0.2
                reasons.append(f'内容较少({text_length}字符)')

            # 检查2: 是否有登录墙
            login_keywords = [
                'please log in', 'please login', 'sign in',
                '请登录', '登录后查看', '登录后继续', '需要登录',
                'login required', 'authentication required'
            ]
            html_lower = html.lower()
            if any(keyword in html_lower for keyword in login_keywords):
                # 检查是否真的是登录页（而不是页面中有登录按钮）
                if text_length < 1000:
                    score -= 0.4
                    reasons.append('可能需要登录')

            # 检查3: 是否是空的SPA框架
            spa_indicators = [
                '<div id="root"></div>',
                '<div id="app"></div>',
                '<div id="main"></div>',
                'id="__next"'
            ]
            if any(indicator in html for indicator in spa_indicators):
                script_count = len(soup.find_all('script'))
                if script_count > 5 and text_length < 500:
                    score -= 0.6
                    reasons.append('SPA应用，需要JS渲染')

            # 检查4: 是否有实际内容标签
            content_tags = soup.find_all(['article', 'main', 'section', 'p', 'h1', 'h2', 'h3'])
            if len(content_tags) < 5:
                score -= 0.2
                reasons.append('内容标签较少')

            # 检查5: 是否有错误提示
            error_indicators = [
                '404', '403', '500', 'not found', 'access denied',
                'error', '错误', '页面不存在', '访问被拒绝'
            ]
            if any(indicator in html_lower for indicator in error_indicators):
                if text_length < 2000:  # 只有在内容少的情况下才判定为错误
                    score -= 0.5
                    reasons.append('可能存在错误页面')

            # 检查6: 是否有丰富的内容
            has_images = len(soup.find_all('img')) > 0
            has_links = len(soup.find_all('a')) > 5
            has_paragraphs = len(soup.find_all('p')) > 3

            if has_images and has_links and has_paragraphs:
                score += 0.1  # 额外加分

            final_score = max(0.0, min(1.0, score))
            reason_text = '; '.join(reasons) if reasons else '质量良好'

            return QualityScore(score=final_score, reason=reason_text)

        except Exception as e:
            logger.error(f"[Analyzer] HTML质量检测失败: {e}")
            return QualityScore(score=0.5, reason=f'检测异常: {str(e)[:50]}')


# 全局分析器实例
url_analyzer = URLAnalyzer()
