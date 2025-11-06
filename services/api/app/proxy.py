# services/api/app/proxy.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import subprocess
import json
import sys
import tempfile
import os
from urllib.parse import urlparse

router = APIRouter(prefix="/api/proxy", tags=["proxy"])

# Cookie存储字典,按域名存储
_cookies_storage: Dict[str, List[Dict]] = {}

class RenderRequest(BaseModel):
    url: str
    timeout_ms: int = 30000
    wait_for: Optional[str] = None

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

class CookieImportRequest(BaseModel):
    domain: str
    cookies: List[Dict[str, Any]]

class CookieExportResponse(BaseModel):
    domain: str
    cookies: List[Dict[str, Any]]
    count: int

@router.post("/cookies/import")
async def import_cookies(req: CookieImportRequest):
    """导入Cookie到指定域名"""
    try:
        _cookies_storage[req.domain] = req.cookies
        print(f"[Cookie] 导入 {len(req.cookies)} 个Cookie到域名: {req.domain}")
        return {
            "success": True,
            "domain": req.domain,
            "count": len(req.cookies),
            "message": f"成功导入 {len(req.cookies)} 个Cookie"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cookies/export")
async def export_cookies(domain: str):
    """导出指定域名的Cookie"""
    if domain not in _cookies_storage:
        raise HTTPException(
            status_code=404,
            detail=f"未找到域名 {domain} 的Cookie"
        )

    cookies = _cookies_storage[domain]
    return {
        "success": True,
        "domain": domain,
        "cookies": cookies,
        "count": len(cookies)
    }

@router.get("/cookies/list")
async def list_cookies():
    """列出所有域名的Cookie"""
    result = {}
    for domain, cookies in _cookies_storage.items():
        result[domain] = {
            "count": len(cookies),
            "cookies": cookies
        }

    return {
        "success": True,
        "domains": list(_cookies_storage.keys()),
        "total_domains": len(_cookies_storage),
        "data": result
    }

@router.delete("/cookies/clear")
async def clear_cookies(domain: Optional[str] = None):
    """清除Cookie(可选指定域名)"""
    if domain:
        if domain in _cookies_storage:
            del _cookies_storage[domain]
            return {
                "success": True,
                "message": f"已清除域名 {domain} 的Cookie"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"未找到域名 {domain} 的Cookie"
            )
    else:
        _cookies_storage.clear()
        return {
            "success": True,
            "message": "已清除所有Cookie"
        }

# ==================== 登录检测API ====================

# 登录检测的Playwright脚本
LOGIN_DETECT_TEMPLATE = """
import sys
import json
import io
from urllib.parse import urlparse

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

def detect_login_requirement(url):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()

            # 访问页面
            response = page.goto(url, wait_until="load", timeout=15000)
            page.wait_for_timeout(2000)

            # 四层检测
            detection_results = {
                "needs_login": False,
                "reasons": [],
                "details": {}
            }

            # 1. HTTP状态码检测
            if response and response.status in [401, 403]:
                detection_results["needs_login"] = True
                detection_results["reasons"].append("HTTP状态码异常")
                detection_results["details"]["http_status"] = response.status

            # 2. URL重定向检测
            current_url = page.url
            parsed_current = urlparse(current_url).path.lower()
            login_keywords = ['login', 'signin', 'auth', 'sso', '登录', '登入']
            if any(keyword in parsed_current for keyword in login_keywords):
                detection_results["needs_login"] = True
                detection_results["reasons"].append("URL重定向到登录页")
                detection_results["details"]["redirected_url"] = current_url

            # 3. 页面元素检测
            login_selectors = [
                'input[type="password"]',
                'input[name*="password"]',
                'input[id*="password"]',
                'button[type="submit"]',
                'form[action*="login"]',
                'a[href*="login"]'
            ]

            found_elements = []
            for selector in login_selectors:
                try:
                    count = page.locator(selector).count()
                    if count > 0:
                        found_elements.append({"selector": selector, "count": count})
                except:
                    pass

            if len(found_elements) >= 2:
                detection_results["needs_login"] = True
                detection_results["reasons"].append("检测到登录表单元素")
                detection_results["details"]["login_elements"] = found_elements

            # 4. 文本提示检测
            body_text = page.inner_text('body')
            login_text_keywords = [
                '请登录', '请先登录', 'please login', 'please sign in',
                '登录后查看', 'login required', '需要登录',
                'sign in to continue', '您需要登录'
            ]

            found_keywords = [kw for kw in login_text_keywords if kw.lower() in body_text.lower()]
            if found_keywords:
                detection_results["needs_login"] = True
                detection_results["reasons"].append("检测到登录提示文本")
                detection_results["details"]["login_keywords"] = found_keywords[:5]

            browser.close()

            return {
                "success": True,
                "url": url,
                "current_url": current_url,
                "detection": detection_results
            }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    url = sys.argv[1]
    result = detect_login_requirement(url)
    output = json.dumps(result, ensure_ascii=True)
    sys.stdout.buffer.write(output.encode('utf-8'))
    sys.stdout.buffer.flush()
"""

class LoginDetectRequest(BaseModel):
    url: str

@router.post("/detect-login")
async def detect_login(req: LoginDetectRequest):
    """检测页面是否需要登录"""
    print(f"[LoginDetect] 检测URL: {req.url}")

    temp_script = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(LOGIN_DETECT_TEMPLATE)
            temp_script = f.name

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        result = subprocess.run(
            [sys.executable, temp_script, req.url],
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            env=env
        )

        print("=== Login Detection STDERR ===")
        print(result.stderr)
        print("=" * 50)

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "检测进程失败",
                    "returncode": result.returncode,
                    "stderr": result.stderr
                }
            )

        output = json.loads(result.stdout)

        if not output.get("success"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": output.get("error", "检测失败"),
                    "traceback": output.get("traceback", "")[:1000]
                }
            )

        print(f"[LoginDetect] 检测结果: {output['detection']}")

        return output

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail={"error": "检测超时"}
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

