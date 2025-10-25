# 智能网站识别功能使用指南

## 🎯 功能概述

SeenFetch 现在具备**智能网站识别**功能，可以自动分析网站类型并推荐最优的爬虫配置，**用户无需手动调整任何参数**！

### 核心特性

✅ **零配置**：输入 URL 即可，系统自动识别并优化
✅ **高性能**：本地规则库 + 缓存，毫秒级响应
✅ **高准确**：规则 + AI 混合策略，置信度 85%+
✅ **低成本**：缓存优先，AI 调用成本约 ¥0.003/次
✅ **易扩展**：规则库持续更新，支持更多网站

---

## 🚀 快速开始

### 1. 运行数据库迁移（首次使用）

```bash
python migrate_add_website_configs.py
```

**说明**：如果是新安装，启动应用时会自动创建数据库，无需手动迁移。

### 2. 启动应用

```bash
cd services/api/app
python main.py
```

### 3. 使用前端

打开浏览器：`http://localhost:8000/services/web/index.html`

1. **输入 URL**：比如 `https://unsplash.com/`
2. **点击"开始提取"**
3. **系统自动识别**：
   - ✓ 识别为图片瀑布流网站
   - ✓ 自动应用优化配置（滚动 30 次，等待 3 秒）
   - ✓ 开始爬取数据
4. **查看结果**：等待 2-3 分钟，获取 300-600 张图片

**就这么简单！** 用户完全感知不到后台的智能识别过程。

---

## 🧠 工作原理

### 识别流程

```
用户输入 URL
    ↓
[1] 数据库缓存查询 (毫秒级)
    ├─ 命中 → 直接使用
    ↓
[2] 本地规则库匹配 (毫秒级)
    ├─ 命中 → 使用规则配置
    ↓
[3] 快速页面分析 (2-5秒)
    ├─ 置信度 > 85% → 使用本地检测
    ↓
[4] DeepSeek AI 分析 (3-5秒)
    ↓
[5] 缓存结果，应用配置
```

### 三层识别机制

#### 1️⃣ 本地规则库（最快）

预配置了 12 个常见网站：
- **图片**: Unsplash, Pinterest, 500px, Flickr
- **电商**: 淘宝搜索、京东搜索
- **社交**: 小红书、微博、Instagram
- **视频**: B站搜索
- **其他**: 知乎、豆瓣

**示例**：
```json
{
    "domain": "unsplash.com",
    "site_name": "Unsplash",
    "load_type": "infinite_scroll",
    "config": {
        "use_stealth": true,
        "auto_scroll": true,
        "max_scrolls": 30,
        "scroll_delay": 3000,
        "stable_checks": 5
    },
    "confidence": 1.0
}
```

#### 2️⃣ 页面特征分析（中等）

当本地规则库没有匹配时，系统会：
1. 快速加载页面
2. 分析 DOM 结构（图片数、文章数、懒加载特征）
3. 检测翻页按钮、无限滚动提示
4. 根据特征判断网站类型

**检测指标**：
- 图片数量 > 20 → 图片分享网站
- 文章数量 > 10 → 新闻/博客
- 有懒加载属性 → 无限滚动
- 有翻页按钮 → 分页加载

#### 3️⃣ AI 深度分析（最准确）

当本地检测置信度 < 85% 时，调用 DeepSeek：
- 分析 URL、标题、页面特征
- 推荐网站类型和加载方式
- 生成优化的爬虫配置
- 置信度通常 > 90%

**成本**：约 ¥0.003/次（不到1分钱）

---

## 📊 支持的网站类型

| 类型 | 英文标识 | 加载方式 | 配置特点 |
|------|----------|----------|----------|
| 图片分享 | photo_sharing | 无限滚动 | 长等待时间（3000ms） |
| 电商平台 | ecommerce | 无限滚动/翻页 | 中等滚动（15-20次） |
| 社交媒体 | social_media | 无限滚动 | 隐身模式必须 |
| 视频平台 | video_platform | 无限滚动 | 中等等待（2500ms） |
| 问答社区 | qa_community | 无限滚动 | 标准配置 |
| 新闻网站 | news | 翻页/无限滚动 | 快速滚动 |
| 其他 | general | 自动检测 | 默认配置 |

---

## 🔧 终端日志示例

### Unsplash（本地规则匹配）

