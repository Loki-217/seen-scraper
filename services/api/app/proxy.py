# services/api/app/proxy.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import subprocess
import json
import sys
import tempfile
import os

router = APIRouter(prefix="/api/proxy", tags=["proxy"])

# Cookie存储字典（按域名存储）
_cookies_storage: Dict[str, list] = {}

class RenderRequest(BaseModel):
    url: str
    timeout_ms: int = 30000
    wait_for: Optional[str] = None

class CookieImportRequest(BaseModel):
    domain: str
    cookies: list

class LoginDetectRequest(BaseModel):
    url: str
    html: Optional[str] = None

class SmartClickRequest(BaseModel):
    url: str
    element: Dict[str, Any]

# 简化的注入脚本
INJECTED_SCRIPT = r"""
(function() {
    if (window.__scraperInjected) return;
    window.__scraperInjected = true;
    
    console.log('[SeenFetch] Script injected!');
    
    var style = document.createElement('style');
    style.innerHTML = '.scraper-hover { outline: 2px solid #4CAF50 !important; outline-offset: 2px; }';
    document.head.appendChild(style);

    document.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        console.log('[SeenFetch] Element clicked:', e.target);
        
        var element = e.target;
        var selector = element.tagName.toLowerCase();
        
        if (element.id) {
            selector = '#' + element.id;
        } else if (element.className && typeof element.className === 'string') {
            var classes = element.className.split(' ').filter(function(c) { return c && !c.match(/^scraper-/); });
            if (classes.length > 0) {
                selector = element.tagName.toLowerCase() + '.' + classes[0];
            }
        }
        
        var elementInfo = {
            tagName: element.tagName.toLowerCase(),
            className: element.className,
            id: element.id,
            text: (element.innerText || element.textContent || '').substring(0, 100),
            selector: selector,
            href: element.href || '',
            src: element.src || ''
        };
        
        console.log('[SeenFetch] Posting message:', elementInfo);
        
       window.parent.postMessage({
           type: 'element-clicked',
           element: elementInfo,
           selector: selector
        }, '*');
        
        return false;
    }, true);
    
    document.addEventListener('mouseover', function(e) {
        e.target.classList.add('scraper-hover');
    }, true);
    
    document.addEventListener('mouseout', function(e) {
        e.target.classList.remove('scraper-hover');
    }, true);
})();
"""

