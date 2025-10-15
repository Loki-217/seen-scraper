// services/web/js/index-v2.js

import { state } from './core/state.js';
import { loadManualMode, switchToSmartMode } from './core/manual-mode.js';
import { 
    loadSmartMode, 
    toggleSuggestion, 
    selectAllSuggestions, 
    applySmartSelections,
    highlightElements,
    clearHighlight
} from './core/smart-mode.js';
import { showAllSamples } from './core/smart-mode-ui.js';
import { 
    renderFields, 
    updateFieldName, 
    removeField, 
    clearFields, 
    confirmFields,
    handleElementClick 
} from './core/field-manager.js';
import { 
    startScraping, 
    renderPreview,
    clearPreview, 
    exportData,
    previewSmartData,
    exportSmartData,
    switchPreviewFile
} from './core/data-scraper.js';

// ========== 模式切换 ==========
function switchMode(mode) {
    state.currentMode = mode;
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
    
    state.currentUrl = url;
    state.fieldsConfirmed = false;
    document.getElementById('confirmBtn').disabled = false;
    clearPreview();
    
    if (state.currentMode === 'manual') {
        await loadManualMode(url);
    } else {
        await loadSmartMode(url);
    }
}

// ========== iframe 消息监听（AI 增强版）==========
window.addEventListener('message', async (event) => {
    if (event.data && event.data.type === 'element-clicked') {
        await handleElementClick(event.data.element);
    }
});

// ========== 初始化 ==========
document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('urlInput').focus();
    document.getElementById('urlInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') loadPage();
    });
});

// ========== 全局导出（供 HTML onclick 使用）==========
window.switchMode = switchMode;
window.toggleConfigModal = toggleConfigModal;
window.closeModalOnBackdrop = closeModalOnBackdrop;
window.loadPage = loadPage;
window.switchToSmartMode = switchToSmartMode;
window.toggleSuggestion = toggleSuggestion;
window.selectAllSuggestions = selectAllSuggestions;
window.applySmartSelections = applySmartSelections;
window.highlightElements = highlightElements;
window.clearHighlight = clearHighlight;
window.showAllSamples = showAllSamples;
window.renderFields = renderFields;
window.updateFieldName = updateFieldName;
window.removeField = removeField;
window.clearFields = clearFields;
window.confirmFields = confirmFields;
window.startScraping = startScraping;
window.clearPreview = clearPreview;
window.exportData = exportData;
window.previewSmartData = previewSmartData;
window.exportSmartData = exportSmartData;
window.switchPreviewFile = switchPreviewFile;