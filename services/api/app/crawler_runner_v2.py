# services/api/app/crawler_runner_v2.py
"""
增强版 Crawl4AI 爬虫 - 支持反反爬虫和自动滚动
日志输出到 stderr，JSON 结果输出到 stdout
"""
import sys
import json
import asyncio
import io
import contextlib
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Windows 特殊处理
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())



def log(message):
    """输出日志到 stderr"""
    print(message, file=sys.stderr, flush=True)

# services/api/app/crawler_runner_v2.py
# 找到 crawl_page_enhanced 函数，修改 browser_config 部分

async def crawl_page_enhanced(url: str, config: dict = None):
    """增强版爬取"""
    crawler = None
    config = config or {}
    
    try:
        log(f"[V2] Initializing enhanced crawler for: {url}")
        
        # 根据配置构建 BrowserConfig
        if config.get('use_stealth'):
            browser_config = BrowserConfig(
                browser_type="chromium",
                headless=True,
                verbose=False,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                extra_args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
                headers={
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            )
            log("[V2] Stealth mode enabled")
        else:
            browser_config = BrowserConfig(
                browser_type="chromium",
                headless=True,
                verbose=False
            )
            log("[V2] Standard mode")
        
        crawler = AsyncWebCrawler(
            config=browser_config,
            verbose=True
        )
        
        await crawler.start()
        
        # JavaScript 脚本
        js_scripts = []
        
        # 隐藏 webdriver 特征
        if config.get('use_stealth'):
            js_scripts.append("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}};
            """)
        
        # 自动滚动
        if config.get('auto_scroll', True):
            js_scripts.append("""
                async function autoScroll() {
                    let lastHeight = document.body.scrollHeight;
                    console.log('[Scroll] Start height:', lastHeight);
                    
                    for (let i = 0; i < 5; i++) {
                        window.scrollTo(0, document.body.scrollHeight);
                        window.scrollBy(0, 9999);
                        
                        document.querySelectorAll('img[loading]').forEach(img => img.loading = 'eager');
                        
                        await new Promise(r => setTimeout(r, 1500));
                        
                        let newHeight = document.body.scrollHeight;
                        console.log(`[Scroll] Step ${i+1}: ${newHeight}px`);
                        
                        if (newHeight === lastHeight) break;
                        lastHeight = newHeight;
                    }
                    
                    window.scrollTo(0, 0);
                    console.log('[Scroll] Complete');
                }
                await autoScroll();
            """)
        
        # 🔥 修复：使用新的 cache_mode 参数
        crawler_config = CrawlerRunConfig(
            js_code="\n".join(js_scripts) if js_scripts else None,
            wait_for=config.get('wait_for'),
            delay_before_return_html=2.0,
            word_count_threshold=10,
            cache_mode=CacheMode.BYPASS,  # 🔥 新参数
            screenshot=False
        )
        
        log("[V2] Starting crawl...")
        result = await crawler.arun(url=url, config=crawler_config)
        
        log(f"[V2] Crawl completed. Success: {result.success}")
        
        # 提取数据
        output = {
            "success": result.success,
            "html": result.html if hasattr(result, 'html') else "",
            "text": result.text if hasattr(result, 'text') else "",
            "markdown": result.markdown if hasattr(result, 'markdown') else "",
            "fit_markdown": result.fit_markdown if hasattr(result, 'fit_markdown') else "",
            "links": result.links if hasattr(result, 'links') else {},
            "media": result.media if hasattr(result, 'media') else {},
            "metadata": result.metadata if hasattr(result, 'metadata') else {},
            "word_count": result.word_count if hasattr(result, 'word_count') else 0,
            "config_used": config
        }
        
        return output
        
    except Exception as e:
        log(f"[V2] Error: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {
            "success": False,
            "error": str(e),
            "config_used": config
        }
    finally:
        if crawler:
            try:
                await crawler.close()
                log("[V2] Crawler closed")
            except:
                pass


# services/api/app/crawler_runner_v2.py

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No params provided"}))
        sys.exit(1)
    
    # 🔥 修复：更健壮的参数解析
    try:
        # 获取原始参数
        raw_param = sys.argv[1]
        
        # 尝试作为 JSON 解析
        params = json.loads(raw_param)
        
        # 🔥 关键修复：验证参数结构
        if isinstance(params, dict):
            url = params.get("url")
            config = params.get("config", {})
        else:
            # 如果不是字典，可能是直接传了 URL
            url = str(params)
            config = {}
            
    except json.JSONDecodeError:
        # 兼容旧版：直接传 URL 字符串
        url = sys.argv[1]
        config = {}
    
    # 🔥 验证 URL
    if not url or not isinstance(url, str):
        error_msg = f"Invalid URL: {url} (type: {type(url).__name__})"
        print(json.dumps({"success": False, "error": error_msg}), file=sys.stderr)
        sys.exit(1)
    
    # 🔥 确保 URL 格式正确
    url = url.strip()
    if not url.startswith(('http://', 'https://', 'file://')):
        error_msg = f"URL must start with http://, https://, or file://. Got: {url}"
        print(json.dumps({"success": False, "error": error_msg}), file=sys.stderr)
        sys.exit(1)
    
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 重定向 stdout
        stdout_buffer = io.StringIO()
        
        with contextlib.redirect_stdout(stdout_buffer):
            result = loop.run_until_complete(crawl_page_enhanced(url, config))
        
        # 捕获的输出发送到 stderr
        captured = stdout_buffer.getvalue()
        if captured:
            sys.stderr.write("=== Crawl4AI Output ===\n")
            sys.stderr.write(captured)
            sys.stderr.write("======================\n")
            sys.stderr.flush()
        
        # 纯 JSON 输出到 stdout
        json_str = json.dumps(result, ensure_ascii=True)
        sys.stdout.buffer.write(json_str.encode('utf-8'))
        sys.stdout.flush()
    
    except Exception as e:
        sys.stderr.write(f"Fatal error: {e}\n")
        import traceback
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"success": False, "error": str(e)}))
        
    finally:
        loop.close()


if __name__ == "__main__":
    main()

