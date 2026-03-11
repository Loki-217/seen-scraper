# services/api/app/models/actions.py
"""V2 操作类型定义"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """操作类型枚举"""
    CLICK = "click"
    SCROLL = "scroll"
    INPUT = "input"
    WAIT = "wait"
    SCREENSHOT = "screenshot"
    EXTRACT = "extract"
    HOVER = "hover"
    NAVIGATE = "navigate"


class Action(BaseModel):
    """用户操作定义"""
    type: ActionType = Field(..., description="操作类型")

    # 点击/悬停操作 - 坐标或选择器
    x: Optional[int] = Field(None, description="点击X坐标")
    y: Optional[int] = Field(None, description="点击Y坐标")
    selector: Optional[str] = Field(None, description="目标元素CSS选择器")

    # 滚动操作
    direction: Optional[str] = Field(None, description="滚动方向: up/down/left/right")
    distance: Optional[int] = Field(None, description="滚动距离(像素)")

    # 输入操作
    text: Optional[str] = Field(None, description="输入文本")
    clear_first: Optional[bool] = Field(True, description="输入前是否清空")

    # 等待操作
    wait_ms: Optional[int] = Field(None, description="等待毫秒数")
    wait_selector: Optional[str] = Field(None, description="等待元素出现")

    # 导航操作
    url: Optional[str] = Field(None, description="导航目标URL")


class InteractiveElement(BaseModel):
    """可交互元素信息"""
    selector: str = Field(..., description="CSS选择器")
    rect: Dict[str, float] = Field(..., description="元素位置 {x, y, width, height}")
    tag: str = Field(..., description="HTML标签名")
    text: str = Field("", description="元素文本(前50字符)")
    element_type: str = Field(..., description="元素类型: link/button/input/image/text")

    # 额外属性
    href: Optional[str] = Field(None, description="链接地址")
    src: Optional[str] = Field(None, description="图片/媒体地址")
    placeholder: Optional[str] = Field(None, description="输入框占位符")
    value: Optional[str] = Field(None, description="输入框当前值")


class PageInfo(BaseModel):
    """页面信息"""
    url: str = Field(..., description="当前页面URL")
    title: str = Field(..., description="页面标题")
    viewport: Dict[str, int] = Field(default_factory=lambda: {"width": 1280, "height": 800})


class ActionResult(BaseModel):
    """操作执行结果"""
    success: bool = Field(..., description="是否成功")
    screenshot_base64: str = Field("", description="页面截图(Base64 JPEG)")
    url: str = Field("", description="当前页面URL")
    title: str = Field("", description="页面标题")
    elements: List[InteractiveElement] = Field(default_factory=list, description="可交互元素列表")
    error: Optional[str] = Field(None, description="错误信息")
    action_type: Optional[str] = Field(None, description="执行的操作类型")


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    url: str = Field(..., description="目标页面URL")
    viewport_width: int = Field(1280, ge=800, le=1920, description="视口宽度")
    viewport_height: int = Field(800, ge=600, le=1080, description="视口高度")
    wait_for: Optional[str] = Field(None, description="等待的选择器")
    timeout_ms: int = Field(30000, ge=5000, le=60000, description="加载超时(毫秒)")


class CreateSessionResponse(BaseModel):
    """创建会话响应"""
    session_id: str = Field(..., description="会话ID")
    screenshot: str = Field(..., description="页面截图(Base64)")
    elements: List[InteractiveElement] = Field(default_factory=list)
    page_info: PageInfo = Field(..., description="页面信息")


class SessionState(BaseModel):
    """会话状态"""
    session_id: str
    url: str
    title: str
    screenshot: str
    elements: List[InteractiveElement] = Field(default_factory=list)
    created_at: str
    last_active: str
    is_active: bool = True
