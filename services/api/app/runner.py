# services/api/app/runner.py
from typing import List, Dict
from playwright.sync_api import sync_playwright, TimeoutError as PLTimeoutError

class RunnerError(Exception):
    pass

def run_preview(
    url: str,
    selector: str,
    attr: str = "text",
    wait_selector: str | None = None,
    timeout_ms: int = 10000,
    limit: int = 50,
) -> Dict:
    """打开页面并按 CSS 选择器抽取。"""
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context()
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)

            loc = page.locator(selector)
            count = loc.count()
            items: List[str] = []
            for i in range(min(count, limit)):
                node = loc.nth(i)
                if attr.lower() == "text":
                    items.append(node.inner_text().strip())
                else:
                    items.append((node.get_attribute(attr) or "").strip())

            ctx.close()
            browser.close()
            return {"count": count, "samples": items, "attr": attr}
    except PLTimeoutError as e:
        raise RunnerError(f"超时：{e}")
    except Exception as e:
        raise RunnerError(f"执行失败：{e}")
