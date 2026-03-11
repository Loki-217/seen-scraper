# services/api/app/models/pagination.py
"""翻页配置数据模型"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PaginationType(str, Enum):
    """翻页类型枚举"""
    NONE = "none"                      # 不翻页
    CLICK_NEXT = "click_next"          # 点击"下一页"按钮
    CLICK_NUMBER = "click_number"      # 点击页码
    INFINITE_SCROLL = "infinite_scroll" # 无限滚动加载
    LOAD_MORE = "load_more"            # 点击"加载更多"按钮
    URL_PATTERN = "url_pattern"        # URL 参数变化


class PaginationConfig(BaseModel):
    """翻页配置"""
    type: PaginationType = Field(PaginationType.NONE, description="翻页类型")

    # 点击类翻页
    next_button_selector: Optional[str] = Field(
        None,
        description="下一页按钮选择器 (CLICK_NEXT/LOAD_MORE)"
    )
    page_number_selector: Optional[str] = Field(
        None,
        description="页码选择器 (CLICK_NUMBER)"
    )

    # 滚动类翻页
    scroll_container: Optional[str] = Field(
        None,
        description="滚动容器选择器（默认 window）"
    )
    scroll_wait_ms: int = Field(
        2000,
        ge=500,
        le=10000,
        description="滚动后等待时间(毫秒)"
    )

    # URL 翻页
    url_pattern: Optional[str] = Field(
        None,
        description="URL 模式，如 '?page={n}' 或 '&offset={n}'"
    )
    start_page: int = Field(1, ge=0, description="起始页码")
    page_step: int = Field(1, ge=1, description="页码步进")

    # 通用配置
    max_pages: int = Field(10, ge=1, le=1000, description="最大页数")
    stop_condition: Optional[str] = Field(
        None,
        description="停止条件选择器（元素出现时停止）"
    )
    stop_text: Optional[str] = Field(
        None,
        description="停止条件文本（按钮文本包含时停止）"
    )

    # 高级配置
    wait_for_selector: Optional[str] = Field(
        None,
        description="翻页后等待元素出现"
    )
    wait_for_network: bool = Field(
        True,
        description="翻页后等待网络空闲"
    )
    dedup_field: Optional[str] = Field(
        None,
        description="去重字段名"
    )


class PaginationResult(BaseModel):
    """翻页执行结果"""
    success: bool = Field(..., description="是否成功")
    pages_scraped: int = Field(0, description="已抓取页数")
    total_items: int = Field(0, description="总数据条数")
    stopped_reason: str = Field(
        "",
        description="停止原因: max_pages/no_more_content/stop_condition/error"
    )
    error: Optional[str] = Field(None, description="错误信息")
    data: List[Dict[str, Any]] = Field(default_factory=list, description="抓取的数据")


class DetectedPagination(BaseModel):
    """检测到的翻页方式"""
    type: PaginationType
    config: PaginationConfig
    confidence: float = Field(..., ge=0, le=1, description="置信度 0-1")
    evidence: str = Field("", description="检测依据")


class PaginationDetectRequest(BaseModel):
    """翻页检测请求"""
    session_id: str = Field(..., description="会话ID")


class PaginationDetectResponse(BaseModel):
    """翻页检测响应"""
    success: bool
    detected: List[DetectedPagination] = Field(default_factory=list)
    recommended: Optional[PaginationConfig] = None
    message: str = ""
