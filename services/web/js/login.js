// ==================== 登录功能 ====================

function showLoginModal() {
    const modal = document.createElement('div');
    modal.id = 'loginModal';
    modal.className = 'modal-overlay active';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 600px;">
            <div class="modal-header">
                <h3>🔐 登录管理</h3>
                <button class="close-btn" onclick="document.getElementById('loginModal').remove()">✕</button>
            </div>
            <div class="modal-body">
                <p style="margin-bottom: 1rem; line-height: 1.6;">
                    该网站需要登录。请选择登录方式：
                </p>

                <div style="display: grid; gap: 1rem;">
                    <!-- iframe登录 -->
                    <button class="btn btn-primary" onclick="loginInIframe()" style="padding: 1rem; justify-content: flex-start; display: flex; align-items: center; gap: 1rem;">
                        <span style="font-size: 1.5rem;">🖼️</span>
                        <div style="text-align: left;">
                            <div style="font-weight: 600;">在页面内登录 (推荐)</div>
                            <small style="opacity: 0.8;">支持密码登录和扫码登录</small>
                        </div>
                    </button>

                    <!-- Cookie导入 -->
                    <button class="btn" style="background: #FFA726; color: white; padding: 1rem; justify-content: flex-start; display: flex; align-items: center; gap: 1rem;" onclick="showCookieImport()">
                        <span style="font-size: 1.5rem;">📋</span>
                        <div style="text-align: left;">
                            <div style="font-weight: 600;">导入Cookie</div>
                            <small style="opacity: 0.8;">如果您已经有Cookie数据</small>
                        </div>
                    </button>

                    <!-- 浏览器弹出登录 -->
                    <button class="btn" style="background: #FF7043; color: white; padding: 1rem; justify-content: flex-start; display: flex; align-items: center; gap: 1rem;" onclick="loginInBrowser()">
                        <span style="font-size: 1.5rem;">🌐</span>
                        <div style="text-align: left;">
                            <div style="font-weight: 600;">独立浏览器登录 (备用)</div>
                            <small style="opacity: 0.8;">如果页面内登录不可用</small>
                        </div>
                    </button>
                </div>

                <div style="margin-top: 1.5rem; padding: 1rem; background: #e3f2fd; border-radius: 8px; border-left: 4px solid #2196F3;">
                    <strong style="color: #1976D2;">💡 提示：</strong>
                    <p style="margin: 0.5rem 0 0 0; color: #555; font-size: 0.9rem;">
                        登录成功后，Cookie会自动保存，下次访问同一网站时会自动使用。
                    </p>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="document.getElementById('loginModal').remove()">
                    取消
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function loginInIframe() {
    document.getElementById('loginModal')?.remove();

    const loadingModal = document.createElement('div');
    loadingModal.id = 'iframeLoginModal';
    loadingModal.className = 'modal-overlay active';
    loadingModal.innerHTML = `
        <div class="modal-content" style="max-width: 90%; max-height: 90vh; width: 800px;">
            <div class="modal-header">
                <h3>🔐 登录页面</h3>
                <button class="close-btn" onclick="document.getElementById('iframeLoginModal').remove()">✕</button>
            </div>
            <div class="modal-body" style="padding: 0; max-height: 70vh; overflow: auto;">
                <div id="iframeLoginContent" style="min-height: 500px; display: flex; align-items: center; justify-content: center;">
                    <div>
                        <div class="spinner"></div>
                        <p style="margin-top: 1rem; color: #666;">正在加载登录页面...</p>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="document.getElementById('iframeLoginModal').remove()">
                    关闭
                </button>
                <button class="btn btn-primary" onclick="completeIframeLogin()">
                    ✅ 登录完成
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(loadingModal);

    try {
        const response = await fetch(`${API_BASE}/api/proxy/login-in-iframe`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: currentUrl,
                timeout_ms: 300000
            })
        });

        if (!response.ok) {
            throw new Error('加载登录页面失败');
        }

        const data = await response.json();

        if (data.success) {
            const container = document.getElementById('iframeLoginContent');
            // 创建iframe并设置srcdoc
            const iframe = document.createElement('iframe');
            iframe.style.cssText = 'width: 100%; height: 600px; border: none;';
            iframe.srcdoc = data.html;
            container.innerHTML = '';
            container.appendChild(iframe);

            showToast('✅ 登录页面已加载，请完成登录', 'success');
        } else {
            throw new Error(data.error || '加载失败');
        }

    } catch (error) {
        document.getElementById('iframeLoginModal')?.remove();
        alert('加载登录页面失败: ' + error.message);
        showLoginModal();
    }
}

async function completeIframeLogin() {
    document.getElementById('iframeLoginModal')?.remove();
    showToast('✅ Cookie已保存，请重新加载页面', 'success');
    // 重新加载页面
    loadPage();
}

async function loginInBrowser() {
    document.getElementById('loginModal')?.remove();

    showToast('🌐 正在打开浏览器窗口，请在弹出的窗口中完成登录...', 'info', 5000);

    try {
        const response = await fetch(`${API_BASE}/api/proxy/login-in-browser`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: currentUrl,
                timeout_ms: 300000
            })
        });

        if (!response.ok) {
            throw new Error('打开浏览器失败');
        }

        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${data.message}，已保存${data.cookie_count}个Cookie`, 'success');
            // 重新加载页面
            loadPage();
        } else {
            throw new Error(data.error || '登录失败');
        }

    } catch (error) {
        alert('浏览器登录失败: ' + error.message);
        showLoginModal();
    }
}

