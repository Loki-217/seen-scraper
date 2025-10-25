# 瀑布流滚动配置指南

## 改进说明

针对 Unsplash 等现代瀑布流网站，我们对滚动加载功能进行了重大改进：

### 主要改进

1. **智能内容检测**
   - 不仅检测页面高度变化，还检测实际元素数量
   - 支持多种选择器自动适配不同网站

2. **加载指示器等待**
   - 自动检测和等待加载动画消失
   - 支持常见的 loading/spinner 元素

3. **平滑滚动**
   - 模拟真实用户行为，分步滚动
   - 避免被反爬虫机制检测

4. **多次稳定性检查**
   - 连续多次检测无变化才停止
   - 防止网络延迟导致的误判

5. **备用滚动策略**
   - 上下滚动触发 Intersection Observer
   - 强制加载懒加载图片

6. **详细日志输出**
   - 实时显示滚动进度
   - 显示高度和元素数量变化

## 配置参数

在调用爬虫时，可以传入以下配置：

```python
config = {
    'use_stealth': True,      # 启用隐身模式（推荐）
    'auto_scroll': True,      # 启用自动滚动
    'max_scrolls': 20,        # 最大滚动次数
    'scroll_delay': 2000,     # 每次滚动后等待时间（毫秒）
    'stable_checks': 3,       # 稳定性检查次数
}
```

### 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `use_stealth` | bool | False | 启用反爬虫对策（隐藏 webdriver 特征） |
| `auto_scroll` | bool | True | 启用自动滚动 |
| `max_scrolls` | int | 20 | 最多滚动次数，防止无限循环 |
| `scroll_delay` | int | 2000 | 每次滚动后等待时间（毫秒） |
| `stable_checks` | int | 3 | 连续多少次无变化才认为加载完成 |

## 针对不同网站的推荐配置

### Unsplash (图片瀑布流)

```python
config = {
    'use_stealth': True,
    'auto_scroll': True,
    'max_scrolls': 30,        # 内容多，需要更多滚动
    'scroll_delay': 3000,     # 图片加载慢，需要更长等待
    'stable_checks': 5,       # 网络波动大，多检查几次
}
```

**特点**：
- 高分辨率图片加载慢
- 使用 Intersection Observer 懒加载
- 需要较长等待时间

### Pinterest (瀑布流)

```python
config = {
    'use_stealth': True,
    'auto_scroll': True,
    'max_scrolls': 25,
    'scroll_delay': 2500,
    'stable_checks': 4,
}
```

**特点**：
- 反爬虫严格，必须用隐身模式
- 动态布局计算需要时间

### 电商网站 (商品列表)

```python
config = {
    'use_stealth': True,
    'auto_scroll': True,
    'max_scrolls': 15,        # 商品数量有限
    'scroll_delay': 1500,     # 加载较快
    'stable_checks': 3,
}
```

**特点**：
- 通常有固定的商品数量
- 加载速度较快

### 社交媒体 (无限滚动)

```python
config = {
    'use_stealth': True,
    'auto_scroll': True,
    'max_scrolls': 50,        # 内容几乎无限
    'scroll_delay': 2000,
    'stable_checks': 3,
}
```

**特点**：
- 内容接近无限
- 需要限制最大滚动次数

### 新闻网站 (文章列表)

```python
config = {
    'use_stealth': False,     # 通常不需要隐身
    'auto_scroll': True,
    'max_scrolls': 10,        # 文章数量有限
    'scroll_delay': 1000,     # 文本加载快
    'stable_checks': 2,
}
```

**特点**：
- 文本内容，加载快
- 通常翻页而非无限滚动

## 使用示例

### 1. Python 代码调用

```python
from crawler_runner_v2 import crawl_page_enhanced
import asyncio

async def main():
    url = "https://unsplash.com/"

    config = {
        'use_stealth': True,
        'auto_scroll': True,
        'max_scrolls': 30,
        'scroll_delay': 3000,
        'stable_checks': 5,
    }

    result = await crawl_page_enhanced(url, config)

    if result['success']:
        html = result['html']
        print(f"获取到 {len(html)} 字符的 HTML")

        # 统计图片数量
        img_count = html.count('<img')
        print(f"检测到 {img_count} 个图片")
    else:
        print(f"错误: {result['error']}")

asyncio.run(main())
```

### 2. 通过 API 调用

在创建 Job 或执行爬取时，传入配置：

```python
import requests

# 创建任务时指定配置
job_data = {
    "name": "Unsplash Photos",
    "start_url": "https://unsplash.com/",
    "config": {
        "use_stealth": True,
        "auto_scroll": True,
        "max_scrolls": 30,
        "scroll_delay": 3000,
        "stable_checks": 5
    },
    "selectors": [
        {
            "name": "photo_url",
            "css": "img[src*='unsplash']",
            "attr": "src"
        }
    ]
}

response = requests.post("http://localhost:8000/jobs", json=job_data)
```

### 3. 命令行测试

使用提供的测试脚本：

```bash
# 默认配置测试
python test_unsplash_scroll.py

# 自定义参数
python test_unsplash_scroll.py --max-scrolls 40 --scroll-delay 3500

# 对比测试不同配置
python test_unsplash_scroll.py --compare
```

## 调优技巧

### 如果内容加载不完整

1. **增加 `scroll_delay`**（优先尝试）
   ```python
   'scroll_delay': 3500  # 从 2000 增加到 3500
   ```

2. **增加 `max_scrolls`**
   ```python
   'max_scrolls': 40  # 从 20 增加到 40
   ```

3. **增加 `stable_checks`**
   ```python
   'stable_checks': 5  # 从 3 增加到 5
   ```

### 如果爬取时间太长

