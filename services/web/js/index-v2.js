// services/web/js/index-v2.js

/* ========================================
   SeenFetch V2 - 完整 JavaScript 逻辑
   ======================================== */

const API_BASE = 'http://127.0.0.1:8000';
let currentMode = 'manual';
let currentUrl = '';
let configuredFields = [];
let smartSuggestions = [];
let selectedSuggestions = new Set();
let fieldsConfirmed = false;
let currentRunId = null;

// ==================== 工具函数 ====================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttribute(text) {
    return (text || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function escapeBacktick(text) {
    return (text || '').replace(/`/g, '\\`').replace(/\$/g, '\\$');
}

function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 90px;
        right: 20px;
        background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : '#667eea'};
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 9999;
        font-size: 0.95rem;
        animation: slideIn 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
    
    return toast;
}

// Toast 动画样式
const toastStyle = document.createElement('style');
toastStyle.textContent = `
    @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
`;
document.head.appendChild(toastStyle);

// ==================== 模式切换 ====================

function switchMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent.includes(mode === 'manual' ? '手动' : '智能'));
    });
    
    document.getElementById('manualMode').classList.toggle('hidden', mode !== 'manual');
    document.getElementById('smartMode').classList.toggle('hidden', mode === 'manual');
}

// ==================== 配置弹窗 ====================

function toggleConfigModal() {
    document.getElementById('configModal').classList.toggle('active');
}

function closeModalOnBackdrop(event) {
    if (event.target.id === 'configModal') {
        toggleConfigModal();
    }
}

// ==================== 加载页面 ====================

async function loadPage() {
    const url = document.getElementById('urlInput').value.trim();
    if (!url) {
        alert('请输入网页地址');
        return;
    }
    
    currentUrl = url;
    fieldsConfirmed = false;
    updateConfirmButton();
    clearPreview();
    
    if (currentMode === 'manual') {
        await loadManualMode(url);
    } else {
        await loadSmartMode(url);
    }
}

// ==================== 手动模式 ====================

async function loadManualMode(url) {
    const loading = document.getElementById('loadingOverlay');
    loading.classList.remove('hidden');
    
    try {
        const response = await fetch(`${API_BASE}/api/proxy/render`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, timeout_ms: 30000 })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            
            if (errorData.detail?.error?.includes('blocked') || 
                errorData.detail?.error?.includes('anti-bot') ||
                errorData.detail?.details?.includes('anti-scraping')) {
                showAntiScrapingModal(url);
                return;
            }
            
            throw new Error(errorData.detail?.error || 'Request failed');
        }
        
        const data = await response.json();

        // 🔥 使用Blob URL代替srcdoc，避免origin=null的安全问题
        const iframe = document.getElementById('previewFrame');
        try {
            const blob = new Blob([data.html], { type: 'text/html; charset=utf-8' });
            const blobUrl = URL.createObjectURL(blob);

            // 清理旧的Blob URL
            if (iframe.dataset.blobUrl) {
                URL.revokeObjectURL(iframe.dataset.blobUrl);
            }

            iframe.src = blobUrl;
            iframe.dataset.blobUrl = blobUrl;

            console.log('[Manual Mode] 使用Blob URL加载页面');
        } catch (error) {
            console.error('[Manual Mode] Blob URL创建失败，降级到srcdoc:', error);
            iframe.srcdoc = data.html;
        }

        // 延迟1秒后自动检测登录需求
        setTimeout(() => {
            if (window.LoginSystem && typeof window.LoginSystem.autoDetect === 'function') {
                console.log('[Manual Mode] 触发登录自动检测');
                window.LoginSystem.autoDetect();
            }
        }, 1000);

    } catch (error) {
        const errorMsg = error.message.toLowerCase();
        if (errorMsg.includes('blocked') || 
            errorMsg.includes('connection') || 
            errorMsg.includes('failed')) {
            showAntiScrapingModal(url);
        } else {
            alert('加载失败: ' + error.message);
        }
    } finally {
        loading.classList.add('hidden');
    }
}

function showAntiScrapingModal(url) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay active';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 500px;">
            <div class="modal-header">
                <h3>🛡️ 检测到反爬虫保护</h3>
                <button class="close-btn" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div class="modal-body">
                <p style="margin-bottom: 1rem; line-height: 1.6;">
                    该网站启用了反爬虫保护，<strong>手动模式</strong>无法正常访问。
                </p>
                <div style="background: #fff3cd; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                    <strong>💡 建议使用智能模式</strong><br>
                    智能模式配备了反反爬虫技术，可以绕过大多数网站的保护机制。
                </div>
                <p style="color: #666; font-size: 0.9rem;">
                    目标网址：<br>
                    <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px; word-break: break-all;">
                        ${url}
                    </code>
                </p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">
                    取消
                </button>
                <button class="btn btn-primary" onclick="switchToSmartMode('${url}')">
                    切换到智能模式
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function switchToSmartMode(url) {
    document.querySelector('.modal-overlay')?.remove();
    switchMode('smart');
    
    const urlInput = document.getElementById('urlInput');
    if (urlInput.value !== url) {
        urlInput.value = url;
    }
    
    loadPage();
    showToast('✅ 已切换到智能模式', 'success');
}

