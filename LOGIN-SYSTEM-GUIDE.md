# 🔐 SeenFetch 登录系统使用指南

## ✅ 系统已完成并测试成功

登录系统已经完整实现并在 tvmaze.com 上测试成功。

---

## 📋 功能概览

SeenFetch现在支持三种登录方式来抓取需要登录才能访问的网页：

1. **手动Cookie导入** ⭐ **推荐**
2. iframe内嵌登录
3. 浏览器弹窗登录

---

## 🎯 推荐方式：手动Cookie导入

### 为什么推荐？

- ✅ **最可靠**：直接使用真实浏览器的Cookie
- ✅ **最简单**：复制粘贴即可
- ✅ **最快速**：无需等待Playwright
- ✅ **最准确**：保证是登录成功后的真实Cookie

### 使用步骤

#### 步骤1：在真实浏览器中登录

1. 打开Chrome/Firefox/Edge
2. 访问目标网站并完成登录（如 https://www.tvmaze.com/login）
3. 确认登录成功（右上角显示用户名）

#### 步骤2：获取PHPSESSID

方法A - 使用浏览器开发者工具：
1. 按 F12 打开开发者工具
2. 切换到 **Application** 标签（Chrome）或 **Storage** 标签（Firefox）
3. 左侧点击 **Cookies** → 选择网站域名
4. 找到 `PHPSESSID`（或类似的会话Cookie）
5. 复制它的 **Value**

方法B - 使用控制台：
```javascript
// 在已登录页面的控制台执行
document.cookie.split(';').forEach(c => {
    const [name, value] = c.trim().split('=');
    if (name.includes('PHP') || name.includes('session')) {
        console.log(`${name}: ${value}`);
    }
});
```

#### 步骤3：在SeenFetch中导入Cookie

在SeenFetch前端的浏览器控制台（F12）执行：

```javascript
// 替换value为你的真实值
const manualCookies = [{
    "name": "PHPSESSID",
    "value": "你复制的Cookie值",  // ⬅️ 替换这里
    "domain": "www.tvmaze.com",    // ⬅️ 替换为目标网站域名
    "path": "/",
    "secure": false,
    "httpOnly": true,
    "sameSite": "Lax"
}];

fetch('http://127.0.0.1:8000/api/proxy/cookies/import', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        domain: 'www.tvmaze.com',  // ⬅️ 替换为目标网站域名
        cookies: manualCookies
    })
})
.then(r => r.json())
.then(data => console.log('✅ Cookie导入成功:', data));
```

#### 步骤4：验证登录

1. 在SeenFetch中访问需要登录的URL
2. 查看后端日志：
   ```
   [Render] 🔍 登录状态检查:
   [Render]   - 登出按钮: True      ✅
   [Render]   - 登录表单: False     ✅
   ```
3. 前端iframe应该显示登录后的内容

---

## 🔄 自动登录检测

### 工作原理

当你访问一个URL时，SeenFetch会自动：

1. **检测是否需要登录**（四层检测）：
   - URL包含login/signin关键词
   - 页面包含密码输入框
   - 页面包含登录表单
   - 页面包含"请登录"等提示文本

2. **检查是否已有Cookie**：
   - 如果已保存该域名的Cookie → 跳过提示
   - 如果没有Cookie → 显示登录弹窗

3. **防止重复提示**：
   - 5分钟内不会重复提示同一个域名

### 登录弹窗选项

当检测到需要登录时，会显示紫色渐变弹窗，提供3个选项：

1. **iframe内嵌登录**（推荐用于简单网站）
   - 在当前页面的iframe中登录
   - 适合没有严格安全限制的网站

2. **浏览器弹窗登录**（适合复杂网站）
   - 打开独立的Playwright浏览器窗口
   - 更真实的浏览器环境
   - **注意**：需要手动点击"我已完成登录"按钮

3. **导入Cookie**（最可靠）
   - 手动粘贴Cookie JSON
   - 适合所有情况

---

## 🛠️ Cookie管理

### 查看已保存的Cookie

在浏览器控制台执行：

```javascript
// 查看所有域名
fetch('http://127.0.0.1:8000/api/proxy/cookies/list')
    .then(r => r.json())
    .then(data => console.table(data.domains));

// 查看特定域名的Cookie详情
fetch('http://127.0.0.1:8000/api/proxy/cookies/inspect/tvmaze.com')
    .then(r => r.json())
    .then(data => {
        console.log('总Cookie数:', data.total_cookies);
        console.table(data.cookie_details);
    });
```

### 删除Cookie

```javascript
// 删除特定域名的Cookie
fetch('http://127.0.0.1:8000/api/proxy/cookies/tvmaze.com', {
    method: 'DELETE'
})
.then(r => r.json())
.then(data => console.log('✅ Cookie已删除:', data));
```

### 导出Cookie

