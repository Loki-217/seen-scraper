// services/web/js/core/data-scraper.js

import { state } from './state.js';
import { api } from './api.js';
import { showToast, escapeHtml } from './utils.js';

export async function startScraping() {
    if (!state.fieldsConfirmed || state.configuredFields.length === 0) {
        alert('请先确认字段配置');
        return;
    }
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const jobName = `采集_${timestamp}`;
    
    try {
        showPreviewLoading();
        
        // 步骤1: 创建任务
        const jobData = {
            name: jobName,
            start_url: state.currentUrl,
            status: "active",
            selectors: state.configuredFields.map(field => ({
                name: field.name,
                css: field.selector,
                attr: field.attr,
                limit: 100
            }))
        };
        
        const job = await api.createJob(jobData);
        console.log('[Scraping] 任务创建成功, ID:', job.id);
        
        // 步骤2: 执行采集
        const run = await api.runJob(job.id, { 
            url: state.currentUrl, 
            limit: 100 
        });
        
        state.currentRunId = run.run_id;
        console.log('[Scraping] 采集已启动, Run ID:', state.currentRunId);
        
        // 步骤3: 轮询结果
        await pollResults(state.currentRunId);
        
    } catch (error) {
        console.error('[Scraping] 异常:', error);
        alert('采集失败: ' + error.message);
        clearPreview();
    }
}

async function pollResults(runId, maxAttempts = 20) {
    for (let i = 0; i < maxAttempts; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        try {
            const runStatus = await api.getRunStatus(runId);
            console.log(`[Scraping] 第 ${i + 1} 次检查, 状态:`, runStatus.status);
            
            if (runStatus.status === 'succeeded') {
                console.log('[Scraping] ✅ 采集成功！');
                await fetchResults(runId);
                return;
            } else if (runStatus.status === 'failed') {
                throw new Error('采集失败: ' + (runStatus.stats?.error || '未知错误'));
            }
        } catch (error) {
            console.error('[Scraping] 检查结果时出错:', error);
            clearPreview();
            alert('检查采集状态失败: ' + error.message);
            return;
        }
    }
    
    throw new Error('采集超时（20秒）');
}

async function fetchResults(runId) {
    try {
        const results = await api.getResults(runId);
        console.log('[Scraping] 获取到结果:', Object.keys(results));
        
        renderPreview(results);
        document.getElementById('exportBtn').disabled = false;
        
    } catch (error) {
        console.error('[Scraping] 获取结果错误:', error);
        alert('获取结果失败: ' + error.message);
        clearPreview();
    }
}

export function renderPreview(results) {
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

export function showPreviewLoading() {
    const container = document.getElementById('previewContent');
    container.innerHTML = `
        <div class="preview-empty">
            <div class="spinner" style="margin: 0 auto 1rem;"></div>
            正在采集数据...
        </div>
    `;
}

export function clearPreview() {
    const container = document.getElementById('previewContent');
    container.innerHTML = `
        <div class="preview-empty">
            请先确认字段并设置，然后点击"确认配置"以预览数据
        </div>
    `;
    document.getElementById('exportBtn').disabled = true;
    state.currentRunId = null;
}

export function exportData() {
    if (!state.currentRunId) {
        alert('没有可导出的数据');
        return;
    }
    
    const exportURL = `${state.API_BASE}/runs/${state.currentRunId}/export?format=csv`;
    window.open(exportURL, '_blank');
}

// 智能模式预览
export async function previewSmartData() {
    if (state.selectedSuggestions.size === 0) {
        alert('请至少选择一个字段');
        return;
    }
    
    const loadingModal = createPreviewModal();
    showModalLoading(loadingModal);
    
    try {
        const fields = Array.from(state.selectedSuggestions).map(idx => {
            const sug = state.smartSuggestions[idx];
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

export function switchPreviewFile() {
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
        start_url: state.currentUrl,
        status: "active",
        selectors: fields.map(field => ({
            name: field.name,
            css: field.selector,
            attr: field.attr,
            limit: 20
        }))
    };
    
    const job = await api.createJob(jobData);
    const run = await api.runJob(job.id, { url: state.currentUrl, limit: 20 });
    
    // 轮询等待结果
    for (let i = 0; i < 20; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        const runStatus = await api.getRunStatus(run.run_id);
        
        if (runStatus.status === 'succeeded') {
            return await api.getResults(run.run_id);
        } else if (runStatus.status === 'failed') {
            throw new Error('采集失败');
        }
    }
    
    throw new Error('采集超时');
}

// 智能模式导出
export async function exportSmartData() {
    if (state.selectedSuggestions.size === 0) {
        alert('请至少选择一个字段');
        return;
    }
    
    const selectedCount = state.selectedSuggestions.size;
    const confirmMsg = selectedCount > 1 
        ? `您选中了 ${selectedCount} 个字段，将生成 ${selectedCount} 个文件。\n是否继续导出？`
        : `确认导出选中的字段数据？`;
    
    if (!confirm(confirmMsg)) {
        return;
    }
    
    showToast('🚀 开始导出...', 'info');
    
    try {
        const fields = Array.from(state.selectedSuggestions).map(idx => {
            const sug = state.smartSuggestions[idx];
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
            start_url: state.currentUrl,
            status: "active",
            selectors: fields.map(field => ({
                name: field.name,
                css: field.selector,
                attr: field.attr,
                limit: 100
            }))
        };
        
        const job = await api.createJob(jobData);
        const run = await api.runJob(job.id, { url: state.currentUrl, limit: 100 });
        
        // 等待完成
        for (let i = 0; i < 30; i++) {
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            const runStatus = await api.getRunStatus(run.run_id);
            
            if (runStatus.status === 'succeeded') {
                const exportURL = `${state.API_BASE}/runs/${run.run_id}/export?format=csv`;
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