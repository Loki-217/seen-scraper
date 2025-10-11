// services/web/js/modules/smart-mode.js
/**
 * 🤖 智能识别模式
 */

import { $, show, hide, empty, createElement } from '../utils/dom.js';
import { apiClient } from '../api/client.js';
import { Toast } from '../ui/toast.js';
import { Loading } from '../ui/loading.js';

export class SmartMode {
    constructor(fieldManager) {
        this.fieldManager = fieldManager;
        this.container = $('smartMode');
        this.resultsContainer = $('suggestionsList');
        this.statsBox = $('statsBox');
        this.loading = new Loading('smartMode', 'AI 正在分析页面结构...');
        
        this.suggestions = [];
        this.selectedIndices = new Set();
    }
    
    /**
     * 分析页面
     */
    async analyzePage(url) {
        if (!url) {
            Toast.error('请输入网页地址');
            return false;
        }
        
        this.loading.show();
        
        try {
            console.log('[SmartMode] Analyzing:', url);
            
            const data = await apiClient.analyzePage(url);
            
            if (data.success) {
                this.displayResults(data);
                Toast.success('智能分析完成！');
                return true;
            } else {
                Toast.error('分析失败: ' + data.error);
                return false;
            }
            
        } catch (error) {
            console.error('[SmartMode] Error:', error);
            Toast.error('分析失败: ' + error.message);
            return false;
        } finally {
            this.loading.hide();
        }
    }
    
    /**
     * 显示分析结果
     */
    displayResults(data) {
        // 显示统计信息
        if (data.stats) {
            this.displayStats(data.stats);
        }
        
        // 显示字段建议
        this.suggestions = data.suggestions || [];
        
        if (this.suggestions.length === 0) {
            this.displayEmptyState();
            return;
        }
        
        this.renderSuggestions();
    }
    
    /**
     * 显示统计信息
     */
    displayStats(stats) {
        show(this.statsBox);
        
        $('statWords').textContent = stats.total_words || 0;
        $('statLinks').textContent = stats.total_links || 0;
        $('statImages').textContent = stats.total_images || 0;
    }
    
    /**
     * 渲染建议列表
     */
    renderSuggestions() {
        empty(this.resultsContainer);
        
        this.suggestions.forEach((suggestion, index) => {
            const card = this.createSuggestionCard(suggestion, index);
            this.resultsContainer.appendChild(card);
        });
    }
    
    /**
     * 创建建议卡片
     */
    createSuggestionCard(suggestion, index) {
        const card = createElement('div', {
            className: 'suggestion-card',
            onclick: () => this.toggleSuggestion(index)
        });
        
        // 头部
        const header = createElement('div', { className: 'suggestion-header' });
        
        const name = createElement('span', {
            className: 'suggestion-name'
        }, [suggestion.name]);
        
        const type = createElement('span', {
            className: 'suggestion-type'
        }, [suggestion.type]);
        
        header.appendChild(name);
        header.appendChild(type);
        
        // 信息
        const info = createElement('div', { className: 'suggestion-info' });
        info.innerHTML = `
            <strong>选择器:</strong> <code>${suggestion.selector}</code><br>
            <strong>数量:</strong> ${suggestion.count} 个
        `;
        
        // 示例数据
        let samples = null;
        if (suggestion.sample_data && suggestion.sample_data.length > 0) {
            samples = createElement('div', { className: 'suggestion-samples' });
            samples.innerHTML = `
                <strong>示例:</strong><br>
                ${suggestion.sample_data.map(s => `• ${s}`).join('<br>')}
            `;
        }
        
        // 置信度条
        const confidenceBar = createElement('div', { className: 'confidence-bar' });
        const confidenceFill = createElement('div', {
            className: 'confidence-fill',
            style: { width: `${(suggestion.confidence || 0.5) * 100}%` }
        });
        confidenceBar.appendChild(confidenceFill);
        
        // 组装
        card.appendChild(header);
        card.appendChild(info);
        if (samples) card.appendChild(samples);
        card.appendChild(confidenceBar);
        
        return card;
    }
    
    /**
     * 切换选中状态
     */
    toggleSuggestion(index) {
        const cards = this.resultsContainer.querySelectorAll('.suggestion-card');
        const card = cards[index];
        
        if (this.selectedIndices.has(index)) {
            this.selectedIndices.delete(index);
            card.classList.remove('selected');
        } else {
            this.selectedIndices.add(index);
            card.classList.add('selected');
        }
    }
    
    /**
     * 全选
     */
    selectAll() {
        const cards = this.resultsContainer.querySelectorAll('.suggestion-card');
        cards.forEach((card, index) => {
            card.classList.add('selected');
            this.selectedIndices.add(index);
        });
    }
    
    /**
     * 应用选中的建议
     */
    applySelectedSuggestions() {
        if (this.selectedIndices.size === 0) {
            Toast.warning('请至少选择一个字段');
            return;
        }
        
        this.selectedIndices.forEach(index => {
            const suggestion = this.suggestions[index];
            this.fieldManager.addField({
                name: suggestion.name,
                selector: suggestion.selector,
                type: suggestion.type,
                attr: suggestion.type === 'image' ? 'src' : (suggestion.type === 'link' ? 'href' : 'text'),
                samples: suggestion.sample_data || []
            });
        });
        
        Toast.success(`已添加 ${this.selectedIndices.size} 个字段`);
        
        // 清空选中状态
        this.selectedIndices.clear();
    }
    
    /**
     * 显示空状态
     */
    displayEmptyState() {
        empty(this.resultsContainer);
        const emptyState = createElement('div', { className: 'empty-state' });
        emptyState.innerHTML = `
            <div class="empty-state-icon">🤖</div>
            <p>未找到可采集的字段</p>
            <small>请尝试其他页面或使用手动模式</small>
        `;
        this.resultsContainer.appendChild(emptyState);
    }
    
    /**
     * 显示模式
     */
    show() {
        show(this.container);
    }
    
    /**
     * 隐藏模式
     */
    hide() {
        hide(this.container);
    }
}

export default SmartMode;