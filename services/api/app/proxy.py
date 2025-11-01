# services/api/app/proxy.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import subprocess
import json
import sys
import tempfile
import os
import httpx
import base64

router = APIRouter(prefix="/api/proxy", tags=["proxy"])

class RenderRequest(BaseModel):
    url: str
    timeout_ms: int = 60000  # 增加到60秒，支持客户端渲染网站
    wait_for: Optional[str] = None

class SmartClickRequest(BaseModel):
    url: str
    element: Dict[str, Any]

class ForwardRequest(BaseModel):
    """Service Worker 转发请求"""
    url: str
    method: str = "GET"
    headers: Dict[str, str] = {}
    body: Optional[str] = None

class ForwardResponse(BaseModel):
    """Service Worker 转发响应"""
    success: bool
    status: int = 200
    headers: Dict[str, str] = {}
    body: Optional[str] = None
    body_base64: Optional[str] = None
    error: Optional[str] = None

# 🔥 反 iframe 跳出脚本（增强版）
# 功能：防止页面检测到在 iframe 中并跳出（如豆瓣等网站）
# 优先级：最高，必须在所有其他脚本之前注入
ANTI_IFRAME_BREAKOUT_SCRIPT = r"""
(function() {
    console.log('[Iframe-Protection] 🛡️ Anti-breakout script loaded');

    try {
        // 1. 冻结 top 对象，使其等于 window.self
        Object.defineProperty(window, 'top', {
            get: function() { return window.self; },
            set: function() { console.warn('[Iframe-Protection] ⚠️ Blocked attempt to modify window.top'); },
            configurable: false
        });

        // 2. 冻结 parent 对象（部分网站会用 parent 跳出）
        Object.defineProperty(window, 'parent', {
            get: function() { return window.self; },
            set: function() { console.warn('[Iframe-Protection] ⚠️ Blocked attempt to modify window.parent'); },
            configurable: false
        });

        // 3. 拦截 frameElement 访问
        Object.defineProperty(window, 'frameElement', {
            get: function() { return null; },  // 返回 null 表示不在 iframe 中
            set: function() {},
            configurable: false
        });

        // 4. 🔥 拦截 location 的所有修改方式
        var originalLocation = window.location;
        var locationProxy = new Proxy(originalLocation, {
            get: function(target, prop) {
                return target[prop];
            },
            set: function(target, prop, value) {
                console.warn('[Iframe-Protection] ⚠️ Blocked location.' + prop + ' modification to:', value);
                // 只允许在同一个iframe内跳转
                if (prop === 'href' && typeof value === 'string' && value.startsWith(window.location.origin)) {
                    target[prop] = value;
                    return true;
                }
                return false;
            }
        });

        // 5. 🔥 拦截 top.location 访问（豆瓣常用技术）
        try {
            if (window.top && window.top.location) {
                Object.defineProperty(window.top, 'location', {
                    get: function() { return window.self.location; },
                    set: function(val) {
                        console.warn('[Iframe-Protection] ⚠️ Blocked top.location redirect to:', val);
                        return false;
                    },
                    configurable: false
                });
            }
        } catch(e) {
            // 跨域访问会抛出异常，这是正常的
        }

        // 6. 🔥 拦截常见的跳出函数调用
        var originalOpen = window.open;
        window.open = function() {
            console.warn('[Iframe-Protection] ⚠️ Blocked window.open() call');
            return null;
        };

        // 7. 🔥 拦截 document.write 和 document.writeln（可能用于重写整个页面）
        var originalWrite = document.write;
        var originalWriteln = document.writeln;
        var writeBlocked = false;

        document.write = function(content) {
            if (!writeBlocked && content && content.includes('<html')) {
                console.warn('[Iframe-Protection] ⚠️ Blocked document.write() - attempting to rewrite page');
                writeBlocked = true;
                return;
            }
            return originalWrite.apply(this, arguments);
        };

        document.writeln = function(content) {
            if (!writeBlocked && content && content.includes('<html')) {
                console.warn('[Iframe-Protection] ⚠️ Blocked document.writeln() - attempting to rewrite page');
                writeBlocked = true;
                return;
            }
            return originalWriteln.apply(this, arguments);
        };

        console.log('[Iframe-Protection] ✅ All protections applied successfully');

    } catch(e) {
        console.error('[Iframe-Protection] ❌ Failed to apply protections:', e);
    }
})();
"""

