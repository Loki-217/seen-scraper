# 🔍 Cookie登录诊断测试

当登录后刷新页面仍显示未登录内容时，使用以下测试找出问题。

---

## 测试步骤

### 1️⃣ **检查保存的Cookie详情**

在浏览器控制台（F12）执行：

```javascript
// 检查tvmaze.com的Cookie详情
fetch('http://127.0.0.1:8000/api/proxy/cookies/inspect/tvmaze.com')
  .then(r => r.json())
  .then(data => {
    console.log('=== Cookie详情 ===');
    console.log('总数:', data.total_cookies);
    console.log('会话Cookie数:', data.session_cookies);
    console.log('认证Cookie数:', data.auth_cookies);
    console.log('\n=== 所有Cookie ===');
    console.table(data.cookie_details);
    console.log('\n=== 分析 ===');
    console.log(data.analysis);
  });
```

**检查重点**：
- ✅ 是否有 `PHPSESSID` 或类似的会话Cookie？
- ✅ Cookie的 `domain` 是否为 `.tvmaze.com`？
- ✅ Cookie的 `secure` 属性是否为 `true`？（如果是，只能在HTTPS下使用）
- ✅ Cookie的 `value_length` 是否大于0？

---

### 2️⃣ **对比登录前后的后端日志**

重新测试登录流程，观察后端终端输出：

**未登录时（第一次访问）**：
```bash
python -m services.api.app.main  # 启动后端（如果未启动）
```

访问 `https://www.tvmaze.com/shows`，查看日志：
```
[API] ⚠️ 域名 tvmaze.com 没有保存的Cookie
[Render] Page loaded
[Render] 🔍 登录状态检查:
[Render]   - 登出按钮: False        ❌ 没有登出按钮
[Render]   - 账户菜单: False        ❌ 没有账户菜单
[Render]   - 登录表单: True         ✅ 有登录表单
```

**登录后（刷新页面）**：
```
[API] ✅ 找到域名 tvmaze.com 的 21 个Cookie
[Render] ✅ 已注入 21 个Cookie
[Render] Cookie[0] - name: PHPSESSID, domain: .tvmaze.com, path: /
[Render] 🔑 发现会话Cookie: ['PHPSESSID']
[Render]   - PHPSESSID: domain=.tvmaze.com, secure=?, httpOnly=?
[Render] Page loaded
[Render] 🔍 登录状态检查:
[Render]   - 登出按钮: ???          ❓ 关键指标
[Render]   - 账户菜单: ???          ❓ 关键指标
[Render]   - 登录表单: ???          ❓ 应该为False
```

**判断标准**：
- ✅ **成功**：登出按钮=True 或 账户菜单=True，登录表单=False
- ❌ **失败**：登出按钮=False 且 账户菜单=False，登录表单=True

---

### 3️⃣ **手动验证Playwright是否真的登录**

修改后端代码临时添加截图功能（可选）：

```python
# 在 proxy.py 的 page.goto() 之后添加
page.screenshot(path="/tmp/tvmaze_logged_in.png")
print("[DEBUG] Screenshot saved to /tmp/tvmaze_logged_in.png", file=sys.stderr)
```

然后查看截图，目视确认是否显示登录状态。

---

### 4️⃣ **检查Cookie的secure属性问题**

如果Cookie有 `secure: true`，但后端使用HTTP访问，Cookie会被忽略。

**测试**：在浏览器登录时观察Cookie：
```javascript
// 在登录后的tvmaze.com页面控制台执行
document.cookie.split(';').forEach(c => console.log(c.trim()));

// 或者查看浏览器的Application/Storage -> Cookies
```

检查 `PHPSESSID` 的 `Secure` 列：
- ✅ 如果是空（未勾选）：Cookie可以在HTTP和HTTPS下使用
- ⚠️ 如果是勾选：Cookie只能在HTTPS下使用，HTTP访问会被忽略

---

### 5️⃣ **检查Cookie domain格式**

Cookie的domain必须匹配访问的域名：

**正确的格式**：
```javascript
{
  "name": "PHPSESSID",
  "value": "abc123...",
  "domain": ".tvmaze.com",      // ✅ 带前导点，适用于所有子域名
  "path": "/"
}
```

**错误的格式**：
```javascript
{
  "domain": "www.tvmaze.com"    // ❌ 只适用于www子域名
  "domain": "tvmaze.com"        // ⚠️ 不适用于www子域名
}
```

---

## 常见问题和解决方案

### 问题1：Cookie已注入但页面仍未登录