// ==================== 智能模式 ====================

async function loadSmartMode(url) {
    const useAdvanced = confirm(
        '🚀 高级选项\n\n' +
        '是否启用以下功能？\n\n' +
        '✅ 自动滚动加载（处理无限滚动）\n' +
        '✅ 隐身模式（绕过反爬虫检测）\n' +
        '✅ Markdown 分析（更精准的内容识别）\n\n' +
        '点击"确定"启用高级功能\n' +
        '点击"取消"使用标准模式'
    );
    
    const previewLoading = document.getElementById('smartPreviewLoading');
    const analysisLoading = document.getElementById('smartLoading');
    
    previewLoading.classList.remove('hidden');
    analysisLoading.classList.remove('hidden');
    
    try {
        console.log('[SmartMode] 开始并行加载...');
        
        const [previewResult, analysisResult] = await Promise.all([
            fetch(`${API_BASE}/api/proxy/render`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, timeout_ms: 30000 })
            }).then(r => r.json()),
            
            fetch(`${API_BASE}/api/smart/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    auto_scroll: true,
                    use_stealth: useAdvanced,
                    use_markdown: useAdvanced,
                    wait_for: null
                })
            }).then(r => r.json())
        ]);
        
        console.log('[SmartMode] 并行加载完成');
        
        if (previewResult.success && previewResult.html) {
            console.log('[SmartMode] 加载预览页面, HTML长度:', previewResult.html.length);
            
            const iframe = document.getElementById('smartPreviewFrame');
            
            const styledHtml = previewResult.html.replace(
                '</head>',
                `<style>
                    .seenfetch-highlight {
                        outline: 3px solid #4CAF50 !important;
                        outline-offset: 2px;
                        background: rgba(76, 175, 80, 0.15) !important;
                        box-shadow: 0 0 10px rgba(76, 175, 80, 0.3) !important;
                        transition: all 0.3s ease !important;
                        position: relative !important;
                        z-index: 999 !important;
                    }
                    .seenfetch-highlight::before {
                        content: '✓ 已选中';
                        position: absolute;
                        top: -25px;
                        left: 0;
                        background: #4CAF50;
                        color: white;
                        padding: 2px 8px;
                        border-radius: 4px;
                        font-size: 12px;
                        font-weight: bold;
                        z-index: 1000;
                    }
                </style></head>`
            );
            
            try {
                const blob = new Blob([styledHtml], { type: 'text/html; charset=utf-8' });
                const blobUrl = URL.createObjectURL(blob);
                
                if (iframe.dataset.blobUrl) {
                    URL.revokeObjectURL(iframe.dataset.blobUrl);
                }
                
                iframe.src = blobUrl;
                iframe.dataset.blobUrl = blobUrl;
                
                console.log('[SmartMode] 预览页面已加载 (Blob URL)');
                
                iframe.onload = () => {
                    console.log('[SmartMode] iframe 加载完成');
                };
                
            } catch (error) {
                console.error('[SmartMode] Blob URL 创建失败，降级到 srcdoc:', error);
                iframe.srcdoc = styledHtml;
            }
        } else {
            console.warn('[SmartMode] 预览加载失败');
        }
        
        if (analysisResult.success) {
            console.log('[SmartMode] 显示分析结果, 字段数:', analysisResult.suggestions?.length);
            displaySmartResults(analysisResult);

            // 延迟1秒后自动检测登录需求
            setTimeout(() => {
                if (window.LoginSystem && typeof window.LoginSystem.autoDetect === 'function') {
                    console.log('[Smart Mode] 触发登录自动检测');
                    window.LoginSystem.autoDetect();
                }
            }, 1000);

            if (analysisResult.config_used) {
                const configInfo = [
                    analysisResult.config_used.auto_scroll ? '✅ 自动滚动' : '❌ 自动滚动',
                    analysisResult.config_used.use_stealth ? '✅ 隐身模式' : '❌ 隐身模式',
                    analysisResult.config_used.use_markdown ? '✅ Markdown分析' : '❌ Markdown分析'
                ].join(' | ');
                
                showToast(`✅ 分析完成！${configInfo}`, 'success', 5000);
            }
        } else {
            alert('分析失败: ' + analysisResult.error);
        }
        
    } catch (error) {
        console.error('[SmartMode] Error:', error);
        alert('加载失败: ' + error.message);
    } finally {
        previewLoading.classList.add('hidden');
        analysisLoading.classList.add('hidden');
    }
}

function displaySmartResults(data) {
    smartSuggestions = data.suggestions || [];
    const container = document.getElementById('suggestionsList');
    
    if (smartSuggestions.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999; padding: 2rem;">未找到可采集的字段</p>';
        return;
    }
    
    container.innerHTML = smartSuggestions.map((sug, idx) => `
        <div class="suggestion-card ${sug.userSelected ? 'user-selected' : ''}" 
             data-index="${idx}"
             data-selector="${escapeAttribute(sug.selector)}"
             onclick="toggleSuggestion(${idx})"
             onmouseenter="highlightElements(\`${escapeBacktick(sug.selector)}\`)"
             onmouseleave="clearHighlight()">
            
            ${sug.userSelected ? `
                <div style="
                    background: linear-gradient(135deg, #4CAF50, #45a049); 
                    color: white; 
                    padding: 0.5rem; 
                    border-radius: 8px 8px 0 0; 
                    margin: -1rem -1rem 0.75rem -1rem;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                ">
                    <span style="font-size: 1.2rem;">👆</span>
                    <strong>您选择的字段</strong>
                </div>
            ` : ''}
            
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <span style="font-weight: 600; font-size: 1.1rem; color: #333;">${sug.name}</span>
                <span style="padding: 0.25rem 0.75rem; background: ${sug.userSelected ? '#4CAF50' : '#667eea'}; color: white; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">
                    ${sug.type}
                </span>
            </div>
            
            <div style="color: #666; font-size: 0.9rem; margin-bottom: 0.75rem;">
                <strong style="color: #333;">选择器:</strong> 
                <code style="background: #f5f5f5; padding: 3px 8px; border-radius: 4px; font-size: 0.85rem; color: #d63384;">
                    ${escapeHtml(sug.selector)}
                </code><br>
                <strong style="color: #333;">数量:</strong> 
                <span style="color: #667eea; font-weight: 600;">${sug.count}</span> 个
            </div>
            
            ${sug.sample_data && sug.sample_data.length > 0 ? `
                <div style="
                    margin-top: 0.75rem; 
                    background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); 
                    padding: 0.75rem; 
                    border-radius: 8px; 
                    border-left: 4px solid #667eea;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <strong style="color: #667eea; font-size: 0.95rem;">📋 数据示例</strong>
                        <span style="font-size: 0.8rem; color: #999;">前 ${Math.min(3, sug.sample_data.length)} 条</span>
                    </div>
                    <ul style="margin: 0; padding-left: 1.2rem; list-style: none;">
                        ${sug.sample_data.slice(0, 3).map((sample, i) => `
                            <li style="
                                color: #333; 
                                font-size: 0.9rem; 
                                margin: 0.5rem 0; 
                                padding-left: 0.5rem;
                                border-left: 2px solid #667eea;
                                line-height: 1.5;
                            ">
                                <span style="color: #999; font-size: 0.8rem; margin-right: 0.5rem;">${i + 1}.</span>
                                ${escapeHtml(sample.substring(0, 60))}${sample.length > 60 ? '<span style="color: #999;">...</span>' : ''}
                            </li>
                        `).join('')}
                    </ul>
                    ${sug.sample_data.length > 3 ? `
                        <div style="text-align: right; margin-top: 0.75rem;">
                            <button class="btn-link" onclick="event.stopPropagation(); showAllSamples(${idx})">
                                查看全部 ${sug.sample_data.length} 条 →
                            </button>
                        </div>
                    ` : ''}
                </div>
            ` : `
                <div style="
                    margin-top: 0.75rem; 
                    background: #fff3cd; 
                    padding: 0.75rem; 
                    border-radius: 8px; 
                    border-left: 4px solid #ffc107;
                    color: #856404;
                    font-size: 0.9rem;
                ">
                    ⚠️ 暂无示例数据
                </div>
            `}
            
            <div style="margin-top: 0.75rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #666; margin-bottom: 0.25rem;">
                    <span>AI 置信度</span>
                    <span style="font-weight: 600; color: ${(sug.confidence || 0.5) >= 0.8 ? '#4CAF50' : (sug.confidence || 0.5) >= 0.6 ? '#FFA726' : '#999'};">
                        ${Math.round((sug.confidence || 0.5) * 100)}%
                    </span>
                </div>
                <div style="height: 6px; background: #e0e0e0; border-radius: 3px; overflow: hidden;">
                    <div style="
                        height: 100%; 
                        background: linear-gradient(90deg, ${(sug.confidence || 0.5) >= 0.8 ? '#4CAF50, #66BB6A' : (sug.confidence || 0.5) >= 0.6 ? '#FFA726, #FFB74D' : '#999, #bbb'}); 
                        width: ${(sug.confidence || 0.5) * 100}%;
                        transition: width 0.5s ease;
                    "></div>
                </div>
            </div>
        </div>
    `).join('');
    
    updateSmartModeActions();
}

function updateSmartModeActions() {
    const actionBar = document.querySelector('#smartMode .action-bar');
    if (!actionBar) return;
    
    actionBar.innerHTML = `
        <button class="btn" style="background: #e0e0e0; color: #333;" onclick="selectAllSuggestions()">
            ✓ 全选
        </button>
        <button class="btn btn-primary" style="flex: 1" onclick="previewSmartData()">
            👁️ 预览数据
        </button>
        <button class="btn btn-primary" style="flex: 1" onclick="applySmartSelections()">
            ✅ 应用选中字段
        </button>
        <button class="btn" style="background: #4CAF50; color: white; flex: 1" onclick="exportSmartData()">
            📥 导出数据
        </button>
    `;
}

function toggleSuggestion(idx) {
    const card = document.querySelectorAll('.suggestion-card')[idx];
    card.classList.toggle('selected');
    
    if (selectedSuggestions.has(idx)) {
        selectedSuggestions.delete(idx);
    } else {
        selectedSuggestions.add(idx);
    }
}

function selectAllSuggestions() {
    document.querySelectorAll('.suggestion-card').forEach((card, idx) => {
        card.classList.add('selected');
        selectedSuggestions.add(idx);
    });
}

function applySmartSelections() {
    if (selectedSuggestions.size === 0) {
        alert('请至少选择一个字段');
        return;
    }
    
    configuredFields = [];
    selectedSuggestions.forEach(idx => {
        const sug = smartSuggestions[idx];
        configuredFields.push({
            name: sug.name,
            selector: sug.selector,
            type: sug.type,
            attr: sug.type === 'image' ? 'src' : (sug.type === 'link' ? 'href' : 'text')
        });
    });
    
    renderFields();
    toggleConfigModal();
}

function highlightElements(selector) {
    const iframe = document.getElementById('smartPreviewFrame');
    if (!iframe || !iframe.contentWindow) return;
    
    try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        
        const highlighted = iframeDoc.querySelectorAll('.seenfetch-highlight');
        highlighted.forEach(el => {
            el.classList.remove('seenfetch-highlight');
        });
        
        const elements = iframeDoc.querySelectorAll(selector);
        console.log(`[Highlight] 找到 ${elements.length} 个元素:`, selector);
        
        elements.forEach((el, index) => {
            el.classList.add('seenfetch-highlight');
        });
        
        if (elements.length > 0) {
            elements[0].scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center',
                inline: 'nearest'
            });
        }
        
    } catch (error) {
        console.warn('[Highlight] 无法高亮元素:', error);
    }
}

function clearHighlight() {
    const iframe = document.getElementById('smartPreviewFrame');
    if (!iframe || !iframe.contentWindow) return;
    
    try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        const highlighted = iframeDoc.querySelectorAll('.seenfetch-highlight');
        highlighted.forEach(el => {
            el.classList.remove('seenfetch-highlight');
        });
    } catch (error) {
        console.warn('[Highlight] 无法清除高亮:', error);
    }
}

function showAllSamples(idx) {
    const sug = smartSuggestions[idx];
    
    const modalHtml = `
        <div id="samplesModal" style="
            position: fixed; 
            top: 0; 
            left: 0; 
            right: 0; 
            bottom: 0; 
            background: rgba(0,0,0,0.6); 
            z-index: 99999; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            animation: fadeIn 0.3s ease;
        " onclick="this.remove()">
            <div style="
                background: white; 
                padding: 2rem; 
                border-radius: 16px; 
                max-width: 700px; 
                max-height: 80vh; 
                overflow-y: auto;
                box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            " onclick="event.stopPropagation()">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                    <h3 style="margin: 0; color: #333;">
                        ${sug.name} - 全部示例数据
                    </h3>
                    <button onclick="document.getElementById('samplesModal').remove()" 
                            style="background: #f5f5f5; border: none; width: 32px; height: 32px; border-radius: 50%; cursor: pointer; font-size: 1.2rem;">
                        ✕
                    </button>
                </div>
                
                <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                    <p style="margin: 0; color: #666; font-size: 0.95rem;">
                        <strong>选择器:</strong> <code style="background: white; padding: 2px 6px; border-radius: 4px;">${escapeHtml(sug.selector)}</code><br>
                        <strong>类型:</strong> ${sug.type}<br>
                        <strong>总数:</strong> ${sug.sample_data.length} 条
                    </p>
                </div>
                
                <div style="max-height: 400px; overflow-y: auto;">
                    <ol style="list-style: none; padding: 0; margin: 0;">
                        ${sug.sample_data.map((sample, i) => `
                            <li style="
                                padding: 0.75rem 1rem; 
                                margin: 0.5rem 0; 
                                background: ${i % 2 === 0 ? '#f9f9f9' : 'white'}; 
                                border-radius: 8px; 
                                border-left: 3px solid #667eea;
                                transition: all 0.2s ease;
                            " onmouseover="this.style.background='#e8f0ff'" onmouseout="this.style.background='${i % 2 === 0 ? '#f9f9f9' : 'white'}'">
                                <span style="color: #999; font-size: 0.85rem; font-weight: 600; margin-right: 0.75rem;">
                                    #${i + 1}
                                </span>
                                <span style="color: #333; font-size: 0.95rem; line-height: 1.5;">
                                    ${escapeHtml(sample)}
                                </span>
                            </li>
                        `).join('')}
                    </ol>
                </div>
                
                <button class="btn btn-primary" 
                        style="width: 100%; margin-top: 1.5rem; padding: 0.75rem;" 
                        onclick="document.getElementById('samplesModal').remove()">
                    关闭
                </button>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

// ==================== 字段管理 ====================

function renderFields() {
    const container = document.getElementById('fieldsList');
    
    if (configuredFields.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📝</div>
                <p>还没有配置任何字段</p>
                <small>选择模式并开始分析页面</small>
            </div>
        `;
        updateConfirmButton();
        return;
    }
    
    container.innerHTML = configuredFields.map((field, idx) => `
        <div class="field-item">
            <div class="field-header">
                <input class="field-name-input"
                       value="${field.name}"
                       onchange="updateFieldName(${idx}, this.value)"
                       placeholder="字段名称">
                <span class="field-type-badge">${field.attr}</span>
                <button class="btn-danger" onclick="removeField(${idx})">删除</button>
            </div>
            <div class="field-info">
                <strong>选择器:</strong> <code>${field.selector}</code>
            </div>
        </div>
    `).join('');
    
    updateConfirmButton();
}

function updateFieldName(idx, name) {
    configuredFields[idx].name = name;
    fieldsConfirmed = false;
    updateConfirmButton();
}

function removeField(idx) {
    configuredFields.splice(idx, 1);
    fieldsConfirmed = false;
    renderFields();
    clearPreview();
}

function clearFields() {
    if (configuredFields.length > 0) {
        if (confirm('确定要清空所有字段吗？')) {
            configuredFields = [];
            fieldsConfirmed = false;
            renderFields();
            clearPreview();
        }
    }
}

function updateConfirmButton() {
    const btn = document.getElementById('confirmBtn');
    btn.disabled = configuredFields.length === 0 || fieldsConfirmed;
    btn.textContent = fieldsConfirmed ? '✓ 已确认' : '✓ 确认配置';
}

// ==================== 数据采集 ====================

// ==================== 数据采集 ====================

async function confirmFields() {
    console.log('[confirmFields] 开始确认字段...');
    
    if (configuredFields.length === 0) {
        alert('请先配置字段');
        return;
    }
    
    const unnamedFields = configuredFields.filter(f => !f.name || f.name.trim() === '');
    if (unnamedFields.length > 0) {
        alert('请为所有字段命名');
        return;
    }
    
    console.log('[confirmFields] 已配置的字段:', configuredFields);
    
    fieldsConfirmed = true;
    updateConfirmButton();
    toggleConfigModal();
    
    console.log('[confirmFields] 准备开始采集...');
    await startScraping();
}

async function startScraping() {
    console.log('[startScraping] 函数被调用');
    
    if (!fieldsConfirmed || configuredFields.length === 0) {
        console.error('[startScraping] 字段未确认或为空');
        alert('请先确认字段配置');
        return;
    }
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const jobName = `采集_${timestamp}`;
    
    console.log('[startScraping] 任务名称:', jobName);
    console.log('[startScraping] 目标URL:', currentUrl);
    console.log('[startScraping] 配置的字段:', configuredFields);
    
    try {
        showPreviewLoading();
        
        console.log('[startScraping] 步骤1: 创建任务...');
        
        const jobData = {
            name: jobName,
            start_url: currentUrl,
            status: "active",
            selectors: configuredFields.map(field => ({
                name: field.name,
                css: field.selector,
                attr: field.attr,
                limit: 100
            }))
        };
        
        console.log('[startScraping] 任务数据:', JSON.stringify(jobData, null, 2));
        
        const jobRes = await fetch(`${API_BASE}/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });
        
        console.log('[startScraping] 创建任务响应状态:', jobRes.status);
        
        if (!jobRes.ok) {
            const errorText = await jobRes.text();
            console.error('[startScraping] 创建任务失败:', errorText);
            throw new Error('创建任务失败: ' + errorText);
        }
        
        const job = await jobRes.json();
        console.log('[startScraping] 任务创建成功, ID:', job.id);
        
        console.log('[startScraping] 步骤2: 执行采集...');
        
        const runPayload = {
            url: currentUrl,
            limit: 100
        };
        
        console.log('[startScraping] 采集参数:', runPayload);
        
        const runRes = await fetch(`${API_BASE}/runs/jobs/${job.id}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(runPayload)
        });
        
        console.log('[startScraping] 启动采集响应状态:', runRes.status);
        
        if (!runRes.ok) {
            const errorText = await runRes.text();
            console.error('[startScraping] 启动采集失败:', errorText);
            throw new Error('启动采集失败: ' + errorText);
        }
        
        const run = await runRes.json();
        currentRunId = run.run_id;
        
        console.log('[startScraping] 采集已启动, Run ID:', currentRunId);
        console.log('[startScraping] 采集状态:', run.status);
        
        console.log('[startScraping] 步骤3: 等待采集完成...');
        
        let attempts = 0;
        const maxAttempts = 20;
        
        const checkResult = async () => {
            attempts++;
            console.log(`[startScraping] 第 ${attempts} 次检查结果...`);
            
            try {
                const statusRes = await fetch(`${API_BASE}/runs/${currentRunId}`);
                if (!statusRes.ok) {
                    throw new Error('获取状态失败');
                }
                
                const runStatus = await statusRes.json();
                console.log('[startScraping] 当前状态:', runStatus.status);
                
                if (runStatus.status === 'succeeded') {
                    console.log('[startScraping] ✅ 采集成功！');
                    await fetchResults(currentRunId);
                } else if (runStatus.status === 'failed') {
                    console.error('[startScraping] ❌ 采集失败:', runStatus.stats);
                    throw new Error('采集失败: ' + (runStatus.stats?.error || '未知错误'));
                } else if (attempts < maxAttempts) {
                    console.log('[startScraping] 继续等待...');
                    setTimeout(checkResult, 1000);
                } else {
                    throw new Error('采集超时（20秒）');
                }
            } catch (error) {
                console.error('[startScraping] 检查结果时出错:', error);
                clearPreview();
                alert('检查采集状态失败: ' + error.message);
            }
        };
        
        setTimeout(checkResult, 1000);
        
    } catch (error) {
        console.error('[startScraping] 异常:', error);
        alert('采集失败: ' + error.message);
        clearPreview();
    }
}

async function fetchResults(runId) {
    console.log('[fetchResults] 获取结果, Run ID:', runId);
    
    try {
        const resultRes = await fetch(`${API_BASE}/runs/${runId}/results`);
        
        console.log('[fetchResults] 响应状态:', resultRes.status);
        
        if (!resultRes.ok) {
            throw new Error('获取结果失败');
        }
        
        const results = await resultRes.json();
        
        console.log('[fetchResults] 获取到的结果:', results);
        console.log('[fetchResults] 结果键:', Object.keys(results));
        
        renderPreview(results);
        
        // 启用对应模式的导出按钮
        const exportBtnId = currentMode === 'manual' ? 'manualExportBtn' : 'exportBtn';
        const exportBtn = document.getElementById(exportBtnId);
        if (exportBtn) {
            exportBtn.disabled = false;
        }
        
        console.log('[fetchResults] ✅ 结果渲染完成');
        
    } catch (error) {
        console.error('[fetchResults] 错误:', error);
        alert('获取结果失败: ' + error.message);
        clearPreview();
    }
}
// ==================== 数据预览 ====================

function renderPreview(results) {
    // 根据当前模式选择容器
    const containerId = currentMode === 'manual' ? 'manualPreviewContent' : 'previewContent';
    const container = document.getElementById(containerId);
    
    if (!container) {
        console.error('[renderPreview] 找不到容器:', containerId);
        return;
    }
    
    if (!results || Object.keys(results).length === 0) {
        container.innerHTML = `
            <div class="preview-empty">
                未采集到数据，请检查选择器配置
            </div>
        `;
        return;
    }
    
    const columns = Object.keys(results);
    const maxRows = Math.max(...columns.map(col => results[col].length));
    
    let html = '<table class="preview-table"><thead><tr>';
    columns.forEach(col => {
        html += `<th>${escapeHtml(col)}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    for (let i = 0; i < maxRows; i++) {
        html += '<tr>';
        columns.forEach(col => {
            const value = results[col][i] || '';
            html += `<td>${escapeHtml(value)}</td>`;
        });
        html += '</tr>';
    }
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

function showPreviewLoading() {
    const containerId = currentMode === 'manual' ? 'manualPreviewContent' : 'previewContent';
    const container = document.getElementById(containerId);
    
    if (!container) return;
    
    container.innerHTML = `
        <div class="preview-empty">
            <div class="spinner" style="margin: 0 auto 1rem;"></div>
            正在采集数据...
        </div>
    `;
}

function clearPreview() {
    const containerId = currentMode === 'manual' ? 'manualPreviewContent' : 'previewContent';
    const container = document.getElementById(containerId);
    
    if (!container) return;
    
    container.innerHTML = `
        <div class="preview-empty">
            请先配置字段并确认，然后开始采集数据
        </div>
    `;
    
    // 禁用对应的导出按钮
    const exportBtnId = currentMode === 'manual' ? 'manualExportBtn' : 'exportBtn';
    const exportBtn = document.getElementById(exportBtnId);
    if (exportBtn) {
        exportBtn.disabled = true;
    }
    
    currentRunId = null;
}

// ==================== 导出数据 ====================

function exportData() {
    if (!currentRunId) {
        alert('没有可导出的数据');
        return;
    }
    
    const exportURL = `${API_BASE}/runs/${currentRunId}/export?format=csv`;
    window.open(exportURL, '_blank');
}

// ==================== 智能模式数据预览 ====================

async function previewSmartData() {
    if (selectedSuggestions.size === 0) {
        alert('请至少选择一个字段');
        return;
    }
    
    const loadingModal = createPreviewModal();
    showModalLoading(loadingModal);
    
    try {
        const fields = Array.from(selectedSuggestions).map(idx => {
            const sug = smartSuggestions[idx];
            return {
                name: sug.name,
                selector: sug.selector,
                type: sug.type,
                attr: sug.type === 'image' ? 'src' : (sug.type === 'link' ? 'href' : 'text')
            };
        });
        
        const results = await executeTempScraping(fields);
        showPreviewResults(loadingModal, results);
        
    } catch (error) {
        loadingModal.remove();
        alert('预览失败: ' + error.message);
    }
}

function createPreviewModal() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay active';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 90%; max-height: 90vh;">
            <div class="modal-header">
                <h3>📊 数据预览</h3>
                <button class="close-btn" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div class="modal-body" id="previewModalBody" style="max-height: 70vh; overflow: auto;">
                <!-- 内容将动态填充 -->
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">
                    关闭
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
    return modal;
}

function showModalLoading(modal) {
    const body = modal.querySelector('#previewModalBody');
    body.innerHTML = `
        <div style="text-align: center; padding: 3rem;">
            <div class="spinner" style="margin: 0 auto 1rem;"></div>
            <p style="color: #666;">正在采集数据...</p>
        </div>
    `;
}

function showPreviewResults(modal, results) {
    const body = modal.querySelector('#previewModalBody');
    
    if (!results || Object.keys(results).length === 0) {
        body.innerHTML = `
            <div style="text-align: center; padding: 3rem; color: #999;">
                未采集到数据，请检查选择器配置
            </div>
        `;
        return;
    }
    
    const fileNames = Object.keys(results);
    const hasMultipleFiles = fileNames.length > 1;
    
    let html = '';
    
    if (hasMultipleFiles) {
        html += `
            <div style="margin-bottom: 1rem; padding: 1rem; background: #f8f9fa; border-radius: 8px;">
                <strong>📂 选择要预览的字段：</strong>
                <select id="previewFileSelector" onchange="switchPreviewFile()" 
                        style="width: 100%; margin-top: 0.5rem; padding: 0.5rem;">
                    ${fileNames.map((name, idx) => `
                        <option value="${idx}">${name}</option>
                    `).join('')}
                </select>
            </div>
        `;
    }
    
    html += '<div id="previewTableContainer"></div>';
    body.innerHTML = html;
    
    window.previewResults = results;
    window.previewFileNames = fileNames;
    renderPreviewFile(0);
}

function switchPreviewFile() {
    const selector = document.getElementById('previewFileSelector');
    const idx = parseInt(selector.value);
    renderPreviewFile(idx);
}

function renderPreviewFile(fileIdx) {
    const container = document.getElementById('previewTableContainer');
    const fileName = window.previewFileNames[fileIdx];
    const data = window.previewResults[fileName];
    
    let html = '<table class="preview-table"><thead><tr>';
    html += `<th>${fileName}</th>`;
    html += '</tr></thead><tbody>';
    
    data.forEach(value => {
        html += `<tr><td>${escapeHtml(value)}</td></tr>`;
    });
    
    html += '</tbody></table>';
    container.innerHTML = html;
}

async function executeTempScraping(fields) {
    const timestamp = Date.now();
    const jobName = `临时预览_${timestamp}`;
    
    const jobData = {
        name: jobName,
        start_url: currentUrl,
        status: "active",
        selectors: fields.map(field => ({
            name: field.name,
            css: field.selector,
            attr: field.attr,
            limit: 20
        }))
    };
    
    const jobRes = await fetch(`${API_BASE}/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(jobData)
    });
    
    if (!jobRes.ok) throw new Error('创建任务失败');
    const job = await jobRes.json();
    
    const runRes = await fetch(`${API_BASE}/runs/jobs/${job.id}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: currentUrl, limit: 20 })
    });
    
    if (!runRes.ok) throw new Error('启动采集失败');
    const run = await runRes.json();
    
    for (let i = 0; i < 20; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const statusRes = await fetch(`${API_BASE}/runs/${run.run_id}`);
        const runStatus = await statusRes.json();
        
        if (runStatus.status === 'succeeded') {
            const resultRes = await fetch(`${API_BASE}/runs/${run.run_id}/results`);
            return await resultRes.json();
        } else if (runStatus.status === 'failed') {
            throw new Error('采集失败');
        }
    }
    
    throw new Error('采集超时');
}