# 简化的注入脚本
# 功能：拦截点击事件，阻止默认行为，发送元素信息到父窗口
# 网络请求由 Service Worker 代理，不需要在这里拦截
INJECTED_SCRIPT = r"""
(function() {
    // 避免重复注入
    if (window.__scraperInjected) {
        console.log('[Iframe] Script already injected, skipping');
        return;
    }
    window.__scraperInjected = true;

    console.log('[Iframe] Interaction script injected successfully');

    // 添加悬停高亮样式
    var style = document.createElement('style');
    style.innerHTML = `
        .scraper-hover {
            outline: 2px solid #4CAF50 !important;
            outline-offset: 2px;
            cursor: pointer !important;
        }
        .scraper-selected {
            outline: 3px solid #2196F3 !important;
            outline-offset: 2px;
            background: rgba(33, 150, 243, 0.1) !important;
        }
    `;
    document.head.appendChild(style);

    // 点击事件处理：拦截所有点击，阻止默认行为
    document.addEventListener('click', function(e) {
        // 阻止默认行为（跳转、表单提交等）
        e.preventDefault();
        e.stopPropagation();

        console.log('[Iframe] Element clicked:', e.target);

        var element = e.target;

        // 生成选择器
        var selector = element.tagName.toLowerCase();

        if (element.id) {
            selector = '#' + element.id;
        } else if (element.className && typeof element.className === 'string') {
            var classes = element.className.split(' ').filter(function(c) {
                return c && !c.match(/^scraper-/);
            });
            if (classes.length > 0) {
                selector = element.tagName.toLowerCase() + '.' + classes[0];
            }
        }

        // 提取元素信息
        var elementInfo = {
            tagName: element.tagName.toLowerCase(),
            className: element.className,
            id: element.id,
            text: (element.innerText || element.textContent || '').substring(0, 100).trim(),
            selector: selector,
            href: element.href || '',
            src: element.src || '',
            type: element.type || '',
            name: element.name || '',
            value: element.value || ''
        };

        console.log('[Iframe] Sending element info to parent:', elementInfo);

        // 发送消息到父窗口
        window.parent.postMessage({
            type: 'element-clicked',
            element: elementInfo,
            selector: selector
        }, '*');

        // 标记为已选中
        element.classList.add('scraper-selected');

        return false;
    }, true);  // 使用捕获阶段，优先拦截

    // 鼠标悬停：添加高亮效果
    document.addEventListener('mouseover', function(e) {
        if (!e.target.classList.contains('scraper-selected')) {
            e.target.classList.add('scraper-hover');
        }
    }, true);

    // 鼠标移出：移除高亮效果
    document.addEventListener('mouseout', function(e) {
        e.target.classList.remove('scraper-hover');
    }, true);

    // 监听来自父窗口的消息（用于高亮控制等）
    window.addEventListener('message', function(e) {
        if (e.data.type === 'highlight-element') {
            console.log('[Iframe] Received highlight command:', e.data.selector);

            try {
                var elements = document.querySelectorAll(e.data.selector);
                elements.forEach(function(el) {
                    el.classList.add('scraper-selected');
                });
            } catch (err) {
                console.error('[Iframe] Failed to highlight element:', err);
            }
        } else if (e.data.type === 'clear-highlights') {
            console.log('[Iframe] Clearing all highlights');

            var selected = document.querySelectorAll('.scraper-selected');
            selected.forEach(function(el) {
                el.classList.remove('scraper-selected');
            });
        }
    });

    console.log('[Iframe] Event listeners registered');
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

def render_page(url, timeout_ms, wait_for, inject_js, anti_iframe_script):
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

            # 🔥 最高优先级：注入反 iframe 跳出脚本
            # 必须在页面加载之前就执行，防止豆瓣等网站跳出 iframe
            page.add_init_script(anti_iframe_script)
            print("[Inject] Anti-iframe breakout script added", file=sys.stderr)

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
                # 🔥 特殊处理：为客户端渲染的网站（如Unsplash）等待网络空闲
                if 'unsplash.com' in url.lower():
                    print("[Render] Detected Unsplash - using networkidle wait", file=sys.stderr)
                    page.goto(url, wait_until="networkidle", timeout=timeout_ms)
                    page.wait_for_timeout(5000)  # 额外等待5秒让React渲染完成
                    # 等待主要内容区域加载
                    try:
                        page.wait_for_selector('img', timeout=10000)
                        print("[Render] Unsplash images detected", file=sys.stderr)
                    except:
                        print("[Render] Warning: Unsplash images not detected", file=sys.stderr)
                else:
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

            # 🔥 检查页面内容是否为空
            if not content or len(content) < 100:
                print(f"[Render] Warning: Page content is empty or too short ({len(content)} bytes)", file=sys.stderr)
                # 对于Unsplash等网站，再尝试一次
                if 'unsplash.com' in url.lower():
                    print("[Render] Retrying Unsplash content fetch...", file=sys.stderr)
                    page.wait_for_timeout(5000)
                    content = page.content()
                    print(f"[Render] Retry result: {len(content)} bytes", file=sys.stderr)

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
        params["inject_js"],
        params["anti_iframe_script"]
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
            "anti_iframe_script": ANTI_IFRAME_BREAKOUT_SCRIPT,  # 反iframe跳出脚本
            "inject_js": INJECTED_SCRIPT  # 交互脚本
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

@router.post("/forward", response_model=ForwardResponse)
async def forward_request(req: ForwardRequest):
    """
    转发跨域请求到目标服务器

    用于 Service Worker 绕过浏览器 CORS 限制

    请求体：
    - url: 目标 URL
    - method: HTTP 方法（GET/POST/PUT/DELETE 等）
    - headers: 请求头字典
    - body: 请求体（可选，用于 POST/PUT 等）

    响应体：
    - success: 是否成功
    - status: HTTP 状态码
    - headers: 响应头字典
    - body: 文本响应内容（HTML/JSON/CSS/JS 等）
    - body_base64: 二进制响应内容（图片/字体等，base64 编码）
    - error: 错误信息（如果失败）
    """

    print(f"[Proxy/Forward] 接收请求: {req.method} {req.url}")

    try:
        # 使用 httpx 发送异步 HTTP 请求
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            verify=False  # 忽略 SSL 证书验证（如果需要）
        ) as client:

            # 准备请求头
            headers = dict(req.headers)

            # 移除可能导致问题的请求头
            headers_to_remove = [
                'host', 'connection', 'content-length',
                'transfer-encoding', 'accept-encoding'
            ]
            for h in headers_to_remove:
                headers.pop(h, None)
                headers.pop(h.capitalize(), None)
                headers.pop(h.upper(), None)

            # 🔥 增强请求头伪装，模拟真实浏览器
            # 解析目标URL以获取域名
            from urllib.parse import urlparse
            parsed_url = urlparse(req.url)
            origin = f"{parsed_url.scheme}://{parsed_url.netloc}"

            # 设置完整的浏览器请求头
            if 'user-agent' not in [k.lower() for k in headers.keys()]:
                headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

            if 'accept' not in [k.lower() for k in headers.keys()]:
                # 根据请求类型设置不同的Accept
                if req.url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg')):
                    headers['Accept'] = 'image/webp,image/apng,image/*,*/*;q=0.8'
                elif req.url.endswith(('.css',)):
                    headers['Accept'] = 'text/css,*/*;q=0.1'
                elif req.url.endswith(('.js',)):
                    headers['Accept'] = '*/*'
                else:
                    headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8'

            if 'accept-language' not in [k.lower() for k in headers.keys()]:
                headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7'

            # 添加Referer（设置为同源或目标网站首页）
            if 'referer' not in [k.lower() for k in headers.keys()]:
                headers['Referer'] = origin + '/'

            # 添加Origin（用于CORS请求）
            if req.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
                if 'origin' not in [k.lower() for k in headers.keys()]:
                    headers['Origin'] = origin

            # 添加Sec-Fetch-* 头（Chrome的安全特性）
            headers['Sec-Fetch-Dest'] = 'empty'
            headers['Sec-Fetch-Mode'] = 'cors'
            headers['Sec-Fetch-Site'] = 'same-origin'

            print(f"[Proxy/Forward] 发送请求到: {req.url}")
            print(f"[Proxy/Forward] 方法: {req.method}")
            print(f"[Proxy/Forward] 请求头: {list(headers.keys())}")

            # 发送请求
            response = await client.request(
                method=req.method,
                url=req.url,
                headers=headers,
                content=req.body.encode('utf-8') if req.body else None
            )

            print(f"[Proxy/Forward] 响应状态: {response.status_code}")
            print(f"[Proxy/Forward] 响应头: {list(response.headers.keys())}")

            # 🔥 转换响应头为字典，移除限制性头部
            response_headers = {}
            # 需要移除的限制性响应头
            skip_headers = [
                # 传输相关
                'transfer-encoding', 'content-encoding', 'connection',
                'keep-alive', 'upgrade',
                # 🔥 安全限制头（会阻止 iframe 嵌入或跨域访问）
                'x-frame-options',           # 防止页面被嵌入iframe
                'content-security-policy',    # CSP策略可能限制iframe
                'x-content-type-options',     # 可能影响资源加载
                'strict-transport-security',  # HSTS
                'x-xss-protection',           # XSS保护
            ]

            removed_security_headers = []  # 记录被移除的安全头

            for key, value in response.headers.items():
                key_lower = key.lower()
                if key_lower not in skip_headers:
                    response_headers[key_lower] = value
                elif key_lower in ['x-frame-options', 'content-security-policy', 'x-content-type-options']:
                    # 记录被移除的安全头
                    removed_security_headers.append(f"{key}: {value}")

            # 输出被移除的安全头（用于调试）
            if removed_security_headers:
                print(f"[Proxy/Forward] 🔓 移除限制性响应头:")
                for header in removed_security_headers:
                    print(f"[Proxy/Forward]   - {header}")

            # 判断是否为二进制内容
            content_type = response.headers.get('content-type', '').lower()
            is_binary = any([
                content_type.startswith('image/'),
                content_type.startswith('font/'),
                content_type.startswith('audio/'),
                content_type.startswith('video/'),
                'octet-stream' in content_type,
                content_type.startswith('application/pdf'),
                content_type.startswith('application/zip')
            ])

            if is_binary:
                # 二进制内容：返回 base64 编码
                body_bytes = response.content
                body_base64 = base64.b64encode(body_bytes).decode('ascii')

                print(f"[Proxy/Forward] 二进制内容，大小: {len(body_bytes)} bytes")

                return ForwardResponse(
                    success=True,
                    status=response.status_code,
                    headers=response_headers,
                    body=None,
                    body_base64=body_base64
                )
            else:
                # 文本内容：直接返回
                try:
                    body_text = response.text
                    print(f"[Proxy/Forward] 文本内容，大小: {len(body_text)} chars")

                    return ForwardResponse(
                        success=True,
                        status=response.status_code,
                        headers=response_headers,
                        body=body_text,
                        body_base64=None
                    )
                except Exception as e:
                    # 如果解码失败，尝试作为二进制处理
                    print(f"[Proxy/Forward] 文本解码失败，作为二进制处理: {e}")
                    body_bytes = response.content
                    body_base64 = base64.b64encode(body_bytes).decode('ascii')

                    return ForwardResponse(
                        success=True,
                        status=response.status_code,
                        headers=response_headers,
                        body=None,
                        body_base64=body_base64
                    )

    except httpx.RequestError as e:
        print(f"[Proxy/Forward] 请求错误: {e}")
        return ForwardResponse(
            success=False,
            status=502,
            headers={},
            error=f"请求失败: {str(e)}"
        )

    except httpx.HTTPStatusError as e:
        print(f"[Proxy/Forward] HTTP 错误: {e}")
        return ForwardResponse(
            success=False,
            status=e.response.status_code,
            headers={},
            error=f"HTTP 错误 {e.response.status_code}: {str(e)}"
        )

    except Exception as e:
        print(f"[Proxy/Forward] 未知错误: {e}")
        import traceback
        traceback.print_exc()

        return ForwardResponse(
            success=False,
            status=500,
            headers={},
            error=f"服务器错误: {str(e)}"
        )