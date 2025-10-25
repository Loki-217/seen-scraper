# Unsplash 瀑布流爬取快速开始指南

## 问题描述

之前的滚动加载实现在处理 Unsplash 等现代瀑布流网站时只能加载到一定位置就停止了。

## 解决方案

我们对滚动加载功能进行了重大改进，现在可以正确处理 Unsplash 的无限滚动。

## 快速测试

### 1. 运行测试脚本

```bash
# 基础测试（使用默认配置）
python test_unsplash_scroll.py

# 自定义配置测试
python test_unsplash_scroll.py --max-scrolls 40 --scroll-delay 3500 --stable-checks 5

# 对比不同配置
python test_unsplash_scroll.py --compare
```

### 2. 通过 API 使用

#### 2.1 创建 Job 时指定配置

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Unsplash Photos",
    "start_url": "https://unsplash.com/",
    "description": "抓取 Unsplash 图片",
    "status": "active",
    "config": {
      "use_stealth": true,
      "auto_scroll": true,
      "max_scrolls": 30,
      "scroll_delay": 3000,
      "stable_checks": 5
    },
    "selectors": [
      {
        "name": "photo_url",
        "css": "img[src*=\"unsplash\"]",
        "attr": "src",
        "limit": 100
      },
      {
        "name": "photo_link",
        "css": "a[href*=\"/photos/\"]",
        "attr": "href",
        "limit": 100
      }
    ]
  }'
```

#### 2.2 执行 Job

```bash
# 创建后会返回 job_id，比如 id=1
curl -X POST http://localhost:8000/runs/jobs/1/run \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://unsplash.com/",
    "limit": 100
  }'
```

#### 2.3 查看结果

```bash
# 获取执行记录（返回 run_id）
curl http://localhost:8000/runs

# 查看具体结果（假设 run_id=1）
curl http://localhost:8000/runs/1/results

# 导出 CSV
curl http://localhost:8000/runs/1/export > unsplash_photos.csv
```

### 3. 通过前端 UI 使用

1. 启动应用：
   ```bash
   cd services/api/app
   python main.py
   ```

2. 打开浏览器访问：
   ```
   http://localhost:8000/services/web/index-v2.html
   ```

3. 创建任务：
   - 输入 URL: `https://unsplash.com/`
   - 点击"Load Page"
   - 使用可视化选择器选择元素
   - 在"高级配置"中设置滚动参数

4. 高级配置示例（在前端界面的配置区域）：
   ```json
   {
     "use_stealth": true,
     "auto_scroll": true,
     "max_scrolls": 30,
     "scroll_delay": 3000,
     "stable_checks": 5
   }
   ```

## 配置参数说明

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `use_stealth` | `true` | **必须启用**，隐藏 webdriver 特征 |
| `auto_scroll` | `true` | 启用自动滚动 |
| `max_scrolls` | `30` | 最多滚动 30 次（加载约 300-600 张图片） |
| `scroll_delay` | `3000` | 每次滚动后等待 3 秒（毫秒） |
| `stable_checks` | `5` | 连续 5 次无变化才停止 |

### 根据需求调整

**如果想要更多图片**：
```json
{
  "max_scrolls": 50,
  "scroll_delay": 3500,
  "stable_checks": 5
}
```

**如果想要快速测试**：
```json
{
  "max_scrolls": 10,
  "scroll_delay": 2000,
  "stable_checks": 2
}
```

## 主要改进

### 1. 智能内容检测
- ✅ 不仅检测页面高度，还检测实际元素数量
- ✅ 多种选择器自动适配（figure、img、article 等）

### 2. 加载指示器等待
- ✅ 自动检测 loading/spinner 元素
- ✅ 等待加载动画消失后才继续

### 3. 平滑滚动
- ✅ 分步滚动，模拟真实用户行为
- ✅ 避免被反爬虫检测

### 4. 多次稳定性检查
- ✅ 连续多次检测无变化才停止
- ✅ 防止网络延迟误判

### 5. 备用滚动策略
- ✅ 上下滚动触发 Intersection Observer
- ✅ 强制加载懒加载图片

## 数据库迁移

如果你已经有现有的数据库，需要运行迁移脚本：

```bash
python migrate_add_config.py
```

如果是新安装，应用会自动创建包含新字段的数据库。

## 故障排查

### 问题 1: 仍然只能加载部分内容

**解决方法**：增加 `scroll_delay` 和 `max_scrolls`

```json
{
  "scroll_delay": 4000,
  "max_scrolls": 40
}
```

### 问题 2: 被反爬虫拦截（403 错误）

