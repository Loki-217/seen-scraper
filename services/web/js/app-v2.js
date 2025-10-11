// services/web/js/app-v2.js
/**
 * 🚀 SeenFetch v2.0 - 八爪鱼风格主应用
 */

import { CONFIG } from './config.js';
import { $ } from './utils/dom.js';
import { apiClient } from './api/client.js';
import { Toast } from './ui/toast.js';
import { FieldManager } from './modules/field-manager.js';
import { ManualMode } from './modules/manual-mode.js';
import { SmartMode } from './modules/smart-mode.js';

class AppV2 {
    constructor() {
        console.log(`🎯 ${CONFIG.BRAND.name} v2.0 - ${CONFIG.BRAND.tagline}`);
        
        // 初始化模块
        this.fieldManager = new FieldManager();
        this.manualMode = new ManualMode(this.fieldManager);
        this.smartMode = new SmartMode(this.fieldManager);
        
        // 状态
        this.currentMode = CONFIG.MODES.MANUAL;
        this.currentUrl = '';
        this.fieldsConfirmed = false; // 🔥 新增：字段确认状态
        
        // UI 元素
        this.configDrawer = $('configDrawer');
        this.drawerOverlay = $('drawerOverlay');
        this.configTrigger = $('configTrigger');
    }
    
    async init() {
        console.log('[AppV2] Initializing...');
        
        this.bindEvents();
        await this.checkHealth();
        this.fieldManager.render();
        
        // 聚焦 URL 输入
        const urlInput = $('urlInput');
        if (urlInput) urlInput.focus();
        
        // 🔥 监听字段变化，更新预览
        this.fieldManager.onFieldsChange = () => this.updateDataPreview();
        
        console.log('[AppV2] ✅ Ready!');
    }
    
