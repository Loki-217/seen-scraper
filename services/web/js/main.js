// 主应用入口
import { CONFIG } from './config.js';
import { APIClient } from './api/client.js';
import { ManualMode } from './modules/manual-mode.js';
import { SmartMode } from './modules/smart-mode.js';
import { FieldManager } from './modules/field-manager.js';
import { Toast } from './ui/toast.js';

// 🔥 简化的 DOM 工具函数
function $(id) {
    return document.getElementById(id);
}

function $$(selector) {
    return document.querySelectorAll(selector);
}

class App {
    constructor() {
        this.apiClient = new APIClient();
        this.fieldManager = new FieldManager();
        this.manualMode = new ManualMode(this.apiClient, this.fieldManager);
        this.smartMode = new SmartMode(this.apiClient, this.fieldManager);
        
        this.currentMode = 'manual';
        this.currentUrl = '';
        this.currentRunId = null;
    }
    
    init() {
        console.log(`${CONFIG.BRAND.name} v${CONFIG.BRAND.version}`);
        
        // 检查必要元素是否存在
        const requiredElements = [
            'urlInput', 'loadBtn', 'configToggle', 'closeConfigBtn',
            'configModal', 'confirmBtn', 'clearFieldsBtn', 'exportBtn'
        ];
        
        const missingElements = requiredElements.filter(id => !$(id));
        if (missingElements.length > 0) {
            console.error('❌ 缺少必要元素:', missingElements);
            alert('页面初始化失败，请刷新页面重试');
            return;
        }
        
        this.bindEvents();
        this.setupMessageListener();
        
        console.log('✅ 应用初始化成功');
    }
    
