# services/api/app/crawler_runner.py
"""
独立进程运行 Crawl4AI，避免 asyncio 冲突
日志输出到 stderr，JSON 结果输出到 stdout
"""
import sys
import json
import asyncio
import io
import contextlib

# Windows 特殊处理 - 必须在导入 crawl4ai 之前
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from crawl4ai import AsyncWebCrawler

def log(message):
    """输出日志到 stderr"""
    print(message, file=sys.stderr, flush=True)

async def crawl_page(url: str):
    """在独立进程中运行爬虫"""
    crawler = None
    try:
        log(f"Initializing crawler for: {url}")
        
        crawler = AsyncWebCrawler(
            browser_type="chromium",
            headless=True,
            verbose=True  # 保留详细日志
        )
        
        await crawler.start()
        
        log("Starting page crawl...")
        result = await crawler.arun(
            url=url,
            word_count_threshold=10,
            bypass_cache=True,
            screenshot=False
        )
        
        log(f"Crawl completed. Success: {result.success}")
        
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
        log(f"Error during crawl: {e}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        return {"success": False, "error": str(e)}
    finally:
        if crawler:
            try:
                await crawler.close()
                log("Crawler closed successfully")
            except:
                pass

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No URL provided"}))
        sys.exit(1)
    
    url = sys.argv[1]
    
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 创建一个字符串缓冲区来捕获所有标准输出
        stdout_buffer = io.StringIO()
        
        # 临时重定向 stdout 到缓冲区，防止 Crawl4AI 的输出污染 JSON
        with contextlib.redirect_stdout(stdout_buffer):
            # 运行爬虫
            result = loop.run_until_complete(crawl_page(url))
        
        # 将捕获的输出作为日志发送到 stderr
        captured_output = stdout_buffer.getvalue()
        if captured_output:
            sys.stderr.write("=== Crawl4AI Output ===\n")
            sys.stderr.write(captured_output)
            sys.stderr.write("======================\n")
            sys.stderr.flush()
        
        # 只将纯 JSON 输出到 stdout，确保 ASCII 编码避免问题
        json_str = json.dumps(result, ensure_ascii=True)
        sys.stdout.buffer.write(json_str.encode('utf-8'))
        sys.stdout.flush()
    
    except Exception as e:
        # 错误信息输出到 stderr
        sys.stderr.write(f"Fatal error: {e}\n")
        import traceback
        traceback.print_exc(file=sys.stderr)
        
        # 输出错误 JSON 到 stdout
        print(json.dumps({"success": False, "error": str(e)}))
        
    finally:
        loop.close()

if __name__ == "__main__":
    main()