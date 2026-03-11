# services/api/app/models_v2/smart.py
"""
智能识别相关数据模型
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """字段类型枚举"""
    TEXT = "text"           # 普通文本
    TITLE = "title"         # 标题
    PRICE = "price"         # 价格
    DATE = "date"           # 日期
    DATETIME = "datetime"   # 日期时间
    EMAIL = "email"         # 邮箱
    PHONE = "phone"         # 电话
    URL = "url"             # 链接
    IMAGE = "image"         # 图片
    RATING = "rating"       # 评分
    NUMBER = "number"       # 数字
    PERCENTAGE = "percentage"  # 百分比


class SuggestedField(BaseModel):
    """建议的字段"""
    name: str = Field(..., description="字段名称")
    selector: str = Field(..., description="CSS选择器（相对于列表项）")
    field_type: FieldType = Field(..., description="字段类型")
    attr: str = Field(default="text", description="提取属性: text, href, src, etc.")
    confidence: float = Field(default=0.8, description="置信度 0-1")
    sample_values: List[str] = Field(default_factory=list, description="示例值")


class DetectedList(BaseModel):
    """检测到的列表"""
    name: str = Field(default="数据列表", description="列表名称")
    container_selector: str = Field(..., description="列表容器选择器")
    item_selector: str = Field(..., description="列表项选择器")
    item_count: int = Field(..., description="检测到的项数")
    confidence: float = Field(..., description="置信度 0-1")
    structure_hash: str = Field(..., description="结构指纹")
    sample_items: List[Dict[str, Any]] = Field(default_factory=list, description="前几项预览数据")
    suggested_fields: List[SuggestedField] = Field(default_factory=list, description="建议的字段")


class InferenceResult(BaseModel):
    """类型推断结果"""
    field_type: FieldType = Field(..., description="推断的字段类型")
    confidence: float = Field(..., description="置信度 0-1")
    extracted_value: Any = Field(default=None, description="提取/格式化后的值")
    suggested_name: str = Field(..., description="建议的字段名")
    extraction_attr: str = Field(default="text", description="提取属性")


class OptimizedSelector(BaseModel):
    """优化后的选择器"""
    selector: str = Field(..., description="推荐选择器")
    stability_score: float = Field(..., description="稳定性评分 0-1")
    specificity: int = Field(default=0, description="CSS特异性")
    match_count: int = Field(..., description="匹配元素数")
    alternatives: List[str] = Field(default_factory=list, description="备选选择器")


class SmartAnalyzeResponse(BaseModel):
    """智能分析响应"""
    success: bool = Field(..., description="是否成功")
    page_type: str = Field(default="unknown", description="页面类型: list, detail, search, article, other")
    confidence: float = Field(default=0.0, description="整体置信度")
    lists: List[DetectedList] = Field(default_factory=list, description="检测到的列表")
    pagination: Optional[Dict[str, Any]] = Field(default=None, description="翻页信息")
    message: str = Field(default="", description="消息")


class ValidateSelectorResponse(BaseModel):
    """选择器验证响应"""
    valid: bool = Field(..., description="是否有效")
    match_count: int = Field(default=0, description="匹配元素数")
    sample_texts: List[str] = Field(default_factory=list, description="示例文本")