# 改进的Playwright脚本 - 添加反反爬虫和滚动功能
PLAYWRIGHT_TEMPLATE = """
import sys
import json
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

def render_page(url, timeout_ms, wait_for, inject_js):
    try:
        with sync_playwright() as p:
            # 🔥 反反爬虫配置
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ]
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='zh-CN',
                timezone_id='Asia/Shanghai',
                extra_http_headers={
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                }
            )
            
            page = context.new_page()
            
            # 🔥 隐藏webdriver特征 + 反反调试
            page.add_init_script('''
                // 隐藏 webdriver
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
                
                // 🔥 反反调试：禁用开发者工具检测
                (function() {
                    // 1. 阻止检测窗口尺寸变化
                    const origAddEventListener = window.addEventListener;
                    window.addEventListener = function(type, listener, options) {
                        if (type === 'resize' || type === 'devtoolschange') {
                            console.log('[SeenFetch] Blocked:', type);
                            return;
                        }
                        return origAddEventListener.call(this, type, listener, options);
                    };
                    
                    // 2. 冻结窗口尺寸差异（常用检测手段）
                    Object.defineProperty(window, 'outerHeight', {
                        get: () => window.innerHeight
                    });
                    Object.defineProperty(window, 'outerWidth', {
                        get: () => window.innerWidth
                    });
                    
                    // 3. 禁用 devtools-detector 等库
                    window.devtools = {isOpen: false, orientation: undefined};
                    
                    // 4. 覆盖常见的检测变量
                    Object.defineProperty(window, '__REACT_DEVTOOLS_GLOBAL_HOOK__', {
                        get: () => undefined
                    });
                    
                    console.log('[SeenFetch] Anti-anti-debug enabled');
                })();
            ''')
            
            # 🔥 导航到页面
            try:
                page.goto(url, wait_until="load", timeout=timeout_ms)
                page.wait_for_timeout(2000)
                print("[Render] Page loaded", file=sys.stderr)
                
                # 🔥 自动滚动预加载
                try:
                    initial_h = page.evaluate("document.body.scrollHeight")
                    print(f"[Scroll] Start: {initial_h}px", file=sys.stderr)
                    
                    for i in range(5):
                        page.evaluate("window.scrollTo(0, 999999); window.scrollBy(0, 9999);")
                        page.wait_for_timeout(1200)
                        page.evaluate('document.querySelectorAll("img[loading]").forEach(i=>i.loading="eager");')
                        
                        new_h = page.evaluate("document.body.scrollHeight")
                        print(f"[Scroll] #{i+1}: {new_h}px", file=sys.stderr)
                        if new_h == initial_h:
                            break
                        initial_h = new_h
                    
                    page.evaluate("window.scrollTo(0, 0)")
                    page.wait_for_timeout(300)
                    print("[Scroll] Complete", file=sys.stderr)
                except Exception as e:
                    print(f"[Scroll] Error: {e}", file=sys.stderr)
                
            except Exception as e:
                error_msg = str(e)
                if 'ERR_CONNECTION_CLOSED' in error_msg or 'ERR_FAILED' in error_msg:
                    return {
                        "success": False,
                        "error": "Website blocked the request (anti-bot protection)",
                        "details": "This website has anti-scraping measures. Try using a different URL or contact support.",
                        "traceback": error_msg
                    }
                raise
            
            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=5000)
                except:
                    pass
            
            # 注入脚本
            try:
                page.add_script_tag(content=inject_js)
                page.wait_for_timeout(500)
            except Exception as e:
                print("Warning: inject failed:", str(e), file=sys.stderr)
            
            content = page.content()
            title = page.title()
            
            # 🔥 修复资源路径、图标库 + 强制显示隐藏元素
            from urllib.parse import urlparse
            parsed = urlparse(page.url)
            base = f"{parsed.scheme}://{parsed.netloc}/"
            
            if '<head>' in content:
                # 1. 添加 <base> 标签
                base_tag = f'<base href="{base}">'
                
                # 2. 添加字体图标库（支持多个版本）
                icon_libs = r'''
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" crossorigin="anonymous">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css" crossorigin="anonymous">
<link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
<style>
/* 🔥 修复 Element UI 图标字体路径 */
@font-face {
    font-family: element-icons;
    src: url(https://unpkg.com/element-ui/lib/theme-chalk/fonts/element-icons.woff) format("woff"),
         url(https://unpkg.com/element-ui/lib/theme-chalk/fonts/element-icons.ttf) format("truetype");
    font-weight: 400;
    font-display: swap;
}

/* 🔥 强制显示所有隐藏元素（反反调试） */
.runoob-block,
.runoob_cf,
div[style*="display: none"],
div[style*="display:none"],
div[style*="visibility: hidden"],
div[style*="visibility:hidden"] {
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
    height: auto !important;
    overflow: visible !important;
}

/* 强制显示底部二维码区域 */
.runoob-block img,
.runoob_cf img,
footer img {
    display: block !important;
    visibility: visible !important;
}
</style>'''
                
                # 3. 一次性插入所有修复
                fixes = base_tag + '\\n' + icon_libs
                content = content.replace('<head>', f'<head>\\n{fixes}', 1)
                
                # 4. 修复常见的相对路径
                content = content.replace('url(/static/', f'url({base}static/')
                content = content.replace('src="/static/', f'src="{base}static/')
                content = content.replace("src='/static/", f"src='{base}static/")

                # 🔥 修复字体文件路径
                content = content.replace('url(/fonts/', f'url({base}fonts/')
                content = content.replace('url("../fonts/', f'url("{base}fonts/')
                content = content.replace("url('../fonts/", f"url('{base}fonts/")
    
                
                print("[Fix] Resources, icons and anti-hiding fixed", file=sys.stderr)
            
            browser.close()
            
            return {
                "success": True,
                "html": content,
                "url": page.url,
                "title": title,
                "script_injected": True
            }
            
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    params = json.loads(sys.argv[1])
    result = render_page(
        params["url"], 
        params["timeout_ms"], 
        params.get("wait_for"),
        params["inject_js"]
    )
    # 🔥 确保使用ASCII编码输出，避免Windows编码问题
    output = json.dumps(result, ensure_ascii=True)
    sys.stdout.buffer.write(output.encode('utf-8'))
    sys.stdout.buffer.flush()
"""

