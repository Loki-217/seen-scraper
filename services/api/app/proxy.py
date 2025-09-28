# services/api/app/proxy.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
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

# 注入的JavaScript代码
INJECTED_SCRIPT = """
(function() {
    if (window.__scraperInjected) return;
    window.__scraperInjected = true;
    
    const style = document.createElement('style');
    style.innerHTML = `
        .scraper-hover { 
            outline: 2px solid #4CAF50 !important;
            outline-offset: 2px;
            cursor: pointer !important;
        }
        .scraper-selected { 
            background: rgba(76, 175, 80, 0.3) !important;
            outline: 2px solid #2196F3 !important;
        }
    `;
    document.head.appendChild(style);

    // 修改点击事件，发送更多信息给父窗口
    document.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        // 收集元素的详细信息
        const elementInfo = {
            tagName: e.target.tagName.toLowerCase(),
            className: e.target.className,
            id: e.target.id,
            innerHTML: e.target.innerHTML.substring(0, 200),
            textContent: e.target.textContent.substring(0, 100),
            attributes: {},
            rect: e.target.getBoundingClientRect(),
            computedStyle: {
                display: getComputedStyle(e.target).display,
                position: getComputedStyle(e.target).position
            }
        };
        
        // 收集所有属性
        Array.from(e.target.attributes).forEach(attr => {
            elementInfo.attributes[attr.name] = attr.value;
        });
        
        // 发送给父窗口
        window.parent.postMessage({
            type: 'element-clicked',
            element: elementInfo,
            selector: generateSelector(e.target)
        }, '*');
        
        return false;
    }, true);
    
    let lastHovered = null;
    
    document.addEventListener('mouseover', function(e) {
        if (lastHovered && lastHovered !== e.target) {
            lastHovered.classList.remove('scraper-hover');
        }
        e.target.classList.add('scraper-hover');
        lastHovered = e.target;
    }, true);
    
    document.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const elem = e.target;
        const isSelected = elem.classList.contains('scraper-selected');
        
        if (isSelected) {
            elem.classList.remove('scraper-selected');
        } else {
            elem.classList.add('scraper-selected');
        }
        
        const selector = generateSelector(elem);
        const text = elem.innerText ? elem.innerText.substring(0, 100) : '';
        const tagName = elem.tagName.toLowerCase();
        
        if (window.parent !== window) {
            window.parent.postMessage({
                type: 'element-selected',
                action: isSelected ? 'remove' : 'add',
                selector: selector,
                text: text,
                tagName: tagName,
                attributes: {
                    href: elem.getAttribute('href'),
                    src: elem.getAttribute('src')
                }
            }, '*');
        }
        
        return false;
    }, true);
    
    function generateSelector(elem) {
        if (elem.id && !elem.id.match(/[0-9]{5,}/)) {
            return '#' + elem.id;
        }
        
        if (elem.className && typeof elem.className === 'string') {
            const classes = elem.className
                .split(' ')
                .filter(c => c && !c.match(/^(active|hover|focus|scraper-)/));
            
            if (classes.length > 0) {
                const selector = '.' + classes.join('.');
                const matches = document.querySelectorAll(selector);
                if (matches.length === 1) return selector;
            }
        }
        
        const path = [];
        let current = elem;
        while (current && current.nodeType === Node.ELEMENT_NODE && path.length < 4) {
            let selector = current.tagName.toLowerCase();
            if (current.className && typeof current.className === 'string') {
                const classes = current.className.split(' ').filter(c => c && !c.match(/^(scraper-|active|hover)/)).slice(0, 1);
                if (classes.length > 0) {
                    selector += '.' + classes[0];
                }
            }
            path.unshift(selector);
            current = current.parentElement;
        }
        return path.join(' > ');
    }
    
    console.log('Scraper script injected!');
})();
"""

# 创建一个独立的Python脚本来运行Playwright
PLAYWRIGHT_SCRIPT = """
import sys
import json
from playwright.sync_api import sync_playwright

def render_page(url, timeout_ms, wait_for=None):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            page.wait_for_timeout(1000)
            
            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=5000)
                except:
                    pass
            
            # 注入脚本
            page.add_script_tag(content='''%s''')
            
            content = page.content()
            title = page.title()
            
            browser.close()
            
            return {
                "success": True,
                "html": content,
                "url": url,
                "title": title,
                "script_injected": True
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    params = json.loads(sys.argv[1])
    result = render_page(params["url"], params["timeout_ms"], params.get("wait_for"))
    print(json.dumps(result))
""" % INJECTED_SCRIPT.replace("'", "\\'").replace('"', '\\"')

@router.post("/render")
async def render_page(req: RenderRequest):
    """通过子进程运行Playwright，完全避开asyncio冲突"""
    
    # 创建临时Python文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(PLAYWRIGHT_SCRIPT)
        temp_script = f.name
    
    try:
        # 准备参数
        params = {
            "url": req.url,
            "timeout_ms": req.timeout_ms,
            "wait_for": req.wait_for
        }
        
        # 运行子进程
        result = subprocess.run(
            [sys.executable, temp_script, json.dumps(params)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Playwright error: {result.stderr}")
        
        # 解析结果
        output = json.loads(result.stdout)
        
        if not output["success"]:
            raise HTTPException(status_code=400, detail=output["error"])
        
        return output
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="页面加载超时")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse output: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 清理临时文件
        try:
            os.unlink(temp_script)
        except:
            pass

@router.get("/test")
async def test_proxy():
    return {"status": "proxy module loaded successfully"}

@router.post("/test-simple")
async def test_simple():
    """测试基本功能 - 也使用子进程方式"""
    simple_script = """
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com", timeout=10000)
    title = page.title()
    browser.close()
    print(json.dumps({"success": True, "title": title}))
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(simple_script)
        temp_script = f.name
    
    try:
        result = subprocess.run(
            [sys.executable, temp_script],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return {"success": False, "error": result.stderr}
        
        return json.loads(result.stdout)
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try:
            os.unlink(temp_script)
        except:
            pass