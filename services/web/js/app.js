// services/web/js/app.js
/**
 * 🚀 SeenFetch 主应用
 */

import { CONFIG } from './config.js';
import { $ } from './utils/dom.js';
import { apiClient } from './api/client.js';
import { Toast } from './ui/toast.js';
import { FieldManager } from './modules/field-manager.js';
import { ManualMode } from './modules/manual-mode.js';
import { SmartMode } from './modules/smart-mode.js';

class App {
    constructor() {
        console.log(`🎯 ${CONFIG.BRAND.name} v${CONFIG.BRAND.version} - ${CONFIG.BRAND.tagline}`);
        
        // 初始化模块
        this.fieldManager = new FieldManager();
        this.manualMode = new ManualMode(this.fieldManager);
        this.smartMode = new SmartMode(this.fieldManager);
        
        // 当前模式
        this.currentMode = CONFIG.MODES.MANUAL;
        
        // 当前 URL
        this.currentUrl = '';
    }
    
    /**
     * 初始化应用
     */
    async init() {
        console.log('[App] Initializing...');
        
        // 绑定事件
        this.bindEvents();
        
        // 健康检查
        await this.checkHealth();
        
        // 渲染初始状态
        this.fieldManager.render();
        
        // 聚焦 URL 输入框
        const urlInput = $('urlInput');
        if (urlInput) urlInput.focus();
        
        console.log('[App] ✅ Ready!');
    }
    
    /**
     * 绑定事件
     */
    bindEvents() {
        // URL 输入框回车
        const urlInput = $('urlInput');
        if (urlInput) {
            urlInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.loadPage();
                }
            });
        }
        
        // 加载按钮
        const loadBtn = $('loadBtn');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => this.loadPage());
        }
        
        // 模式切换按钮
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = btn.textContent.includes('手动') ? 'manual' : 'smart';
                this.switchMode(mode);
            });
        });
        
        // 开始采集按钮
        const startBtn = $('startScrapingBtn');
        if (startBtn) {
            startBtn.addEventListener('click', () => this.startScraping());
        }
        
        // 清空字段按钮
        const clearBtn = $('clearFieldsBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.fieldManager.clear());
        }
        
        // 智能模式：全选按钮
        const selectAllBtn = $('selectAllBtn');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('click', () => this.smartMode.selectAll());
        }
        
        // 智能模式：应用选择按钮
        const applyBtn = $('applySelectionsBtn');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                this.smartMode.applySelectedSuggestions();
                this.switchTab('fields');
            });
        }
        
        // 标签页切换
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                if (tabName) this.switchTab(tabName);
            });
        });
    }
    
    /**
     * 健康检查
     */
    async checkHealth() {
        try {
            const result = await apiClient.healthCheck();
            console.log('[App] Health check:', result);
            return true;
        } catch (error) {
            console.error('[App] Health check failed:', error);
            Toast.error('无法连接到后端服务，请确保后端正在运行');
            return false;
        }
    }
    
    /**
     * 加载页面
     */
    async loadPage() {
        const urlInput = $('urlInput');
        const url = urlInput?.value.trim();
        
        if (!url) {
            Toast.warning('请输入网页地址');
            return;
        }
        
        this.currentUrl = url;
        
        if (this.currentMode === CONFIG.MODES.MANUAL) {
            await this.manualMode.loadPage(url);
        } else {
            await this.smartMode.analyzePage(url);
        }
    }
    
    /**
     * 切换模式
     */
    switchMode(mode) {
        this.currentMode = mode;
        
        // 更新按钮状态
        document.querySelectorAll('.mode-btn').forEach(btn => {
            const isManual = btn.textContent.includes('手动');
            const isActive = (mode === 'manual' && isManual) || (mode === 'smart' && !isManual);
            btn.classList.toggle('active', isActive);
        });
        
        // 切换显示
        if (mode === CONFIG.MODES.MANUAL) {
            this.manualMode.show();
            this.smartMode.hide();
        } else {
            this.manualMode.hide();
            this.smartMode.show();
        }
        
        console.log('[App] Switched to', mode, 'mode');
    }
    
    /**
     * 切换标签页
     */
    switchTab(tabName) {
        // 更新标签按钮
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        
        // 更新标签内容
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === `${tabName}Tab`);
        });
    }
    
    /**
     * 开始采集
     */
    async startScraping() {
        const fields = this.fieldManager.getFields();
        
        if (fields.length === 0) {
            Toast.warning('请至少选择一个要采集的字段');
            return;
        }
        
        // 验证字段名
        const invalidFields = fields.filter(f => !f.name || f.name.trim() === '');
        if (invalidFields.length > 0) {
            Toast.warning('请为所有字段命名');
            return;
        }
        
        // 创建任务
        const jobName = prompt('请输入任务名称：', `采集任务_${new Date().toLocaleDateString()}`);
        if (!jobName) return;
        
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
        
        try {
            Toast.info('正在创建任务...');
            
            // 创建 Job
            const job = await apiClient.createJob(jobData);
            console.log('[App] Job created:', job);
            
            // 执行采集
            const run = await apiClient.runJob(job.id, {
                url: this.currentUrl,
                limit: CONFIG.DEFAULTS.MAX_ITEMS
            });
            console.log('[App] Run started:', run);
            
            Toast.success(`✅ 采集任务已启动！任务ID: ${run.run_id}`);
            
            // 延迟检查结果
            setTimeout(async () => {
                const runData = await apiClient.getRunResult(run.run_id);
                
                if (runData.status === 'succeeded') {
                    if (confirm('采集完成！是否下载结果？')) {
                        const exportURL = apiClient.getExportURL(run.run_id);
                        window.open(exportURL, '_blank');
                    }
                } else if (runData.status === 'failed') {
                    Toast.error('采集失败，请检查配置');
                }
            }, 3000);
            
        } catch (error) {
            console.error('[App] Scraping failed:', error);
            Toast.error('操作失败: ' + error.message);
        }
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    const app = new App();
    app.init();
    
    // 全局暴露（方便调试）
    window.app = app;
});

export default App;