1. **减少 `scroll_delay`**（但可能丢失内容）
   ```python
   'scroll_delay': 1500  # 从 2000 减少到 1500
   ```

2. **减少 `stable_checks`**
   ```python
   'stable_checks': 2  # 从 3 减少到 2
   ```

3. **限制 `max_scrolls`**
   ```python
   'max_scrolls': 10  # 只加载前面的内容
   ```

### 如果被反爬虫拦截

1. **启用隐身模式**（必须）
   ```python
   'use_stealth': True
   ```

2. **增加等待时间**（模拟真实用户）
   ```python
   'scroll_delay': 4000  # 更长的等待时间
   ```

3. **减少滚动次数**（降低请求频率）
   ```python
   'max_scrolls': 10
   ```

## 监控和调试

### 查看滚动日志

爬取过程中会输出详细日志：

```
[Scroll] Starting enhanced auto-scroll
[Scroll] Config: maxScrolls=30, delay=3000ms, stableChecks=5
[Scroll] Initial height: 5420
[Scroll] Round 1/30
[Scroll] Waiting 3000ms for content...
[Scroll] Loading indicator disappeared
[Scroll] Height: 5420 -> 7832, Items: 20 -> 40
[Scroll] New content detected, continuing...
...
[Scroll] Complete! Total scrolls: 18, Final items: 320
```

### 关键指标

- **Total scrolls**: 实际执行的滚动次数
- **Final items**: 最终检测到的元素数量
- **Height changes**: 页面高度变化情况

## 常见问题

### Q: 为什么 Unsplash 只能加载到一定位置？

A: 主要有以下原因：

1. **等待时间不够**：图片加载需要时间，原来 1.5 秒不够
2. **检测机制单一**：只检查高度，但 DOM 可能还在更新
3. **滚动次数限制**：默认只滚动 5 次，对于大网站不够
4. **Intersection Observer 未触发**：需要更接近真实用户的滚动行为

**解决方案**：使用改进后的配置（已实现）。

### Q: 如何确定最佳配置？

A: 使用对比测试脚本：

```bash
python test_unsplash_scroll.py --compare
```

这会测试三种配置（激进/平衡/保守），找出最适合的。

### Q: 配置能保存到 Job 中吗？

A: 可以！在创建 Job 时将配置保存到数据库，之后每次执行都会使用相同配置。

### Q: 滚动太慢怎么办？

A: 如果不需要加载全部内容，可以使用激进配置：

```python
config = {
    'use_stealth': True,
    'auto_scroll': True,
    'max_scrolls': 10,     # 只滚动 10 次
    'scroll_delay': 1000,  # 等待 1 秒
    'stable_checks': 2,    # 检查 2 次
}
```

## 技术细节

### 滚动算法流程

```
1. 初始化计数器和检测器
2. 循环开始：
   ├─ 平滑滚动到页面底部（分 5 步）
   ├─ 强制触发懒加载图片
   ├─ 等待指定时间
   ├─ 等待加载指示器消失
   ├─ 检测高度和元素数量变化
   │
   ├─ 如果有变化：
   │  └─ 重置稳定计数器，继续滚动
   │
   └─ 如果无变化：
      ├─ 增加稳定计数器
      ├─ 尝试备用滚动策略（上下滚动）
      └─ 如果连续多次无变化：停止
3. 滚动回顶部
4. 返回结果
```

### 内容检测选择器

自动尝试以下选择器（针对 Unsplash 等网站）：

```javascript
[
    'figure',                   // 图片容器
    '[data-test*="photo"]',     // Unsplash 特定属性
    'img[src*="unsplash"]',     // Unsplash 图片
    'a[href*="/photos/"]',      // 照片链接
    'article',                  // 文章/卡片
    '[class*="photo"]',         // 包含 photo 的类名
    '[class*="image"]'          // 包含 image 的类名
]
```

### 加载指示器检测

自动检测以下元素：

```javascript
[
    '[data-test="loader"]',     // 测试属性
    '[class*="loading"]',       // loading 类名
    '[class*="spinner"]',       // spinner 类名
    '[aria-busy="true"]',       // ARIA 忙碌状态
    '.loading',                 // loading 类
    '.spinner'                  // spinner 类
]
```

## 性能优化建议

### 1. 按需加载

如果只需要前面的内容：

```python
'max_scrolls': 5  # 只加载前 5 屏
```

### 2. 并发爬取

如果需要爬取多个类别：

```python
# 同时爬取多个 URL
urls = [
    "https://unsplash.com/t/nature",
    "https://unsplash.com/t/animals",
    "https://unsplash.com/t/technology",
]

tasks = [crawl_page_enhanced(url, config) for url in urls]
results = await asyncio.gather(*tasks)
```

### 3. 增量爬取

记录上次爬取的元素数量，下次只爬取新内容：

```python
# 第一次：全量爬取
result = await crawl_page_enhanced(url, {
    'max_scrolls': 30,
    'scroll_delay': 3000,
})

# 后续：增量爬取
result = await crawl_page_enhanced(url, {
    'max_scrolls': 5,   # 只需要少量滚动
    'scroll_delay': 2000,
})
```

## 总结

改进后的滚动功能解决了 Unsplash 等现代瀑布流网站的加载问题。关键改进包括：

✅ 智能内容检测（高度 + 元素数量）
✅ 加载指示器等待
✅ 平滑滚动（模拟真实用户）
✅ 多次稳定性检查
✅ 备用滚动策略
✅ 详细日志输出

针对 Unsplash，推荐使用：

```python
config = {
    'use_stealth': True,
    'auto_scroll': True,
    'max_scrolls': 30,
    'scroll_delay': 3000,
    'stable_checks': 5,
}
```

如有问题，请查看日志输出或使用测试脚本进行调试。