    bindEvents() {
        // URL 输入框回车
        const urlInput = $('urlInput');
        if (urlInput) {
            urlInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.loadPage();
            });
        }
        
        // 加载按钮
        const loadBtn = $('loadBtn');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => this.loadPage());
        }
        
        // 🟢 配置抽屉控制
        this.configTrigger.addEventListener('click', () => this.toggleDrawer());
        this.drawerOverlay.addEventListener('click', () => this.closeDrawer());
        $('drawerClose').addEventListener('click', () => this.closeDrawer());
        
        // 模式切换
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const mode = btn.textContent.includes('手动') ? 'manual' : 'smart';
                this.switchMode(mode);
            });
        });
        
        // 开始采集按钮
        $('startScrapingBtn').addEventListener('click', () => this.startScraping());
        
        // 清空字段按钮
        $('clearFieldsBtn').addEventListener('click', () => {
            this.fieldManager.clear();
            this.fieldsConfirmed = false;
            this.updateDataPreview();
        });
        
        // 标签页切换
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const tabName = e.target.dataset.tab;
                if (tabName) this.switchTab(tabName);
            });
        });
    }
    
    async checkHealth() {
        try {
            const result = await apiClient.healthCheck();
            console.log('[AppV2] Health check:', result);
            return true;
        } catch (error) {
            console.error('[AppV2] Health check failed:', error);
            Toast.error('无法连接到后端服务');
            return false;
        }
    }
    
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
        
        console.log('[AppV2] Switched to', mode, 'mode');
    }
    
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
    
    // 🟢 抽屉控制
    toggleDrawer() {
        const isActive = this.configDrawer.classList.contains('active');
        
        if (isActive) {
            this.closeDrawer();
        } else {
            this.openDrawer();
        }
    }
    
    openDrawer() {
        this.configDrawer.classList.add('active');
        this.drawerOverlay.classList.add('active');
        this.configTrigger.classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    closeDrawer() {
        this.configDrawer.classList.remove('active');
        this.drawerOverlay.classList.remove('active');
        this.configTrigger.classList.remove('active');
        document.body.style.overflow = '';
    }
    
    // 🔥 更新数据预览
    updateDataPreview() {
        const fields = this.fieldManager.getFields();
        const fieldCount = fields.length;
        
        // 更新字段数量
        $('fieldCountBadge').textContent = `${fieldCount} 字段`;
        $('configuredFields').textContent = fieldCount;
        
        // 更新字段确认状态
        const allFieldsNamed = fields.every(f => f.name && f.name.trim() !== '');
        this.fieldsConfirmed = fieldCount > 0 && allFieldsNamed;
        
        if (fieldCount === 0) {
            $('statusBadge').textContent = '未配置';
            $('statusBadge').className = 'status-badge warning';
            $('fieldValidation').textContent = '⚠️';
            $('validationLabel').textContent = '未配置';
        } else if (!allFieldsNamed) {
            $('statusBadge').textContent = '待命名';
            $('statusBadge').className = 'status-badge warning';
            $('fieldValidation').textContent = '⚠️';
            $('validationLabel').textContent = '待命名';
        } else {
            $('statusBadge').textContent = '已确认';
            $('statusBadge').className = 'status-badge success';
            $('fieldValidation').textContent = '✅';
            $('validationLabel').textContent = '已确认';
        }
        
        // 生成预览表格
        this.renderPreviewTable(fields);
    }
    
    // 🔥 渲染预览表格
    renderPreviewTable(fields) {
        const container = $('tablePreview');
        
        if (fields.length === 0) {
            container.innerHTML = `
                <div class="empty-state" style="padding: 2rem;">
                    <p style="color: var(--text-tertiary); text-align: center;">
                        配置字段后预览数据
                    </p>
                </div>
            `;
            $('estimatedRows').textContent = '0';
            return;
        }
        
        // 生成表格
        const sampleData = this.generateSampleData(fields);
        
        container.innerHTML = `
            <table class="preview-table">
                <thead>
                    <tr>
                        ${fields.map(f => `<th>${f.name || '未命名'}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${sampleData.map(row => `
                        <tr>
                            ${row.map(cell => `<td title="${cell}">${cell}</td>`).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        
        // 更新预计行数
        $('estimatedRows').textContent = sampleData.length;
    }
    
    // 生成示例数据
    generateSampleData(fields) {
        const maxRows = Math.max(...fields.map(f => f.samples?.length || 0));
        const rows = [];
        
        for (let i = 0; i < Math.min(maxRows, 3); i++) {
            const row = fields.map(f => {
                const sample = f.samples?.[i] || '';
                return sample.length > 30 ? sample.substring(0, 30) + '...' : sample;
            });
            rows.push(row);
        }
        
        return rows;
    }
    
    // 🚀 开始采集
    async startScraping() {
        const fields = this.fieldManager.getFields();
        
        if (fields.length === 0) {
            Toast.warning('请至少配置一个字段');
            this.openDrawer(); // 打开抽屉提示用户
            return;
        }
        
        // 🔥 检查字段是否已确认
        if (!this.fieldsConfirmed) {
            Toast.warning('请先为所有字段命名后再开始采集');
            this.openDrawer();
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
                limit: parseInt($('maxItems').value) || CONFIG.DEFAULTS.MAX_ITEMS
            }))
        };
        
        try {
            Toast.info('正在创建任务...');
            
            // 创建 Job
            const job = await apiClient.createJob(jobData);
            console.log('[AppV2] Job created:', job);
            
            // 执行采集
            const run = await apiClient.runJob(job.id, {
                url: this.currentUrl,
                limit: parseInt($('maxItems').value) || CONFIG.DEFAULTS.MAX_ITEMS
            });
            console.log('[AppV2] Run started:', run);
            
            Toast.success(`✅ 采集任务已启动！任务ID: ${run.run_id}`);
            
            // 关闭抽屉
            this.closeDrawer();
            
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
            console.error('[AppV2] Scraping failed:', error);
            Toast.error('操作失败: ' + error.message);
        }
    }
}

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    const app = new AppV2();
    app.init();
    
    // 全局暴露（方便调试）
    window.app = app;
});

export default AppV2;