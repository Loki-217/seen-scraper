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

# 增强的注入脚本
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
        .scraper-similar {
            outline: 3px solid #FF9800 !important;
            outline-offset: 2px;
            background: rgba(255, 152, 0, 0.1) !important;
        }
    `;
    document.head.appendChild(style);

    // 增强的点击处理
    document.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const element = e.target;
        
        // 生成智能选择器
        function getSmartSelector(el) {
            // 优先使用ID
            if (el.id && !el.id.match(/[0-9]{5,}/)) {
                return '#' + el.id;
            }
            
            // 尝试使用class
            if (el.className && typeof el.className === 'string') {
                const classes = el.className
                    .split(' ')
                    .filter(c => c && !c.match(/^(scraper-|active|hover|focus)/))
                    .slice(0, 2);
                if (classes.length > 0) {
                    return el.tagName.toLowerCase() + '.' + classes.join('.');
                }
            }
            
            // 使用标签+属性
            let selector = el.tagName.toLowerCase();
            if (el.hasAttribute('type')) {
                selector += '[type="' + el.getAttribute('type') + '"]';
            }
            return selector;
        }
        
        const selector = getSmartSelector(element);
        
        // 查找相似元素
        const allSimilar = document.querySelectorAll(selector);
        const similarCount = allSimilar.length;
        
        // 收集详细信息
        const elementInfo = {
            tagName: element.tagName.toLowerCase(),
            className: element.className,
            id: element.id,
            text: element.innerText?.substring(0, 100) || '',
            selector: selector,
            similarCount: similarCount,
            rect: element.getBoundingClientRect(),
            attributes: {}
        };
        
        // 收集属性
        Array.from(element.attributes).forEach(attr => {
            elementInfo.attributes[attr.name] = attr.value;
        });
        
        // 如果有多个相似元素，高亮它们
        if (similarCount > 1) {
            allSimilar.forEach(el => {
                el.classList.add('scraper-similar');
            });
            
            // 3秒后移除高亮
            setTimeout(() => {
                allSimilar.forEach(el => {
                    el.classList.remove('scraper-similar');
                });
            }, 3000);
        }
        
        // 发送给父窗口
        window.parent.postMessage({
            type: 'element-clicked',
            element: elementInfo,
            selector: selector,
            hasSimilar: similarCount > 1
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
    
    console.log('Scraper script injected!');
})();
"""

# Playwright渲染脚本（保持不变）
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
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(PLAYWRIGHT_SCRIPT)
        temp_script = f.name
    
    try:
        params = {
            "url": req.url,
            "timeout_ms": req.timeout_ms,
            "wait_for": req.wait_for
        }
        
        result = subprocess.run(
            [sys.executable, temp_script, json.dumps(params)],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Playwright error: {result.stderr}")
        
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
        try:
            os.unlink(temp_script)
        except:
            pass

@router.post("/smart-click")
async def smart_click(req: SmartClickRequest):
    """处理智能点击，分析相似元素"""
    
    # 创建分析脚本
    analyze_script = f"""
import sys
import json
from playwright.sync_api import sync_playwright

def analyze_similar(url, element_info):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        
        # 根据元素信息生成选择器
        selector = element_info.get('selector')
        if not selector:
            # 尝试生成选择器
            if element_info.get('id'):
                selector = '#' + element_info['id']
            elif element_info.get('className'):
                classes = element_info['className'].split()[0]
                selector = element_info['tagName'] + '.' + classes
            else:
                selector = element_info['tagName']
        
        # 查找所有匹配元素
        elements = page.query_selector_all(selector)
        
        samples = []
        for i, el in enumerate(elements[:10]):  # 最多取10个样本
            try:
                samples.append({{
                    'index': i,
                    'text': el.inner_text()[:100] if el.inner_text() else '',
                    'html': el.inner_html()[:200] if el.inner_html() else ''
                }})
            except:
                pass
        
        browser.close()
        
        return {{
            'success': True,
            'selector': selector,
            'count': len(elements),
            'samples': samples
        }}

if __name__ == "__main__":
    import sys
    params = json.loads(sys.argv[1])
    result = analyze_similar(params['url'], params['element'])
    print(json.dumps(result))
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(analyze_script)
        temp_script = f.name
    
    try:
        params = {
            "url": req.url,
            "element": req.element
        }
        
        result = subprocess.run(
            [sys.executable, temp_script, json.dumps(params)],
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

@router.get("/test")
async def test_proxy():
    return {"status": "proxy module loaded successfully"}

@router.post("/test-simple")
async def test_simple():
    """测试基本功能"""
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