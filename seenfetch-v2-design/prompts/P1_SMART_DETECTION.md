# P1 - 智能识别增强开发提示词

## 功能概述

增强 SeenFetch 的智能识别能力：
- 自动检测页面中的列表/表格结构
- 智能推断字段类型（价格、日期、评分等）
- 提供更准确的选择器建议
- 减少用户手动配置工作

---

## Prompt 1: 列表结构检测器

```
实现 SeenFetch 的页面列表结构自动检测。

要求：
1. 创建 services/api/app/services/list_detector.py

2. 实现 ListDetector 类：

class ListDetector:
    async def detect_lists(self, page: Page) -> List[DetectedList]
    
@dataclass
class DetectedList:
    container_selector: str     # 列表容器选择器
    item_selector: str          # 列表项选择器
    item_count: int             # 检测到的项数
    confidence: float           # 置信度 0-1
    structure_hash: str         # 结构指纹（用于判断相似度）
    sample_items: List[Dict]    # 前3项预览数据
    suggested_fields: List[SuggestedField]  # 建议的字段

3. 检测算法：

步骤1 - 寻找候选容器：
- 遍历所有可能的列表容器：ul, ol, tbody, div, section
- 筛选条件：直接子元素 >= 3

步骤2 - 计算子元素结构相似度：
```javascript
function getStructureHash(element) {
    // 提取结构特征：标签序列 + class模式
    const tags = Array.from(element.children).map(c => c.tagName).join(',');
    const classes = element.className.split(' ').filter(c => !c.match(/\d/)).sort().join(',');
    return `${element.tagName}:${tags}:${classes}`;
}
```
- 相似度 = 相同结构的子元素数 / 总子元素数
- 阈值：相似度 >= 0.8

步骤3 - 分析列表项内部结构：
- 提取每个列表项的子元素
- 识别标题（h1-h6, .title, a的主文本）
- 识别图片（img）
- 识别链接（a[href]）
- 识别价格/评分等（基于文本模式）

步骤4 - 生成建议字段：
- 每个识别到的内容类型 → 一个 SuggestedField
- 包含：字段名建议、选择器、类型、示例值

4. 返回结果按置信度降序排列

5. 测试用例：
- 豆瓣电影列表（复杂结构）
- 商品列表（图片+标题+价格）
- 简单表格（tbody > tr）
```

---

## Prompt 2: 字段类型推断器

```
实现 SeenFetch 的字段类型智能推断。

要求：
1. 创建 services/api/app/services/field_inferrer.py

2. 定义字段类型枚举：
class FieldType(Enum):
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
    PERCENTAGE = "percentage" # 百分比

3. 实现 FieldTypeInferrer 类：

class FieldTypeInferrer:
    def infer(self, text: str, element_info: Dict) -> InferenceResult
    
@dataclass
class InferenceResult:
    field_type: FieldType
    confidence: float
    extracted_value: Any      # 提取/格式化后的值
    suggested_name: str       # 建议的字段名
    extraction_attr: str      # "text" | "href" | "src" | 其他属性

4. 推断逻辑（按优先级）：

a. 基于元素标签：
   - img → IMAGE, 提取 src
   - a → URL（有href时），提取 href
   - h1-h4 → TITLE

b. 基于 class/id 名称（模糊匹配）：
   - *price*, *cost*, *money* → PRICE
   - *title*, *name*, *heading* → TITLE
   - *date*, *time*, *created* → DATE
   - *rating*, *score*, *star* → RATING
   - *desc*, *description*, *content* → TEXT

c. 基于文本内容正则匹配：
   价格模式：
   - /[\$€£¥]\s*[\d,]+\.?\d*/
   - /[\d,]+\.?\d*\s*元/
   - /[\d,]+\.?\d*\s*(USD|CNY|EUR|RMB)/
   
   日期模式：
   - /\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?/
   - /\d{1,2}[-/]\d{1,2}[-/]\d{2,4}/
   - /(Jan|Feb|Mar|...|Dec)\s+\d{1,2},?\s+\d{4}/
   - /\d+\s*(天|小时|分钟|秒)前/
   
   评分模式：
   - /[\d.]+\s*[/／]\s*[\d.]+/     # 8.5/10
   - /[\d.]+\s*分/                 # 9.2分
   - /★+☆*/                        # ★★★★☆
   
   邮箱：/[\w\.-]+@[\w\.-]+\.\w+/
   电话：/1[3-9]\d{9}|(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/
   百分比：/\d+\.?\d*\s*%/

5. 值提取与格式化：
   - PRICE: 提取数字，保留小数
   - DATE: 尝试解析为标准格式
   - RATING: 转换为数字（如 ★★★★☆ → 4）

6. 字段名建议规则：
   - 基于类型：price→"价格", date→"日期"
   - 基于位置：第一个标题→"标题", 第一个图片→"封面"
   - 基于class名：class="product-name" → "商品名称"
```

