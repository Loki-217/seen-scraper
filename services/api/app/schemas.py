# services/api/app/schemas.py
from __future__ import annotations

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


# -------- Job / Selector 输入输出 --------
class PagerConf(BaseModel):
    """翻页配置（简单版，与 models 中的 3 个列相对应）"""
    selector: Optional[str] = None
    attr: str = "href"
    max_pages: int = 1


class SelectorIn(BaseModel):
    name: str
    css: str
    attr: str = "text"
    limit: int = 10
    required: bool = False
    regex: Optional[str] = None
    order_no: int = 0


class SelectorOut(SelectorIn):
    id: int
    model_config = ConfigDict(from_attributes=True)


class JobBase(BaseModel):
    name: str
    start_url: str
    status: str = "active"
    description: Optional[str] = ""
    pager: PagerConf = Field(default_factory=PagerConf)
    selectors: List[SelectorIn] = Field(default_factory=list)


class JobCreate(JobBase):
    """创建 Job 的载体（与路由 /jobs 对应）"""
    pass


class JobOut(BaseModel):
    """返回 Job 时的结构（含 selectors）"""
    id: int
    name: str
    start_url: str
    description: Optional[str] = ""
    status: str
    pager_selector: Optional[str] = None
    pager_attr: Optional[str] = None
    max_pages: int = 1
    selectors: List[SelectorOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# -------- 预览/运行 公共请求体 --------
class JobPreviewReq(BaseModel):
    url: str
    limit: int = 10


class JobPreviewResp(BaseModel):
    url: str
    samples: Dict[str, List[str]]


# -------- Run 输出 --------
class RunOut(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    # stats_json 会被解析成 dict 返回
    stats: Optional[Dict[str, Any]] = None