@router.post("/render")
async def render_page(req: RenderRequest):
    """通过子进程运行Playwright"""
    
    print(f"[API] Rendering URL: {req.url}")
    
    temp_script = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.py', 
            delete=False, 
            encoding='utf-8'
        ) as f:
            f.write(PLAYWRIGHT_TEMPLATE)
            temp_script = f.name
        
        params = {
            "url": req.url,
            "timeout_ms": req.timeout_ms,
            "wait_for": req.wait_for,
            "inject_js": INJECTED_SCRIPT
        }
        
        params_json = json.dumps(params, ensure_ascii=True)
        
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        result = subprocess.run(
            [sys.executable, temp_script, params_json],
            capture_output=True,
            text=True,
            timeout=60,
            encoding='utf-8',
            env=env
        )
        
        # 🔥 输出详细调试信息
        print("=== Playwright STDERR ===")
        print(result.stderr)
        print("=" * 50)

        # 检查返回的 HTML
        if result.stdout:
            try:
                output = json.loads(result.stdout)
                html_snippet = output.get('html', '')[:800]
                print("=== HTML Preview (first 800 chars) ===")
                print(html_snippet)
                print("=" * 50)
                
                # 检查关键标签
                html_full = output.get('html', '')
                if '<base href=' in html_full:
                    print("✅ <base> tag found!")
                else:
                    print("❌ <base> tag NOT found!")
                
                if 'font-awesome' in html_full:
                    print("✅ Font Awesome link found!")
                else:
                    print("❌ Font Awesome link NOT found!")
                    
                print(f"📊 HTML length: {len(html_full)} bytes")
                
            except Exception as e:
                print(f"⚠️ Failed to parse output: {e}")

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Playwright process failed",
                    "returncode": result.returncode,
                    "stderr": result.stderr,
                    "stdout": result.stdout[:500] if result.stdout else ""
                }
            )
        
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Failed to parse output",
                    "parse_error": str(e),
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr[:500]
                }
            )
        
        if not output.get("success"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": output.get("error", "Render failed"),
                    "details": output.get("details", output.get("error", "")),
                    "traceback": output.get("traceback", "")[:1000]
                }
            )
        
        print(f"[API] ✅ Success, HTML length: {len(output.get('html', ''))} bytes")
        
        return output
        
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408, 
            detail={"error": "Timeout"}
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )
    finally:
        if temp_script and os.path.exists(temp_script):
            try:
                os.unlink(temp_script)
            except:
                pass

@router.get("/test")
async def test_proxy():
    return {"status": "ok"}

# ==================== Cookie管理API ====================

