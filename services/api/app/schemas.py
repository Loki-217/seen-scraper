from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field

# ---- Selector ----
class SelectorCreate(BaseModel):
    name: str
    css: str
    attr: str = "text"
    limit: int = 50
    required: bool = False
    regex: Optional[str] = None
    order_no: int = 0

class SelectorOut(SelectorCreate):
    id: int
    class Config:
        from_attributes = True  # Pydantic v2: 允许 ORM 转换


# ---- Job ----
class PagerConfig(BaseModel):
    selector: Optional[str] = None
    attr: str = "href"
    max_pages: int = 1

class JobCreate(BaseModel):
    name: str
    start_url: str
    description: Optional[str] = None
    status: str = "draft"
    pager: PagerConfig = Field(default_factory=PagerConfig)
    selectors: List[SelectorCreate] = Field(default_factory=list)

class JobOut(BaseModel):
    id: int
    name: str
    start_url: str
    description: Optional[str]
    status: str
    pager_selector: Optional[str]
    pager_attr: str
    max_pages: int
    selectors: List[SelectorOut] = Field(default_factory=list)
    class Config:
        from_attributes = True


# ---- Run / Result ----
class RunCreate(BaseModel):
    job_id: int
    status: str = "queued"
    settings_json: Optional[str] = None

class RunOut(BaseModel):
    id: int
    job_id: int
    status: str
    class Config:
        from_attributes = True

class ResultOut(BaseModel):
    id: int
    run_id: int
    field: str
    row_idx: int
    value: Optional[str]
    url: Optional[str]
    class Config:
        from_attributes = True
