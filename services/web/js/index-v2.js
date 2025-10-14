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

// ========== 模式切换 ==========
function switchMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent.includes(mode === 'manual' ? '手动' : '智能'));
    });
    
    document.getElementById('manualMode').classList.toggle('hidden', mode !== 'manual');
    document.getElementById('smartMode').classList.toggle('hidden', mode === 'manual');
}

// ========== 配置弹窗 ==========
function toggleConfigModal() {
    document.getElementById('configModal').classList.toggle('active');
}

function closeModalOnBackdrop(event) {
    if (event.target.id === 'configModal') {
        toggleConfigModal();
    }
}

// ========== 加载页面 ==========
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

// ========== 手动模式 ==========
async function loadManualMode(url) {
    const loading = document.getElementById('loadingOverlay');
    loading.classList.remove('hidden');
    
    try {
        const response = await fetch(`${API_BASE}/api/proxy/render`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, timeout_ms: 30000 })
        });
        
        if (!response.ok) throw new Error('加载失败');
        
        const data = await response.json();
        document.getElementById('previewFrame').srcdoc = data.html;
        
    } catch (error) {
        alert('加载失败: ' + error.message);
    } finally {
        loading.classList.add('hidden');
    }
}

// ========== 智能模式 ==========
// services/web/js/index-v2.js

