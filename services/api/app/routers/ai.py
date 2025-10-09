# services/api/app/routers/ai.py
"""
AI 相关的 API 路由
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict

from ..ai_service import ai_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ElementInfo(BaseModel):
    """元素信息"""
    text: str = Field(..., description="元素文本内容")
    tagName: str = Field(..., description="HTML 标签名")
    className: str = Field(default="", description="CSS 类名")
    id: str = Field(default="", description="元素 ID")
    href: str = Field(default="", description="链接地址")
    src: str = Field(default="", description="图片地址")


class ContextInfo(BaseModel):
    """上下文信息"""
    previousText: str = Field(default="", description="前一个元素的文本")
    parentClassName: str = Field(default="", description="父元素的类名")
    surroundingText: str = Field(default="", description="周围的文本")
    isInList: bool = Field(default=False, description="是否在列表中")
    pageType: str = Field(default="", description="页面类型")


class SuggestFieldNameRequest(BaseModel):
    """请求体"""
    element: ElementInfo
    context: Optional[ContextInfo] = None


class SuggestFieldNameResponse(BaseModel):
    """响应体"""
    success: bool
    fieldName: str
    confidence: float
    source: str  # "rule" | "ai"
    reasoning: str
    ai_error: Optional[str] = None


@router.post("/suggest-field-name", response_model=SuggestFieldNameResponse)
def suggest_field_name(req: SuggestFieldNameRequest):
    """
    智能建议字段名
    
    - 优先使用规则判断（快速、免费）
    - 规则不确定时调用 AI（准确、有成本）
    """
    try:
        element_dict = req.element.dict()
        context_dict = req.context.dict() if req.context else {}
        
        result = ai_service.suggest_field_name(element_dict, context_dict)
        
        return SuggestFieldNameResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "message": "字段名建议失败"
            }
        )


@router.get("/status")
def get_ai_status():
    """获取 AI 服务状态"""
    return {
        "enabled": ai_service.enabled,
        "has_api_key": bool(ai_service.api_key),
        "model": ai_service.endpoint_id,  # 🔥 修复：改为 endpoint_id
        "api_base": ai_service.api_base
    }