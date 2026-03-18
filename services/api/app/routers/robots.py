# services/api/app/routers/robots.py
"""
Robot API 路由 (V2)

端点：
- GET    /robots              列出所有 Robot
- POST   /robots              创建 Robot
- GET    /robots/{id}         获取 Robot 详情
- PUT    /robots/{id}         更新 Robot
- DELETE /robots/{id}         删除 Robot
- POST   /robots/{id}/run     立即执行 Robot
"""

import json
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..db import session_scope
from ..models import RobotDB
from ..models_v2.schedule import (
    Robot,
    Action,
    FieldConfig,
    PaginationConfig,
)
from ..robot_executor import RobotExecutor, save_results_to_file


router = APIRouter(prefix="/robots", tags=["robots"])


# ============ 请求/响应模型 ============

class CreateRobotRequest(BaseModel):
    """创建 Robot 请求"""
    name: str = Field(..., description="Robot 名称")
    description: str = Field("", description="描述")
    origin_url: str = Field(..., description="起始URL")
    actions: List[dict] = Field(default_factory=list, description="操作序列")
    item_selector: str = Field(..., description="列表项选择器")
    fields: List[dict] = Field(default_factory=list, description="字段配置")
    pagination: Optional[dict] = Field(None, description="翻页配置")


class UpdateRobotRequest(BaseModel):
    """更新 Robot 请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    origin_url: Optional[str] = None
    actions: Optional[List[dict]] = None
    item_selector: Optional[str] = None
    fields: Optional[List[dict]] = None
    pagination: Optional[dict] = None


class RobotResponse(BaseModel):
    """Robot 响应"""
    id: str
    name: str
    description: str
    origin_url: str
    actions: List[dict]
    item_selector: str
    fields: List[dict]
    pagination: Optional[dict]
    created_at: datetime
    updated_at: datetime
    last_run_at: Optional[datetime]
    run_count: int


class RobotListResponse(BaseModel):
    """Robot 列表响应"""
    total: int
    items: List[RobotResponse]


class RunRobotResponse(BaseModel):
    """执行 Robot 响应"""
    success: bool
    pages_scraped: int
    items_extracted: int
    duration_seconds: float
    result_file: Optional[str]
    error: Optional[str]
    items: Optional[List[dict]] = None


# ============ 辅助函数 ============

def db_to_response(robot_db: RobotDB) -> RobotResponse:
    """将数据库模型转换为响应模型"""
    actions = json.loads(robot_db.actions_json) if robot_db.actions_json else []
    fields = json.loads(robot_db.fields_json) if robot_db.fields_json else []
    pagination = json.loads(robot_db.pagination_json) if robot_db.pagination_json else None

    return RobotResponse(
        id=robot_db.id,
        name=robot_db.name,
        description=robot_db.description,
        origin_url=robot_db.origin_url,
        actions=actions,
        item_selector=robot_db.item_selector,
        fields=fields,
        pagination=pagination,
        created_at=robot_db.created_at,
        updated_at=robot_db.updated_at,
        last_run_at=robot_db.last_run_at,
        run_count=robot_db.run_count,
    )


def db_to_robot(robot_db: RobotDB) -> Robot:
    """将数据库模型转换为 Robot 模型"""
    actions = []
    if robot_db.actions_json:
        actions_data = json.loads(robot_db.actions_json)
        actions = [Action(**a) for a in actions_data]

    fields = []
    if robot_db.fields_json:
        fields_data = json.loads(robot_db.fields_json)
        fields = [FieldConfig(**f) for f in fields_data]

    pagination = None
    if robot_db.pagination_json:
        pagination_data = json.loads(robot_db.pagination_json)
        pagination = PaginationConfig(**pagination_data)

    return Robot(
        id=robot_db.id,
        name=robot_db.name,
        description=robot_db.description,
        origin_url=robot_db.origin_url,
        actions=actions,
        item_selector=robot_db.item_selector,
        fields=fields,
        pagination=pagination,
        created_at=robot_db.created_at,
        updated_at=robot_db.updated_at,
        last_run_at=robot_db.last_run_at,
        run_count=robot_db.run_count,
    )


# ============ API 端点 ============

@router.get("", response_model=RobotListResponse, summary="列出所有 Robot")
def list_robots(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取 Robot 列表"""
    with session_scope() as s:
        # 统计总数
        total_stmt = select(RobotDB)
        total = len(s.execute(total_stmt).scalars().all())

        # 分页查询
        stmt = select(RobotDB).offset(offset).limit(limit).order_by(RobotDB.updated_at.desc())
        robots = s.execute(stmt).scalars().all()

        return RobotListResponse(
            total=total,
            items=[db_to_response(r) for r in robots]
        )


