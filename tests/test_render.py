# test_render.py
import subprocess
import json
import sys
import tempfile

PLAYWRIGHT_TEST = """
import sys
import json
from playwright.sync_api import sync_playwright

def test_render(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # 导航
        page.goto(url, wait_until="load", timeout=30000)
        page.wait_for_timeout(2000)
        
        print("Page loaded, starting scroll...", file=sys.stderr)
        
        # 滚动测试
        try:
            last_height = page.evaluate("() => document.body.scrollHeight")
            print(f"Initial height: {last_height}", file=sys.stderr)
            
            for i in range(3):
                page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
                new_height = page.evaluate("() => document.body.scrollHeight")
                print(f"Scroll {i+1}: {new_height}", file=sys.stderr)
                if new_height == last_height:
                    break
                last_height = new_height
            
            page.evaluate("() => window.scrollTo(0, 0)")
        except Exception as e:
            print(f"Scroll error: {e}", file=sys.stderr)
        
        # 获取内容
        content = page.content()
        
        # 修复图标
        if '<head>' in content:
            fixes = '<base href="https://ssr1.scrape.center/"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">'
            content = content.replace('<head>', f'<head>\\n{fixes}', 1)
            print("Icon fixes applied", file=sys.stderr)
        
        browser.close()
        return {"success": True, "html": content, "scroll_tested": True}

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://ssr1.scrape.center/page/2"
    result = test_render(url)
    print(json.dumps(result, ensure_ascii=False))
"""

# 运行测试
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
    f.write(PLAYWRIGHT_TEST)
    temp_file = f.name

result = subprocess.run(
    [sys.executable, temp_file, "https://ssr1.scrape.center/page/2"],
    capture_output=True,
    text=True,
    timeout=60
)

print("=== STDERR (日志) ===")
print(result.stderr)
print("\n=== STDOUT (结果) ===")
# 只打印前1000字符
output = result.stdout[:1000] if result.stdout else "No output"
print(output)

import os
os.unlink(temp_file)