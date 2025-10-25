from __future__ import annotations

from typing import Optional, List, Dict
from datetime import datetime
import json

from pydantic import BaseModel, Field, ConfigDict, field_validator, field_serializer


# -----------------------------
# 选择器（Selector）
# -----------------------------
class SelectorIn(BaseModel):
    """创建/更新 Job 时提交的选择器配置。"""
    name: str = Field(..., description="字段名，如 title、link")
    css: str = Field(..., description="CSS 选择器")
    attr: str = Field("text", description="提取 text 或属性名（href/src/...）")
    limit: int = Field(20, ge=1, le=200, description="最多提取条数")
    required: bool = Field(False, description="是否必填（可用于后续校验）")
    regex: Optional[str] = Field(None, description="可选的正则提取")
    order_no: int = Field(0, ge=0, description="排序，用于执行/展示顺序")


class SelectorOut(SelectorIn):
    """返回给前端时的选择器结构（包含 id）。"""
    id: int
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# 翻页配置（Pager）
# -----------------------------
class PagerConf(BaseModel):
    """翻页配置（映射到 Job 的 pager_selector/pager_attr/max_pages 三列）"""
    selector: Optional[str] = Field(None, description="下一页的 CSS 选择器（为空表示不翻页）")
    attr: str = Field("href", description="翻页链接取值属性，通常为 href")
    max_pages: int = Field(1, ge=1, le=1000, description="最大翻页页数")


# -----------------------------
# Job
# -----------------------------
class JobCreate(BaseModel):
    """新建/更新 Job 的请求体。"""
    name: str = Field(..., description="任务名称，唯一")
    start_url: str = Field(..., description="起始 URL")
    status: str = Field("active", description="任务状态：active / inactive")
    description: Optional[str] = Field("", description="任务描述")
    pager: Optional[PagerConf] = Field(None, description="翻页配置")
    selectors: List[SelectorIn] = Field(default_factory=list, description="字段选择器列表")
    # 🔥 新增：爬虫配置
    config: Optional[Dict] = Field(None, description="爬虫配置（auto_scroll, use_stealth 等）")


class JobOut(BaseModel):
    """返回 Job 详情/列表时使用的结构。"""
    id: int
    name: str
    start_url: str
    description: Optional[str] = ""
    status: str

    # 平铺的 pager 字段
    pager_selector: Optional[str] = None
    pager_attr: Optional[str] = None
    max_pages: Optional[int] = None

    # 🔥 新增：爬虫配置（从 config_json 映射）
    config_json: Optional[str] = None

    selectors: List[SelectorOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @property
    def config(self) -> Optional[Dict]:
        """将 config_json 字符串转换为字典"""
        if self.config_json is None:
            return None
        if isinstance(self.config_json, str):
            try:
                return json.loads(self.config_json)
            except:
                return None
        return None

    @field_serializer('config_json', when_used='json')
    def serialize_config_json(self, config_json: Optional[str], _info) -> Optional[Dict]:
        """序列化时将 config_json 转换为 config 字段"""
        if config_json is None:
            return None
        try:
            return json.loads(config_json)
        except:
            return None


class JobPreviewReq(BaseModel):
    url: str = Field(..., description="要预览的页面 URL")
    limit: int = Field(20, ge=1, le=200, description="每个选择器最多返回多少条样本")
    wait_selector: Optional[str] = Field(
        default=None, description="进入页面后等待的选择器（可选）"
    )
    # 🔧 关键修复：补上 timeout_ms（路由里会用到）
    timeout_ms: int = Field(10000, ge=1000, le=60000, description="超时时间(ms)")


class JobPreviewResp(BaseModel):
    url: str
    samples: Dict[str, List[str]]
    model_config = ConfigDict(from_attributes=True)


# -----------------------------
# Run（运行）
# -----------------------------
class RunStartReq(BaseModel):
    url: str = Field(..., description="本次运行的入口 URL")
    limit: int = Field(20, ge=1, le=200, description="每个字段最大提取条数")


class RunStartResp(BaseModel):
    run_id: int
    status: str  # queued / running / succeeded / failed


class RunOut(BaseModel):
    id: int
    job_id: int
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stats: Optional[Dict] = None

    @field_serializer("started_at", "finished_at")
    def _dt(self, v: Optional[datetime], _info):
        return v and v.isoformat()

    model_config = ConfigDict(from_attributes=True)

    @field_validator("stats", mode="before")
    @classmethod
    def _parse_stats(cls, v):
        # v 已是 dict
        if isinstance(v, dict) or v is None:
            return v
        # SA 对象场景：字段名通常是 stats_json
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return None