---

## Prompt 3: 选择器优化器

```
实现 SeenFetch 的 CSS 选择器优化，生成更稳定的选择器。

要求：
1. 创建 services/api/app/services/selector_optimizer.py

2. 实现 SelectorOptimizer 类：

class SelectorOptimizer:
    def optimize(self, element: ElementHandle, context: Page) -> OptimizedSelector
    def generate_alternatives(self, element: ElementHandle) -> List[str]
    def validate_selector(self, selector: str, page: Page) -> ValidationResult

@dataclass
class OptimizedSelector:
    selector: str           # 推荐选择器
    stability_score: float  # 稳定性评分 0-1
    specificity: int        # CSS特异性
    match_count: int        # 匹配元素数
    alternatives: List[str] # 备选选择器

3. 选择器生成策略（按优先级）：

a. 基于 data-* 属性（最稳定）：
   - [data-testid="xxx"]
   - [data-id="xxx"]
   - [data-item="xxx"]

b. 基于语义化 ID：
   - #product-list .item
   - 排除动态ID（包含数字/hash的）

c. 基于语义化 class 组合：
   - .product-card .title
   - 排除动态class（BEM生成的hash类名）

d. 基于结构路径：
   - ul.list > li:nth-child(n) > h3
   - 尽量使用标签+class，避免纯位置选择

e. 基于文本内容（最后手段）：
   - :has-text("xxx")  # Playwright特有
   - 仅用于唯一文本

4. 稳定性评分规则：
   - data-* 属性：+0.3
   - 语义化ID：+0.2
   - 语义化class：+0.15
   - 标签名：+0.1
   - nth-child：-0.1
   - 纯数字/hash：-0.2

5. 选择器验证：
   - 检查匹配数量是否符合预期
   - 检查是否匹配到预期元素
   - 动态页面：等待后重新验证

6. 批量选择器（用于列表项）：
   - 输入：一个列表项元素
   - 输出：能匹配所有同类项的选择器
   - 去除 :nth-child 等位置相关部分
```

---

## Prompt 4: AI 增强识别

```
增强 SeenFetch 的 AI 字段识别能力，结合 DeepSeek API。

要求：
1. 修改 services/api/app/ai_service.py

2. 新增方法 analyze_page_structure：

async def analyze_page_structure(self, page_info: Dict) -> StructureAnalysis:
    """
    使用 AI 分析页面结构，识别主要数据区域
    
    输入 page_info:
    - url: str
    - title: str
    - html_snippet: str (简化的DOM结构，去除样式和脚本)
    - visible_text: str (可见文本摘要)
    
    输出 StructureAnalysis:
    - page_type: str  # "list", "detail", "search", "article", "other"
    - main_content_selector: str
    - detected_lists: List[{selector, description, item_count}]
    - suggested_fields: List[{name, selector, type, description}]
    """

3. Prompt 模板：

SYSTEM_PROMPT = """
你是一个网页结构分析专家。分析给定的网页信息，识别其数据结构。

输出 JSON 格式：
{
  "page_type": "list|detail|search|article|other",
  "main_content_selector": "CSS选择器",
  "lists": [
    {
      "selector": "列表容器选择器",
      "item_selector": "列表项选择器",
      "description": "这是什么列表",
      "fields": [
        {"name": "字段名", "selector": "相对选择器", "type": "text|image|link|price|date|rating"}
      ]
    }
  ]
}

注意：
- 选择器要具体、稳定，优先使用 class 和 data 属性
- 字段名用中文，简洁明了
- 只识别结构化数据，忽略导航、广告等
"""

4. 优化策略：
   - 先用规则检测，置信度 < 0.7 时调用 AI
   - 缓存 AI 结果（相同URL结构）
   - 超时处理：AI 调用超时则降级到规则结果

5. 错误处理：
   - API 调用失败：返回规则检测结果
   - JSON 解析失败：重试一次，仍失败则降级
   - 结果验证：AI 返回的选择器需在页面上验证
```

---

## Prompt 5: 前端智能识别UI

