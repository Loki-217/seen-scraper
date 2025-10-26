# 智能识别功能测试指南

## ⚠️ 重要：确保干净环境

智能识别功能需要 **Job 没有配置** 才会触发。如果之前有测试数据，需要清理。

## 🔍 诊断步骤

### 步骤 1：检查代码是否完整

运行诊断脚本：
```bash
python diagnose_smart_detection.py
```

应该看到：
```
✓ 所有核心文件都存在
✓ runs.py 中包含智能识别代码
✓ 规则库加载成功，包含 12 条规则
```

### 步骤 2：清理旧数据（重要！）

删除数据库，确保干净环境：
```bash
rm -f seen.db
```

### 步骤 3：启动应用

```bash
cd services/api/app
python main.py
```

### 步骤 4：测试智能识别

1. 打开浏览器：`http://localhost:8000/services/web/index.html`

2. 输入 URL：`https://unsplash.com/`

3. 配置一个字段：
   - 点击页面上的任意图片
   - 命名字段为 "图片"

4. 点击"开始采集"

5. **立即查看终端输出**

## ✅ 预期的终端输出

如果智能识别正常工作，你应该看到：

```
[Run] 开始采集: https://unsplash.com/
[Run] Job 无配置，启动智能识别...
[Analyzer] 开始分析: https://unsplash.com/
[Analyzer] 域名: unsplash.com
[Analyzer] ✓ 匹配本地规则: Unsplash (置信度: 1.0)
[Analyzer] 创建缓存: unsplash.com
[Run] ✓ 智能识别完成:
[Run]   - 网站: Unsplash
[Run]   - 类型: photo_sharing
[Run]   - 加载方式: infinite_scroll
[Run]   - 置信度: 1.0
[Run]   - 来源: local_rules
[Run] 最终配置: {'use_stealth': True, 'auto_scroll': True, 'max_scrolls': 30, 'scroll_delay': 3000, 'stable_checks': 5, 'wait_for': None}
[Run] 使用配置: {'use_stealth': True, 'auto_scroll': True, 'max_scrolls': 30, 'scroll_delay': 3000, 'stable_checks': 5, 'wait_for': None}
[Run] 使用新版爬虫: .../crawler_runner_v2.py
[Run] 超时时间: 150 秒
[V2] Initializing enhanced crawler for: https://unsplash.com/
[V2] Stealth mode enabled
[V2] Starting crawl...
...
[Scroll] Starting enhanced auto-scroll
[Scroll] Config: maxScrolls=30, delay=3000ms, stableChecks=5
...
```

## ❌ 如果没有看到智能识别日志

### 情况 1：看到 "使用 Job 配置"

```
[Run] 使用 Job 配置: {...}
```

**原因**：Job 中已经有配置了（之前的测试留下的）

**解决**：
```bash
# 停止应用 (Ctrl+C)
rm -f seen.db
# 重新启动应用
python main.py
```

### 情况 2：看到 "使用默认配置"

```
[Run] 使用配置: {'use_stealth': True, 'auto_scroll': True, 'max_scrolls': 30, ...}
```

但**没有看到**"智能识别"的日志。

**原因**：可能是前端传了 config 字段，或者代码有问题

**解决**：
1. 检查前端代码 `services/web/js/index-v2.js` 第 771-781 行
2. 确保 `jobData` 对象**不包含** `config` 字段
3. 或者检查终端是否有错误信息

### 情况 3：完全没有日志

**原因**：应用没有正确启动或崩溃了

**解决**：
1. 检查是否有 Python 错误
2. 确保所有依赖都已安装：`pip install -r requirements.txt`
3. 检查端口 8000 是否被占用

### 情况 4：看到"智能识别失败"

```
[Run] 智能识别失败: ...
[Run] 使用默认配置
```

**原因**：智能识别模块出错了

**解决**：
1. 查看完整的错误信息
2. 检查是否缺少依赖包
3. 提供错误日志以便诊断

## 🔬 深度诊断

如果仍然有问题，可以手动测试每个组件：

### 测试 1：直接调用分析器

创建文件 `test_analyzer_direct.py`：

```python
import sys
sys.path.insert(0, 'services/api/app')

from website_analyzer import get_analyzer
from db import session_scope

url = "https://unsplash.com/"

analyzer = get_analyzer()

with session_scope() as session:
    result = analyzer.analyze(url, session)

    print("\n分析结果:")
    print(f"  网站: {result['site_name']}")
    print(f"  类型: {result['site_type']}")
    print(f"  加载方式: {result['load_type']}")
    print(f"  置信度: {result['confidence']}")
    print(f"  来源: {result['source']}")
    print(f"  配置: {result['config']}")
```

运行：
```bash
python test_analyzer_direct.py
```

应该输出：
```
[Analyzer] 开始分析: https://unsplash.com/
[Analyzer] 域名: unsplash.com
[Analyzer] ✓ 匹配本地规则: Unsplash (置信度: 1.0)

分析结果:
  网站: Unsplash
  类型: photo_sharing
  加载方式: infinite_scroll
  置信度: 1.0
  来源: local_rules
  配置: {'use_stealth': True, 'auto_scroll': True, 'max_scrolls': 30, ...}
```

### 测试 2：检查数据库

启动应用后，检查数据库：

```bash
sqlite3 seen.db

# 查看所有表
.tables

# 查看 Job 表
SELECT id, name, config_json FROM jobs;

# 查看缓存表
SELECT domain, site_name, load_type, source FROM website_configs;
```

**Job 表应该显示**：
- `config_json` 字段为 `NULL`（如果前端没传配置）
- 或者包含 JSON 字符串（如果之前有测试数据）

**website_configs 表应该包含**：
- unsplash.com 的缓存记录（第一次运行后）

## 📋 检查清单

运行前确认：

- [ ] 已删除旧的 `seen.db`
- [ ] 使用的是 `index.html`（不是 `index-v2.html`）
- [ ] 应用已正确启动（看到 "Uvicorn running on..."）
- [ ] 浏览器访问正确的地址（localhost:8000）
- [ ] 终端窗口可见（能看到日志输出）

## 🆘 仍然有问题？

提供以下信息：

1. **终端的完整输出**（从启动到执行采集）
2. **数据库内容**：
   ```bash
   sqlite3 seen.db "SELECT id, name, config_json FROM jobs;"
   ```
3. **浏览器控制台输出**（F12 打开开发者工具）
4. **使用的前端页面**（index.html 还是 index-v2.html？）

## 💡 提示

智能识别功能的触发条件：

```python
# 在 runs.py 的 _execute_run 函数中

if job.config_json:
    # 有配置 → 使用 Job 配置
    crawler_config = json.loads(job.config_json)
else:
    # 无配置 → 触发智能识别 ✅
    analyzer = get_analyzer()
    analysis_result = analyzer.analyze(url, session)
    crawler_config = analysis_result['config']
```

关键点：**`job.config_json` 必须为 `None`**

前端创建 Job 时不传 `config` 字段，`crud.py` 就会将 `config_json` 设为 `None`。
