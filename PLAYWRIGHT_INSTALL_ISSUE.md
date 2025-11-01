# Playwright 浏览器安装问题及解决方案

## 问题说明

当前环境无法下载 Playwright 浏览器，导致页面渲染失败。

### 错误信息
```
❌ HTML length: 0 bytes
INFO: "POST /api/proxy/render HTTP/1.1" 400 Bad Request
```

### 根本原因
网络环境限制，无法访问 Playwright CDN：
- https://playwright.azureedge.net (403 Forbidden)
- https://cdn.playwright.dev (403 Forbidden)
- https://playwright.download.prss.microsoft.com (403 Forbidden)

## 解决方案

### 方案 1：在本地环境运行（推荐）

如果你在本地有网络访问权限：

```bash
# 1. 克隆代码
git clone <your-repo-url>
cd seen-scraper

# 2. 安装依赖
pip install -r requirements.txt

# 3. 安装 Playwright 浏览器
playwright install chromium

# 4. 启动服务
uvicorn services.api.app.main:app --host 127.0.0.1 --port 8000
```

### 方案 2：手动下载浏览器（当前环境）

如果你能从其他地方下载 Playwright 浏览器：

1. 在有网络的机器上下载：
   ```bash
   playwright install chromium
   # 浏览器会被下载到：~/.cache/ms-playwright/
   ```

2. 压缩浏览器目录：
   ```bash
   cd ~/.cache/ms-playwright
   tar -czf playwright-chromium.tar.gz chromium-*
   ```

3. 传输到当前环境并解压：
   ```bash
   mkdir -p /root/.cache/ms-playwright
   cd /root/.cache/ms-playwright
   tar -xzf playwright-chromium.tar.gz
   ```

### 方案 3：使用 Docker（最简单）

创建 `docker-compose.yml`：

```yaml
version: '3.8'
services:
  seen-scraper:
    image: mcr.microsoft.com/playwright/python:v1.40.0-jammy
    working_dir: /app
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    command: |
      bash -c "
        pip install -r requirements.txt &&
        playwright install chromium &&
        uvicorn services.api.app.main:app --host 0.0.0.0 --port 8000
      "
```

启动：
```bash
docker-compose up
```

### 方案 4：使用系统 Chrome/Chromium

如果系统已安装 Chrome：

修改 `services/api/app/proxy.py`，添加 `executable_path` 参数：

```python
browser = p.chromium.launch(
    headless=True,
    executable_path='/usr/bin/google-chrome',  # 或 chromium-browser
    args=[...]
)
```

## 当前状态

✅ **代码是最新的，所有修复已完成：**
- 反iframe脚本正确注入
- Service Worker 包含 m.douban.com 代理
- Unsplash 特殊处理逻辑
- 7层 iframe 防护机制

❌ **唯一问题：无法下载 Playwright 浏览器**

## 验证修复生效

一旦浏览器安装成功，你应该看到：

**豆瓣（movie.douban.com/top250）：**
```
[Iframe-Protection] 🛡️ Anti-breakout script loaded
[Iframe-Protection] ✅ All protections applied successfully
[SW] 🔗 拦截代理请求: m.douban.com
```

**Unsplash（unsplash.com）：**
```
[Render] Detected Unsplash - using networkidle wait
[Render] Unsplash images detected
📊 HTML length: 50000+ bytes
```

## 需要帮助？

如果上述方案都不可行，请告诉我你的环境信息：
- 操作系统
- 是否有网络代理
- 是否可以使用 Docker
- 是否可以在本地运行

我可以提供更具体的解决方案。