    bindEvents() {
        // URL 输入回车
        const urlInput = $('urlInput');
        if (urlInput) {
            urlInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.loadPage();
            });
        }
        
        // 加载按钮
        const loadBtn = $('loadBtn');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => {
                console.log('[App] Load button clicked');
                this.loadPage();
            });
        }
        
        // 模式切换
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.switchMode(btn.dataset.mode);
            });
        });
        
        // 配置弹窗
        const configToggle = $('configToggle');
        const closeConfigBtn = $('closeConfigBtn');
        const configModal = $('configModal');
        
        if (configToggle) {
            configToggle.addEventListener('click', () => this.toggleConfigModal());
        }
        if (closeConfigBtn) {
            closeConfigBtn.addEventListener('click', () => this.toggleConfigModal());
        }
        if (configModal) {
            configModal.addEventListener('click', (e) => {
                if (e.target.id === 'configModal') this.toggleConfigModal();
            });
        }
        
        // 按钮事件
        const confirmBtn = $('confirmBtn');
        const clearFieldsBtn = $('clearFieldsBtn');
        const applySmartBtn = $('applySmartBtn');
        const selectAllBtn = $('selectAllBtn');
        const exportBtn = $('exportBtn');
        
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.confirmFields());
        }
        if (clearFieldsBtn) {
            clearFieldsBtn.addEventListener('click', () => this.fieldManager.clear());
        }
        if (applySmartBtn) {
            applySmartBtn.addEventListener('click', () => this.smartMode.applySelections());
        }
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => this.smartMode.selectAll());
        }
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportData());
        }
    }
    
    async loadPage() {
        console.log('[App] loadPage called');
        
        const urlInput = $('urlInput');
        console.log('[App] urlInput element:', urlInput);
        
        if (!urlInput) {
            console.error('[App] urlInput element not found!');
            Toast.error('URL 输入框未找到');
            return;
        }
        
        const url = urlInput.value.trim();
        console.log('[App] URL value:', url);
        
        if (!url) {
            Toast.warning('请输入网页地址');
            return;
        }
        
        // 验证 URL 格式
        try {
            new URL(url);
        } catch (e) {
            Toast.error('请输入有效的网址（包含 http:// 或 https://）');
            return;
        }
        
        this.currentUrl = url;
        console.log('[App] Current mode:', this.currentMode);
        
        if (this.currentMode === 'manual') {
            console.log('[App] Calling manual mode');
            await this.manualMode.loadPage(url);
        } else {
            console.log('[App] Calling smart mode');
            await this.smartMode.analyzePage(url);
        }
    }
    
    switchMode(mode) {
        this.currentMode = mode;
        
        // 更新按钮状态
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });
        
        // 切换显示
        const manualMode = $('manualMode');
        const smartMode = $('smartMode');
        
        if (manualMode) manualMode.classList.toggle('hidden', mode !== 'manual');
        if (smartMode) smartMode.classList.toggle('hidden', mode !== 'smart');
    }
    
    toggleConfigModal() {
        const modal = $('configModal');
        if (modal) {
            modal.classList.toggle('active');
        }
    }
    
    async confirmFields() {
        const fields = this.fieldManager.getFields();
        
        if (fields.length === 0) {
            Toast.warning('请先配置字段');
            return;
        }
        
        // 检查字段名
        const unnamedFields = fields.filter(f => !f.name || f.name.trim() === '');
        if (unnamedFields.length > 0) {
            Toast.warning('请为所有字段命名');
            return;
        }
        
        const confirmBtn = $('confirmBtn');
        if (confirmBtn) confirmBtn.disabled = true;
        
        this.toggleConfigModal();
        
        await this.startScraping();
    }
    
    async startScraping() {
        const fields = this.fieldManager.getFields();
        const jobName = prompt('请输入任务名称：', `采集任务_${new Date().toLocaleDateString()}`);
        
        if (!jobName) return;
        
        try {
            Toast.info('正在创建任务...');
            
            // 创建任务
            const jobData = {
                name: jobName,
                start_url: this.currentUrl,
                status: "active",
                selectors: fields.map(f => ({
                    name: f.name,
                    css: f.selector,
                    attr: f.attr,
                    limit: CONFIG.DEFAULTS.MAX_ITEMS
                }))
            };
            
            const job = await this.apiClient.post(CONFIG.ENDPOINTS.JOBS, jobData);
            
            // 执行采集
            const run = await this.apiClient.post(
                `${CONFIG.ENDPOINTS.RUNS}/jobs/${job.id}/run`,
                { url: this.currentUrl, limit: CONFIG.DEFAULTS.MAX_ITEMS }
            );
            
            this.currentRunId = run.run_id;
            Toast.success(`✅ 采集任务已启动！任务ID: ${run.run_id}`);
            
            // 延迟检查结果
            setTimeout(async () => {
                await this.checkRunStatus(run.run_id);
            }, 3000);
            
        } catch (error) {
            console.error('[App] Scraping failed:', error);
            Toast.error('操作失败: ' + error.message);
        }
    }
    
    async checkRunStatus(runId) {
        try {
            const runData = await this.apiClient.get(`${CONFIG.ENDPOINTS.RUNS}/${runId}`);
            
            if (runData.status === 'succeeded') {
                await this.renderPreview(runId);
                const exportBtn = $('exportBtn');
                if (exportBtn) exportBtn.disabled = false;
                
                if (confirm('采集完成！是否下载结果？')) {
                    this.exportData(runId);
                }
            } else if (runData.status === 'failed') {
                Toast.error('采集失败，请检查配置');
            }
        } catch (error) {
            Toast.error('获取运行状态失败: ' + error.message);
        }
    }
    
    async renderPreview(runId) {
        try {
            const results = await this.apiClient.get(`${CONFIG.ENDPOINTS.RUNS}/${runId}/results`);
            
            const previewContent = $('previewContent');
            if (!previewContent) return;
            
            if (!results || Object.keys(results).length === 0) {
                previewContent.innerHTML = '<div class="preview-empty">未采集到数据</div>';
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
                    html += `<td>${this.escapeHtml(value)}</td>`;
                });
                html += '</tr>';
            }
            
            html += '</tbody></table>';
            previewContent.innerHTML = html;
            
        } catch (error) {
            Toast.error('获取结果失败: ' + error.message);
        }
    }
    
    exportData(runId = this.currentRunId) {
        if (!runId) {
            Toast.warning('没有可导出的数据');
            return;
        }
        
        const exportURL = `${CONFIG.API_BASE}${CONFIG.ENDPOINTS.RUNS}/${runId}/export?format=csv`;
        window.open(exportURL, '_blank');
    }
    
    setupMessageListener() {
        window.addEventListener('message', async (event) => {
            if (event.data && event.data.type === 'element-clicked') {
                await this.handleElementClick(event.data.element);
            }
        });
    }
    
    async handleElementClick(element) {
        console.log('[App] Element clicked:', element);
        
        // 调用 AI 建议字段名
        let fieldName = this.suggestFieldName(element);
        
        try {
            Toast.info('🤖 AI 正在分析...');
            const aiResult = await this.apiClient.post(CONFIG.ENDPOINTS.AI_SUGGEST, {
                element: {
                    text: element.text || '',
                    tagName: element.tagName || '',
                    className: element.className || '',
                    id: element.id || '',
                    href: element.href || '',
                    src: element.src || ''
                }
            });
            
            if (aiResult.success) {
                fieldName = aiResult.fieldName;
            }
        } catch (error) {
            console.warn('[AI] Failed:', error);
        }
        
        const message = `AI 建议字段名: ${fieldName}\n\n标签: ${element.tagName}\n文本: ${element.text}\n选择器: ${element.selector}\n\n是否添加到采集字段？`;
        
        if (confirm(message)) {
            this.fieldManager.addField({
                name: fieldName,
                selector: element.selector,
                tagName: element.tagName,
                text: element.text,
                href: element.href,
                src: element.src
            });
            
            this.toggleConfigModal();
        }
    }
    
    suggestFieldName(element) {
        const tag = (element.tagName || '').toLowerCase();
        const text = (element.text || '').toLowerCase();
        
        if (tag === 'h1' || tag === 'h2' || tag === 'h3') return '标题';
        if (tag === 'a') return '链接';
        if (tag === 'img') return '图片';
        if (text.includes('￥') || text.includes('$')) return '价格';
        if (text.includes('时间') || text.includes('日期')) return '时间';
        
        return `字段${this.fieldManager.fields.length + 1}`;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    const app = new App();
    app.init();
    window.app = app; // 调试用
});