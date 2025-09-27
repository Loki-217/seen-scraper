# test_smart_extractor.py
import asyncio
from services.api.app.smart_extractor import SmartExtractor

async def test():
    extractor = SmartExtractor()
    result = await extractor.analyze_page("https://example.com")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    import json
    asyncio.run(test())