```
[Run] 开始采集: https://unsplash.com/
[Run] Job 无配置，启动智能识别...
[Analyzer] 开始分析: https://unsplash.com/
[Analyzer] 域名: unsplash.com
[Analyzer] ✓ 匹配本地规则: Unsplash (置信度: 1.0)
[Run] ✓ 智能识别完成:
[Run]   - 网站: Unsplash
[Run]   - 类型: photo_sharing
[Run]   - 加载方式: infinite_scroll
[Run]   - 置信度: 1.0
[Run]   - 来源: local_rules
[Run] 最终配置: {'use_stealth': True, 'max_scrolls': 30, 'scroll_delay': 3000, ...}
[Run] 使用配置: {'use_stealth': True, ...}
[Run] 使用新版爬虫: .../crawler_runner_v2.py
[Run] 超时时间: 150 秒
[V2] Initializing enhanced crawler for: https://unsplash.com/
...
[Scroll] Starting enhanced auto-scroll
[Scroll] Config: maxScrolls=30, delay=3000ms, stableChecks=5
[Scroll] Complete! Total scrolls: 25, Final items: 520
[Run] 爬取成功，HTML 长度: 1,250,000
```

### 未知网站（AI 分析）

```
[Run] 开始采集: https://example-unknown-site.com/
[Analyzer] 开始分析: https://example-unknown-site.com/
[Analyzer] 域名: example-unknown-site.com
[Analyzer] 本地规则未匹配，进行页面分析...
[Analyzer] 正在加载页面...
[Analyzer] 页面分析完成:
[Analyzer]   - 标题: Example Site...
[Analyzer]   - 图片: 45 个
[Analyzer]   - 文章: 5 个
[Analyzer] 本地检测结果: infinite_scroll (置信度: 0.7)
[Analyzer] 调用 DeepSeek AI 分析...
[AI] 调用 DeepSeek 分析网站: https://example-unknown-site.com/
[AI] 响应状态: 200
[AI] 响应内容: {"site_name": "Example Gallery", ...}
[Analyzer] ✓ AI 分析完成: infinite_scroll (置信度: 0.92)
[Analyzer] 采用 AI 分析结果（置信度更高）
[Analyzer] 创建缓存: example-unknown-site.com
[Run] ✓ 智能识别完成:
[Run]   - 网站: Example Gallery
[Run]   - 类型: photo_sharing
[Run]   - 置信度: 0.92
[Run]   - 来源: deepseek
```

---

## 💾 数据库缓存

### 自动缓存

识别结果会自动保存到 `website_configs` 表：

```sql
SELECT * FROM website_configs;
```

| domain | site_name | load_type | confidence | source | last_used_at |
|--------|-----------|-----------|------------|--------|--------------|
| unsplash.com | Unsplash | infinite_scroll | 1.0 | local_rules | 2025-01-25 |
| pinterest.com | Pinterest | infinite_scroll | 1.0 | local_rules | 2025-01-25 |
| example.com | Example | infinite_scroll | 0.92 | deepseek | 2025-01-25 |

### 缓存优势

1. **极速响应**：第二次访问直接从数据库读取（毫秒级）
2. **节省成本**：避免重复调用 AI API
3. **持续优化**：记录成功/失败次数，可后续优化

---

## 📝 手动扩展规则库

如果你想添加更多网站到规则库：

编辑 `services/api/app/website_rules.json`：

```json
{
    "rules": [
        {
            "domain": "your-site.com",
            "site_name": "你的网站",
            "site_type": "photo_sharing",
            "load_type": "infinite_scroll",
            "config": {
                "use_stealth": true,
                "auto_scroll": true,
                "max_scrolls": 25,
                "scroll_delay": 2500,
                "stable_checks": 4
            },
            "confidence": 1.0,
            "notes": "网站说明"
        }
    ]
}
```

**重启应用**即可生效。

---

## 🧪 测试功能

### 1. 测试本地规则和缓存

```bash
python test_smart_detection.py
```

输出示例：
```
============================================================
测试 1: 本地规则库匹配
============================================================

本地规则库包含 12 条规则

✓ https://unsplash.com/
  - 网站: Unsplash
  - 类型: photo_sharing
  - 加载方式: infinite_scroll
  - 置信度: 1.0
  - 配置: max_scrolls=30, delay=3000ms

✓ https://pinterest.com/
  - 网站: Pinterest
  - 类型: photo_sharing
  - 加载方式: infinite_scroll
  - 置信度: 1.0
  - 配置: max_scrolls=40, delay=3500ms
...
```

### 2. 测试完整爬取流程

通过前端测试：
1. 打开 `http://localhost:8000/services/web/index.html`
2. 输入 URL（例如 `https://unsplash.com/`）
3. 配置字段（例如选择图片）
4. 点击"开始采集"
5. 观察终端日志，查看识别过程
6. 等待结果

