# 🔧 故障排查指南

## 问题：Playwright 超时错误

### 错误信息
```
Page.goto: Timeout 30000ms exceeded.
navigating to "https://unsplash.com/", waiting until "load"
```

### 原因分析

1. **Playwright 浏览器未安装**
2. **网络问题**（unsplash.com 访问慢或被限制）
3. **目标网站反爬虫保护**

---

## 解决方案

### 步骤 1：检查 Playwright 浏览器

Playwright 需要先安装浏览器才能工作。

在你的虚拟环境中执行：

```bash
# Windows (PowerShell)
.venv\Scripts\activate
python -m playwright install chromium

# macOS/Linux
source .venv/bin/activate
python -m playwright install chromium
```

**安装完成后**，你应该看到类似输出：
```
Downloading Chromium 120.0.6099.109 (playwright build v1097) from https://playwright.azureedge.net/builds/chromium/1097/chromium-win64.zip
100% [====================]
Chromium 120.0.6099.109 (playwright build v1097) downloaded to ...
```

### 步骤 2：验证安装

```bash
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); browser = p.chromium.launch(); print('✅ Playwright 工作正常'); browser.close()"
```

如果看到 `✅ Playwright 工作正常`，说明安装成功！

### 步骤 3：重启服务器

```bash
cd services/api
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 测试建议

### 推荐测试网站（从简单到复杂）

1. **✅ http://example.com** - 最简单，无反爬虫
2. **✅ https://httpbin.org/html** - 测试用网站
3. **✅ https://www.baidu.com** - 国内网站
4. **⚠️ https://unsplash.com** - 可能较慢或有反爬虫

### 测试步骤

1. 打开浏览器访问 http://localhost:8000/index.html
2. 在输入框输入 `http://example.com`
3. 点击"开始提取"

**预期结果**：
- 页面加载成功
- iframe 中显示目标网站
- 控制台显示 `[Main] HTML received, length: XXX chars`

---

## 常见问题

### Q1: 仍然超时怎么办？

**方案 A：增加超时时间**

修改 `services/web/js/index-v2.js`：

```javascript
body: JSON.stringify({ url, timeout_ms: 60000 })  // 改为 60 秒
```

**方案 B：使用智能模式**

智能模式配备了更好的反爬虫技术：
1. 点击页面顶部的"智能识别"按钮
2. 输入 URL
3. 点击"开始提取"

### Q2: 为什么智能模式能成功？

从你的日志可以看到：
```
[SmartExtractor] 使用新版爬虫，配置: {'auto_scroll': True, 'use_stealth': True, 'wait_for': None}
INFO: 127.0.0.1:50051 - "POST /api/smart/analyze HTTP/1.1" 200 OK
```

智能模式使用了：
- ✅ 隐身模式（绕过反爬虫检测）
- ✅ 自动滚动（加载动态内容）
- ✅ Markdown 分析（更精准）

**建议**：如果手动模式失败，优先使用智能模式！

### Q3: 网络代理问题

如果你在公司网络或使用了代理：

```python
# 在 services/api/app/proxy.py 的 Playwright 配置中添加：
browser = p.chromium.launch(
    headless=True,
    proxy={
        "server": "http://your-proxy:port"
    }
)
```

### Q4: 防火墙/杀毒软件

某些安全软件可能阻止 Playwright 下载浏览器或访问网站：
- 临时关闭防火墙/杀毒软件
- 将 Playwright 可执行文件添加到白名单

---

## 调试技巧

### 1. 查看完整错误堆栈

浏览器控制台 → Network 标签 → 找到失败的请求 → Response

### 2. 手动测试 Playwright

创建测试脚本 `test_playwright.py`：

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # 显示浏览器
    page = browser.new_page()

    print("正在访问 unsplash.com...")
    page.goto("https://unsplash.com", timeout=60000)

    print(f"标题: {page.title()}")
    print(f"URL: {page.url}")
    print("✅ 成功！")

    browser.close()
```

运行：
```bash
python test_playwright.py
```

### 3. 使用非无头模式调试

修改 `services/api/app/proxy.py`：

```python
browser = p.chromium.launch(
    headless=False,  # 改为 False，可以看到浏览器窗口
    # ...
)
```

这样可以直观看到浏览器的行为。

---

## Service Worker 相关

### 验证 Service Worker 工作

1. 浏览器 F12 → Application → Service Workers
2. 应该看到 `/sw.js` 状态为 **activated**

### 重新注册 Service Worker

如果 Service Worker 有问题：

```javascript
// 浏览器控制台执行：
navigator.serviceWorker.getRegistrations().then(regs => {
    regs.forEach(reg => reg.unregister());
    console.log('已注销所有 Service Worker，刷新页面重新注册');
});
```

然后刷新页面（Ctrl+F5）。

---

## 成功案例

根据你的日志，**智能模式已经成功**了：

```
[SmartExtractor] 使用新版爬虫
INFO: "POST /api/smart/analyze HTTP/1.1" 200 OK
[SmartMode] 显示分析结果, 字段数: 7
```

这说明：
- ✅ Playwright 可以访问 unsplash.com（智能模式下）
- ✅ Service Worker 正常工作
- ✅ 后端 API 正常

**只是手动模式的超时设置可能不够**。

---

## 推荐配置

对于 **unsplash.com** 这类复杂网站：

### 选项 1：优先使用智能模式
- 自动处理反爬虫
- 更高的成功率

### 选项 2：调整手动模式超时
```javascript
// services/web/js/index-v2.js
body: JSON.stringify({
    url,
    timeout_ms: 90000  // 90 秒
})
```

### 选项 3：使用更简单的测试网站
- http://example.com
- https://httpbin.org/html
- https://www.bing.com

---

## 联系支持

如果以上方案都无法解决：

1. 运行诊断脚本（见下）
2. 收集完整的错误日志
3. 提供网络环境信息（是否使用代理、防火墙等）

### 诊断脚本

```bash
# 创建 diagnostics.py
cat > diagnostics.py << 'EOF'
import sys
import subprocess

print("=== 系统诊断 ===\n")

# 1. Python 版本
print(f"Python 版本: {sys.version}")

# 2. Playwright 安装
try:
    import playwright
    print(f"✅ Playwright 版本: {playwright.__version__}")
except ImportError:
    print("❌ Playwright 未安装")

# 3. 浏览器安装
result = subprocess.run([sys.executable, "-m", "playwright", "install", "--dry-run"],
                       capture_output=True, text=True)
print(f"浏览器状态:\n{result.stdout}")

# 4. 网络测试
import urllib.request
try:
    urllib.request.urlopen("https://unsplash.com", timeout=10)
    print("✅ 可以访问 unsplash.com")
except Exception as e:
    print(f"❌ 无法访问 unsplash.com: {e}")

print("\n=== 诊断完成 ===")
EOF

python diagnostics.py
```

---

## 快速参考

| 问题 | 解决方案 | 优先级 |
|------|---------|--------|
| Playwright 浏览器未安装 | `python -m playwright install chromium` | ⭐⭐⭐ |
| 超时 | 使用智能模式 / 增加超时时间 | ⭐⭐⭐ |
| 网络慢 | 测试简单网站（example.com） | ⭐⭐ |
| 反爬虫 | 使用智能模式 | ⭐⭐⭐ |
| Service Worker 问题 | 注销重新注册 | ⭐ |

---

**✨ 提示**：根据你的日志，智能模式已经工作正常，建议优先使用智能模式！
