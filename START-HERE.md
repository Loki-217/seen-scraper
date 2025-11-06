# SeenFetch 启动指南

## 🚀 快速启动

SeenFetch需要同时运行**后端API**和**前端Web服务器**。

### 方法1：使用提供的启动脚本（推荐）

```bash
# 在VS Code终端中执行
./start-web.sh
```

然后在浏览器访问：**http://localhost:3000**

### 方法2：使用VS Code Live Server扩展

1. 在VS Code中安装 **Live Server** 扩展
2. 打开 `services/web/index.html`
3. 右键选择 **"Open with Live Server"**
4. 自动打开浏览器访问 `http://127.0.0.1:5500`

### 方法3：手动启动

```bash
# 进入前端目录
cd services/web

# 启动HTTP服务器（选择其中一种）
python3 -m http.server 3000        # Python方式
# 或
npx http-server -p 3000           # Node.js方式
```

## 📌 重要说明

### 为什么需要HTTP服务器？

如果直接用浏览器打开 `file:///path/to/index.html`，会导致：
- ❌ `origin` 为 `null`
- ❌ CORS错误
- ❌ Cookie无法正常工作
- ❌ Blob URL继承null origin

通过HTTP服务器访问（`http://localhost:3000`）可以：
- ✅ 正常的origin（`http://localhost:3000`）
- ✅ Blob URL有正确的origin
- ✅ 无CORS限制
- ✅ Cookie和localStorage正常工作

## 🔧 服务器配置

- **前端Web服务器**: http://localhost:3000
- **后端API服务器**: http://localhost:8000

前端会自动连接到后端API。

## 🧪 测试登录系统

1. 访问 http://localhost:3000
2. 输入需要登录的网站（如 `https://www.tvmaze.com/shows`）
3. 点击"加载"
4. 等待登录检测弹窗出现
5. 选择登录方式完成登录
6. 刷新页面，应显示登录后的内容

## 📝 检查是否工作正常

在浏览器控制台中检查：
```javascript
// 应该看到正常的origin，而不是null
console.log(window.location.origin);  // 应该是 "http://localhost:3000"

// Blob URL的origin应该继承自父页面
const blob = new Blob(['test'], {type: 'text/html'});
const url = URL.createObjectURL(blob);
console.log(url);  // 应该是 "blob:http://localhost:3000/..."
```

如果看到 `blob:null/...` 说明还是通过file://协议打开的，需要使用HTTP服务器。
