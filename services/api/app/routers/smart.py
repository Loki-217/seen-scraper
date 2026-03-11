# services/api/app/routers/smart.py
"""
智能识别 API 路由

端点：
- POST /smart/analyze          智能分析页面结构
- POST /smart/validate-selector 验证选择器
- POST /smart/detect-lists      仅检测列表
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from ..session_manager import session_manager
from ..models_v2.smart import (
    SmartAnalyzeResponse,
    ValidateSelectorResponse,
    DetectedList,
    SuggestedField,
    FieldType,
)
from ..services.list_detector import ListDetector
from ..services.pagination_detector import PaginationDetector
from ..ai_service import ai_service


router = APIRouter(prefix="/smart", tags=["smart"])

# 明确的字段类型，不需要 AI 优化
CLEAR_FIELD_TYPES = {
    FieldType.TITLE,
    FieldType.IMAGE,
    FieldType.URL,
    FieldType.PRICE,
    FieldType.RATING,
    FieldType.DATE,
    FieldType.DATETIME,
    FieldType.EMAIL,
    FieldType.PHONE,
}


async def enhance_field_names_with_ai(detected_lists: List[DetectedList]) -> List[DetectedList]:
    """
    使用 AI 优化不明确字段的命名

    规则：
    - 明确类型（标题、图片、链接、价格、评分、日期等）保持原名
    - 不明确类型（text, number, container 等）调用 AI 优化
    """
    for lst in detected_lists:
        for field in lst.suggested_fields:
            # 明确类型，跳过
            if field.field_type in CLEAR_FIELD_TYPES:
                continue

            # 置信度高的也跳过
            if field.confidence >= 0.85:
                continue

            # 调用 AI 优化命名
            try:
                element_info = {
                    'text': field.sample_values[0] if field.sample_values else '',
                    'tagName': '',  # 可从 selector 推断
                    'className': field.selector if '.' in field.selector else '',
                    'id': field.selector[1:] if field.selector.startswith('#') else '',
                }

                result = ai_service.suggest_field_name(element_info, {})

                # AI 返回的名称置信度更高时采用
                if result.get('confidence', 0) > field.confidence:
                    field.name = result.get('fieldName', field.name)
                    field.confidence = min(result.get('confidence', 0.8), 0.95)

            except Exception as e:
                # AI 调用失败，保持原名
                print(f"[Smart] AI naming failed for {field.selector}: {e}")
                continue

    return detected_lists


class AnalyzeRequest(BaseModel):
    """分析请求"""
    session_id: str = Field(..., description="会话ID")


class ValidateSelectorRequest(BaseModel):
    """选择器验证请求"""
    session_id: str = Field(..., description="会话ID")
    selector: str = Field(..., description="CSS选择器")
    expected_count: Optional[int] = Field(None, description="期望匹配数")


@router.post("/analyze", response_model=SmartAnalyzeResponse, summary="智能分析页面")
async def analyze_page(req: AnalyzeRequest):
    """
    智能分析页面结构

    返回:
    - 页面类型（列表页/详情页/搜索页等）
    - 检测到的数据列表
    - 建议的字段配置
    - 翻页信息

    **示例响应:**
    ```json
    {
        "success": true,
        "page_type": "list",
        "confidence": 0.95,
        "lists": [
            {
                "name": "电影列表",
                "container_selector": ".grid_view",
                "item_selector": ".grid_view > li",
                "item_count": 25,
                "suggested_fields": [...]
            }
        ],
        "pagination": {
            "type": "click_next",
            "selector": "a.next"
        }
    }
    ```
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {req.session_id}"
        )

    try:
        # 检测列表结构
        list_detector = ListDetector()
        detected_lists = await list_detector.detect_lists(session.page)

        # 使用 AI 优化不明确字段的命名
        if detected_lists:
            detected_lists = await enhance_field_names_with_ai(detected_lists)

        # 检测翻页
        pagination_detector = PaginationDetector()
        pagination_results = await pagination_detector.detect(session.page)

        pagination_info = None
        if pagination_results:
            best = pagination_results[0]
            pagination_info = {
                "detected": True,
                "type": best.type.value,
                "confidence": best.confidence,
                "config": best.config.model_dump()
            }

        # 推断页面类型
        if detected_lists:
            page_type = "list"
            confidence = detected_lists[0].confidence
        elif pagination_info:
            page_type = "list"
            confidence = 0.7
        else:
            page_type = "detail"
            confidence = 0.6

        return SmartAnalyzeResponse(
            success=True,
            page_type=page_type,
            confidence=confidence,
            lists=detected_lists,
            pagination=pagination_info,
            message=f"检测到 {len(detected_lists)} 个列表" if detected_lists else "未检测到列表结构"
        )

    except Exception as e:
        return SmartAnalyzeResponse(
            success=False,
            page_type="unknown",
            confidence=0,
            lists=[],
            pagination=None,
            message=f"分析失败: {str(e)}"
        )


