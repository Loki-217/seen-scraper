// services/web/js/core/smart-mode-ui.js

import { state } from './state.js';
import { escapeHtml, escapeAttribute, escapeBacktick } from './utils.js';

export function renderSmartSuggestions() {
    const container = document.getElementById('suggestionsList');
    
    if (state.smartSuggestions.length === 0) {
        container.innerHTML = '<p style="text-align: center; color: #999; padding: 2rem;">未找到可采集的字段</p>';
        return;
    }
    
    container.innerHTML = state.smartSuggestions.map((sug, idx) => 
        createSuggestionCard(sug, idx)
    ).join('');
    
    updateActionButtons();
}

function createSuggestionCard(sug, idx) {
    return `
        <div class="suggestion-card ${sug.userSelected ? 'user-selected' : ''}" 
             data-index="${idx}"
             onclick="toggleSuggestion(${idx})"
             onmouseenter="highlightElements(\`${escapeBacktick(sug.selector)}\`)"
             onmouseleave="clearHighlight()">
            
            ${sug.userSelected ? `
                <div style="background: linear-gradient(135deg, #4CAF50, #45a049); color: white; padding: 0.5rem; border-radius: 8px 8px 0 0; margin: -1rem -1rem 0.75rem -1rem; display: flex; align-items: center; gap: 0.5rem;">
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
                <strong>选择器:</strong> <code style="background: #f5f5f5; padding: 3px 8px; border-radius: 4px;">${escapeHtml(sug.selector)}</code><br>
                <strong>数量:</strong> <span style="color: #667eea; font-weight: 600;">${sug.count}</span> 个
            </div>
            
            ${renderSampleData(sug, idx)}
            ${renderConfidenceBar(sug)}
        </div>
    `;
}

function renderSampleData(sug, idx) {
    if (!sug.sample_data || sug.sample_data.length === 0) {
        return `
            <div style="margin-top: 0.75rem; background: #fff3cd; padding: 0.75rem; border-radius: 8px; border-left: 4px solid #ffc107; color: #856404; font-size: 0.9rem;">
                ⚠️ 暂无示例数据
            </div>
        `;
    }
    
    return `
        <div style="margin-top: 0.75rem; background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%); padding: 0.75rem; border-radius: 8px; border-left: 4px solid #667eea;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                <strong style="color: #667eea; font-size: 0.95rem;">📋 数据示例</strong>
                <span style="font-size: 0.8rem; color: #999;">前 ${Math.min(3, sug.sample_data.length)} 条</span>
            </div>
            <ul style="margin: 0; padding-left: 1.2rem; list-style: none;">
                ${sug.sample_data.slice(0, 3).map((sample, i) => `
                    <li style="color: #333; font-size: 0.9rem; margin: 0.5rem 0; padding-left: 0.5rem; border-left: 2px solid #667eea; line-height: 1.5;">
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
    `;
}

function renderConfidenceBar(sug) {
    const conf = sug.confidence || 0.5;
    const color = conf >= 0.8 ? '#4CAF50' : conf >= 0.6 ? '#FFA726' : '#999';
    
    return `
        <div style="margin-top: 0.75rem;">
            <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #666; margin-bottom: 0.25rem;">
                <span>AI 置信度</span>
                <span style="font-weight: 600; color: ${color};">${Math.round(conf * 100)}%</span>
            </div>
            <div style="height: 6px; background: #e0e0e0; border-radius: 3px; overflow: hidden;">
                <div style="height: 100%; background: ${color}; width: ${conf * 100}%; transition: width 0.5s ease;"></div>
            </div>
        </div>
    `;
}

function updateActionButtons() {
    const actionBar = document.querySelector('#smartMode .action-bar');
    if (!actionBar) return;
    
    actionBar.innerHTML = `
        <button class="btn" style="background: #e0e0e0; color: #333;" onclick="selectAllSuggestions()">✓ 全选</button>
        <button class="btn btn-primary" style="flex: 1" onclick="previewSmartData()">👁️ 预览数据</button>
        <button class="btn btn-primary" style="flex: 1" onclick="applySmartSelections()">✅ 应用选中字段</button>
        <button class="btn" style="background: #4CAF50; color: white; flex: 1" onclick="exportSmartData()">📥 导出数据</button>
    `;
}

export function showAllSamples(idx) {
    const sug = state.smartSuggestions[idx];
    
    const modal = document.createElement('div');
    modal.id = 'samplesModal';
    modal.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); z-index: 99999; display: flex; align-items: center; justify-content: center;';
    modal.onclick = () => modal.remove();
    
    modal.innerHTML = `
        <div style="background: white; padding: 2rem; border-radius: 16px; max-width: 700px; max-height: 80vh; overflow-y: auto; box-shadow: 0 10px 40px rgba(0,0,0,0.3);" onclick="event.stopPropagation()">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h3 style="margin: 0; color: #333;">${sug.name} - 全部示例数据</h3>
                <button onclick="this.closest('#samplesModal').remove()" style="background: #f5f5f5; border: none; width: 32px; height: 32px; border-radius: 50%; cursor: pointer; font-size: 1.2rem;">✕</button>
            </div>
            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <p style="margin: 0; color: #666; font-size: 0.95rem;">
                    <strong>选择器:</strong> <code>${escapeHtml(sug.selector)}</code><br>
                    <strong>类型:</strong> ${sug.type}<br>
                    <strong>总数:</strong> ${sug.sample_data.length} 条
                </p>
            </div>
            <div style="max-height: 400px; overflow-y: auto;">
                <ol style="list-style: none; padding: 0; margin: 0;">
                    ${sug.sample_data.map((sample, i) => `
                        <li style="padding: 0.75rem 1rem; margin: 0.5rem 0; background: ${i % 2 === 0 ? '#f9f9f9' : 'white'}; border-radius: 8px; border-left: 3px solid #667eea;">
                            <span style="color: #999; font-size: 0.85rem; font-weight: 600; margin-right: 0.75rem;">#${i + 1}</span>
                            <span style="color: #333; font-size: 0.95rem; line-height: 1.5;">${escapeHtml(sample)}</span>
                        </li>
                    `).join('')}
                </ol>
            </div>
            <button class="btn btn-primary" style="width: 100%; margin-top: 1.5rem; padding: 0.75rem;" onclick="this.closest('#samplesModal').remove()">关闭</button>
        </div>
    `;
    
    document.body.appendChild(modal);
}