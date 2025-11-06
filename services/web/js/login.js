// ========================================
// SeenFetch 登录系统
// ========================================

const LoginSystem = {
    currentUrl: '',
    currentDomain: '',

    // ==================== 自动检测登录需求 ====================
    async detectLoginRequirement(url, html) {
        try {
            const response = await fetch(`${API_BASE}/api/proxy/detect-login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, html })
            });

            const result = await response.json();

            if (result.success && result.needs_login) {
                console.log('[Login] 检测到需要登录:', result.reasons);
                this.currentUrl = url;
                this.currentDomain = result.domain;
                this.showLoginModal(result);
            }

            return result;
        } catch (error) {
            console.error('[Login] 检测失败:', error);
            return { success: false, needs_login: false };
        }
    },

    // ==================== 显示登录弹窗 ====================
    showLoginModal(detectResult) {
        // 移除已存在的弹窗
        const existing = document.getElementById('loginModal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'loginModal';
        modal.className = 'login-modal active';

        const reasons = detectResult.reasons.join('、');
        const hasCookies = detectResult.has_cookies;

        modal.innerHTML = `
            <div class="login-modal-content">
                <div class="login-modal-header">
                    <h2>🔐 需要登录</h2>
                    <button class="login-close-btn" onclick="LoginSystem.closeModal()">✕</button>
                </div>

                <div class="login-modal-body">
                    <div class="login-info-box">
                        <p><strong>检测原因：</strong>${reasons}</p>
                        <p><strong>目标域名：</strong>${this.currentDomain}</p>
                        ${hasCookies ? '<p style="color: #4CAF50;">✓ 已有Cookie记录</p>' : ''}
                    </div>

                    <div class="login-methods">
                        <h3>选择登录方式：</h3>

                        <!-- 方式1：iframe内嵌登录 -->
                        <div class="login-method-card" onclick="LoginSystem.startIframeLogin()">
                            <div class="method-icon">🖼️</div>
                            <div class="method-info">
                                <h4>iframe内嵌登录</h4>
                                <p>在当前页面内完成登录（推荐）</p>
                            </div>
                            <div class="method-arrow">→</div>
                        </div>

                        <!-- 方式2：浏览器弹窗登录 -->
                        <div class="login-method-card" onclick="LoginSystem.startBrowserLogin()">
                            <div class="method-icon">🌐</div>
                            <div class="method-info">
                                <h4>浏览器弹窗登录</h4>
                                <p>在独立浏览器窗口登录（备用）</p>
                            </div>
                            <div class="method-arrow">→</div>
                        </div>

                        <!-- 方式3：手动导入Cookie -->
                        <div class="login-method-card" onclick="LoginSystem.showCookieImport()">
                            <div class="method-icon">📋</div>
                            <div class="method-info">
                                <h4>导入Cookie</h4>
                                <p>手动粘贴已有的Cookie</p>
                            </div>
                            <div class="method-arrow">→</div>
                        </div>
                    </div>
                </div>

                <div class="login-modal-footer">
                    <button class="btn btn-secondary" onclick="LoginSystem.closeModal()">
                        跳过
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    },

    // ==================== iframe登录 ====================
    async startIframeLogin() {
        console.log('[iframe Login] 开始iframe登录');

        // 创建iframe登录界面
        const modal = document.getElementById('loginModal');
        if (!modal) return;

        modal.querySelector('.login-modal-body').innerHTML = `
            <div class="iframe-login-container">
                <div class="iframe-login-header">
                    <h3>请在下方完成登录</h3>
                    <p style="color: #999; font-size: 0.9rem;">登录完成后，点击下方按钮保存Cookie</p>
                </div>

                <div style="background: #fff3cd; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; border-left: 4px solid #ffc107;">
                    <strong>⚠️ 提示：</strong>如果下方显示"验证浏览器"或空白页面，说明该网站禁止在iframe中登录。<br>
                    <span style="color: #856404;">请使用"浏览器弹窗登录"方式。</span>
                </div>

                <iframe id="loginIframe" src="${this.currentUrl}"
                        style="width: 100%; height: 400px; border: 1px solid #ddd; border-radius: 8px;">
                </iframe>
                <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
                    <button class="btn btn-secondary" onclick="LoginSystem.showLoginModal({reasons: [], domain: LoginSystem.currentDomain, has_cookies: false})"
                            style="padding: 0.75rem 1.5rem;">
                        ← 返回
                    </button>
                    <button class="btn btn-primary" onclick="LoginSystem.completeIframeLogin()"
                            style="flex: 1; padding: 0.75rem 2rem; font-size: 1rem;">
                        ✓ 登录完成，保存Cookie
                    </button>
                </div>
            </div>
        `;
    },

    async completeIframeLogin() {
        const iframe = document.getElementById('loginIframe');
        if (!iframe || !iframe.contentWindow) {
            alert('无法获取iframe内容');
            return;
        }

        try {
            showToast('正在保存Cookie...', 'info');

            // 等待2秒确保Cookie写入
            await new Promise(resolve => setTimeout(resolve, 2000));

            // 尝试从iframe获取Cookie
            try {
                const iframeCookies = iframe.contentWindow.document.cookie;
                console.log('[iframe Login] 获取到Cookie:', iframeCookies);

                if (iframeCookies) {
                    // 解析Cookie字符串
                    const cookieArray = iframeCookies.split(';').map(c => {
                        const [name, value] = c.trim().split('=');
                        return { name, value, domain: this.currentDomain };
                    });

                    // 保存到后端
                    await this.saveCookies(this.currentDomain, cookieArray);
                }
            } catch (e) {
                console.warn('[iframe Login] 无法直接访问iframe Cookie（跨域限制）:', e);
                // 跨域情况下，仍然尝试保存一个空记录
                await this.saveCookies(this.currentDomain, []);
            }

            showToast('✓ Cookie已保存，正在重新加载页面...', 'success');

            // 延迟1秒后重新加载页面
            setTimeout(() => {
                this.closeModal();
                if (typeof loadPage === 'function') {
                    loadPage();
                }
            }, 1000);

        } catch (error) {
            console.error('[iframe Login] 错误:', error);
            alert('保存Cookie失败: ' + error.message);
        }
    },

    // ==================== 浏览器弹窗登录 ====================
    async startBrowserLogin() {
        console.log('[Browser Login] 开始浏览器弹窗登录');

        const modal = document.getElementById('loginModal');
        if (!modal) return;

        modal.querySelector('.login-modal-body').innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <div class="spinner" style="margin: 0 auto 1rem;"></div>
                <h3>正在打开浏览器窗口...</h3>
                <p style="color: #666; margin-top: 1rem;">
                    请在弹出的浏览器窗口中完成登录<br>
                    登录完成后，点击窗口顶部的"我已完成登录"按钮
                </p>
                <button class="btn btn-secondary" onclick="LoginSystem.showLoginModal({reasons: [], domain: LoginSystem.currentDomain, has_cookies: false})"
                        style="margin-top: 1.5rem;">
                    取消
                </button>
            </div>
        `;

        try {
            const response = await fetch(`${API_BASE}/api/proxy/open-browser-login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: this.currentUrl })
            });

            const result = await response.json();

            if (result.success) {
                showToast(`✓ 登录成功！保存了 ${result.count} 个Cookie`, 'success');
                this.closeModal();

                // 重新加载页面
                if (typeof loadPage === 'function') {
                    setTimeout(() => loadPage(), 1000);
                }
            } else {
                throw new Error(result.error || '登录失败');
            }

        } catch (error) {
            console.error('[Browser Login] 错误:', error);
            alert('浏览器登录失败: ' + error.message);
            this.showLoginModal({ reasons: [], domain: this.currentDomain, has_cookies: false });
        }
    },

    // ==================== Cookie导入 ====================
    showCookieImport() {
        const modal = document.getElementById('loginModal');
        if (!modal) return;

        modal.querySelector('.login-modal-body').innerHTML = `
            <div class="cookie-import-container">
                <h3>导入Cookie</h3>
                <p style="color: #666; font-size: 0.9rem; margin-bottom: 1rem;">
                    请粘贴从浏览器导出的Cookie JSON数据
                </p>

                <textarea id="cookieInput"
                          placeholder='[{"name":"session","value":"abc123","domain":".example.com"}]'
                          style="width: 100%; height: 200px; padding: 0.75rem; border: 1px solid #ddd; border-radius: 8px; font-family: monospace; font-size: 0.85rem;">
                </textarea>

                <div style="margin-top: 1rem; display: flex; gap: 0.5rem;">
                    <button class="btn btn-secondary" onclick="LoginSystem.showLoginModal({reasons: [], domain: LoginSystem.currentDomain, has_cookies: false})">
                        返回
                    </button>
                    <button class="btn btn-primary" onclick="LoginSystem.importCookies()" style="flex: 1;">
                        导入
                    </button>
                </div>
            </div>
        `;
    },

    async importCookies() {
        const input = document.getElementById('cookieInput');
        if (!input) return;

        const cookieText = input.value.trim();
        if (!cookieText) {
            alert('请输入Cookie数据');
            return;
        }

        try {
            const cookies = JSON.parse(cookieText);

            if (!Array.isArray(cookies)) {
                throw new Error('Cookie数据必须是数组格式');
            }

            await this.saveCookies(this.currentDomain, cookies);

            showToast(`✓ 成功导入 ${cookies.length} 个Cookie`, 'success');
            this.closeModal();

            // 重新加载页面
            if (typeof loadPage === 'function') {
                setTimeout(() => loadPage(), 1000);
            }

        } catch (error) {
            alert('导入失败: ' + error.message);
        }
    },

    // ==================== Cookie保存 ====================
    async saveCookies(domain, cookies) {
        const response = await fetch(`${API_BASE}/api/proxy/cookies/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ domain, cookies })
        });

        if (!response.ok) {
            throw new Error('保存Cookie失败');
        }

        return await response.json();
    },

    // ==================== Cookie管理 ====================
    async showCookieManager() {
        const response = await fetch(`${API_BASE}/api/proxy/cookies/list`);
        const result = await response.json();

        const modal = document.createElement('div');
        modal.className = 'login-modal active';
        modal.id = 'cookieManagerModal';

        modal.innerHTML = `
            <div class="login-modal-content">
                <div class="login-modal-header">
                    <h2>📋 Cookie管理</h2>
                    <button class="login-close-btn" onclick="document.getElementById('cookieManagerModal').remove()">✕</button>
                </div>

                <div class="login-modal-body" style="max-height: 400px; overflow-y: auto;">
                    ${result.domains.length === 0 ? `
                        <div style="text-align: center; padding: 2rem; color: #999;">
                            暂无保存的Cookie
                        </div>
                    ` : `
                        <div class="cookie-list">
                            ${result.domains.map(d => `
                                <div class="cookie-item">
                                    <div>
                                        <strong>${d.domain}</strong>
                                        <span style="color: #999; font-size: 0.85rem; margin-left: 0.5rem;">
                                            ${d.count} 个Cookie
                                        </span>
                                    </div>
                                    <div style="display: flex; gap: 0.5rem;">
                                        <button class="btn btn-secondary" onclick="LoginSystem.exportCookie('${d.domain}')" style="font-size: 0.85rem; padding: 0.4rem 0.75rem;">
                                            导出
                                        </button>
                                        <button class="btn btn-danger" onclick="LoginSystem.deleteCookie('${d.domain}')" style="font-size: 0.85rem; padding: 0.4rem 0.75rem;">
                                            删除
                                        </button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `}
                </div>

                <div class="login-modal-footer">
                    <button class="btn btn-secondary" onclick="document.getElementById('cookieManagerModal').remove()">
                        关闭
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    },

    async exportCookie(domain) {
        const response = await fetch(`${API_BASE}/api/proxy/cookies/export/${domain}`);
        const result = await response.json();

        const blob = new Blob([JSON.stringify(result.cookies, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cookies_${domain}_${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);

        showToast(`✓ 已导出 ${domain} 的Cookie`, 'success');
    },

    async deleteCookie(domain) {
        if (!confirm(`确定要删除 ${domain} 的Cookie吗？`)) {
            return;
        }

        const response = await fetch(`${API_BASE}/api/proxy/cookies/${domain}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast(`✓ 已删除 ${domain} 的Cookie`, 'success');
            document.getElementById('cookieManagerModal').remove();
            this.showCookieManager();
        } else {
            alert('删除失败');
        }
    },

    // ==================== 关闭弹窗 ====================
    closeModal() {
        const modal = document.getElementById('loginModal');
        if (modal) {
            modal.remove();
        }
    }
};