@router.post("/validate-selector", response_model=ValidateSelectorResponse, summary="验证选择器")
async def validate_selector(req: ValidateSelectorRequest):
    """
    验证 CSS 选择器是否有效

    返回选择器匹配的元素数量和示例文本。
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {req.session_id}"
        )

    try:
        # 在页面中验证选择器
        result = await session.page.evaluate(f'''
            (selector) => {{
                try {{
                    const elements = document.querySelectorAll(selector);
                    const count = elements.length;
                    const samples = Array.from(elements).slice(0, 5).map(el => {{
                        return (el.textContent || '').trim().substring(0, 100);
                    }}).filter(t => t);
                    return {{ valid: count > 0, count, samples }};
                }} catch(e) {{
                    return {{ valid: false, count: 0, samples: [], error: e.message }};
                }}
            }}
        ''', req.selector)

        valid = result['valid']
        if req.expected_count is not None:
            valid = result['count'] == req.expected_count

        return ValidateSelectorResponse(
            valid=valid,
            match_count=result['count'],
            sample_texts=result['samples']
        )

    except Exception as e:
        return ValidateSelectorResponse(
            valid=False,
            match_count=0,
            sample_texts=[]
        )


@router.post("/detect-lists", summary="仅检测列表")
async def detect_lists(req: AnalyzeRequest):
    """
    仅检测页面中的列表结构

    比完整分析更快，只返回列表信息。
    """
    session = session_manager.get_session(req.session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {req.session_id}"
        )

    try:
        detector = ListDetector()
        lists = await detector.detect_lists(session.page)

        return {
            "success": True,
            "count": len(lists),
            "lists": [lst.model_dump() for lst in lists]
        }

    except Exception as e:
        return {
            "success": False,
            "count": 0,
            "lists": [],
            "error": str(e)
        }


@router.post("/extract-preview", summary="预览数据提取")
async def extract_preview(session_id: str, config: Dict[str, Any]):
    """
    根据配置预览数据提取结果

    **请求示例:**
    ```json
    {
        "container_selector": ".grid_view",
        "item_selector": ".grid_view > li",
        "fields": [
            {"name": "标题", "selector": "span.title", "attr": "text"},
            {"name": "图片", "selector": "img", "attr": "src"}
        ]
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
        item_selector = config.get('item_selector', '')
        fields = config.get('fields', [])

        if not item_selector or not fields:
            return {
                "success": False,
                "error": "缺少 item_selector 或 fields 配置",
                "data": []
            }

        # 在页面中执行提取
        data = await session.page.evaluate('''
            ({itemSelector, fields}) => {
                const items = document.querySelectorAll(itemSelector);
                const results = [];

                for (let i = 0; i < Math.min(items.length, 10); i++) {
                    const item = items[i];
                    const row = {};

                    for (const field of fields) {
                        const el = item.querySelector(field.selector);
                        if (el) {
                            if (field.attr === 'text') {
                                row[field.name] = (el.textContent || '').trim();
                            } else if (field.attr === 'href') {
                                row[field.name] = el.href || '';
                            } else if (field.attr === 'src') {
                                row[field.name] = el.src || el.dataset.src || '';
                            } else {
                                row[field.name] = el.getAttribute(field.attr) || '';
                            }
                        } else {
                            row[field.name] = null;
                        }
                    }

                    results.push(row);
                }

                return results;
            }
        ''', {'itemSelector': item_selector, 'fields': fields})

        return {
            "success": True,
            "count": len(data),
            "data": data
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": []
        }