@router.post("", response_model=RobotResponse, status_code=status.HTTP_201_CREATED, summary="创建 Robot")
def create_robot(req: CreateRobotRequest):
    """创建新的 Robot"""
    with session_scope() as s:
        robot_db = RobotDB(
            id=str(uuid.uuid4()),
            name=req.name,
            description=req.description,
            origin_url=req.origin_url,
            actions_json=json.dumps(req.actions, ensure_ascii=False) if req.actions else None,
            item_selector=req.item_selector,
            fields_json=json.dumps(req.fields, ensure_ascii=False) if req.fields else None,
            pagination_json=json.dumps(req.pagination, ensure_ascii=False) if req.pagination else None,
        )
        print(f"[DEBUG] create_robot item_selector: {req.item_selector}")
        print(f"[DEBUG] create_robot fields: {req.fields}")
        print(f"[DEBUG] create_robot pagination: {req.pagination}")
        s.add(robot_db)
        s.commit()
        s.refresh(robot_db)

        return db_to_response(robot_db)


@router.get("/{robot_id}", response_model=RobotResponse, summary="获取 Robot 详情")
def get_robot(robot_id: str):
    """获取 Robot 详情"""
    with session_scope() as s:
        robot_db = s.get(RobotDB, robot_id)
        if not robot_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Robot 不存在: {robot_id}"
            )
        return db_to_response(robot_db)


@router.put("/{robot_id}", response_model=RobotResponse, summary="更新 Robot")
def update_robot(robot_id: str, req: UpdateRobotRequest):
    """更新 Robot 配置"""
    with session_scope() as s:
        robot_db = s.get(RobotDB, robot_id)
        if not robot_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Robot 不存在: {robot_id}"
            )

        # 更新字段
        if req.name is not None:
            robot_db.name = req.name
        if req.description is not None:
            robot_db.description = req.description
        if req.origin_url is not None:
            robot_db.origin_url = req.origin_url
        if req.actions is not None:
            robot_db.actions_json = json.dumps(req.actions, ensure_ascii=False)
        if req.item_selector is not None:
            robot_db.item_selector = req.item_selector
        if req.fields is not None:
            robot_db.fields_json = json.dumps(req.fields, ensure_ascii=False)
        if req.pagination is not None:
            robot_db.pagination_json = json.dumps(req.pagination, ensure_ascii=False)

        robot_db.updated_at = datetime.utcnow()
        s.commit()
        s.refresh(robot_db)

        return db_to_response(robot_db)


@router.delete("/{robot_id}", summary="删除 Robot")
def delete_robot(robot_id: str):
    """删除 Robot"""
    with session_scope() as s:
        robot_db = s.get(RobotDB, robot_id)
        if not robot_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Robot 不存在: {robot_id}"
            )

        s.delete(robot_db)
        s.commit()

        return {"ok": True, "message": f"Robot {robot_id} 已删除"}


@router.post("/{robot_id}/run", response_model=RunRobotResponse, summary="立即执行 Robot")
async def run_robot(robot_id: str):
    """立即执行 Robot（不通过调度）"""
    with session_scope() as s:
        robot_db = s.get(RobotDB, robot_id)
        if not robot_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Robot 不存在: {robot_id}"
            )

        robot = db_to_robot(robot_db)

    # 执行
    executor = RobotExecutor(robot)
    result = await executor.execute()

    # 保存结果
    result_file = None
    if result.success and result.items:
        try:
            result_file = await save_results_to_file(result.items, robot.name)
        except Exception as e:
            print(f"[Robot] 保存结果失败: {e}")

    # 更新统计
    with session_scope() as s:
        robot_db = s.get(RobotDB, robot_id)
        if robot_db:
            robot_db.last_run_at = datetime.utcnow()
            robot_db.run_count += 1
            s.commit()

    return RunRobotResponse(
        success=result.success,
        pages_scraped=result.pages_scraped,
        items_extracted=len(result.items),
        duration_seconds=result.duration_seconds,
        result_file=result_file,
        error=result.error,
        items=result.items if result.success else None,
    )
