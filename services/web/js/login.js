// ==================== 登录功能 ====================

function showLoginModal() {
    const modal = document.createElement('div');
    modal.id = 'loginModal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        animation: fadeIn 0.3s ease;
    `;
    modal.innerHTML = `
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 600px;
            width: 90%;
            overflow: hidden;
            animation: slideUp 0.3s ease;
        ">
            <div style="
                background: rgba(0,0,0,0.1);
                padding: 1.5rem 2rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
            ">
                <h3 style="margin: 0; color: white; font-size: 1.3rem;">🔐 登录管理</h3>
                <button onclick="document.getElementById('loginModal').remove()" style="
                    background: rgba(255,255,255,0.2);
                    border: none;
                    color: white;
                    width: 36px;
                    height: 36px;
                    border-radius: 50%;
                    cursor: pointer;
                    font-size: 1.2rem;
                    transition: all 0.3s;
                ">✕</button>
            </div>
            <div style="padding: 2rem; color: white;">
                <p style="margin-bottom: 1.5rem; line-height: 1.6; font-size: 1rem; opacity: 0.95;">
                    该网站需要登录。请选择登录方式：
                </p>

                <div style="display: grid; gap: 1rem; margin-bottom: 1.5rem;">
                    <!-- iframe登录 -->
                    <button onclick="loginInIframe()" style="
                        background: rgba(255,255,255,0.15);
                        border: 2px solid rgba(255,255,255,0.3);
                        color: white;
                        padding: 1.2rem;
                        border-radius: 12px;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        gap: 1rem;
                        transition: all 0.3s;
                        backdrop-filter: blur(10px);
                    " onmouseover="this.style.background='rgba(255,255,255,0.25)'" onmouseout="this.style.background='rgba(255,255,255,0.15)'">
                        <span style="font-size: 2rem;">🖼️</span>
                        <div style="text-align: left; flex: 1;">
                            <div style="font-weight: 600; font-size: 1.05rem;">在页面内登录 (推荐)</div>
                            <small style="opacity: 0.9; font-size: 0.9rem;">支持密码登录和扫码登录</small>
                        </div>
                    </button>

                    <!-- Cookie导入 -->
                    <button onclick="showCookieImport()" style="
                        background: rgba(255,255,255,0.15);
                        border: 2px solid rgba(255,255,255,0.3);
                        color: white;
                        padding: 1.2rem;
                        border-radius: 12px;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        gap: 1rem;
                        transition: all 0.3s;
                        backdrop-filter: blur(10px);
                    " onmouseover="this.style.background='rgba(255,255,255,0.25)'" onmouseout="this.style.background='rgba(255,255,255,0.15)'">
                        <span style="font-size: 2rem;">📋</span>
                        <div style="text-align: left; flex: 1;">
                            <div style="font-weight: 600; font-size: 1.05rem;">导入Cookie</div>
                            <small style="opacity: 0.9; font-size: 0.9rem;">如果您已经有Cookie数据</small>
                        </div>
                    </button>

                    <!-- 浏览器弹出登录 -->
                    <button onclick="loginInBrowser()" style="
                        background: rgba(255,255,255,0.15);
                        border: 2px solid rgba(255,255,255,0.3);
                        color: white;
                        padding: 1.2rem;
                        border-radius: 12px;
                        cursor: pointer;
                        display: flex;
                        align-items: center;
                        gap: 1rem;
                        transition: all 0.3s;
                        backdrop-filter: blur(10px);
                    " onmouseover="this.style.background='rgba(255,255,255,0.25)'" onmouseout="this.style.background='rgba(255,255,255,0.15)'">
                        <span style="font-size: 2rem;">🌐</span>
                        <div style="text-align: left; flex: 1;">
                            <div style="font-weight: 600; font-size: 1.05rem;">独立浏览器登录 (推荐)</div>
                            <small style="opacity: 0.9; font-size: 0.9rem;">弹出浏览器窗口，完成后点击按钮</small>
                        </div>
                    </button>
                </div>

                <div style="padding: 1rem; background: rgba(255,255,255,0.15); border-radius: 12px; border-left: 4px solid rgba(255,255,255,0.5); backdrop-filter: blur(10px);">
                    <strong style="font-size: 1rem;">💡 提示：</strong>
                    <p style="margin: 0.5rem 0 0 0; font-size: 0.9rem; opacity: 0.95; line-height: 1.5;">
                        登录成功后，Cookie会自动保存，下次访问同一网站时会自动使用。
                    </p>
                </div>
            </div>
            <div style="padding: 1rem 2rem; display: flex; justify-content: flex-end;">
                <button onclick="document.getElementById('loginModal').remove()" style="
                    background: rgba(255,255,255,0.2);
                    border: none;
                    color: white;
                    padding: 0.75rem 1.5rem;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 1rem;
                    transition: all 0.3s;
                " onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">
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
    showToast('🔄 正在保存Cookie...', 'info');

    try {
        // 给iframe一些时间完成登录和设置Cookie
        await new Promise(resolve => setTimeout(resolve, 2000));

        document.getElementById('iframeLoginModal')?.remove();
        showToast('✅ Cookie已保存，正在重新加载页面...', 'success');

        // 等待一下再重新加载
        await new Promise(resolve => setTimeout(resolve, 1000));

        // 重新加载页面
        loadPage();
    } catch (error) {
        document.getElementById('iframeLoginModal')?.remove();
        showToast('⚠️ 登录过程出错，请重试', 'error');
    }
}

