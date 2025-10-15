// services/web/js/core/field-manager.js

import { state } from './state.js';
import { api } from './api.js';
import { showToast } from './utils.js';

export function renderFields() {
    const container = document.getElementById('fieldsList');
    
    if (state.configuredFields.length === 0) {
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
    
    container.innerHTML = state.configuredFields.map((field, idx) => `
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

export function updateFieldName(idx, name) {
    state.configuredFields[idx].name = name;
    state.fieldsConfirmed = false;
    updateConfirmButton();
}

export function removeField(idx) {
    state.configuredFields.splice(idx, 1);
    state.fieldsConfirmed = false;
    renderFields();
    window.clearPreview();
}

export function clearFields() {
    if (state.configuredFields.length > 0) {
        if (confirm('确定要清空所有字段吗？')) {
            state.configuredFields = [];
            state.fieldsConfirmed = false;
            renderFields();
            window.clearPreview();
        }
    }
}

function updateConfirmButton() {
    const btn = document.getElementById('confirmBtn');
    btn.disabled = state.configuredFields.length === 0 || state.fieldsConfirmed;
    btn.textContent = state.fieldsConfirmed ? '✓ 已确认' : '✓ 确认配置';
}

export async function confirmFields() {
    if (state.configuredFields.length === 0) {
        alert('请先配置字段');
        return;
    }
    
    const unnamedFields = state.configuredFields.filter(f => !f.name || f.name.trim() === '');
    if (unnamedFields.length > 0) {
        alert('请为所有字段命名');
        return;
    }
    
    state.fieldsConfirmed = true;
    updateConfirmButton();
    window.toggleConfigModal();
    
    // 立即开始采集
    await window.startScraping();
}

// AI 字段名建议（用于手动点击元素）
export async function handleElementClick(element) {
    const loadingToast = showToast('🤖 AI 正在分析...', 'info');
    
    let suggestedName = '字段';
    try {
        const result = await api.suggestFieldName({
            text: element.text || '',
            tagName: element.tagName || '',
            className: element.className || '',
            id: element.id || '',
            href: element.href || '',
            src: element.src || ''
        }, {
            previousText: '',
            parentClassName: '',
            surroundingText: element.text || '',
            isInList: false,
            pageType: 'unknown'
        });
        
        suggestedName = result.fieldName || suggestedName;
        console.log(`[AI] 建议字段名: ${suggestedName} (置信度: ${result.confidence})`);
    } catch (error) {
        console.warn('[AI] 字段名建议失败，使用本地规则:', error);
        suggestedName = suggestFieldNameLocal(element);
    } finally {
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
        
        if (state.currentMode === 'smart') {
            await addUserSelectedToSuggestions(userSelectedField);  // 🔥 添加 await
        } else {
            state.configuredFields.push(userSelectedField);
            state.fieldsConfirmed = false;
            renderFields();
            document.getElementById('configModal').classList.add('active');
        }
        
        showToast(`✅ 已添加字段: ${finalName}`, 'success');
    }
}

// 🔥 修复：添加 async
async function addUserSelectedToSuggestions(userField) {
    const existingIdx = state.smartSuggestions.findIndex(s => s.selector === userField.selector);
    
    if (existingIdx !== -1) {
        state.smartSuggestions[existingIdx].userSelected = true;
        const existing = state.smartSuggestions.splice(existingIdx, 1)[0];
        state.smartSuggestions.unshift(existing);
    } else {
        state.smartSuggestions.unshift({
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
    
    // 🔥 修复：改为动态导入
    const { renderSmartSuggestions } = await import('./smart-mode-ui.js');
    renderSmartSuggestions();
    
    // 自动选中该字段
    state.selectedSuggestions.add(0);
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
    
    return `字段${state.configuredFields.length + 1}`;
}