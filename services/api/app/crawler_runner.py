# services/api/app/crawler_runner.py
"""
独立进程运行 Crawl4AI，避免 asyncio 冲突
"""
import sys
import json
import asyncio

# Windows 特殊处理 - 必须在导入 crawl4ai 之前
if sys.platform == 'win32':
    # 使用 ProactorEventLoop 而不是 SelectorEventLoop
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from crawl4ai import AsyncWebCrawler

async def crawl_page(url: str):
    """在独立进程中运行爬虫"""
    crawler = None
    try:
        crawler = AsyncWebCrawler(
            browser_type="chromium",
            headless=True,
            verbose=False
        )
        
        await crawler.start()
        
        result = await crawler.arun(
            url=url,
            word_count_threshold=10,
            bypass_cache=True,
            screenshot=False
        )
        
        # 提取需要的数据
        output = {
            "success": result.success,
            "html": result.html if hasattr(result, 'html') else "",
            "text": result.text if hasattr(result, 'text') else "",
            "markdown": result.markdown if hasattr(result, 'markdown') else "",
            "links": result.links if hasattr(result, 'links') else {},
            "media": result.media if hasattr(result, 'media') else {},
            "metadata": result.metadata if hasattr(result, 'metadata') else {},
            "word_count": result.word_count if hasattr(result, 'word_count') else 0
        }
        
        return output
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
    finally:
        if crawler:
            await crawler.close()

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No URL provided"}))
        sys.exit(1)
    
    url = sys.argv[1]
    
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(crawl_page(url))
        print(json.dumps(result, ensure_ascii=False))
    finally:
        loop.close()

if __name__ == "__main__":
    main()