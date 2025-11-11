// ========================================
// SeenFetch 登录系统
// ========================================

const LoginSystem = {
    currentUrl: '',
    currentDomain: '',
    lastLoginCheck: {},  // 记录最近的登录检测时间，防止重复弹窗

    // ==================== 自动检测登录需求 ====================
    async detectLoginRequirement(url, html) {
        try {
            const response = await fetch(`${API_BASE}/api/proxy/detect-login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, html })
            });

            const result = await response.json();
            console.log('[Login] 检测结果:', result);

            if (result.success && result.needs_login) {
                console.log('[Login] 检测到需要登录:', result.reasons);

                // 如果已经有Cookie，不弹窗（可能Cookie需要一些时间生效）
                if (result.has_cookies) {
                    console.log('[Login] 域名已有Cookie，跳过登录提示');
                    return result;
                }

                // 防止短时间内重复弹窗（5分钟内）
                const now = Date.now();
                const lastCheck = this.lastLoginCheck[result.domain] || 0;
                if (now - lastCheck < 5 * 60 * 1000) {
                    console.log('[Login] 5分钟内已提示过登录，跳过');
                    return result;
                }

                // 记录本次检测时间
                this.lastLoginCheck[result.domain] = now;

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

        // 如果是从iframe登录返回，需要移除内联样式以恢复默认大小
        // （新创建的modal会使用CSS默认样式）

        const modal = document.createElement('div');
        modal.id = 'loginModal';
        modal.className = 'login-modal active';

        const reasons = detectResult.reasons.join('、');
        const hasCookies = detectResult.has_cookies;

        modal.innerHTML = `
            <div class="login-modal-content">
                <div class="login-modal-header">
                    <h2>🔐 需要登录</h2>
                    <button type="button" class="login-close-btn" onclick="LoginSystem.closeModal()">✕</button>
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

                        <!-- 方式2：自动从浏览器导入 -->
                        <div class="login-method-card" onclick="LoginSystem.startAutoImport()">
                            <div class="method-icon">🚀</div>
                            <div class="method-info">
                                <h4>自动从浏览器导入Cookie</h4>
                                <p>打开真实浏览器登录，自动读取Cookie（推荐）</p>
                            </div>
                            <div class="method-arrow">→</div>
                        </div>

                        <!-- 方式4：手动导入Cookie -->
                        <div class="login-method-card" onclick="LoginSystem.showCookieImport()">
                            <div class="method-icon">📋</div>
                            <div class="method-info">
                                <h4>手动导入Cookie</h4>
                                <p>粘贴已有的Cookie JSON</p>
                            </div>
                            <div class="method-arrow">→</div>
                        </div>
                    </div>
                </div>

                <div class="login-modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="LoginSystem.closeModal()">
                        跳过
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    },

    // ==================== iframe登录 ====================
    async startIframeLogin() {
        console.log('[iframe Login] 🚀🚀🚀 开始iframe登录 - 全屏模式');

        // 创建iframe登录界面
        const modal = document.getElementById('loginModal');
        if (!modal) {
            console.error('[iframe Login] ❌ 找不到 loginModal 元素');
            return;
        }

        // 🔥 改为全屏模式
        const modalContent = modal.querySelector('.login-modal-content');
        if (modalContent) {
            console.log('[iframe Login] ✅ 找到 modalContent，开始设置全屏样式');
            modalContent.style.maxWidth = '100vw';
            modalContent.style.maxHeight = '100vh';
            modalContent.style.width = '100%';
            modalContent.style.height = '100%';
            modalContent.style.borderRadius = '0';  // 全屏时移除圆角
            modalContent.style.margin = '0';
            console.log('[iframe Login] ✅ 全屏样式已应用');
        } else {
            console.error('[iframe Login] ❌ 找不到 .login-modal-content 元素');
        }

        modal.querySelector('.login-modal-body').innerHTML = `
            <div class="iframe-login-container" style="display: flex; flex-direction: column; height: 100%; padding: 0;">
                <!-- 顶部操作栏 -->
                <div style="background: rgba(0, 0, 0, 0.15); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-shrink: 0;">
                    <div style="flex: 1;">
                        <h3 style="margin: 0; color: white; font-size: 1.2rem;">请在下方完成登录</h3>
                        <p style="margin: 0.25rem 0 0 0; color: rgba(255,255,255,0.8); font-size: 0.9rem;">登录完成后，点击右侧按钮保存Cookie</p>
                    </div>
                    <div style="display: flex; gap: 0.5rem; flex-shrink: 0;">
                        <button type="button" class="btn btn-secondary" onclick="LoginSystem.showLoginModal({reasons: [], domain: LoginSystem.currentDomain, has_cookies: false})"
                                style="padding: 0.75rem 1.5rem; background: rgba(255,255,255,0.2); color: white; border: 1px solid rgba(255,255,255,0.3);">
                            ← 返回
                        </button>
                        <button type="button" class="btn btn-primary" onclick="LoginSystem.completeIframeLogin()"
                                style="padding: 0.75rem 2rem; background: #4CAF50; color: white; font-weight: bold;">
                            ✓ 登录完成，保存Cookie
                        </button>
                    </div>
                </div>

                <!-- 提示信息 -->
                <div style="background: #fff3cd; padding: 1rem 2rem; border-left: 4px solid #ffc107; flex-shrink: 0;">
                    <strong>⚠️ 提示：</strong>如果下方显示"验证浏览器"或空白页面，说明该网站禁止在iframe中登录。
                    <span style="color: #856404;">请使用"自动从浏览器导入Cookie"方式。</span>
                </div>

                <!-- iframe 登录页面 -->
                <iframe id="loginIframe" src="${this.currentUrl}"
                        sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-top-navigation-by-user-activation"
                        style="width: 100%; flex: 1; border: none; background: white;">
                </iframe>
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

    showAutoImportError(errorMessage) {
        const modal = document.getElementById('loginModal');
        if (!modal) return;

        modal.querySelector('.login-modal-body').innerHTML = `
            <div style="padding: 1.5rem;">
                <div style="text-align: center; margin-bottom: 1.5rem;">
                    <div style="font-size: 3rem; margin-bottom: 0.5rem;">❌</div>
                    <h3 style="color: #f44336;">操作失败</h3>
                </div>

                <div style="background: #fff3cd; padding: 1rem; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 1rem;">
                    <strong>⚠️ 错误原因：</strong><br>
                    <span style="color: #856404; font-family: monospace; font-size: 0.9rem;">${errorMessage}</span>
                </div>

                <div style="display: flex; gap: 0.5rem;">
                    <button type="button" class="btn btn-secondary" onclick="LoginSystem.showLoginModal({reasons: [], domain: LoginSystem.currentDomain, has_cookies: false})"
                            style="flex: 1;">
                        ← 返回选择
                    </button>
                    <button type="button" class="btn btn-primary" onclick="LoginSystem.showCookieImport()"
                            style="flex: 1;">
                        手动导入
                    </button>
                </div>
            </div>
        `;
    },

    // ==================== 自动Cookie导入 ====================
    async startAutoImport() {
        console.log('[Auto Import] 开始自动Cookie导入流程');

        const modal = document.getElementById('loginModal');
        if (!modal) return;

        // 第一步：检测可用浏览器
        modal.querySelector('.login-modal-body').innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <div class="spinner" style="margin: 0 auto 1rem;"></div>
                <h3>正在检测可用浏览器...</h3>
                <p style="color: #666; margin-top: 1rem;">请稍候...</p>
            </div>
        `;

        try {
            // 检测浏览器
            const detectResponse = await fetch(`${API_BASE}/api/proxy/cookies/detect-browsers`);
            const detectResult = await detectResponse.json();

            if (!detectResult.success) {
                throw new Error('检测浏览器失败');
            }

            const browsers = detectResult.browsers;

            // 找到第一个可用且能读取Cookie的浏览器
            let bestBrowser = 'default';
            for (const [name, info] of Object.entries(browsers)) {
                if (info.can_read_cookies) {
                    bestBrowser = name;
                    break;
                }
            }

            // 第二步：打开浏览器
            modal.querySelector('.login-modal-body').innerHTML = `
                <div style="padding: 2rem;">
                    <div style="text-align: center; margin-bottom: 1.5rem;">
                        <div style="font-size: 3rem; margin-bottom: 0.5rem;">🌐</div>
                        <h3>正在打开浏览器...</h3>
                    </div>

                    <div style="background: #e7f3ff; padding: 1.5rem; border-radius: 8px; border-left: 4px solid #2196F3; margin-bottom: 1.5rem;">
                        <strong>📝 操作步骤：</strong>
                        <ol style="margin: 0.75rem 0 0 1.5rem; color: #333; line-height: 1.8;">
                            <li>在打开的浏览器中登录 <strong>${this.currentDomain}</strong></li>
                            <li>确认登录成功（能看到你的账户信息）</li>
                            <li><strong style="color: #f44336;">关闭浏览器</strong>（重要！否则无法读取Cookie）</li>
                            <li>点击下方的"我已完成登录"按钮</li>
                        </ol>
                    </div>

                    <div style="background: #fff3cd; padding: 1rem; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 1.5rem;">
                        <strong>⚠️ 重要提示：</strong><br>
                        <span style="color: #856404;">
                            登录完成后，<strong>务必关闭浏览器</strong>，否则Cookie数据库会被锁定，无法读取。
                        </span>
                    </div>

                    <div style="display: flex; gap: 0.5rem;">
                        <button type="button" class="btn btn-secondary" onclick="LoginSystem.showLoginModal({reasons: [], domain: LoginSystem.currentDomain, has_cookies: false})"
                                style="flex: 1;">
                            取消
                        </button>
                        <button type="button" class="btn btn-primary" onclick="LoginSystem.confirmLoginComplete()"
                                style="flex: 2; padding: 0.75rem; font-size: 1rem;">
                            ✓ 我已完成登录并关闭浏览器
                        </button>
                    </div>
                </div>
            `;

            // 打开浏览器
            const openResponse = await fetch(`${API_BASE}/api/proxy/cookies/open-browser`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: this.currentUrl,
                    browser: bestBrowser
                })
            });

            const openResult = await openResponse.json();

            if (!openResult.success) {
                throw new Error(openResult.error || '打开浏览器失败');
            }

            console.log('[Auto Import] 浏览器已打开:', openResult);

        } catch (error) {
            console.error('[Auto Import] 错误:', error);
            this.showAutoImportError(error.message);
        }
    },

    async confirmLoginComplete() {
        console.log('[Auto Import] 用户确认登录完成，开始读取Cookie');

        const modal = document.getElementById('loginModal');
        if (!modal) return;

        // 显示读取中状态
        modal.querySelector('.login-modal-body').innerHTML = `
            <div style="text-align: center; padding: 2rem;">
                <div class="spinner" style="margin: 0 auto 1rem;"></div>
                <h3>正在从浏览器读取Cookie...</h3>
                <p style="color: #666; margin-top: 1rem;">
                    正在尝试从 Chrome、Firefox、Edge 读取 ${this.currentDomain} 的Cookie<br>
                    <span style="font-size: 0.85rem;">这可能需要几秒钟...</span>
                </p>
            </div>
        `;

        try {
            const response = await fetch(`${API_BASE}/api/proxy/cookies/auto-import-all/${this.currentDomain}`);
            const result = await response.json();

            if (result.success) {
                // 显示成功详情
                const bestBrowser = result.best_browser;
                const count = result.count;
                const summary = result.summary;

                modal.querySelector('.login-modal-body').innerHTML = `
                    <div style="padding: 1.5rem;">
                        <div style="text-align: center; margin-bottom: 1.5rem;">
                            <div style="font-size: 3rem; margin-bottom: 0.5rem;">✅</div>
                            <h3 style="color: #4CAF50;">自动导入成功！</h3>
                        </div>

                        <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #ddd;">
                                <strong>来源浏览器：</strong>
                                <span>${bestBrowser.toUpperCase()}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #ddd;">
                                <strong>导入Cookie总数：</strong>
                                <span>${count} 个</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #ddd;">
                                <strong>会话Cookie：</strong>
                                <span style="color: #4CAF50;">${summary.session_count} 个 ${summary.session_names.join(', ')}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #ddd;">
                                <strong>认证Cookie：</strong>
                                <span>${summary.auth_count} 个</span>
                            </div>
                            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0;">
                                <strong>Secure Cookie：</strong>
                                <span>${summary.secure_count} 个</span>
                            </div>
                        </div>

                        <div style="background: #e7f3ff; padding: 1rem; border-radius: 8px; border-left: 4px solid #2196F3; margin-bottom: 1rem;">
                            <strong>💡 提示：</strong>Cookie已自动保存到后端，页面将自动刷新以应用新的登录状态。
                        </div>

                        <button type="button" class="btn btn-primary" onclick="LoginSystem.completeAutoImport()"
                                style="width: 100%; padding: 0.75rem; font-size: 1rem;">
                            ✓ 确认并刷新页面
                        </button>
                    </div>
                `;

            } else {
                throw new Error(result.error || '未找到Cookie');
            }

        } catch (error) {
            console.error('[Auto Import] 错误:', error);

            // 显示失败界面
            modal.querySelector('.login-modal-body').innerHTML = `
                <div style="padding: 1.5rem;">
                    <div style="text-align: center; margin-bottom: 1.5rem;">
                        <div style="font-size: 3rem; margin-bottom: 0.5rem;">❌</div>
                        <h3 style="color: #f44336;">自动导入失败</h3>
                    </div>

                    <div style="background: #fff3cd; padding: 1rem; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 1rem;">
                        <strong>⚠️ 错误原因：</strong><br>
                        <span style="color: #856404; font-family: monospace; font-size: 0.9rem;">${error.message}</span>
                    </div>

                    <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                        <strong>可能的原因：</strong>
                        <ul style="margin: 0.5rem 0 0 1.5rem; color: #666;">
                            <li>浏览器中没有登录 ${this.currentDomain}</li>
                            <li>浏览器数据库被锁定（请关闭浏览器后重试）</li>
                            <li>权限不足，无法访问浏览器数据</li>
                        </ul>
                    </div>

                    <div style="background: #e7f3ff; padding: 1rem; border-radius: 8px; border-left: 4px solid #2196F3; margin-bottom: 1rem;">
                        <strong>💡 建议：</strong>
                        <ol style="margin: 0.5rem 0 0 1.5rem; color: #666;">
                            <li>在浏览器中登录 ${this.currentDomain}</li>
                            <li>完全关闭浏览器（确保数据库解锁）</li>
                            <li>重新尝试自动导入</li>
                            <li>或使用"手动导入Cookie"方式</li>
                        </ol>
                    </div>

                    <div style="display: flex; gap: 0.5rem;">
                        <button type="button" class="btn btn-secondary" onclick="LoginSystem.showLoginModal({reasons: [], domain: LoginSystem.currentDomain, has_cookies: false})"
                                style="flex: 1;">
                            ← 返回选择
                        </button>
                        <button type="button" class="btn btn-primary" onclick="LoginSystem.showCookieImport()"
                                style="flex: 1;">
                            手动导入
                        </button>
                    </div>
                </div>
            `;
        }
    },

    async completeAutoImport() {
        showToast('✓ 正在刷新页面...', 'success');

        this.closeModal();

        // 重新加载页面
        if (typeof loadPage === 'function') {
            setTimeout(() => loadPage(), 500);
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
                    <button type="button" class="btn btn-secondary" onclick="LoginSystem.showLoginModal({reasons: [], domain: LoginSystem.currentDomain, has_cookies: false})">
                        返回
                    </button>
                    <button type="button" class="btn btn-primary" onclick="LoginSystem.importCookies()" style="flex: 1;">
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
                    <button type="button" class="login-close-btn" onclick="document.getElementById('cookieManagerModal').remove()">✕</button>
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
                                        <button type="button" class="btn btn-secondary" onclick="LoginSystem.exportCookie('${d.domain}')" style="font-size: 0.85rem; padding: 0.4rem 0.75rem;">
                                            导出
                                        </button>
                                        <button type="button" class="btn btn-danger" onclick="LoginSystem.deleteCookie('${d.domain}')" style="font-size: 0.85rem; padding: 0.4rem 0.75rem;">
                                            删除
                                        </button>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `}
                </div>

                <div class="login-modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('cookieManagerModal').remove()">
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

    console.log('[Login] 调用检测API, URL:', currentUrl, 'HTML长度:', html ? html.length : 'null');
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
