# iframe HTML 提取测试程序使用说明

## 概述

`test_iframe_html_extraction.py` 是一个测试工具，用于提取服务器通过 `/api/proxy/render` 端点渲染的HTML内容。这个HTML就是前端iframe中显示的内容。

## 功能特性

1. **提取HTML**: 调用API获取Playwright渲染后的HTML
2. **自动保存**: 将HTML和元数据保存到文件
3. **历史记录**: 查看所有提取过的HTML文件
4. **内容预览**: 查看HTML文件的详细信息和摘要
5. **最新链接**: 自动维护指向最新HTML的软链接

## 安装依赖

```bash
pip install httpx
```

或者安装完整项目依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 启动API服务器

首先确保API服务器正在运行：

```bash
cd services/api
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. 提取HTML

提取指定URL的HTML并保存：

```bash
python tests/test_iframe_html_extraction.py https://example.com

python tests/test_iframe_html_extraction.py https://unsplash.com/
```

输出示例：
```
🔄 正在渲染: https://example.com
📡 API端点: http://localhost:8000/api/proxy/render
⏱️  超时设置: 30000ms
✅ HTML提取成功
📄 标题: Example Domain
📏 HTML大小: 12345 字符
💾 HTML已保存: tests/output/iframe_html/20250103_120530_example_com.html
📋 元数据已保存: tests/output/iframe_html/20250103_120530_example_com.json
🔗 最新文件链接: tests/output/iframe_html/latest.html

✨ 完成! 最近一次渲染的HTML已保存
📂 文件路径: tests/output/iframe_html/20250103_120530_example_com.html
💡 查看内容: python tests/test_iframe_html_extraction.py --view 20250103_120530_example_com.html
```

### 3. 查看所有保存的HTML

列出所有提取过的HTML文件：

```bash
python tests/test_iframe_html_extraction.py --list
```

输出示例：
```
📚 找到 3 个HTML文件:

1. 20250103_120530_example_com.html
   📄 标题: Example Domain
   🔗 URL: https://example.com
   📏 大小: 12,345 字符
   🕒 时间: 20250103_120530

2. 20250103_115200_github_com.html
   📄 标题: GitHub
   🔗 URL: https://github.com
   📏 大小: 54,321 字符
   🕒 时间: 20250103_115200
```

### 4. 查看HTML内容摘要

查看特定HTML文件的详细信息：

```bash
python tests/test_iframe_html_extraction.py --view latest.html
```

或者查看特定文件：

```bash
python tests/test_iframe_html_extraction.py --view 20250103_120530_example_com.html
```

输出示例：
```
📖 查看文件: tests/output/iframe_html/latest.html

📋 元数据:
   🔗 URL: https://example.com
   📄 标题: Example Domain
   🕒 时间: 20250103_120530
   📏 大小: 12,345 字符

📝 HTML内容摘要:
   总长度: 12,345 字符

   前500字符预览:
   ======================================================================
   <!DOCTYPE html><html><head>
   <base href="https://example.com/">
   <link rel="stylesheet" href="https://cdnjs.cloudflare.com/...">
   ...
   ======================================================================

   ✅ 包含 <html> 标签
   ✅ 包含 <head> 标签
   ✅ 包含 <body> 标签
   ✅ 包含 <base> 标签（资源路径修复）
   ✅ 包含 Font Awesome CDN
   ✅ 包含注入的交互监听脚本

💡 使用浏览器打开: file:///home/user/seen-scraper/tests/output/iframe_html/latest.html
```

### 5. 自定义API地址

如果API服务器运行在其他地址：

```bash
python tests/test_iframe_html_extraction.py \
  --api-base http://192.168.1.100:8000 \
  https://example.com
```

### 6. 自定义超时时间

设置更长的渲染超时（默认30秒）：

```bash
python tests/test_iframe_html_extraction.py \
  --timeout 60000 \
  https://example.com
```

## 输出文件说明

### 目录结构

```
tests/output/iframe_html/
├── README.md                           # 目录说明
├── latest.html                         # 最新HTML（软链接）
├── latest.json                         # 最新元数据（软链接）
├── 20250103_120530_example_com.html    # HTML文件
├── 20250103_120530_example_com.json    # 元数据文件
└── ...
```

### HTML文件特点

提取的HTML包含以下特性（由 `/api/proxy/render` 自动添加）：

1. **`<base>` 标签**: 修复所有相对路径资源
   ```html
   <base href="https://example.com/">
   ```

2. **Font Awesome CDN**: 自动注入图标库
   ```html
   <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
   ```

3. **交互监听脚本**: 注入点击检测脚本
   ```javascript
   function seenElementClickListener(e) { ... }
   ```

4. **完整渲染**: Playwright自动滚动加载所有内容

### 元数据文件格式

每个HTML文件都有对应的JSON元数据：

```json
{
  "url": "https://example.com",
  "title": "Example Domain",
  "timestamp": "20250103_120530",
  "html_size": 12345,
  "filepath": "tests/output/iframe_html/20250103_120530_example_com.html"
}
```

## 在浏览器中查看

提取的HTML可以直接在浏览器中打开：

```bash
# Linux/Mac
open tests/output/iframe_html/latest.html

