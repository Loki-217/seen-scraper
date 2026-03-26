# services/api/app/routers/smart.py
"""
智能识别 API 路由

端点：
- POST /smart/analyze          智能分析页面结构
- POST /smart/validate-selector 验证选择器
- POST /smart/detect-lists      仅检测列表
- POST /smart/analyze-fields    AI 智能分析字段
"""

import json
import re

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


# ============ AI 智能分析字段 ============

class RawItemDataRequest(BaseModel):
    """AI 字段分析请求"""
    rawItemData: Dict[str, Any] = Field(..., description="列表项原始数据 {texts, links, images}")


class AnalyzedField(BaseModel):
    """AI 分析后的字段"""
    name: str
    selector: str
    attr: str
    captureType: str = "list"


class AnalyzeFieldsResponse(BaseModel):
    """AI 字段分析响应"""
    fields: List[AnalyzedField] = Field(default_factory=list)
    aiEnhanced: bool = False


def _build_analyze_fields_prompt(raw: Dict[str, Any]) -> str:
    """构建 AI 分析 prompt"""
    texts_desc = ""
    for t in raw.get("texts", [])[:20]:
        texts_desc += f"  [{t['index']}] tag=<{t.get('tag', '?')}> text=\"{t['text']}\"\n"

    links_desc = ""
    for l in raw.get("links", [])[:10]:
        links_desc += f"  [{l['index']}] href=\"{l['href']}\" text=\"{l['text']}\"\n"

    images_desc = ""
    for img in raw.get("images", [])[:10]:
        images_desc += f"  [{img['index']}] src=\"{img['src']}\" alt=\"{img['alt']}\"\n"

    return f"""You are a web data extraction expert. Below is raw data extracted from one item in a webpage list.

## Texts (text content of elements):
{texts_desc or '  (none)'}

## Links (<a> elements):
{links_desc or '  (none)'}

## Images (<img> elements):
{images_desc or '  (none)'}

## Task:
1. Analyze the semantic meaning of each data fragment above.
2. Filter out worthless fragments (whitespace, decorative icons, navigation boilerplate, duplicate content that is a parent containing child text).
3. For each valuable fragment, assign a concise human-readable field name. Use the content's own language (Chinese names for Chinese content, English for English).
4. Return ONLY a JSON array, no extra text.

## Output format:
[
  {{"name": "field name", "source_type": "texts|links|images", "source_index": 0, "data_type": "text|link|image"}}
]

## Critical rules for source selection:
- For human-readable text fields (names, titles, descriptions, ratings, dates, prices), ALWAYS use source_type="texts" with data_type="text". The texts array has more precise selectors pointing to specific text nodes.
- Only use source_type="links" with data_type="link" when the field's VALUE is a URL (e.g. a detail page link, a profile link). The extracted value will be the href URL, NOT the link text.
- Only use source_type="images" with data_type="image" when the field's VALUE is an image URL.
- If the same text appears in both texts and links arrays, use the texts entry (its selector is more precise).
- When a link element contains useful text AND a useful URL, create TWO separate fields: one from texts (for the text content) and one from links (for the URL).

## Other rules:
- Field names should be 2-6 characters, clear and descriptive.
- If a text fragment is just a subset of a longer text already selected, skip the longer one (keep the more specific element).
- Skip pure numbers that look like rankings (e.g. "1", "2", "3").
- Return at most 10 fields.
- Return ONLY the JSON array."""


def _find_by_index(items: List[Dict], index: int) -> Optional[Dict]:
    """Find item in rawItemData array by index field"""
    for item in items:
        if item.get("index") == index:
            return item
    return None


def _find_text_with_same_content(texts: List[Dict], link_text: str) -> Optional[Dict]:
    """Find a texts entry whose text matches a link's text content"""
    if not link_text:
        return None
    link_text_clean = link_text.strip()
    for t in texts:
        t_text = (t.get("text") or "").strip()
        if t_text and t.get("selector") and (t_text == link_text_clean or link_text_clean in t_text):
            return t
    return None