async function loadSmartMode(url) {
    // 🔥 显示配置对话框
    const useAdvanced = confirm(
        '🚀 高级选项\n\n' +
        '是否启用以下功能？\n\n' +
        '✅ 自动滚动加载（处理无限滚动）\n' +
        '✅ 隐身模式（绕过反爬虫检测）\n' +
        '✅ Markdown 分析（更精准的内容识别）\n\n' +
        '点击"确定"启用高级功能\n' +
        '点击"取消"使用标准模式'
    );
    
    const loading = document.getElementById('smartLoading');
    loading.classList.remove('hidden');
    
    try {
        const requestBody = {
            url: url,
            auto_scroll: true,           // 🔥 始终启用自动滚动
            use_stealth: useAdvanced,    // 🔥 用户选择
            use_markdown: useAdvanced,   // 🔥 用户选择
            wait_for: null               // 可以后续扩展
        };
        
        console.log('[SmartMode] Request config:', requestBody);
        
        const response = await fetch(`${API_BASE}/api/smart/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) throw new Error('分析失败');
        
        const data = await response.json();
        
        if (data.success) {
            displaySmartResults(data);
            
            // 🔥 显示配置信息
            if (data.config_used) {
                const configInfo = [
                    data.config_used.auto_scroll ? '✅ 自动滚动' : '❌ 自动滚动',
                    data.config_used.use_stealth ? '✅ 隐身模式' : '❌ 隐身模式',
                    data.config_used.use_markdown ? '✅ Markdown分析' : '❌ Markdown分析'
                ].join(' | ');
                
                showToast(`分析完成！配置：${configInfo}`, 'success', 5000);
            }
        } else {
            alert('分析失败: ' + data.error);
        }
        
    } catch (error) {
        console.error('[SmartMode] Error:', error);
        alert('分析失败: ' + error.message);
    } finally {
        loading.classList.add('hidden');
    }
}

function displaySmartResults(data) {
    smartSuggestions = data.suggestions || [];
    const container = document.getElementById('suggestionsList');
    
    if (smartSuggestions.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999;">未找到可采集的字段</p>';
        return;
    }
    
    container.innerHTML = smartSuggestions.map((sug, idx) => `
        <div class="suggestion-card" onclick="toggleSuggestion(${idx})">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600; font-size: 1.1rem;">${sug.name}</span>
                <span style="padding: 0.25rem 0.75rem; background: #667eea; color: white; border-radius: 12px; font-size: 0.75rem;">${sug.type}</span>
            </div>
            <div style="color: #666; font-size: 0.9rem; margin-top: 0.5rem;">
                <strong>选择器:</strong> <code>${sug.selector}</code><br>
                <strong>数量:</strong> ${sug.count} 个
            </div>
        </div>
    `).join('');
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

// ========== 字段管理 ==========
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

// ========== 确认字段并采集 ==========
async function confirmFields() {
    if (configuredFields.length === 0) {
        alert('请先配置字段');
        return;
    }
    
    const unnamedFields = configuredFields.filter(f => !f.name || f.name.trim() === '');
    if (unnamedFields.length > 0) {
        alert('请为所有字段命名');
        return;
    }
    
    fieldsConfirmed = true;
    updateConfirmButton();
    toggleConfigModal();
    
    await startScraping();
}

async function startScraping() {
    if (!fieldsConfirmed || configuredFields.length === 0) {
        alert('请先确认字段配置');
        return;
    }
    
    const jobName = `采集任务_${new Date().toLocaleString()}`;
    
    try {
        showPreviewLoading();
        
        // 创建任务
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
        
        const jobRes = await fetch(`${API_BASE}/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });
        
        if (!jobRes.ok) throw new Error('创建任务失败');
        const job = await jobRes.json();
        
        // 执行采集
        const runRes = await fetch(`${API_BASE}/runs/jobs/${job.id}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: currentUrl, limit: 100 })
        });
        
        if (!runRes.ok) throw new Error('启动采集失败');
        const run = await runRes.json();
        currentRunId = run.run_id;
        
        // 等待采集完成
        setTimeout(async () => {
            await fetchResults(currentRunId);
        }, 3000);
        
    } catch (error) {
        alert('采集失败: ' + error.message);
        clearPreview();
    }
}

async function fetchResults(runId) {
    try {
        const resultRes = await fetch(`${API_BASE}/runs/${runId}/results`);
        if (!resultRes.ok) throw new Error('获取结果失败');
        
        const results = await resultRes.json();
        renderPreview(results);
        
        document.getElementById('exportBtn').disabled = false;
        
    } catch (error) {
        alert('获取结果失败: ' + error.message);
        clearPreview();
    }
}

// ========== 数据预览 ==========
function renderPreview(results) {
    const container = document.getElementById('previewContent');
    
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
        html += `<th>${col}</th>`;
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
    const container = document.getElementById('previewContent');
    container.innerHTML = `
        <div class="preview-empty">
            <div class="spinner" style="margin: 0 auto 1rem;"></div>
            正在采集数据...
        </div>
    `;
}

function clearPreview() {
    const container = document.getElementById('previewContent');
    container.innerHTML = `
        <div class="preview-empty">
            请先确认字段名设置，然后点击"确认配置"以预览数据
        </div>
    `;
    document.getElementById('exportBtn').disabled = true;
    currentRunId = null;
}

// ========== 导出数据 ==========
function exportData() {
    if (!currentRunId) {
        alert('没有可导出的数据');
        return;
    }
    
    const exportURL = `${API_BASE}/runs/${currentRunId}/export?format=csv`;
    window.open(exportURL, '_blank');
}

// ========== 工具函数 ==========
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========== iframe 消息监听（AI 增强版）==========
window.addEventListener('message', async (event) => {
    if (event.data && event.data.type === 'element-clicked') {
        const element = event.data.element;
        
        // 显示加载提示
        const loadingToast = showToast('🤖 AI 正在分析...', 'info');
        
        // 调用 AI 建议字段名
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
        
        // 显示确认对话框
        const finalName = prompt(
            `AI 建议字段名: ${suggestedName}\n\n` +
            `标签: ${element.tagName}\n` +
            `文本: ${element.text}\n` +
            `选择器: ${element.selector}\n\n` +
            `请确认或修改字段名称：`,
            suggestedName
        );
        
        if (finalName && finalName.trim()) {
            configuredFields.push({
                name: finalName.trim(),
                selector: element.selector,
                type: element.tagName,
                attr: element.tagName === 'IMG' ? 'src' : (element.tagName === 'A' ? 'href' : 'text')
            });
            fieldsConfirmed = false;
            renderFields();
            
            // 自动打开配置弹窗
            document.getElementById('configModal').classList.add('active');
            
            showToast(`✅ 已添加字段: ${finalName}`, 'success');
        }
    }
});

// 本地规则建议字段名（AI 降级方案）
function suggestFieldNameLocal(element) {
    const tag = (element.tagName || '').toLowerCase();
    const text = (element.text || '').toLowerCase();
    const className = (element.className || '').toLowerCase();
    
    if (tag === 'h1' || tag === 'h2' || tag === 'h3') return '标题';
    if (tag === 'h4' || tag === 'h5') return '副标题';
    if (tag === 'a') return '链接';
    if (tag === 'img') return '图片';
    
    if (text.includes('￥') || text.includes('$') || text.includes('价格') || text.includes('price')) {
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

// Toast 提示函数
function showToast(message, type = 'info') {
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
    }, 3000);
    
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

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('urlInput').focus();
    document.getElementById('urlInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loadPage();
    });
});

loadSmartMode