function showCookieImport() {
    document.getElementById('loginModal')?.remove();

    const modal = document.createElement('div');
    modal.id = 'cookieImportModal';
    modal.className = 'modal-overlay active';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 700px;">
            <div class="modal-header">
                <h3>📋 导入Cookie</h3>
                <button class="close-btn" onclick="document.getElementById('cookieImportModal').remove()">✕</button>
            </div>
            <div class="modal-body">
                <p style="margin-bottom: 1rem; line-height: 1.6;">
                    请粘贴从浏览器导出的Cookie JSON数据：
                </p>

                <textarea id="cookieInput"
                          style="width: 100%; height: 200px; padding: 0.75rem; border: 1px solid #e0e0e0; border-radius: 8px; font-family: monospace; font-size: 0.9rem;"
                          placeholder='[{"name": "session", "value": "...", "domain": "..."}]'></textarea>

                <div style="margin-top: 1rem; padding: 1rem; background: #fff3cd; border-radius: 8px; border-left: 4px solid #ffc107;">
                    <strong style="color: #856404;">💡 如何获取Cookie：</strong>
                    <ol style="margin: 0.5rem 0 0 1.5rem; color: #666; font-size: 0.9rem;">
                        <li>在浏览器中打开目标网站并登录</li>
                        <li>按F12打开开发者工具</li>
                        <li>切换到"Application"或"存储"标签</li>
                        <li>点击"Cookies"，复制所有Cookie</li>
                        <li>或使用浏览器扩展导出为JSON格式</li>
                    </ol>
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="document.getElementById('cookieImportModal').remove()">
                    取消
                </button>
                <button class="btn btn-primary" onclick="importCookies()">
                    ✅ 导入
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

async function importCookies() {
    const cookieInput = document.getElementById('cookieInput');
    const cookieText = cookieInput.value.trim();

    if (!cookieText) {
        alert('请输入Cookie数据');
        return;
    }

    try {
        const cookies = JSON.parse(cookieText);

        if (!Array.isArray(cookies)) {
            throw new Error('Cookie数据格式错误，应该是一个数组');
        }

        const response = await fetch(`${API_BASE}/api/proxy/import-cookies`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: currentUrl,
                cookies: cookies
            })
        });

        if (!response.ok) {
            throw new Error('导入失败');
        }

        const data = await response.json();

        if (data.success) {
            document.getElementById('cookieImportModal')?.remove();
            showToast(`✅ ${data.message}`, 'success');
            // 重新加载页面
            loadPage();
        } else {
            throw new Error(data.error || '导入失败');
        }

    } catch (error) {
        alert('导入Cookie失败: ' + error.message);
    }
}

// 自动检测登录需求
async function detectLoginRequirement(url) {
    try {
        const response = await fetch(`${API_BASE}/api/proxy/detect-login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                timeout_ms: 5000
            })
        });

        if (!response.ok) {
            console.warn('[Login] 登录检测失败');
            return false;
        }

        const data = await response.json();

        if (data.success && data.required) {
            console.log(`[Login] 检测到登录需求: ${data.reason} (置信度: ${data.confidence})`);

            // 显示登录提示
            const shouldLogin = confirm(
                `🔐 登录提示\n\n` +
                `检测到该网站需要登录：\n` +
                `${data.reason}\n\n` +
                `是否现在登录？`
            );

            if (shouldLogin) {
                showLoginModal();
                return true;
            }
        }

        return false;

    } catch (error) {
        console.error('[Login] 检测错误:', error);
        return false;
    }
}

console.log('[Login] 登录功能模块已加载');
