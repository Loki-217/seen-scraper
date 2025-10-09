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
            
            # 🔥 隐藏webdriver特征
            page.add_init_script('''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
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
            
            # 🔥 修复资源路径和添加图标库
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
    
                
                print("[Fix] Resources and icons fixed", file=sys.stderr)
            
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