**解决方法**：确保启用隐身模式

```json
{
  "use_stealth": true
}
```

### 问题 3: 爬取时间太长

**解决方法**：减少滚动次数或缩短延迟

```json
{
  "max_scrolls": 15,
  "scroll_delay": 2000
}
```

### 问题 4: 超时错误

超时时间会根据配置自动计算：

```
超时 = (max_scrolls × scroll_delay / 1000) + 60 秒
```

例如：30 次滚动 × 3 秒 = 90 秒 + 60 秒 = 150 秒超时

如果仍然超时，可能是网络问题或 Unsplash 响应慢。

## Python 代码示例

### 完整示例：爬取 Unsplash 并保存到数据库

```python
import requests
import json

BASE_URL = "http://localhost:8000"

# 1. 创建 Job
job_data = {
    "name": "Unsplash Nature Photos",
    "start_url": "https://unsplash.com/t/nature",
    "description": "自然风光照片",
    "status": "active",
    "config": {
        "use_stealth": True,
        "auto_scroll": True,
        "max_scrolls": 30,
        "scroll_delay": 3000,
        "stable_checks": 5
    },
    "selectors": [
        {
            "name": "image_url",
            "css": "img[srcset]",
            "attr": "src",
            "limit": 200,
            "order_no": 0
        },
        {
            "name": "image_alt",
            "css": "img[alt]",
            "attr": "alt",
            "limit": 200,
            "order_no": 1
        },
        {
            "name": "photo_link",
            "css": "a[href*='/photos/']",
            "attr": "href",
            "limit": 200,
            "order_no": 2
        }
    ]
}

response = requests.post(f"{BASE_URL}/jobs", json=job_data)
print(f"创建 Job: {response.json()}")

job_id = response.json()['id']

# 2. 执行 Job
run_data = {
    "url": "https://unsplash.com/t/nature",
    "limit": 200
}

response = requests.post(f"{BASE_URL}/runs/jobs/{job_id}/run", json=run_data)
run_info = response.json()
run_id = run_info['run_id']
print(f"启动 Run: {run_info}")

# 3. 等待完成并查看结果
import time

max_wait = 300  # 最多等待 5 分钟
waited = 0

while waited < max_wait:
    response = requests.get(f"{BASE_URL}/runs/{run_id}")
    run_status = response.json()

    status = run_status['status']
    print(f"状态: {status}")

    if status in ['succeeded', 'failed']:
        break

    time.sleep(10)
    waited += 10

# 4. 获取结果
if status == 'succeeded':
    response = requests.get(f"{BASE_URL}/runs/{run_id}/results")
    results = response.json()
    print(f"共提取 {len(results)} 条数据")

    # 导出 CSV
    response = requests.get(f"{BASE_URL}/runs/{run_id}/export")
    with open('unsplash_nature.csv', 'w', encoding='utf-8') as f:
        f.write(response.text)
    print("已导出到 unsplash_nature.csv")
else:
    print(f"执行失败: {run_status.get('stats_json')}")
```

## 性能优化建议

1. **并发爬取多个类别**：
   ```python
   import asyncio

   categories = ['nature', 'animals', 'technology']
   tasks = [crawl_category(cat) for cat in categories]
   results = await asyncio.gather(*tasks)
   ```

2. **增量更新**：
   - 第一次：`max_scrolls=30`（全量）
   - 后续：`max_scrolls=5`（增量）

3. **避开高峰期**：
   - Unsplash 在某些时段可能更慢
   - 可以在凌晨或早晨爬取

## 进一步阅读

- 详细配置指南：[SCROLL_CONFIG_GUIDE.md](./SCROLL_CONFIG_GUIDE.md)
- 爬虫引擎源码：[crawler_runner_v2.py](./services/api/app/crawler_runner_v2.py:78-249)
- 测试脚本：[test_unsplash_scroll.py](./test_unsplash_scroll.py)

## 支持的其他网站

这个改进的滚动功能不仅适用于 Unsplash，还支持：

- Pinterest（瀑布流）
- 小红书（图文列表）
- Instagram（照片流）
- Twitter/X（推文流）
- 淘宝/京东（商品列表）
- 新闻网站（文章列表）

每个网站可能需要微调配置参数，请参考 [SCROLL_CONFIG_GUIDE.md](./SCROLL_CONFIG_GUIDE.md) 中的推荐配置。

## 问题反馈

如果遇到问题，请：

1. 查看日志输出（stderr）
2. 尝试调整配置参数
3. 使用测试脚本验证
4. 检查网络连接和 Unsplash 可访问性

---

祝爬取愉快！ 🎉