// ==================== 智能模式导出 ====================

async function exportSmartData() {
    if (selectedSuggestions.size === 0) {
        alert('请至少选择一个字段');
        return;
    }
    
    const selectedCount = selectedSuggestions.size;
    const confirmMsg = selectedCount > 1 
        ? `您选中了 ${selectedCount} 个字段，将生成 ${selectedCount} 个文件。\n是否继续导出？`
        : `确认导出选中的字段数据？`;
    
    if (!confirm(confirmMsg)) {
        return;
    }
    
    showToast('🚀 开始导出...', 'info');
    
    try {
        const fields = Array.from(selectedSuggestions).map(idx => {
            const sug = smartSuggestions[idx];
            return {
                name: sug.name,
                selector: sug.selector,
                type: sug.type,
                attr: sug.type === 'image' ? 'src' : (sug.type === 'link' ? 'href' : 'text')
            };
        });
        
        const timestamp = Date.now();
        const jobName = `导出_${timestamp}`;
        
        const jobData = {
            name: jobName,
            start_url: currentUrl,
            status: "active",
            selectors: fields.map(field => ({
                name: field.name,
                css: field.selector,
                attr: field.attr,
                limit: 100
            }))
        };
        
        const jobRes = await fetch(`${API_BASE}/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });
        
        if (!jobRes.ok) throw new Error('创建任务失败');
        const job = await jobRes.json();
        
        const runRes = await fetch(`${API_BASE}/runs/jobs/${job.id}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: currentUrl, limit: 100 })
        });
        
        if (!runRes.ok) throw new Error('启动采集失败');
        const run = await runRes.json();
        
        for (let i = 0; i < 30; i++) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            const statusRes = await fetch(`${API_BASE}/runs/${run.run_id}`);
            const runStatus = await statusRes.json();
            
            if (runStatus.status === 'succeeded') {
                const exportURL = `${API_BASE}/runs/${run.run_id}/export?format=csv`;
                window.open(exportURL, '_blank');
                showToast(`✅ 导出成功！共 ${selectedCount} 个字段`, 'success');
                return;
            } else if (runStatus.status === 'failed') {
                throw new Error('采集失败');
            }
        }
        
        throw new Error('采集超时');
        
    } catch (error) {
        alert('导出失败: ' + error.message);
    }
}