def _map_ai_result_to_fields(ai_fields: List[Dict], raw: Dict[str, Any]) -> List[AnalyzedField]:
    """Map AI analysis result back to selectors from rawItemData"""
    result = []
    seen_selectors = set()
    texts = raw.get("texts", [])

    for af in ai_fields:
        source_type = af.get("source_type", "")
        source_index = af.get("source_index", -1)
        data_type = af.get("data_type", "text")
        name = af.get("name", "")

        if not name or source_type not in ("texts", "links", "images"):
            continue

        items = raw.get(source_type, [])
        source_item = _find_by_index(items, source_index)

        if not source_item:
            continue

        # Fix: if AI says links but data_type is text, redirect to texts array
        if source_type == "links" and data_type == "text":
            link_text = (source_item.get("text") or "").strip()
            text_match = _find_text_with_same_content(texts, link_text)
            if text_match and text_match.get("selector"):
                source_item = text_match
                source_type = "texts"

        selector = source_item.get("selector", "")
        if not selector or selector in seen_selectors:
            continue

        # Determine attr based on source_type + data_type
        if source_type == "links" and data_type == "link":
            attr = "href"
        elif source_type == "images" and data_type == "image":
            attr = "src"
        else:
            attr = "text"

        seen_selectors.add(selector)
        result.append(AnalyzedField(
            name=name,
            selector=selector,
            attr=attr,
            captureType="list"
        ))

    return result


def _fallback_fields_from_raw(raw: Dict[str, Any]) -> List[AnalyzedField]:
    """Fallback: generate basic fields from rawItemData without AI"""
    fields = []
    seen = set()

    # First meaningful text → title (skip pure numbers, single chars)
    texts = raw.get("texts", [])
    title_item = None
    for t in texts:
        text_val = (t.get("text") or "").strip()
        sel = t.get("selector", "")
        if not sel or not text_val:
            continue
        # Skip pure numbers (e.g. rankings like "1", "2", "3")
        if re.match(r'^\d+\.?$', text_val):
            continue
        # Skip very short text (single char)
        if len(text_val) <= 1:
            continue
        title_item = t
        break

    if title_item:
        fields.append(AnalyzedField(name="title", selector=title_item["selector"], attr="text"))
        seen.add(title_item["selector"])

    # First link → url
    links = raw.get("links", [])
    if links and links[0].get("selector") and links[0]["selector"] not in seen:
        fields.append(AnalyzedField(name="url", selector=links[0]["selector"], attr="href"))
        seen.add(links[0]["selector"])

    # First image → image
    images = raw.get("images", [])
    if images and images[0].get("selector") and images[0]["selector"] not in seen:
        fields.append(AnalyzedField(name="image", selector=images[0]["selector"], attr="src"))
        seen.add(images[0]["selector"])

    # Add more text fields beyond title (skip duplicates of title)
    extra_count = 0
    for t in texts:
        if extra_count >= 3:
            break
        sel = t.get("selector", "")
        text_val = (t.get("text") or "").strip()
        if not sel or sel in seen or not text_val:
            continue
        if re.match(r'^\d+\.?$', text_val) or len(text_val) <= 1:
            continue
        fields.append(AnalyzedField(name=f"field_{extra_count + 1}", selector=sel, attr="text"))
        seen.add(sel)
        extra_count += 1

    return fields


@router.post("/analyze-fields", response_model=AnalyzeFieldsResponse, summary="AI 智能分析字段")
async def analyze_fields(req: RawItemDataRequest):
    """
    使用 AI 分析列表项的原始数据，智能生成字段配置。

    接收 rawItemData（texts/links/images），调用 DeepSeek API 分析语义，
    返回带有 CSS selector 的字段列表。如果 AI 不可用则降级到基础提取。
    """
    raw = req.rawItemData

    # Validate input has content
    has_content = (
        len(raw.get("texts", [])) > 0 or
        len(raw.get("links", [])) > 0 or
        len(raw.get("images", [])) > 0
    )
    if not has_content:
        return AnalyzeFieldsResponse(fields=[], aiEnhanced=False)

    # Try AI analysis
    if ai_service.enabled:
        try:
            prompt = _build_analyze_fields_prompt(raw)

            import httpx
            headers = {
                'Authorization': f'Bearer {ai_service.api_key}',
                'Content-Type': 'application/json'
            }
            payload = {
                'model': ai_service.endpoint_id,
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a web data extraction expert. You analyze HTML element data and identify meaningful fields. Respond ONLY with valid JSON.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': 0.1,
                'max_tokens': 800
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f'{ai_service.api_base}/chat/completions',
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                data = response.json()
                content = data['choices'][0]['message']['content'].strip()

                # Parse JSON array from response
                # Try to extract JSON array even if wrapped in markdown
                json_match = re.search(r'\[[\s\S]*\]', content)
                if json_match:
                    ai_fields = json.loads(json_match.group())
                else:
                    raise ValueError(f"No JSON array found in AI response: {content[:200]}")

                fields = _map_ai_result_to_fields(ai_fields, raw)

                if fields:
                    return AnalyzeFieldsResponse(fields=fields, aiEnhanced=True)

        except Exception:
            pass

    # Fallback: basic extraction without AI
    fallback = _fallback_fields_from_raw(raw)
    return AnalyzeFieldsResponse(fields=fallback, aiEnhanced=False)
