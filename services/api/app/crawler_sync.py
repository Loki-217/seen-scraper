# services/api/app/crawler_sync.py
"""
完全同步的 Crawl4AI 运行器
"""
import sys
import json
from crawl4ai import WebCrawler  # 使用同步版本

def crawl_page(url: str):
    """同步运行爬虫"""
    try:
        # 使用同步版本的 WebCrawler
        crawler = WebCrawler(
            browser_type="chromium",
            headless=True,
            verbose=False
        )
        
        result = crawler.run(
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
        return {
            "success": False,
            "error": str(e)
        }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No URL provided"}))
        sys.exit(1)
    
    url = sys.argv[1]
    result = crawl_page(url)
    print(json.dumps(result, ensure_ascii=False))