// ==================== iframe 消息监听（AI 增强版）====================

window.addEventListener('message', async (event) => {
    if (event.data && event.data.type === 'element-clicked') {
        const element = event.data.element;
        
        const loadingToast = showToast('🤖 AI 正在分析...', 'info');
        
        let suggestedName = '字段';
        try {
            const aiResponse = await fetch(`${API_BASE}/api/ai/suggest-field-name`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    element: {
                        text: element.text || '',
                        tagName: element.tagName || '',
                        className: element.className || '',
                        id: element.id || '',
                        href: element.href || '',
                        src: element.src || ''
                    },
                    context: {
                        previousText: '',
                        parentClassName: '',
                        surroundingText: element.text || '',
                        isInList: false,
                        pageType: 'unknown'
                    }
                })
            });
            
            if (aiResponse.ok) {
                const aiResult = await aiResponse.json();
                suggestedName = aiResult.fieldName || suggestedName;
                console.log(`[AI] 建议字段名: ${suggestedName} (置信度: ${aiResult.confidence}, 来源: ${aiResult.source})`);
            }
            
            if (loadingToast) loadingToast.remove();
            
        } catch (error) {
            console.warn('[AI] 字段名建议失败，使用默认规则:', error);
            suggestedName = suggestFieldNameLocal(element);
            if (loadingToast) loadingToast.remove();
        }
        
        const finalName = prompt(
            `AI 建议字段名: ${suggestedName}\n\n` +
            `标签: ${element.tagName}\n` +
            `文本: ${element.text}\n` +
            `选择器: ${element.selector}\n\n` +
            `请确认或修改字段名称：`,
            suggestedName
        );
        
        if (finalName && finalName.trim()) {
            const userSelectedField = {
                name: finalName.trim(),
                selector: element.selector,
                type: element.tagName,
                attr: element.tagName === 'IMG' ? 'src' : (element.tagName === 'A' ? 'href' : 'text'),
                userSelected: true,
                sample_data: [element.text || '']
            };
            
            if (currentMode === 'smart') {
                addUserSelectedToSuggestions(userSelectedField);
            } else {
                configuredFields.push(userSelectedField);
                fieldsConfirmed = false;
                renderFields();
                document.getElementById('configModal').classList.add('active');
            }
            
            showToast(`✅ 已添加字段: ${finalName}`, 'success');
        }
    }
});

