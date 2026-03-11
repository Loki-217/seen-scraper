# services/api/app/routers/browser.py
"""
V2 Session API 路由

端点：
- POST   /sessions                    创建会话
- POST   /sessions/{id}/actions       执行操作
- GET    /sessions/{id}/state         获取状态
- DELETE /sessions/{id}               关闭会话
- GET    /sessions                    列表所有会话
- POST   /sessions/{id}/detect-pagination  检测翻页方式
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional, List

from ..session_manager import session_manager
from ..models_v2.actions import (
    Action,
    ActionResult,
    CreateSessionRequest,
    CreateSessionResponse,
    SessionState,
)
from ..models_v2.pagination import (
    PaginationConfig,
    DetectedPagination,
    PaginationDetectResponse,
)
from ..services.pagination_detector import PaginationDetector

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse, summary="创建浏览器会话")
async def create_session(req: CreateSessionRequest):
    """
    创建新的浏览器会话

    - 加载指定 URL
    - 返回页面截图和可交互元素列表
    - 会话 30 分钟未活动自动过期

    **请求示例:**
    ```json
    {
        "url": "https://movie.douban.com/top250",
        "viewport_width": 1280,
        "viewport_height": 800
    }
    ```
    """
    try:
        result = await session_manager.create_session(
            url=req.url,
            viewport_width=req.viewport_width,
            viewport_height=req.viewport_height,
            wait_for=req.wait_for,
            timeout_ms=req.timeout_ms
        )
        return result
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建会话失败: {str(e)}"
        )


@router.post("/{session_id}/actions", response_model=ActionResult, summary="执行操作")
async def execute_action(session_id: str, action: Action):
    """
    在指定会话中执行操作

    **操作类型:**
    - `click`: 点击 - 提供 x/y 坐标或 selector
    - `scroll`: 滚动 - 提供 direction (up/down/left/right) 和 distance
    - `input`: 输入 - 提供 selector 和 text
    - `wait`: 等待 - 提供 wait_ms 或 wait_selector
    - `hover`: 悬停 - 提供 x/y 或 selector
    - `navigate`: 导航 - 提供 url

    **示例 - 点击操作:**
    ```json
    {
        "type": "click",
        "x": 100,
        "y": 200
    }
    ```

    **示例 - 滚动操作:**
    ```json
    {
        "type": "scroll",
        "direction": "down",
        "distance": 500
    }
    ```
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {session_id}"
        )

    if session.is_expired():
        await session_manager.close_session(session_id)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="会话已过期，请重新创建"
        )

    result = await session_manager.execute_action(session_id, action)
    return result


@router.get("/{session_id}/state", response_model=SessionState, summary="获取会话状态")
async def get_session_state(session_id: str):
    """
    获取当前会话状态

    返回：
    - 当前页面 URL
    - 页面标题
    - 页面截图
    - 可交互元素列表
    """
    state = await session_manager.get_state(session_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {session_id}"
        )
    return state


@router.delete("/{session_id}", summary="关闭会话")
async def close_session(session_id: str):
    """
    关闭会话，释放资源

    建议在完成操作后主动关闭会话，避免资源占用。
    """
    success = await session_manager.close_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {session_id}"
        )
    return {"success": True, "message": "会话已关闭"}


@router.get("", summary="列出所有会话")
async def list_sessions():
    """
    列出所有活跃会话的统计信息

    用于调试和监控。
    """
    return session_manager.get_stats()


# 额外的辅助端点
@router.post("/{session_id}/screenshot", summary="仅获取截图")
async def get_screenshot(session_id: str, quality: int = 80):
    """
    获取当前页面截图

    参数:
    - quality: JPEG 质量 (1-100)，默认 80
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {session_id}"
        )

    screenshot = await session.screenshot(quality=quality)
    return {
        "screenshot": screenshot,
        "url": session.page.url
    }


@router.post("/{session_id}/elements", summary="仅获取元素")
async def get_elements(session_id: str):
    """
    获取当前页面可交互元素列表
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {session_id}"
        )

    elements = await session.get_elements()
    return {
        "elements": elements,
        "count": len(elements),
        "url": session.page.url
    }


@router.post("/{session_id}/detect-pagination", response_model=PaginationDetectResponse, summary="检测翻页方式")
async def detect_pagination(session_id: str):
    """
    智能检测页面的翻页方式

    返回检测到的所有翻页方式及推荐配置。

    **支持的翻页类型:**
    - `click_next`: 点击"下一页"按钮
    - `load_more`: 点击"加载更多"按钮
    - `infinite_scroll`: 无限滚动加载
    - `url_pattern`: URL 参数翻页

    **示例响应:**
    ```json
    {
        "success": true,
        "detected": [
            {
                "type": "click_next",
                "config": {...},
                "confidence": 0.95,
                "evidence": "找到下一页按钮: '下一页'"
            }
        ],
        "recommended": {...}
    }
    ```
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {session_id}"
        )

    try:
        detector = PaginationDetector()
        detected = await detector.detect(session.page)

        return PaginationDetectResponse(
            success=True,
            detected=detected,
            recommended=detected[0].config if detected else None,
            message=f"检测到 {len(detected)} 种翻页方式" if detected else "未检测到翻页方式"
        )

    except Exception as e:
        return PaginationDetectResponse(
            success=False,
            detected=[],
            recommended=None,
            message=f"检测失败: {str(e)}"
        )


@router.post("/{session_id}/test-pagination", summary="测试翻页")
async def test_pagination(session_id: str, config: PaginationConfig):
    """
    测试翻页配置是否有效

    执行一次翻页操作并返回结果。
    """
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {session_id}"
        )

    from ..services.pagination_executor import PaginationExecutor

    try:
        executor = PaginationExecutor(session.page, config)

        # 检查是否有下一页
        has_next = await executor.has_next_page()
        if not has_next:
            return {
                "success": False,
                "message": "没有找到下一页",
                "has_next": False
            }

        # 获取当前 URL
        old_url = session.page.url

        # 执行翻页
        success = await executor.go_to_next_page()

        # 获取新状态
        new_url = session.page.url
        screenshot = await session.screenshot()

        return {
            "success": success,
            "message": "翻页成功" if success else "翻页失败",
            "has_next": has_next,
            "old_url": old_url,
            "new_url": new_url,
            "url_changed": old_url != new_url,
            "screenshot": screenshot
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"测试失败: {str(e)}",
            "has_next": False
        }
