// 智能模式模块
import { Toast } from '../ui/toast.js';
import { CONFIG } from '../config.js';

// 🔥 简化工具函数
function $(id) {
    return document.getElementById(id);
}

function show(element) {
    if (element) element.classList.remove('hidden');
}

function hide(element) {
    if (element) element.classList.add('hidden');
}

export class SmartMode {
    constructor(apiClient, fieldManager) {
        console.log('[SmartMode] Constructor called');
        this.apiClient = apiClient;
        this.fieldManager = fieldManager;
        this.loading = $('smartLoading');
        this.statsBox = $('statsBox');
        this.suggestionsList = $('suggestionsList');
        
        this.suggestions = [];
        this.selectedIndices = new Set();
    }
    
    async analyzePage(url) {
        console.log('[SmartMode] analyzePage called');
        
        if (!url) {
            Toast.error('请输入网页地址');
            return false;
        }
        
        if (this.loading) show(this.loading);
        
        try {
            console.log('[SmartMode] Calling API...');
            
            const data = await this.apiClient.post(`${CONFIG.ENDPOINTS.SMART_ANALYZE}?url=${encodeURIComponent(url)}`);
            
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
            if (this.loading) hide(this.loading);
        }
    }
    
    displayResults(data) {
        // 显示统计
        if (data.stats && this.statsBox) {
            show(this.statsBox);
            const statWords = $('statWords');
            const statLinks = $('statLinks');
            const statImages = $('statImages');
            
            if (statWords) statWords.textContent = data.stats.total_words || 0;
            if (statLinks) statLinks.textContent = data.stats.total_links || 0;
            if (statImages) statImages.textContent = data.stats.total_images || 0;
        }
        
        // 显示建议
        this.suggestions = data.suggestions || [];
        
        if (!this.suggestionsList) {
            console.error('[SmartMode] suggestionsList element not found');
            return;
        }
        
        if (this.suggestions.length === 0) {
            this.suggestionsList.innerHTML = '<p style="text-align: center; color: #999;">未找到可采集的字段</p>';
            return;
        }
        
        this.renderSuggestions();
    }
    
    renderSuggestions() {
        if (!this.suggestionsList) return;
        
        this.suggestionsList.innerHTML = this.suggestions.map((sug, idx) => `
            <div class="suggestion-card" data-index="${idx}">
                <div class="suggestion-header">
                    <span class="suggestion-name">${sug.name}</span>
                    <span class="suggestion-type">${sug.type}</span>
                </div>
                <div class="suggestion-info">
                    <strong>选择器:</strong> <code>${sug.selector}</code><br>
                    <strong>数量:</strong> ${sug.count} 个
                </div>
                ${sug.sample_data && sug.sample_data.length > 0 ? `
                    <div style="background: white; padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem; font-size: 0.85rem; max-height: 100px; overflow-y: auto;">
                        <strong>示例:</strong><br>
                        ${sug.sample_data.map(s => `• ${s}`).join('<br>')}
                    </div>
                ` : ''}
            </div>
        `).join('');
        
        // 🔥 添加点击事件
        this.suggestionsList.querySelectorAll('.suggestion-card').forEach((card, idx) => {
            card.addEventListener('click', () => this.toggleSuggestion(idx));
        });
    }
    
    toggleSuggestion(index) {
        const cards = this.suggestionsList.querySelectorAll('.suggestion-card');
        const card = cards[index];
        
        if (!card) return;
        
        if (this.selectedIndices.has(index)) {
            this.selectedIndices.delete(index);
            card.classList.remove('selected');
        } else {
            this.selectedIndices.add(index);
            card.classList.add('selected');
        }
    }
    
    selectAll() {
        const cards = this.suggestionsList?.querySelectorAll('.suggestion-card');
        if (!cards) return;
        
        cards.forEach((card, index) => {
            card.classList.add('selected');
            this.selectedIndices.add(index);
        });
    }
    
    applySelections() {
        if (this.selectedIndices.size === 0) {
            Toast.warning('请至少选择一个字段');
            return;
        }
        
        this.selectedIndices.forEach(index => {
            const sug = this.suggestions[index];
            this.fieldManager.addField({
                name: sug.name,
                selector: sug.selector,
                type: sug.type,
                attr: sug.type === 'image' ? 'src' : (sug.type === 'link' ? 'href' : 'text'),
                samples: sug.sample_data || []
            });
        });
        
        Toast.success(`已添加 ${this.selectedIndices.size} 个字段`);
        this.selectedIndices.clear();
        
        // 清除选中状态
        const cards = this.suggestionsList?.querySelectorAll('.suggestion-card');
        if (cards) {
            cards.forEach(card => card.classList.remove('selected'));
        }
    }
}