## 🐛 页面自动刷新问题 - 解决方案

### 问题原因

从调试日志可以看到刷新由 `socket.onmessage @ index.html:198` 触发，这是 **VS Code Live Server** 的热重载 WebSocket。

你当前使用的地址是 `http://127.0.0.1:5500`，这是 Live Server 的端口。Live Server 会监听文件变化并自动刷新页面，这与我们的应用冲突。

### 解决方法

**请使用我们启动的 Python HTTP Server，而不是 Live Server：**

#### 方法1：使用已运行的服务器（推荐）

访问：**http://localhost:3000** (不是 5500)

这是我们启动的 Python HTTP Server（通过 `bash start-web.sh` 或 `python -m http.server 3000`）

#### 方法2：关闭 VS Code Live Server

1. 在 VS Code 中，点击右下角的 "Port: 5500" 或 "Go Live"
2. 点击"Stop Live Server"
3. 然后访问 `http://localhost:3000`

### 验证

正确的配置应该是：
- ✅ 前端：`http://localhost:3000` (Python HTTP Server)
- ✅ 后端：`http://localhost:8000` (Uvicorn FastAPI)

错误的配置（会导致刷新）：
- ❌ 前端：`http://localhost:5500` (VS Code Live Server - 有热重载)
- ❌ 后端：`http://localhost:8000`

### 如何确认

打开浏览器控制台，应该看到：
```
[Debug] 发起网络请求: http://127.0.0.1:8000/api/...  ← 注意这里应该是 localhost:3000 访问 8000 API
```

如果看到 5500 端口，说明还在使用 Live Server。

### 测试

切换到 `http://localhost:3000` 后：
1. 加载页面
2. 选择字段
3. 点击"预览数据"或"导出数据"
4. **页面应该不会再刷新了** ✅