```javascript
// 导出特定域名的Cookie
fetch('http://127.0.0.1:8000/api/proxy/cookies/export/tvmaze.com')
    .then(r => r.json())
    .then(data => {
        console.log('导出的Cookie:', data.cookies);
        // 可以保存到文件备用
    });
```

---

## 🔍 故障排查

### 问题1：Cookie已导入但页面还是未登录

**可能原因**：
- Cookie已过期
- Cookie的domain不匹配（如 www.example.com vs example.com）
- 需要额外的Cookie（某些网站需要多个Cookie）

**解决方法**：
1. 重新在真实浏览器登录
2. 复制最新的Cookie
3. 确认domain格式正确（带www或不带www）
4. 检查是否需要导入多个Cookie

### 问题2：登录检测不触发

**可能原因**：
- 5分钟内已经提示过
- 该域名已有Cookie（系统跳过提示）

**解决方法**：
```javascript
// 清除lastLoginCheck缓存
if (window.LoginSystem) {
    window.LoginSystem.lastLoginCheck = {};
    console.log('✅ 登录检测缓存已清除');
}
```

### 问题3：浏览器弹窗立即关闭

**原因**：广告Cookie误触发检测（已修复）

**解决方法**：
1. 重启后端服务器（应用最新修复）
2. 或使用手动Cookie导入方式

---

## 📊 成功标志

### 后端日志

登录成功后，后端日志应该显示：

```
[API] ✅ 找到域名 tvmaze.com 的 X 个Cookie
[Render] ✅ 已注入 X 个Cookie
[Render] 🔑 发现会话Cookie: ['PHPSESSID']
[Render] 🔍 登录状态检查:
[Render]   - 登出按钮: True        ✅
[Render]   - 账户菜单: True/False
[Render]   - 登录表单: False       ✅
[Render]   - 页面标题: XXX (不是Login)
📊 HTML length: XXXXX bytes (明显大于未登录时)
```

### 前端显示

- iframe中显示登录后的内容
- 有账户菜单或用户名
- 有"退出"或"Logout"按钮
- 内容比未登录时更丰富

---

## 🎯 最佳实践

### 1. 使用正确的URL

确保URL的domain与Cookie的domain一致：

```javascript
// ✅ 正确
Cookie domain: www.tvmaze.com
访问URL: https://www.tvmaze.com/shows

// ❌ 错误
Cookie domain: www.tvmaze.com
访问URL: https://tvmaze.com/shows  （缺少www）
```

### 2. 定期更新Cookie

Session cookie通常有过期时间，建议：
- 每次使用前重新登录并获取最新Cookie
- 或在真实浏览器保持登录状态

### 3. 保护Cookie安全

Cookie包含敏感信息：
- 不要分享给他人
- 不要提交到版本控制系统
- 定期更换密码后重新获取

### 4. 测试Cookie有效性

导入Cookie后，先测试简单页面：
- ✅ 访问网站首页
- ✅ 访问个人资料页
- ✅ 确认能看到登录后的内容
- ❌ 再访问复杂的目标页面

---

## 🚀 完整示例：tvmaze.com

### 步骤1：登录
```
1. 浏览器访问 https://www.tvmaze.com/login
2. 输入用户名和密码
3. 点击 "Log in"
4. 确认右上角显示用户名
```

### 步骤2：获取Cookie
```javascript
// 在 www.tvmaze.com 的控制台执行
document.cookie.split(';').find(c => c.includes('PHPSESSID'));
// 输出类似: " PHPSESSID=9lci6o525q92fajcfjoc37sopd"
```

### 步骤3：导入到SeenFetch
```javascript
// 在 SeenFetch 前端控制台执行
const manualCookies = [{
    "name": "PHPSESSID",
    "value": "9lci6o525q92fajcfjoc37sopd",
    "domain": "www.tvmaze.com",
    "path": "/",
    "secure": false,
    "httpOnly": true,
    "sameSite": "Lax"
}];

fetch('http://127.0.0.1:8000/api/proxy/cookies/import', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        domain: 'www.tvmaze.com',
        cookies: manualCookies
    })
}).then(r => r.json()).then(console.log);
```

### 步骤4：测试
```
1. 在SeenFetch中输入: https://www.tvmaze.com/shows
2. 点击"开始提取"
3. 查看后端日志确认登录状态
4. iframe应显示完整的节目列表
```

---

## 📞 支持

如果遇到问题：

1. **查看后端日志**：所有Cookie操作都有详细日志
2. **使用诊断工具**：参考 `DIAGNOSTIC-TESTS.md`
3. **检查Cookie格式**：使用 `/api/proxy/cookies/inspect/{domain}` endpoint

---

## 🎉 总结

SeenFetch的登录系统现在已经完全可用：

- ✅ 自动检测登录需求
- ✅ 多种登录方式支持
- ✅ Cookie持久化存储
- ✅ 完善的错误处理
- ✅ 详细的诊断日志

**推荐使用手动Cookie导入方式**，这是最可靠的方法，已在 tvmaze.com 上验证成功！