**可能原因**：
1. Cookie的 `secure: true`，但Playwright访问的是HTTP（虽然你输入HTTPS，但可能有重定向）
2. Cookie的 `domain` 不匹配（如 `www.tvmaze.com` vs `tvmaze.com`）
3. 会话Cookie已过期
4. 网站需要额外的headers（User-Agent、Referer等）

**解决方案**：
```python
# 在保存Cookie时，强制设置secure=False（仅用于测试）
for cookie in cookies:
    cookie['secure'] = False  # 临时禁用secure限制
```

---

### 问题2：浏览器登录时获取的Cookie不完整

**可能原因**：
- 有些Cookie是HttpOnly，JavaScript无法读取
- 浏览器自动登录工具可能没捕获所有Cookie

**解决方案**：
使用浏览器扩展导出Cookie（如EditThisCookie、Cookie-Editor），然后手动导入。

---

### 问题3：域名标准化问题

**检查**：
```javascript
// 测试域名标准化
fetch('http://127.0.0.1:8000/api/proxy/cookies/list')
  .then(r => r.json())
  .then(data => {
    console.log('保存的域名:', data.domains.map(d => d.domain));
  });
```

如果看到 `www.tvmaze.com` 和 `tvmaze.com` 同时存在，说明域名标准化有问题。

---

## 🎯 快速诊断命令

将以下代码粘贴到浏览器控制台，一次性运行所有诊断：

```javascript
async function diagnoseLogin() {
    console.log('🔍 开始Cookie登录诊断...\n');

    // 1. 检查Cookie列表
    const list = await fetch('http://127.0.0.1:8000/api/proxy/cookies/list').then(r => r.json());
    console.log('1️⃣ 保存的域名:', list.domains);

    // 2. 检查tvmaze.com的Cookie详情
    const inspect = await fetch('http://127.0.0.1:8000/api/proxy/cookies/inspect/tvmaze.com').then(r => r.json());
    console.log('\n2️⃣ tvmaze.com Cookie详情:');
    console.log('  - 总数:', inspect.total_cookies);
    console.log('  - 会话Cookie:', inspect.session_cookies);
    console.log('  - Secure Cookie数:', inspect.analysis.secure_only_count);
    console.log('  - HttpOnly Cookie数:', inspect.analysis.httponly_count);

    // 3. 显示关键Cookie
    const sessionCookies = inspect.cookie_details.filter(c =>
        c.name.toLowerCase().includes('session') || c.name === 'PHPSESSID'
    );
    console.log('\n3️⃣ 关键会话Cookie:');
    console.table(sessionCookies);

    // 4. 问题诊断
    console.log('\n4️⃣ 问题诊断:');
    if (inspect.total_cookies === 0) {
        console.error('❌ 没有保存任何Cookie！请先完成登录流程。');
    } else if (inspect.session_cookies === 0) {
        console.warn('⚠️ 没有会话Cookie（PHPSESSID等），登录可能无效。');
    } else if (inspect.analysis.secure_only_count > 0) {
        console.warn(`⚠️ 有 ${inspect.analysis.secure_only_count} 个Cookie设置了secure=true，`);
        console.warn('   这些Cookie只能在HTTPS下使用。如果Playwright使用HTTP访问会被忽略。');
    } else {
        console.log('✅ Cookie配置看起来正常。');
    }

    console.log('\n📋 下一步：');
    console.log('1. 查看后端日志中的 [Render] 🔍 登录状态检查');
    console.log('2. 如果登出按钮=False且账户菜单=False，说明Cookie未生效');
    console.log('3. 检查Cookie的secure属性是否与访问协议匹配');
}

diagnoseLogin();
```

---

## 预期结果

**成功的登录流程应该显示**：

1. **后端日志**：
```
[Render] 🔑 发现会话Cookie: ['PHPSESSID']
[Render] 🔍 登录状态检查:
[Render]   - 登出按钮: True         ✅
[Render]   - 账户菜单: True         ✅
[Render]   - 登录表单: False        ✅
```

2. **前端iframe**：
   - 显示用户名/账户菜单
   - 显示"退出"或"Logout"按钮
   - 没有登录表单
   - 内容比未登录时更丰富

---

## 需要报告的信息

如果问题仍未解决，请提供：

1. **Cookie详情输出**（运行上面的 `diagnoseLogin()` 函数）
2. **后端日志中的登录状态检查部分**（包含🔍标记的那几行）
3. **页面截图**（登录后刷新的iframe内容）
4. **浏览器中tvmaze.com的Cookie**（Application -> Cookies -> https://www.tvmaze.com）

这些信息将帮助精确定位问题所在。