# Windows
start tests/output/iframe_html/latest.html
start tests/output/iframe_html/20251104_000239_unsplash.com_.clean.html

# 或者使用浏览器直接打开
file:///home/user/seen-scraper/tests/output/iframe_html/latest.html
```

## 常见问题

### 1. 连接被拒绝

```
❌ HTTP错误: Connection refused
```

**解决方案**: 确保API服务器正在运行：
```bash
cd services/api
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 2. 请求超时

```
⏰ 请求超时（60秒）
```

**解决方案**:
- 增加超时时间：`--timeout 90000`
- 检查网络连接
- 选择加载速度更快的页面

### 3. ModuleNotFoundError

```
ModuleNotFoundError: No module named 'httpx'
```

**解决方案**: 安装依赖
```bash
pip install httpx
```

## 工作流示例

### 典型测试流程

1. **启动服务器**
   ```bash
   cd services/api
   python -m uvicorn app.main:app --reload
   ```

2. **提取测试页面**
   ```bash
   python tests/test_iframe_html_extraction.py https://example.com
   ```

3. **查看结果**
   ```bash
   python tests/test_iframe_html_extraction.py --view latest.html
   ```

4. **在浏览器中验证**
   ```bash
   open tests/output/iframe_html/latest.html
   ```

5. **对比前端iframe显示**
   - 打开前端页面: `http://localhost:8000/visual-builder-v3.html`
   - 输入相同URL
   - 对比iframe中的显示与保存的HTML

### 批量测试多个URL

创建一个shell脚本：

```bash
#!/bin/bash
# test_multiple_urls.sh

URLS=(
    "https://example.com"
    "https://github.com"
    "https://stackoverflow.com"
)

for url in "${URLS[@]}"; do
    echo "Testing: $url"
    python tests/test_iframe_html_extraction.py "$url"
    sleep 2
done

python tests/test_iframe_html_extraction.py --list
```

## 调试技巧

### 检查HTML是否完整

```bash
python tests/test_iframe_html_extraction.py --view latest.html | grep "✅"
```

应该看到：
- ✅ 包含 `<html>` 标签
- ✅ 包含 `<head>` 标签
- ✅ 包含 `<body>` 标签
- ✅ 包含 `<base>` 标签
- ✅ 包含 Font Awesome CDN
- ✅ 包含注入的交互监听脚本

### 比较两次提取的差异

```bash
diff tests/output/iframe_html/20250103_120530_example_com.html \
     tests/output/iframe_html/20250103_130000_example_com.html
```

### 查看HTML文件大小

```bash
ls -lh tests/output/iframe_html/*.html
```

## 环境变量

可以通过环境变量配置：

```bash
export API_BASE=http://localhost:8000
python tests/test_iframe_html_extraction.py https://example.com
```

## 项目集成

这个工具可以集成到CI/CD流程中进行自动化测试：

```yaml
# .github/workflows/test-iframe.yml
name: Test iframe HTML Extraction

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Start API server
        run: |
          cd services/api
          python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &
          sleep 5
      - name: Test HTML extraction
        run: |
          python tests/test_iframe_html_extraction.py https://example.com
      - name: Verify HTML
        run: |
          python tests/test_iframe_html_extraction.py --view latest.html
```

## 相关文件

- **测试脚本**: `tests/test_iframe_html_extraction.py`
- **输出目录**: `tests/output/iframe_html/`
- **API端点**: `services/api/app/proxy.py` (第311-440行)
- **前端实现**: `services/web/visual-builder-v3.html` (第540-566行)

## 技术细节

### API流程

```
用户 → Python脚本
    ↓
POST /api/proxy/render {url, timeout_ms}
    ↓
API服务器 (proxy.py)
    ├─ 创建临时Playwright脚本
    ├─ 启动子进程
    └─ Playwright执行:
        ├─ 启动Chromium
        ├─ 访问页面
        ├─ 自动滚动加载
        ├─ 注入交互脚本
        ├─ 修复资源路径
        ├─ 添加<base>和CDN
        └─ 返回HTML
    ↓
Python脚本接收JSON {success, html, url, title}
    ↓
保存HTML和元数据到文件
```

### 与前端iframe的一致性

这个测试工具提取的HTML **完全相同** 于前端iframe中显示的HTML：

- 前端: `iframe.srcdoc = data.html`
- 测试工具: `file.write(data.html)`

因此可以用来：
1. 验证API返回的HTML是否正确
2. 调试iframe显示问题
3. 离线查看渲染结果
4. 对比不同时间的渲染差异

## 许可证

与主项目相同。