@router.post("/cookies/import")
async def import_cookies(req: CookieImportRequest):
    """导入Cookie"""
    try:
        _cookies_storage[req.domain] = req.cookies
        print(f"[Cookie] 已导入 {len(req.cookies)} 个Cookie到域名: {req.domain}")
        return {
            "success": True,
            "domain": req.domain,
            "count": len(req.cookies)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cookies/export/{domain}")
async def export_cookies(domain: str):
    """导出指定域名的Cookie"""
    cookies = _cookies_storage.get(domain, [])
    return {
        "success": True,
        "domain": domain,
        "cookies": cookies,
        "count": len(cookies)
    }

@router.get("/cookies/list")
async def list_cookies():
    """列出所有已保存的Cookie域名"""
    domains = []
    for domain, cookies in _cookies_storage.items():
        domains.append({
            "domain": domain,
            "count": len(cookies),
            "has_cookies": len(cookies) > 0
        })
    return {
        "success": True,
        "domains": domains,
        "total": len(domains)
    }

@router.delete("/cookies/{domain}")
async def delete_cookies(domain: str):
    """删除指定域名的Cookie"""
    if domain in _cookies_storage:
        del _cookies_storage[domain]
        return {"success": True, "message": f"已删除域名 {domain} 的Cookie"}
    else:
        raise HTTPException(status_code=404, detail="域名不存在")

# ==================== 登录检测API ====================

@router.post("/detect-login")
async def detect_login(req: LoginDetectRequest):
    """
    四层登录检测：
    1. HTTP状态码检测（401/403）
    2. URL重定向检测（跳转到login页面）
    3. 页面元素检测（登录表单、登录按钮）
    4. 文本提示检测（多语言"登录"关键词）
    """
    try:
        from urllib.parse import urlparse

        # 解析URL
        parsed = urlparse(req.url)
        domain = parsed.netloc

        # 检测标志
        needs_login = False
        reasons = []

        # 第2层：URL重定向检测
        url_lower = req.url.lower()
        if any(keyword in url_lower for keyword in ['login', 'signin', 'auth', 'account']):
            needs_login = True
            reasons.append("URL包含登录关键词")

        # 如果提供了HTML，进行元素和文本检测
        if req.html:
            html_lower = req.html.lower()

            # 第3层：页面元素检测
            if any(keyword in html_lower for keyword in [
                'type="password"',
                'name="password"',
                'id="password"',
                '<form' and ('login' in html_lower or 'signin' in html_lower)
            ]):
                needs_login = True
                reasons.append("检测到登录表单元素")

            # 第4层：多语言文本检测
            login_keywords = [
                'please log in', 'please sign in', 'login required',
                '请登录', '请先登录', '需要登录',
                'ログイン', 'サインイン',
                'se connecter', 'iniciar sesión'
            ]
            if any(keyword in html_lower for keyword in login_keywords):
                needs_login = True
                reasons.append("检测到登录提示文本")

        return {
            "success": True,
            "needs_login": needs_login,
            "domain": domain,
            "reasons": reasons,
            "has_cookies": domain in _cookies_storage
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "needs_login": False
        }

# ==================== iframe登录API ====================

@router.get("/login-in-iframe")
async def login_in_iframe(url: str):
    """返回用于iframe登录的HTML页面"""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc

        # 构建iframe登录页面
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>登录 - {domain}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }}
        iframe {{
            width: 100%;
            height: 100vh;
            border: none;
        }}
    </style>
</head>
<body>
    <iframe src="{url}" sandbox="allow-same-origin allow-scripts allow-forms allow-popups"></iframe>
</body>
</html>
"""
        return {"success": True, "html": html, "domain": domain}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 浏览器弹窗登录API ====================

BROWSER_LOGIN_SCRIPT = """
import sys
import json
import io
import time

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright
from urllib.parse import urlparse

