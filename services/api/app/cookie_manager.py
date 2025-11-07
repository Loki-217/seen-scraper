"""
统一Cookie管理器 - 支持多种Cookie来源和格式
"""

import browser_cookie3
import json
import os
import webbrowser
import platform
import subprocess
from typing import Dict, List, Optional
from http.cookiejar import Cookie


class UniversalCookieManager:
    """统一Cookie管理器 - 支持从多种来源导入Cookie"""

    def __init__(self):
        self.storage: Dict[str, List[Dict]] = {}

    # ==================== 自动导入方法 ====================

    def import_from_chrome(self, domain: str) -> List[Dict]:
        """
        从Chrome浏览器自动读取Cookie

        Args:
            domain: 域名 (如 'tvmaze.com' 或 'www.tvmaze.com')

        Returns:
            Cookie字典列表
        """
        try:
            print(f"[CookieManager] 尝试从Chrome读取域名: {domain}")
            cj = browser_cookie3.chrome(domain_name=domain)
            cookies = self._cookiejar_to_dict(cj)
            print(f"[CookieManager] ✅ 从Chrome读取到 {len(cookies)} 个Cookie")
            return cookies
        except Exception as e:
            print(f"[CookieManager] ❌ Chrome读取失败: {e}")
            raise Exception(f"从Chrome读取Cookie失败: {str(e)}")

    def import_from_firefox(self, domain: str) -> List[Dict]:
        """
        从Firefox浏览器自动读取Cookie

        Args:
            domain: 域名

        Returns:
            Cookie字典列表
        """
        try:
            print(f"[CookieManager] 尝试从Firefox读取域名: {domain}")
            cj = browser_cookie3.firefox(domain_name=domain)
            cookies = self._cookiejar_to_dict(cj)
            print(f"[CookieManager] ✅ 从Firefox读取到 {len(cookies)} 个Cookie")
            return cookies
        except Exception as e:
            print(f"[CookieManager] ❌ Firefox读取失败: {e}")
            raise Exception(f"从Firefox读取Cookie失败: {str(e)}")

    def import_from_edge(self, domain: str) -> List[Dict]:
        """
        从Edge浏览器自动读取Cookie

        Args:
            domain: 域名

        Returns:
            Cookie字典列表
        """
        try:
            print(f"[CookieManager] 尝试从Edge读取域名: {domain}")
            cj = browser_cookie3.edge(domain_name=domain)
            cookies = self._cookiejar_to_dict(cj)
            print(f"[CookieManager] ✅ 从Edge读取到 {len(cookies)} 个Cookie")
            return cookies
        except Exception as e:
            print(f"[CookieManager] ❌ Edge读取失败: {e}")
            raise Exception(f"从Edge读取Cookie失败: {str(e)}")

    def import_from_all_browsers(self, domain: str) -> Dict[str, List[Dict]]:
        """
        尝试从所有浏览器读取Cookie

        Args:
            domain: 域名

        Returns:
            字典 {浏览器名: Cookie列表}
        """
        results = {}

        # 尝试Chrome
        try:
            results['chrome'] = self.import_from_chrome(domain)
        except:
            results['chrome'] = []

        # 尝试Firefox
        try:
            results['firefox'] = self.import_from_firefox(domain)
        except:
            results['firefox'] = []

        # 尝试Edge
        try:
            results['edge'] = self.import_from_edge(domain)
        except:
            results['edge'] = []

        # 返回找到Cookie最多的浏览器
        return results

    # ==================== 格式转换方法 ====================

    def import_from_json(self, json_data: str) -> List[Dict]:
        """
        从JSON字符串导入Cookie

        Args:
            json_data: JSON格式的Cookie字符串

        Returns:
            Cookie字典列表
        """
        try:
            cookies = json.loads(json_data)
            if isinstance(cookies, dict) and 'cookies' in cookies:
                # Playwright storage_state format
                return cookies['cookies']
            elif isinstance(cookies, list):
                # Simple JSON array format
                return cookies
            else:
                raise ValueError("不支持的JSON格式")
        except json.JSONDecodeError as e:
            raise Exception(f"JSON解析失败: {str(e)}")

    def import_from_playwright_state(self, state_data: dict) -> List[Dict]:
        """
        从Playwright存储状态导入

        Args:
            state_data: Playwright storage_state字典

        Returns:
            Cookie字典列表
        """
        return state_data.get('cookies', [])

    def import_from_netscape(self, netscape_content: str) -> List[Dict]:
        """
        从Netscape格式导入Cookie

        Args:
            netscape_content: Netscape格式的Cookie内容

        Returns:
            Cookie字典列表
        """
        cookies = []

        for line in netscape_content.strip().split('\n'):
            # 跳过注释和空行
            if line.startswith('#') or not line.strip():
                continue

            parts = line.strip().split('\t')
            if len(parts) == 7:
                cookies.append({
                    'domain': parts[0],
                    'path': parts[2],
                    'secure': parts[3] == 'TRUE',
                    'expires': int(parts[4]) if parts[4] != '0' else -1,
                    'name': parts[5],
                    'value': parts[6],
                    'httpOnly': False,
                    'sameSite': 'Lax'
                })

        print(f"[CookieManager] 从Netscape格式解析了 {len(cookies)} 个Cookie")
        return cookies

    # ==================== 导出方法 ====================

    def export_to_playwright_state(self, cookies: List[Dict]) -> Dict:
        """
        导出为Playwright存储状态格式

        Args:
            cookies: Cookie列表

        Returns:
            Playwright storage_state格式
        """
        return {
            "cookies": cookies,
            "origins": []
        }

    def export_to_netscape(self, cookies: List[Dict]) -> str:
        """
        导出为Netscape格式

        Args:
            cookies: Cookie列表

        Returns:
            Netscape格式字符串
        """
        lines = ["# Netscape HTTP Cookie File\n"]

        for cookie in cookies:
            domain = cookie.get('domain', '')
            path = cookie.get('path', '/')
            secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
            expires = str(cookie.get('expires', 0))
            name = cookie.get('name', '')
            value = cookie.get('value', '')

            # Netscape格式: domain	flag	path	secure	expiration	name	value
            line = f"{domain}\tTRUE\t{path}\t{secure}\t{expires}\t{name}\t{value}\n"
            lines.append(line)

        return ''.join(lines)

    # ==================== 辅助方法 ====================

    def _cookiejar_to_dict(self, cookiejar) -> List[Dict]:
        """
        转换http.cookiejar.CookieJar为字典列表

        Args:
            cookiejar: CookieJar对象

        Returns:
            Cookie字典列表
        """
        cookies = []

        for cookie in cookiejar:
            cookie_dict = {
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path,
                'secure': bool(cookie.secure),  # 🔥 显式转换为布尔值（避免0/1导致的类型错误）
                'httpOnly': bool(cookie.has_nonstandard_attr('HttpOnly')) if hasattr(cookie, 'has_nonstandard_attr') else False,
                'sameSite': cookie.get_nonstandard_attr('SameSite', 'Lax') if hasattr(cookie, 'get_nonstandard_attr') else 'Lax',
                'expires': int(cookie.expires) if cookie.expires else -1  # 🔥 确保expires是整数
            }

            cookies.append(cookie_dict)

        return cookies

    def get_cookie_summary(self, cookies: List[Dict]) -> Dict:
        """
        获取Cookie摘要信息

        Args:
            cookies: Cookie列表

        Returns:
            摘要信息字典
        """
        session_cookie_names = ['phpsessid', 'sessionid', 'session', 'jsessionid', 'sid', 'sess']
        auth_cookie_names = ['auth', 'token', 'jwt', 'access_token']

        session_cookies = [
            c for c in cookies
            if c.get('name', '').lower() in session_cookie_names
        ]

        auth_cookies = [
            c for c in cookies
            if any(keyword in c.get('name', '').lower() for keyword in auth_cookie_names)
        ]

        return {
            'total': len(cookies),
            'session_count': len(session_cookies),
            'auth_count': len(auth_cookies),
            'session_names': [c.get('name') for c in session_cookies],
            'auth_names': [c.get('name') for c in auth_cookies],
            'secure_count': len([c for c in cookies if c.get('secure', False)]),
            'httponly_count': len([c for c in cookies if c.get('httpOnly', False)])
        }

    # ==================== 浏览器操作方法 ====================

    def detect_available_browsers(self) -> Dict[str, Dict]:
        """
        检测系统中可用的浏览器

        Returns:
            字典 {浏览器名: {可用状态, 路径}}
        """
        result = {}
        system = platform.system()

        # Chrome检测
        chrome_paths = {
            'Windows': [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                os.path.expanduser(r'~\AppData\Local\Google\Chrome\Application\chrome.exe')
            ],
            'Darwin': ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'],
            'Linux': ['/usr/bin/google-chrome', '/usr/bin/chromium-browser', '/usr/bin/chromium']
        }

        # Firefox检测
        firefox_paths = {
            'Windows': [
                r'C:\Program Files\Mozilla Firefox\firefox.exe',
                r'C:\Program Files (x86)\Mozilla Firefox\firefox.exe'
            ],
            'Darwin': ['/Applications/Firefox.app/Contents/MacOS/firefox'],
            'Linux': ['/usr/bin/firefox', '/usr/bin/firefox-esr']
        }

        # Edge检测
        edge_paths = {
            'Windows': [
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
            ],
            'Darwin': ['/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge'],
            'Linux': ['/usr/bin/microsoft-edge', '/usr/bin/microsoft-edge-stable']
        }

        browsers = {
            'chrome': chrome_paths,
            'firefox': firefox_paths,
            'edge': edge_paths
        }

        for browser_name, paths_dict in browsers.items():
            paths = paths_dict.get(system, [])
            found_path = None

            for path in paths:
                if os.path.exists(path):
                    found_path = path
                    break

            # 还可以通过browser_cookie3测试是否能读取Cookie
            can_read_cookies = False
            try:
                if browser_name == 'chrome':
                    browser_cookie3.chrome(domain_name='google.com')
                    can_read_cookies = True
                elif browser_name == 'firefox':
                    browser_cookie3.firefox(domain_name='google.com')
                    can_read_cookies = True
                elif browser_name == 'edge':
                    browser_cookie3.edge(domain_name='google.com')
                    can_read_cookies = True
            except:
                pass

            result[browser_name] = {
                'available': found_path is not None or can_read_cookies,
                'path': found_path,
                'can_read_cookies': can_read_cookies
            }

        print(f"[CookieManager] 检测到的浏览器: {result}")
        return result

    def open_browser_for_login(self, url: str, browser: str = 'default') -> Dict:
        """
        打开系统浏览器以供用户登录

        Args:
            url: 要打开的URL
            browser: 浏览器类型 ('chrome', 'firefox', 'edge', 'default')

        Returns:
            操作结果
        """
        try:
            if browser == 'default':
                # 使用系统默认浏览器
                webbrowser.open(url)
                print(f"[CookieManager] 已用默认浏览器打开: {url}")
                return {
                    'success': True,
                    'browser': 'default',
                    'message': '已打开系统默认浏览器'
                }
            else:
                # 尝试打开指定浏览器
                browsers_info = self.detect_available_browsers()
                browser_info = browsers_info.get(browser, {})

                if not browser_info.get('available'):
                    raise Exception(f"浏览器 {browser} 不可用")

                browser_path = browser_info.get('path')

                if browser_path and os.path.exists(browser_path):
                    # 使用subprocess打开指定浏览器
                    if platform.system() == 'Windows':
                        subprocess.Popen([browser_path, url])
                    elif platform.system() == 'Darwin':
                        subprocess.Popen(['open', '-a', browser_path, url])
                    else:  # Linux
                        subprocess.Popen([browser_path, url])

                    print(f"[CookieManager] 已用 {browser} 打开: {url}")
                    return {
                        'success': True,
                        'browser': browser,
                        'path': browser_path,
                        'message': f'已打开 {browser.upper()} 浏览器'
                    }
                else:
                    # 回退到默认浏览器
                    webbrowser.open(url)
                    return {
                        'success': True,
                        'browser': 'default',
                        'message': f'未找到 {browser}，已使用默认浏览器'
                    }

        except Exception as e:
            print(f"[CookieManager] 打开浏览器失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'打开浏览器失败: {str(e)}'
            }


# 创建全局实例
cookie_manager = UniversalCookieManager()
