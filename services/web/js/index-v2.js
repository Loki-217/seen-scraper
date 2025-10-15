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
        
        // 🔥 并行加载页面预览和智能分析
        const [previewResult, analysisResult] = await Promise.all([
            // 加载页面预览
            fetch(`${API_BASE}/api/proxy/render`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, timeout_ms: 30000 })
            }).then(r => r.json()),
            
            // 加载智能分析
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
        
        // 🔥 加载预览页面到 iframe
        // 🔥 加载预览页面到 iframe
        if (previewResult.success && previewResult.html) {
            console.log('[SmartMode] 加载预览页面, HTML长度:', previewResult.html.length);
            
            const iframe = document.getElementById('smartPreviewFrame');
            
            // 🔥 注入高亮样式
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
            
            // 🔥 使用 Blob URL 替代 srcdoc（避免大 HTML 内容问题）
            try {
                // 创建 Blob
                const blob = new Blob([styledHtml], { type: 'text/html; charset=utf-8' });
                const blobUrl = URL.createObjectURL(blob);
                
                // 清理旧的 Blob URL（如果存在）
                if (iframe.dataset.blobUrl) {
                    URL.revokeObjectURL(iframe.dataset.blobUrl);
                }
                
                // 设置新的 URL
                iframe.src = blobUrl;
                iframe.dataset.blobUrl = blobUrl;
                
                console.log('[SmartMode] 预览页面已加载 (Blob URL)');
                
                // iframe 加载完成后清理 Blob URL（可选）
                iframe.onload = () => {
                    console.log('[SmartMode] iframe 加载完成');
                    // 注意：不要立即清理，因为高亮功能需要访问 iframe
                };
                
            } catch (error) {
                console.error('[SmartMode] Blob URL 创建失败，降级到 srcdoc:', error);
                // 降级方案：使用 srcdoc
                iframe.srcdoc = styledHtml;
            }
        } else {
            console.warn('[SmartMode] 预览加载失败');
        }
        
        // 🔥 显示智能分析结果
        if (analysisResult.success) {
            console.log('[SmartMode] 显示分析结果, 字段数:', analysisResult.suggestions?.length);
            displaySmartResults(analysisResult);
            
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
        <div class="suggestion-card" 
             data-index="${idx}"
             data-selector="${escapeAttribute(sug.selector)}"
             onclick="toggleSuggestion(${idx})"
             onmouseenter="highlightElements(\`${escapeBacktick(sug.selector)}\`)"
             onmouseleave="clearHighlight()">
            
            <!-- 标题行 -->
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <span style="font-weight: 600; font-size: 1.1rem; color: #333;">${sug.name}</span>
                <span style="padding: 0.25rem 0.75rem; background: #667eea; color: white; border-radius: 12px; font-size: 0.75rem; font-weight: 600;">
                    ${sug.type}
                </span>
            </div>
            
            <!-- 选择器信息 -->
            <div style="color: #666; font-size: 0.9rem; margin-bottom: 0.75rem;">
                <strong style="color: #333;">选择器:</strong> 
                <code style="background: #f5f5f5; padding: 3px 8px; border-radius: 4px; font-size: 0.85rem; color: #d63384;">
                    ${escapeHtml(sug.selector)}
                </code><br>
                <strong style="color: #333;">数量:</strong> 
                <span style="color: #667eea; font-weight: 600;">${sug.count}</span> 个
            </div>
            
            <!-- 🔥 示例数据区域 -->
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
            
            <!-- 🔥 置信度条 -->
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
// ========== 确认字段并采集 ==========
async function confirmFields() {
    console.log('[confirmFields] 开始确认字段...');
    
    if (configuredFields.length === 0) {
        alert('请先配置字段');
        return;
    }
    
    // 检查是否所有字段都有名称
    const unnamedFields = configuredFields.filter(f => !f.name || f.name.trim() === '');
    if (unnamedFields.length > 0) {
        alert('请为所有字段命名');
        return;
    }
    
    console.log('[confirmFields] 已配置的字段:', configuredFields);
    
    fieldsConfirmed = true;
    updateConfirmButton();
    toggleConfigModal();
    
    // 🔥 立即开始采集
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
    
    // 🔥 生成唯一的任务名称
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const jobName = `采集_${timestamp}`;
    
    console.log('[startScraping] 任务名称:', jobName);
    console.log('[startScraping] 目标URL:', currentUrl);
    console.log('[startScraping] 配置的字段:', configuredFields);
    
    try {
        // 显示加载状态
        showPreviewLoading();
        
        // 🔥 步骤1: 创建任务
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
        
        // 🔥 步骤2: 执行采集
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
        
        // 🔥 步骤3: 轮询结果
        console.log('[startScraping] 步骤3: 等待采集完成...');
        
        let attempts = 0;
        const maxAttempts = 20; // 最多等待20秒
        
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
                    // 继续等待
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
        
        // 1秒后开始检查
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
        console.log('[fetchResults] 数据行数:', Object.keys(results).length > 0 ? results[Object.keys(results)[0]].length : 0);
        
        renderPreview(results);
        
        // 启用导出按钮
        document.getElementById('exportBtn').disabled = false;
        
        console.log('[fetchResults] ✅ 结果渲染完成');
        
    } catch (error) {
        console.error('[fetchResults] 错误:', error);
        alert('获取结果失败: ' + error.message);
        clearPreview();
    }
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

// ========== 新增：高亮和预览辅助函数 ==========

// 🔥 转义 HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 🔥 转义属性中的引号
function escapeAttribute(text) {
    return (text || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// 🔥 转义模板字符串中的反引号
function escapeBacktick(text) {
    return (text || '').replace(/`/g, '\\`').replace(/\$/g, '\\$');
}

// 🔥 高亮左侧预览中的元素
function highlightElements(selector) {
    const iframe = document.getElementById('smartPreviewFrame');
    if (!iframe || !iframe.contentWindow) return;
    
    try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        
        // 清除之前的高亮
        const highlighted = iframeDoc.querySelectorAll('.seenfetch-highlight');
        highlighted.forEach(el => {
            el.classList.remove('seenfetch-highlight');
        });
        
        // 添加新的高亮
        const elements = iframeDoc.querySelectorAll(selector);
        console.log(`[Highlight] 找到 ${elements.length} 个元素:`, selector);
        
        elements.forEach((el, index) => {
            el.classList.add('seenfetch-highlight');
        });
        
        // 滚动到第一个元素
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

// 🔥 清除高亮
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

// 🔥 查看全部示例数据
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