async function loginInBrowser() {
    document.getElementById('loginModal')?.remove();

    showToast('🌐 正在打开浏览器窗口...', 'info', 3000);

    // 显示进度提示
    const progressModal = document.createElement('div');
    progressModal.id = 'loginProgressModal';
    progressModal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.8);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
    `;
    progressModal.innerHTML = `
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 2rem;
            text-align: center;
            color: white;
            max-width: 400px;
        ">
            <div class="spinner" style="margin: 0 auto 1rem;"></div>
            <h3 style="margin-bottom: 1rem;">正在等待登录...</h3>
            <p style="opacity: 0.9; line-height: 1.6;">
                请在弹出的浏览器窗口中完成登录<br>
                登录完成后点击窗口顶部的"我已完成登录"按钮<br>
                或等待自动检测
            </p>
            <div style="margin-top: 1.5rem; padding: 1rem; background: rgba(255,255,255,0.15); border-radius: 8px;">
                <small>⏱️ 最长等待时间: 5分钟</small>
            </div>
        </div>
    `;
    document.body.appendChild(progressModal);

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 360000); // 6分钟超时

        const response = await fetch(`${API_BASE}/api/proxy/login-in-browser`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: currentUrl,
                timeout_ms: 300000 // 5分钟
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        document.getElementById('loginProgressModal')?.remove();

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || '请求失败');
        }

        const data = await response.json();

        if (data.success) {
            showToast(`✅ ${data.message}，已保存${data.cookie_count}个Cookie`, 'success', 5000);

            // 等待一下再重新加载
            await new Promise(resolve => setTimeout(resolve, 1000));

            // 重新加载页面
            loadPage();
        } else {
            throw new Error(data.error || '登录失败');
        }

    } catch (error) {
        document.getElementById('loginProgressModal')?.remove();

        if (error.name === 'AbortError') {
            showToast('⏱️ 登录超时，请重试', 'error', 5000);
        } else {
            showToast('❌ 浏览器登录失败: ' + error.message, 'error', 5000);
        }

        // 显示重试选项
        setTimeout(() => {
            const retry = confirm('登录失败，是否重试？');
            if (retry) {
                loginInBrowser();
            } else {
                showLoginModal();
            }
        }, 1000);
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
        showToast('🔍 正在检测是否需要登录...', 'info', 2000);

        const response = await fetch(`${API_BASE}/api/proxy/detect-login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: url,
                timeout_ms: 8000
            })
        });

        if (!response.ok) {
            console.warn('[Login] 登录检测失败');
            return false;
        }

        const data = await response.json();

        if (data.success && data.required) {
            console.log(`[Login] 检测到登录需求: ${data.reason} (置信度: ${data.confidence})`);

            // 自动显示登录弹窗
            showToast(`🔐 检测到需要登录: ${data.reason}`, 'info', 3000);
            setTimeout(() => {
                showLoginModal();
            }, 500);

            return true;
        }

        return false;

    } catch (error) {
        console.error('[Login] 检测错误:', error);
        return false;
    }
}

// 在页面加载完成后自动检测登录需求
window.addEventListener('load', function() {
    // 延迟1秒后检测，确保页面完全加载
    setTimeout(async () => {
        const urlInput = document.getElementById('urlInput');
        if (urlInput && urlInput.value) {
            await detectLoginRequirement(urlInput.value);
        }
    }, 1000);
});

// 添加CSS动画
const loginAnimationStyles = document.createElement('style');
loginAnimationStyles.textContent = `
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes slideUp {
        from {
            transform: translateY(50px);
            opacity: 0;
        }
        to {
            transform: translateY(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(loginAnimationStyles);

console.log('[Login] 登录功能模块已加载');