# ==================== iframe登录API ====================

@router.get("/login-in-iframe")
async def login_in_iframe(url: str):
    """返回iframe登录页面的HTML"""
    try:
        # 解析域名
        parsed = urlparse(url)
        domain = parsed.netloc

        # 返回一个简单的HTML,里面嵌入目标登录页
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>登录 - {domain}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100vh;
            overflow: hidden;
        }}
        iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}
    </style>
</head>
<body>
    <iframe src="{url}" sandbox="allow-same-origin allow-scripts allow-forms allow-popups"></iframe>
</body>
</html>
        """

        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e)}
        )

# ==================== 浏览器窗口登录API ====================

# 浏览器登录的Playwright脚本
BROWSER_LOGIN_TEMPLATE = """
import sys
import json
import io
from urllib.parse import urlparse

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

def browser_login(url):
    try:
        with sync_playwright() as p:
            # 启动有头浏览器
            browser = p.chromium.launch(
                headless=False,
                args=['--start-maximized']
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = context.new_page()

            # 访问登录页
            page.goto(url, wait_until="load", timeout=30000)
            page.wait_for_timeout(1000)

            # 注入顶部横幅和按钮
            page.evaluate('''
                () => {
                    // 创建顶部横幅
                    const banner = document.createElement('div');
                    banner.id = 'seenfetch-login-banner';
                    banner.style.cssText = `
                        position: fixed;
                        top: 0;
                        left: 0;
                        right: 0;
                        height: 60px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        padding: 0 20px;
                        z-index: 999999;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                    `;

                    banner.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 24px;">🔐</span>
                            <span style="font-size: 16px; font-weight: 600;">SeenFetch 登录助手</span>
                        </div>
                        <button id="seenfetch-login-done" style="
                            background: rgba(255,255,255,0.15);
                            border: 2px solid rgba(255,255,255,0.5);
                            backdrop-filter: blur(10px);
                            color: white;
                            padding: 10px 24px;
                            border-radius: 8px;
                            font-size: 15px;
                            font-weight: 600;
                            cursor: pointer;
                            transition: all 0.3s;
                        " onmouseover="this.style.background='rgba(255,255,255,0.25)'"
                           onmouseout="this.style.background='rgba(255,255,255,0.15)'">
                            ✓ 我已完成登录
                        </button>
                    `;

                    document.body.appendChild(banner);

                    // 调整body的padding,避免内容被遮挡
                    document.body.style.paddingTop = '60px';

                    window.__loginDone = false;
                    document.getElementById('seenfetch-login-done').onclick = () => {
                        window.__loginDone = true;
                    };
                }
            ''')

            print("[Browser] 浏览器已打开,等待用户登录...", file=sys.stderr)

            # 获取初始Cookie数量
            initial_cookies = context.cookies()
            initial_count = len(initial_cookies)
            print(f"[Browser] 初始Cookie数量: {initial_count}", file=sys.stderr)

            # 双重检测机制:按钮点击 OR Cookie增加
            login_completed = False
            check_interval = 1000  # 1秒
            max_wait = 300000  # 5分钟
            elapsed = 0

            while not login_completed and elapsed < max_wait:
                page.wait_for_timeout(check_interval)
                elapsed += check_interval

                # 检测1:按钮是否被点击
                button_clicked = page.evaluate('() => window.__loginDone')
                if button_clicked:
                    print("[Browser] ✅ 用户点击了完成按钮", file=sys.stderr)
                    login_completed = True
                    break

                # 检测2:Cookie数量是否显著增加
                current_cookies = context.cookies()
                current_count = len(current_cookies)
                if current_count > initial_count + 3:
                    print(f"[Browser] ✅ Cookie数量增加: {initial_count} -> {current_count}", file=sys.stderr)
                    login_completed = True
                    break

            if not login_completed:
                print("[Browser] ⚠️ 登录超时", file=sys.stderr)
                browser.close()
                return {
                    "success": False,
                    "error": "登录超时(5分钟)",
                    "timeout": True
                }

            # 获取最终Cookie
            final_cookies = context.cookies()
            print(f"[Browser] 获取到 {len(final_cookies)} 个Cookie", file=sys.stderr)

            # 获取当前域名
            current_url = page.url
            domain = urlparse(current_url).netloc

            browser.close()

            return {
                "success": True,
                "domain": domain,
                "cookies": final_cookies,
                "cookie_count": len(final_cookies),
                "final_url": current_url
            }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

if __name__ == "__main__":
    url = sys.argv[1]
    result = browser_login(url)
    output = json.dumps(result, ensure_ascii=True)
    sys.stdout.buffer.write(output.encode('utf-8'))
    sys.stdout.buffer.flush()
"""

class BrowserLoginRequest(BaseModel):
    url: str

@router.post("/login-browser")
async def login_browser(req: BrowserLoginRequest):
    """打开浏览器窗口进行登录"""
    print(f"[BrowserLogin] 打开浏览器登录: {req.url}")

    temp_script = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(BROWSER_LOGIN_TEMPLATE)
            temp_script = f.name

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        result = subprocess.run(
            [sys.executable, temp_script, req.url],
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
                    "error": "浏览器登录进程失败",
                    "returncode": result.returncode,
                    "stderr": result.stderr
                }
            )

        output = json.loads(result.stdout)

        if not output.get("success"):
            if output.get("timeout"):
                raise HTTPException(
                    status_code=408,
                    detail={"error": "登录超时", "message": "请在5分钟内完成登录"}
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": output.get("error", "登录失败"),
                        "traceback": output.get("traceback", "")[:1000]
                    }
                )

        # 自动保存Cookie到存储
        domain = output.get("domain")
        cookies = output.get("cookies", [])
        if domain and cookies:
            _cookies_storage[domain] = cookies
            print(f"[BrowserLogin] 自动保存 {len(cookies)} 个Cookie到域名: {domain}")

        print(f"[BrowserLogin] ✅ 登录成功, 获取 {output.get('cookie_count')} 个Cookie")

        return output

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail={"error": "浏览器登录超时"}
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

# ==================== 带Cookie渲染页面API ====================

# 带Cookie渲染的Playwright脚本
RENDER_WITH_COOKIES_TEMPLATE = """
import sys
import json
import io
from urllib.parse import urlparse

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

def render_with_cookies(url, cookies, timeout_ms, inject_js):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-blink-features=AutomationControlled']
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            # 添加Cookie
            if cookies:
                context.add_cookies(cookies)
                print(f"[Render] 添加 {len(cookies)} 个Cookie", file=sys.stderr)

            page = context.new_page()

            # 访问页面
            page.goto(url, wait_until="load", timeout=timeout_ms)
            page.wait_for_timeout(2000)

            # 注入脚本
            if inject_js:
                try:
                    page.add_script_tag(content=inject_js)
                    page.wait_for_timeout(500)
                except Exception as e:
                    print(f"[Render] 注入脚本失败: {e}", file=sys.stderr)

            content = page.content()
            title = page.title()

            # 修复资源路径
            parsed = urlparse(page.url)
            base = f"{parsed.scheme}://{parsed.netloc}/"

            if '<head>' in content:
                base_tag = f'<base href="{base}">'
                content = content.replace('<head>', f'<head>\\n{base_tag}', 1)

            browser.close()

            return {
                "success": True,
                "html": content,
                "url": page.url,
                "title": title,
                "cookies_used": len(cookies) if cookies else 0
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
    result = render_with_cookies(
        params["url"],
        params.get("cookies"),
        params["timeout_ms"],
        params.get("inject_js")
    )
    output = json.dumps(result, ensure_ascii=True)
    sys.stdout.buffer.write(output.encode('utf-8'))
    sys.stdout.buffer.flush()
"""

class RenderWithCookiesRequest(BaseModel):
    url: str
    timeout_ms: int = 30000
    use_saved_cookies: bool = True

@router.post("/render-with-cookies")
async def render_with_cookies(req: RenderWithCookiesRequest):
    """使用保存的Cookie渲染页面"""
    print(f"[RenderCookies] 渲染URL: {req.url}")

    # 获取域名对应的Cookie
    parsed = urlparse(req.url)
    domain = parsed.netloc
    cookies = []

    if req.use_saved_cookies and domain in _cookies_storage:
        cookies = _cookies_storage[domain]
        print(f"[RenderCookies] 使用保存的 {len(cookies)} 个Cookie")

    temp_script = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(RENDER_WITH_COOKIES_TEMPLATE)
            temp_script = f.name

        params = {
            "url": req.url,
            "cookies": cookies,
            "timeout_ms": req.timeout_ms,
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

        print("=== Render with Cookies STDERR ===")
        print(result.stderr)
        print("=" * 50)

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "渲染进程失败",
                    "returncode": result.returncode,
                    "stderr": result.stderr
                }
            )

        output = json.loads(result.stdout)

        if not output.get("success"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": output.get("error", "渲染失败"),
                    "traceback": output.get("traceback", "")[:1000]
                }
            )

        print(f"[RenderCookies] ✅ 渲染成功, HTML长度: {len(output.get('html', ''))} bytes")

        return output

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail={"error": "渲染超时"}
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