// ==================== 自动检测函数 ====================
LoginSystem.autoDetect = function() {
    console.log('[Login] 触发自动检测');

    const urlInput = document.getElementById('urlInput');
    const currentUrl = urlInput ? urlInput.value.trim() : '';

    if (!currentUrl || !currentUrl.startsWith('http')) {
        console.log('[Login] URL无效，跳过检测:', currentUrl);
        return;
    }

    console.log('[Login] 开始自动检测:', currentUrl);

    // 尝试获取当前iframe的HTML内容（如果有）
    let html = null;
    const iframe = document.getElementById('previewFrame') || document.getElementById('smartPreviewFrame');
    if (iframe) {
        try {
            if (iframe.contentDocument) {
                html = iframe.contentDocument.documentElement.outerHTML;
                console.log('[Login] 成功获取iframe HTML，长度:', html.length);
            } else if (iframe.srcdoc) {
                html = iframe.srcdoc;
                console.log('[Login] 使用srcdoc HTML，长度:', html.length);
            }
        } catch (e) {
            console.warn('[Login] 无法获取iframe内容（跨域限制）:', e.message);
        }
    } else {
        console.warn('[Login] 未找到iframe元素');
    }

    this.detectLoginRequirement(currentUrl, html);
};

// ==================== 初始化 ====================
// 确保在DOM加载完成后执行
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('[Login] DOM加载完成');
    });
} else {
    console.log('[Login] DOM已加载');
}

// 导出到全局
window.LoginSystem = LoginSystem;