---

## 🔍 故障排查

### 问题 1: AI 分析失败

**症状**：日志显示 `[AI] 网站分析失败`

**原因**：DeepSeek API 配置问题或网络问题

**解决方法**：
1. 检查 `services/api/app/settings.py` 中的 API 配置
2. 确保 `ai_enabled = True`
3. 验证 `deepseek_api_key` 和 `deepseek_endpoint_id`

**降级**：AI 失败时会自动使用本地检测结果，不影响功能

### 问题 2: 本地规则不匹配

**症状**：应该匹配的网站没有匹配到规则

**原因**：域名提取或规则配置问题

**解决方法**：
1. 检查日志中的域名提取：`[Analyzer] 域名: xxx`
2. 确保规则库中的 `domain` 字段与提取的域名一致
3. 可以添加 `url_pattern` 字段进行模糊匹配

### 问题 3: 缓存不更新

**症状**：修改规则后没有生效

**原因**：数据库中已有缓存

**解决方法**：
```python
# 删除特定网站的缓存
from db import session_scope
from models import WebsiteConfig

with session_scope() as session:
    session.query(WebsiteConfig).filter(
        WebsiteConfig.domain == 'unsplash.com'
    ).delete()
```

或者在调用时强制刷新：
```python
analyzer.analyze(url, session, force_refresh=True)
```

---

## 📈 性能统计

### 响应时间

| 场景 | 响应时间 | 说明 |
|------|----------|------|
| 缓存命中 | < 10ms | 数据库查询 |
| 本地规则匹配 | < 50ms | JSON 遍历 |
| 页面分析 | 2-5秒 | HTTP 请求 + 解析 |
| AI 分析 | 3-5秒 | DeepSeek API 调用 |

### 成本估算

假设 1000 个用户，每人测试 10 个网站：

- **缓存命中率**：70%（常见网站） → 成本 ¥0
- **本地规则**：20% → 成本 ¥0
- **AI 分析**：10%（1000 次） → 成本 ¥3

**月成本**：约 ¥3（非常低）

---

## 🎁 用户体验

### 传统方式（之前）

```
用户：我想爬 Unsplash
系统：请设置爬虫参数：
  - 滚动次数？
  - 等待时间？
  - 是否隐身？
用户：我不懂这些... 😵
```

### 智能方式（现在）

```
用户：我想爬 Unsplash
系统：✓ 已自动识别为图片瀑布流网站
      ✓ 已应用优化配置
      ✓ 开始爬取...
用户：太棒了！😄
```

---

## 🚀 未来扩展

### 计划中的功能

1. **更多规则**：持续添加常见网站
2. **自动学习**：根据成功率自动优化配置
3. **众包规则**：用户可以分享成功的配置
4. **翻页识别**：自动检测和点击"下一页"按钮
5. **视觉分析**：使用 AI 视觉模型分析页面布局

### 贡献规则

如果你发现某个网站配置效果很好，欢迎提交到规则库：

1. Fork 项目
2. 编辑 `website_rules.json`
3. 提交 Pull Request
4. 说明网站类型和测试结果

---

## 💡 最佳实践

### 1. 优先使用本地规则

对于常见网站，在规则库中预配置，避免每次都进行分析。

### 2. 合理设置缓存时间

网站结构变化不频繁（几个月甚至一年），缓存可以长期保留。

### 3. 监控 AI 调用

定期检查 `website_configs` 表，查看哪些网站依赖 AI 分析，考虑添加到规则库。

### 4. 提供用户反馈

如果识别不准确，可以记录用户手动调整后的配置，用于优化规则。

---

## 📚 相关文档

- [瀑布流滚动配置指南](SCROLL_CONFIG_GUIDE.md)
- [Unsplash 快速开始](UNSPLASH_QUICK_START.md)
- [项目总体说明](README.md)

---

## ❓ 常见问题

**Q: 用户需要了解这些技术细节吗？**
A: 不需要！用户只需输入 URL，系统自动处理一切。

**Q: 如果识别错误怎么办？**
A: 系统会使用默认的保守配置，确保至少能爬取部分数据。未来可以添加手动修正功能。

**Q: 所有网站都支持吗？**
A: 目前专注于无限滚动类型，翻页类型的自动识别正在开发中。

**Q: 性能会变慢吗？**
A: 首次访问可能需要几秒，但之后都是毫秒级响应（缓存）。

**Q: 会增加成本吗？**
A: 成本极低，月均约 ¥3（1000 用户场景）。本地规则库命中率 > 70%。

---

祝使用愉快！🎉
