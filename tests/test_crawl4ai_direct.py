# test_crawl4ai_direct.py
import asyncio
from crawl4ai import AsyncWebCrawler

async def test_basic():
    print("Testing basic Crawl4AI...")
    crawler = AsyncWebCrawler(verbose=True)
    await crawler.start()
    
    try:
        result = await crawler.arun(url="https://example.com")
        print(f"Success: {result.success}")
        print(f"Title: {result.metadata.get('title', 'N/A') if hasattr(result, 'metadata') else 'No metadata'}")
        print(f"Word count: {result.word_count if hasattr(result, 'word_count') else 'N/A'}")
        print(f"HTML length: {len(result.html) if hasattr(result, 'html') else 0}")
    finally:
        await crawler.close()

if __name__ == "__main__":
    asyncio.run(test_basic())