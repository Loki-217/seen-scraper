// services/web/js/core/smart-mode.js

import { state } from './state.js';
import { api } from './api.js';
import { showToast } from './utils.js';
import { renderSmartSuggestions } from './smart-mode-ui.js';

export async function loadSmartMode(url) {
    const useAdvanced = confirm(
        '🚀 高级选项\n\n' +
        '是否启用以下功能？\n\n' +
        '✅ 自动滚动加载\n✅ 隐身模式\n✅ Markdown 分析\n\n' +
        '点击"确定"启用高级功能'
    );
    
    const previewLoading = document.getElementById('smartPreviewLoading');
    const analysisLoading = document.getElementById('smartLoading');
    
    previewLoading.classList.remove('hidden');
    analysisLoading.classList.remove('hidden');
    
    try {
        const [previewResult, analysisResult] = await Promise.all([
            api.renderPage(url).then(r => r.json()),
            api.analyzePageSmart(url, {
                auto_scroll: true,
                use_stealth: useAdvanced,
                use_markdown: useAdvanced,
                wait_for: null
            })
        ]);
        
        if (previewResult.success && previewResult.html) {
            loadPreviewIframe(previewResult.html);
        }
        
        if (analysisResult.success) {
            state.smartSuggestions = analysisResult.suggestions || [];
            renderSmartSuggestions();
            
            if (analysisResult.config_used) {
                const info = [
                    analysisResult.config_used.auto_scroll ? '✅ 自动滚动' : '❌ 自动滚动',
                    analysisResult.config_used.use_stealth ? '✅ 隐身模式' : '❌ 隐身模式',
                    analysisResult.config_used.use_markdown ? '✅ Markdown' : '❌ Markdown'
                ].join(' | ');
                showToast(`✅ 分析完成！${info}`, 'success', 5000);
            }
        } else {
            alert('分析失败: ' + analysisResult.error);
        }
        
    } catch (error) {
        alert('加载失败: ' + error.message);
    } finally {
        previewLoading.classList.add('hidden');
        analysisLoading.classList.add('hidden');
    }
}

function loadPreviewIframe(html) {
    const iframe = document.getElementById('smartPreviewFrame');
    const styledHtml = html.replace('</head>', `
        <style>
            .seenfetch-highlight {
                outline: 3px solid #4CAF50 !important;
                outline-offset: 2px;
                background: rgba(76, 175, 80, 0.15) !important;
                box-shadow: 0 0 10px rgba(76, 175, 80, 0.3) !important;
                transition: all 0.3s ease !important;
                position: relative !important;
                z-index: 999 !important;
            }
        </style></head>`
    );
    
    try {
        const blob = new Blob([styledHtml], { type: 'text/html; charset=utf-8' });
        const blobUrl = URL.createObjectURL(blob);
        if (iframe.dataset.blobUrl) URL.revokeObjectURL(iframe.dataset.blobUrl);
        iframe.src = blobUrl;
        iframe.dataset.blobUrl = blobUrl;
    } catch {
        iframe.srcdoc = styledHtml;
    }
}

export function toggleSuggestion(idx) {
    const card = document.querySelectorAll('.suggestion-card')[idx];
    card.classList.toggle('selected');
    state.selectedSuggestions.has(idx) ? 
        state.selectedSuggestions.delete(idx) : 
        state.selectedSuggestions.add(idx);
}

export function selectAllSuggestions() {
    document.querySelectorAll('.suggestion-card').forEach((card, idx) => {
        card.classList.add('selected');
        state.selectedSuggestions.add(idx);
    });
}

export function applySmartSelections() {
    if (state.selectedSuggestions.size === 0) {
        alert('请至少选择一个字段');
        return;
    }
    
    state.configuredFields = Array.from(state.selectedSuggestions).map(idx => {
        const sug = state.smartSuggestions[idx];
        return {
            name: sug.name,
            selector: sug.selector,
            type: sug.type,
            attr: sug.type === 'image' ? 'src' : (sug.type === 'link' ? 'href' : 'text')
        };
    });
    
    window.renderFields();
    window.toggleConfigModal();
}

// 高亮功能
export function highlightElements(selector) {
    const iframe = document.getElementById('smartPreviewFrame');
    if (!iframe?.contentWindow) return;
    
    try {
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        doc.querySelectorAll('.seenfetch-highlight').forEach(el => 
            el.classList.remove('seenfetch-highlight')
        );
        doc.querySelectorAll(selector).forEach((el, i) => {
            el.classList.add('seenfetch-highlight');
            if (i === 0) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
    } catch (e) {}
}

export function clearHighlight() {
    const iframe = document.getElementById('smartPreviewFrame');
    if (!iframe?.contentWindow) return;
    try {
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        doc.querySelectorAll('.seenfetch-highlight').forEach(el => 
            el.classList.remove('seenfetch-highlight')
        );
    } catch (e) {}
}