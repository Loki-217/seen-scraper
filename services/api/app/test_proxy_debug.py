# test_proxy_debug.py
import subprocess
import sys
import json
import tempfile

# 测试1：基本subprocess调用
print("=== 测试1: 基本subprocess ===")
test_script = """
print("Hello from subprocess")
"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
    f.write(test_script)
    temp_file = f.name

try:
    result = subprocess.run(
        [sys.executable, temp_file],
        capture_output=True,
        text=True,
        timeout=5
    )
    print(f"返回码: {result.returncode}")
    print(f"输出: {result.stdout}")
    print(f"错误: {result.stderr}")
except Exception as e:
    print(f"错误: {e}")

import os
os.unlink(temp_file)

# 测试2：Playwright是否可用
print("\n=== 测试2: Playwright ===")
playwright_test = """
from playwright.sync_api import sync_playwright
import json

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com", timeout=10000)
        title = page.title()
        browser.close()
        print(json.dumps({"success": True, "title": title}))
except Exception as e:
    import traceback
    print(json.dumps({"success": False, "error": str(e), "traceback": traceback.format_exc()}))
"""

with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
    f.write(playwright_test)
    temp_file = f.name

try:
    result = subprocess.run(
        [sys.executable, temp_file],
        capture_output=True,
        text=True,
        timeout=30
    )
    print(f"返回码: {result.returncode}")
    print(f"输出: {result.stdout}")
    if result.stderr:
        print(f"错误输出: {result.stderr}")
except Exception as e:
    print(f"错误: {e}")

os.unlink(temp_file)

# 测试3：直接调用API端点逻辑
print("\n=== 测试3: 模拟API调用 ===")
try:
    from services.api.app.proxy import render_page
    print("成功导入render_page函数")
except Exception as e:
    print(f"导入失败: {e}")
    import traceback
    traceback.print_exc()