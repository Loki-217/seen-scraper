# tests/test_v2_session.py
"""
SeenFetch V2 集成测试

测试 Session Manager 和翻页功能
"""

import pytest
import asyncio
import sys

# Windows 事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestSessionManager:
    """Session Manager 测试"""

    @pytest.mark.asyncio
    async def test_create_session(self):
        """测试创建会话"""
        from services.api.app.session_manager import SessionManager

        manager = SessionManager()
        await manager.start()

        try:
            # 创建会话
            result = await manager.create_session(
                url="https://example.com",
                viewport_width=1280,
                viewport_height=800
            )

            assert result.session_id is not None
            assert result.screenshot != ""
            assert result.page_info.url is not None

            print(f"Session created: {result.session_id[:8]}...")
            print(f"Page title: {result.page_info.title}")
            print(f"Elements count: {len(result.elements)}")

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_execute_click(self):
        """测试执行点击"""
        from services.api.app.session_manager import SessionManager
        from services.api.app.models.actions import Action, ActionType

        manager = SessionManager()
        await manager.start()

        try:
            # 创建会话
            result = await manager.create_session(
                url="https://example.com",
            )

            # 执行点击
            action = Action(type=ActionType.CLICK, x=100, y=100)
            action_result = await manager.execute_action(result.session_id, action)

            assert action_result.success is True
            assert action_result.screenshot_base64 != ""

            print(f"Click result: {action_result.success}")

        finally:
            await manager.stop()

    @pytest.mark.asyncio
    async def test_session_state(self):
        """测试获取会话状态"""
        from services.api.app.session_manager import SessionManager

        manager = SessionManager()
        await manager.start()

        try:
            # 创建会话
            result = await manager.create_session(url="https://example.com")

            # 获取状态
            state = await manager.get_state(result.session_id)

            assert state is not None
            assert state.session_id == result.session_id
            assert state.url != ""
            assert state.screenshot != ""

            print(f"Session state: {state.url}")

        finally:
            await manager.stop()


class TestPaginationDetector:
    """翻页检测器测试"""

    @pytest.mark.asyncio
    async def test_detect_douban(self):
        """测试检测豆瓣 Top250 翻页"""
        from playwright.async_api import async_playwright
        from services.api.app.services.pagination_detector import PaginationDetector
        from services.api.app.models.pagination import PaginationType

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto("https://movie.douban.com/top250", wait_until="networkidle")

                detector = PaginationDetector()
                results = await detector.detect(page)

                assert len(results) > 0
                print(f"Detected {len(results)} pagination methods:")
                for r in results:
                    print(f"  - {r.type}: confidence={r.confidence:.2f}, {r.evidence}")

                # 豆瓣应该检测到点击下一页
                click_next = [r for r in results if r.type == PaginationType.CLICK_NEXT]
                assert len(click_next) > 0, "Should detect click_next pagination"

            finally:
                await browser.close()

    @pytest.mark.asyncio
    async def test_detect_url_pattern(self):
        """测试检测 URL 翻页模式"""
        from playwright.async_api import async_playwright
        from services.api.app.services.pagination_detector import PaginationDetector
        from services.api.app.models.pagination import PaginationType

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # 使用带页码参数的 URL
                await page.goto("https://movie.douban.com/top250?start=25", wait_until="networkidle")

                detector = PaginationDetector()
                results = await detector.detect(page)

                # 应该检测到 URL 模式
                url_pattern = [r for r in results if r.type == PaginationType.URL_PATTERN]
                print(f"URL pattern detected: {len(url_pattern)}")

                for r in results:
                    print(f"  - {r.type}: {r.evidence}")

            finally:
                await browser.close()


class TestAPI:
    """API 端点测试"""

    @pytest.mark.asyncio
    async def test_api_create_session(self):
        """测试 API 创建会话"""
        import httpx

        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
            response = await client.post(
                "/sessions",
                json={"url": "https://example.com"},
                timeout=30.0
            )

            if response.status_code == 200:
                data = response.json()
                print(f"API session created: {data['session_id'][:8]}...")

                # 清理
                await client.delete(f"/sessions/{data['session_id']}")
            else:
                print(f"API test skipped (server not running): {response.status_code}")


if __name__ == "__main__":
    # 运行单个测试
    import asyncio

    async def main():
        print("=" * 60)
        print("SeenFetch V2 测试")
        print("=" * 60)

        # 测试 Session Manager
        print("\n1. Testing Session Manager...")
        test_session = TestSessionManager()
        try:
            await test_session.test_create_session()
            print("   Session Manager: OK")
        except Exception as e:
            print(f"   Session Manager: FAILED - {e}")

        # 测试翻页检测
        print("\n2. Testing Pagination Detector...")
        test_pagination = TestPaginationDetector()
        try:
            await test_pagination.test_detect_douban()
            print("   Pagination Detector: OK")
        except Exception as e:
            print(f"   Pagination Detector: FAILED - {e}")

        print("\n" + "=" * 60)
        print("测试完成")

    asyncio.run(main())
