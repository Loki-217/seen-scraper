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

class RenderRequest(BaseModel):
    url: str
    timeout_ms: int = 30000
    wait_for: Optional[str] = None

class SmartClickRequest(BaseModel):
    url: str
    element: Dict[str, Any]

# 支持模式切换的注入脚本
INJECTED_SCRIPT = r"""
(function() {
    if (window.__scraperInjected) return;
    window.__scraperInjected = true;

    console.log('[SeenFetch] Script injected!');

    // 🔥 模式控制：'config' 或 'login'
    var mode = 'config';

    var style = document.createElement('style');
    style.innerHTML = '.scraper-hover { outline: 2px solid #4CAF50 !important; outline-offset: 2px; }';
    document.head.appendChild(style);

    // 🔥 监听模式切换消息
    window.addEventListener('message', function(event) {
        if (event.data && event.data.type === 'switch-mode') {
            mode = event.data.mode;
            console.log('[SeenFetch] Mode switched to:', mode);

            // 清除所有高亮
            var highlighted = document.querySelectorAll('.scraper-hover');
            highlighted.forEach(function(el) {
                el.classList.remove('scraper-hover');
            });
        }
    });

    // 🔥 点击事件：只在config模式下拦截
    document.addEventListener('click', function(e) {
        if (mode === 'config') {
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
        }
        // login模式：不拦截，让点击正常执行
    }, true);

    // 🔥 鼠标悬停：只在config模式下高亮
    document.addEventListener('mouseover', function(e) {
        if (mode === 'config') {
            e.target.classList.add('scraper-hover');
        }
    }, true);

    document.addEventListener('mouseout', function(e) {
        if (mode === 'config') {
            e.target.classList.remove('scraper-hover');
        }
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

# ==================== 登录检测功能 ====================

class DetectLoginRequest(BaseModel):
    url: str
    timeout_ms: int = 5000

# Playwright检测登录脚本
DETECT_LOGIN_TEMPLATE = """
import sys
import json
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

def detect_login(url, timeout_ms):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = context.new_page()

            # 访问页面
            response = page.goto(url, wait_until="load", timeout=timeout_ms)
            page.wait_for_timeout(1000)

            result = {
                "success": True,
                "required": False,
                "confidence": "low",
                "reason": "未检测到登录需求",
                "details": {}
            }

            # 🔥 检测层1：HTTP状态码
            if response.status in [401, 403]:
                result["required"] = True
                result["confidence"] = "high"
                result["reason"] = f"HTTP {response.status} - 需要认证"
                result["details"]["status_code"] = response.status
                return result

            # 🔥 检测层2：URL重定向
            current_url = page.url
            if 'login' in current_url.lower() or 'signin' in current_url.lower():
                result["required"] = True
                result["confidence"] = "high"
                result["reason"] = "URL跳转到登录页"
                result["details"]["redirected_url"] = current_url
                return result

            # 🔥 检测层3：页面元素
            login_indicators = {
                'login_form': 'form[action*="login"], form[action*="signin"]',
                'password_input': 'input[type="password"]',
                'login_button': 'button:has-text("登录"), button:has-text("Sign In"), button:has-text("Log In")',
            }

            detected_elements = {}
            for key, selector in login_indicators.items():
                try:
                    count = page.locator(selector).count()
                    if count > 0:
                        detected_elements[key] = count
                except:
                    pass

            # 如果同时有表单和密码框，很可能需要登录
            if 'login_form' in detected_elements and 'password_input' in detected_elements:
                result["required"] = True
                result["confidence"] = "high"
                result["reason"] = "检测到登录表单和密码输入框"
                result["details"]["elements"] = detected_elements
                return result

            # 只有密码框，中等置信度
            if 'password_input' in detected_elements:
                result["required"] = True
                result["confidence"] = "medium"
                result["reason"] = "检测到密码输入框"
                result["details"]["elements"] = detected_elements
                return result

            # 🔥 检测层4：提示文本
            login_texts = [
                '请登录', 'Please log in', 'Please sign in',
                'Sign in to continue', 'Login to continue',
                '登录后查看', 'Login required', '需要登录'
            ]

            found_texts = []
            for text in login_texts:
                try:
                    if page.locator(f'text="{text}"').count() > 0:
                        found_texts.append(text)
                except:
                    pass

            if found_texts:
                result["required"] = True
                result["confidence"] = "medium"
                result["reason"] = f"检测到登录提示文字: {found_texts[0]}"
                result["details"]["texts"] = found_texts
                return result

            browser.close()
            return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "type": type(e).__name__
        }

if __name__ == "__main__":
    params = json.loads(sys.argv[1])
    result = detect_login(params["url"], params["timeout_ms"])
    output = json.dumps(result, ensure_ascii=True)
    sys.stdout.buffer.write(output.encode('utf-8'))
    sys.stdout.buffer.flush()
"""

@router.post("/detect-login")
async def detect_login(req: DetectLoginRequest):
    """检测网站是否需要登录"""

    print(f"[API] Detecting login requirement for: {req.url}")

    temp_script = None
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(DETECT_LOGIN_TEMPLATE)
            temp_script = f.name

        params = {
            "url": req.url,
            "timeout_ms": req.timeout_ms
        }

        params_json = json.dumps(params, ensure_ascii=True)

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        result = subprocess.run(
            [sys.executable, temp_script, params_json],
            capture_output=True,
            text=True,
            timeout=10,
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
                    "error": "Detection process failed",
                    "returncode": result.returncode,
                    "stderr": result.stderr
                }
            )

        try:
            output = json.loads(result.stdout)
            print(f"[API] Detection result: {output}")
            return output
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Failed to parse detection output",
                    "parse_error": str(e),
                    "stdout": result.stdout[:500]
                }
            )

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