function addUserSelectedToSuggestions(userField) {
    const existingIdx = smartSuggestions.findIndex(s => s.selector === userField.selector);
    
    if (existingIdx !== -1) {
        smartSuggestions[existingIdx].userSelected = true;
        const existing = smartSuggestions.splice(existingIdx, 1)[0];
        smartSuggestions.unshift(existing);
    } else {
        smartSuggestions.unshift({
            name: userField.name,
            selector: userField.selector,
            type: userField.type,
            attr: userField.attr,
            count: 1,
            sample_data: userField.sample_data,
            confidence: 1.0,
            userSelected: true
        });
    }
    
    displaySmartResults({ suggestions: smartSuggestions });
    
    selectedSuggestions.add(0);
    document.querySelectorAll('.suggestion-card')[0]?.classList.add('selected');
}

function suggestFieldNameLocal(element) {
    const tag = (element.tagName || '').toLowerCase();
    const text = (element.text || '').toLowerCase();
    const className = (element.className || '').toLowerCase();
    
    if (tag === 'h1' || tag === 'h2' || tag === 'h3') return '标题';
    if (tag === 'h4' || tag === 'h5') return '副标题';
    if (tag === 'a') return '链接';
    if (tag === 'img') return '图片';
    
    if (text.includes('¥') || text.includes('$') || text.includes('价格') || text.includes('price')) {
        return '价格';
    }
    if (text.includes('时间') || text.includes('日期') || text.includes('发布')) {
        return '时间';
    }
    if (text.includes('评分') || text.includes('分数') || className.includes('rating') || className.includes('score')) {
        return '评分';
    }
    if (text.includes('作者') || className.includes('author')) {
        return '作者';
    }
    if (text.includes('标签') || className.includes('tag')) {
        return '标签';
    }
    
    if (text.length > 100) return '描述';
    if (text.length > 50) return '简介';
    
    return `字段${configuredFields.length + 1}`;
}

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('urlInput').focus();
    document.getElementById('urlInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loadPage();
    });
});