```
为 SeenFetch 前端添加智能识别结果展示和交互。

要求：
1. 修改 services/web/js/index-v2.js，添加智能识别相关逻辑

2. 智能识别流程：
   a. 用户输入 URL 并加载页面
   b. 后端自动分析，返回识别结果
   c. 前端展示检测到的列表和字段建议
   d. 用户可以一键采纳或手动调整

3. UI 组件：

【检测结果面板】
┌────────────────────────────────────────────┐
│ 🔍 智能识别结果                    置信度: 95% │
├────────────────────────────────────────────┤
│ 检测到 1 个数据列表                          │
│                                            │
│ 📋 电影列表 (25项)                          │
│   ├─ 封面图片  [img.pic img]               │
│   ├─ 电影名称  [span.title]        ✓ 采纳  │
│   ├─ 评分      [span.rating_num]   ✓ 采纳  │
│   ├─ 评价人数  [span.rating_nums]  ✓ 采纳  │
│   └─ 简介      [p.quote]           ○ 跳过  │
│                                            │
│        [全部采纳]  [手动选择]               │
└────────────────────────────────────────────┘

4. 交互功能：
   - 鼠标悬停字段：Canvas 上高亮对应元素
   - 点击"采纳"：添加到已配置字段
   - 点击"跳过"：从建议中移除
   - "全部采纳"：一次性添加所有建议字段
   - "手动选择"：切换到手动模式

5. 采纳后的处理：
   - 建议字段转为正式字段配置
   - 更新字段配置面板
   - 显示预览数据

6. 样式要求：
   - 使用卡片式设计
   - 置信度用颜色表示（绿色高、黄色中、红色低）
   - 选择器用代码样式显示
   - 动画过渡（建议项被采纳时的反馈）

保持与现有 smartMode 的风格一致
```

---

## Prompt 6: 识别结果 API

```
创建 SeenFetch 智能识别的 API 端点。

要求：
1. 创建/修改 services/api/app/routers/smart.py

2. 实现端点：

POST /api/smart/analyze
- 请求：{ session_id: str } 或 { url: str }
- 响应：
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
      "fields": [
        {
          "name": "封面",
          "selector": "img.poster",
          "type": "image",
          "attr": "src",
          "sample_values": ["https://...", "https://..."]
        },
        {
          "name": "电影名称",
          "selector": "span.title",
          "type": "title",
          "attr": "text",
          "sample_values": ["肖申克的救赎", "霸王别姬"]
        }
      ]
    }
  ],
  "pagination": {
    "detected": true,
    "type": "click_next",
    "selector": "a.next",
    "confidence": 0.9
  }
}

POST /api/smart/validate-selector
- 请求：{ session_id: str, selector: str }
- 响应：{ valid: bool, match_count: int, sample_texts: List[str] }

POST /api/smart/suggest-name
- 请求：{ element_info: {...}, context: {...} }
- 响应：{ name: str, confidence: float }
- 这个已有，确保兼容

3. 整合流程：
   - /analyze 内部调用 ListDetector + FieldTypeInferrer + PaginationDetector
   - 结果合并后返回
   - 支持仅分析部分（如只检测翻页）

4. 性能优化：
   - 缓存分析结果（基于 URL + 页面hash）
   - 分析超时限制（10秒）
   - 大页面采样分析（只分析前100个元素）
```

---

## Prompt 7: 集成测试

```
为 SeenFetch 智能识别功能编写测试。

要求：
1. 创建 tests/test_smart_detection.py

2. 测试用例：

【列表检测】
- test_detect_douban_list: 豆瓣电影列表
- test_detect_table_list: 表格形式列表
- test_detect_card_list: 卡片式列表
- test_no_list_page: 无列表的页面（详情页）

【字段类型推断】
- test_infer_price_cny: 人民币价格 "¥99.00"
- test_infer_price_usd: 美元价格 "$19.99"
- test_infer_date_cn: 中文日期 "2024年1月1日"
- test_infer_date_en: 英文日期 "Jan 1, 2024"
- test_infer_rating_score: 评分 "8.5/10"
- test_infer_rating_star: 星级 "★★★★☆"
- test_infer_email: 邮箱
- test_infer_phone_cn: 中国手机号

【选择器优化】
- test_optimize_data_attr: 优先使用 data-* 属性
- test_optimize_semantic_class: 使用语义化 class
- test_avoid_dynamic_class: 避免动态生成的 class
- test_batch_selector: 批量选择器生成

3. 使用 pytest fixtures 共享浏览器实例

4. Mock AI 服务（单元测试不依赖外部 API）

5. 对比测试：规则检测 vs AI 检测的准确率
```

---

## 开发顺序建议

1. **Prompt 1**: 列表检测器（核心）
2. **Prompt 2**: 字段类型推断器
3. **Prompt 3**: 选择器优化器
4. **Prompt 6**: 整合 API
5. **Prompt 5**: 前端 UI
6. **Prompt 4**: AI 增强（可选，提升准确率）
7. **Prompt 7**: 测试

先完成规则检测，再考虑 AI 增强。