def open_browser_for_login(url, domain):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--window-size=1280,800'
                ]
            )

            context = browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = context.new_page()

            # 注入确认按钮
            page.add_init_script('''
                window.addEventListener('load', () => {
                    const banner = document.createElement('div');
                    banner.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        right: 0;
                        z-index: 999999;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        padding: 15px;
                        text-align: center;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                    `;

                    banner.innerHTML = `
                        <div style="font-size: 16px; font-weight: 600; margin-bottom: 10px;">
                            请在此窗口完成登录
                        </div>
                        <button id="loginCompleteBtn" style="
                            background: white;
                            color: #667eea;
                            border: none;
                            padding: 10px 30px;
                            border-radius: 8px;
                            font-size: 14px;
                            font-weight: 600;
                            cursor: pointer;
                            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                        ">
                            我已完成登录 ✓
                        </button>
                    `;

                    document.body.appendChild(banner);

                    document.getElementById('loginCompleteBtn').addEventListener('click', () => {
                        window.__loginCompleted = true;
                    });
                });
            ''')

            # 记录初始Cookie数量
            page.goto(url, wait_until="load")
            initial_cookies = context.cookies()
            initial_count = len(initial_cookies)

            print(f"[Browser] 初始Cookie数量: {initial_count}", file=sys.stderr)

            # 等待登录完成（双重检测）
            login_completed = False
            max_wait = 300  # 5分钟超时

            for i in range(max_wait):
                time.sleep(1)

                # 检测1：按钮被点击
                button_clicked = page.evaluate('window.__loginCompleted === true')

                # 检测2：Cookie数量增加超过3个
                current_cookies = context.cookies()
                cookie_increased = len(current_cookies) > initial_count + 3

                if button_clicked or cookie_increased:
                    login_completed = True
                    reason = "按钮点击" if button_clicked else "Cookie增加"
                    print(f"[Browser] 登录完成（{reason}）", file=sys.stderr)
                    break

            if not login_completed:
                browser.close()
                return {
                    "success": False,
                    "error": "登录超时（5分钟）",
                    "timeout": True
                }

            # 等待2秒确保Cookie完全保存
            time.sleep(2)

            # 获取所有Cookie
            all_cookies = context.cookies()

            browser.close()

            return {
                "success": True,
                "cookies": all_cookies,
                "count": len(all_cookies),
                "domain": domain
            }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    params = json.loads(sys.argv[1])
    result = open_browser_for_login(params["url"], params["domain"])
    output = json.dumps(result, ensure_ascii=True)
    sys.stdout.buffer.write(output.encode('utf-8'))
    sys.stdout.buffer.flush()
"""

@router.post("/open-browser-login")
async def open_browser_login(req: RenderRequest):
    """打开浏览器窗口供用户登录"""
    from urllib.parse import urlparse

    parsed = urlparse(req.url)
    domain = parsed.netloc

    print(f"[Browser Login] 打开浏览器登录: {req.url}")

    temp_script = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(BROWSER_LOGIN_SCRIPT)
            temp_script = f.name

        params = {"url": req.url, "domain": domain}
        params_json = json.dumps(params, ensure_ascii=True)

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        # 执行浏览器登录脚本（阻塞等待）
        result = subprocess.run(
            [sys.executable, temp_script, params_json],
            capture_output=True,
            text=True,
            timeout=360,  # 6分钟超时
            encoding='utf-8',
            env=env
        )

        print("=== Browser Login STDERR ===")
        print(result.stderr)
        print("=" * 50)

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "浏览器登录失败",
                    "stderr": result.stderr
                }
            )

        output = json.loads(result.stdout)

        if output.get("success"):
            # 保存Cookie到内存
            cookies = output.get("cookies", [])
            _cookies_storage[domain] = cookies
            print(f"[Browser Login] ✅ 成功，保存了 {len(cookies)} 个Cookie")

        return output

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail={"error": "登录超时"}
        )
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        )
    finally:
        if temp_script and os.path.exists(temp_script):
            try:
                os.unlink(temp_script)
            except:
                pass

# ==================== 保存iframe登录的Cookie ====================

@router.post("/save-iframe-cookies")
async def save_iframe_cookies(req: CookieImportRequest):
    """保存从iframe登录获取的Cookie"""
    try:
        domain = req.domain
        cookies = req.cookies

        _cookies_storage[domain] = cookies
        print(f"[iframe Login] 保存了 {len(cookies)} 个Cookie到域名: {domain}")

        return {
            "success": True,
            "domain": domain,
            "count": len(cookies),
            "message": "Cookie已保存"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))