// 手动模式模块
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

export class ManualMode {
    constructor(apiClient, fieldManager) {
        console.log('[ManualMode] Constructor called');
        this.apiClient = apiClient;
        this.fieldManager = fieldManager;
        this.iframe = $('previewFrame');
        this.loading = $('loadingOverlay');
        
        console.log('[ManualMode] iframe:', this.iframe);
        console.log('[ManualMode] loading:', this.loading);
    }
    
    async loadPage(url) {
        console.log('[ManualMode] loadPage called with:', url);
        
        if (!url) {
            Toast.error('请输入网页地址');
            return false;
        }
        
        // 验证 URL
        try {
            new URL(url);
        } catch (e) {
            Toast.error('请输入有效的网址（包含 http:// 或 https://）');
            return false;
        }
        
        // 显示加载动画
        console.log('[ManualMode] Showing loading overlay');
        if (this.loading) {
            show(this.loading);
        } else {
            console.error('[ManualMode] Loading overlay element not found!');
        }
        
        try {
            console.log('[ManualMode] Calling API...');
            console.log('[ManualMode] API URL:', `${CONFIG.API_BASE}${CONFIG.ENDPOINTS.RENDER}`);
            
            const data = await this.apiClient.post(CONFIG.ENDPOINTS.RENDER, {
                url,
                timeout_ms: CONFIG.DEFAULTS.TIMEOUT_MS
            });
            
            console.log('[ManualMode] API response received');
            console.log('[ManualMode] HTML length:', data.html?.length);
            
            if (!this.iframe) {
                console.error('[ManualMode] iframe element not found!');
                Toast.error('预览框架未找到');
                return false;
            }
            
            this.iframe.srcdoc = data.html;
            console.log('[ManualMode] HTML loaded into iframe');
            
            Toast.success('页面加载成功！点击选择要采集的内容');
            
            return true;
            
        } catch (error) {
            console.error('[ManualMode] Error:', error);
            console.error('[ManualMode] Error message:', error.message);
            Toast.error('加载失败: ' + error.message);
            return false;
        } finally {
            console.log('[ManualMode] Hiding loading overlay');
            if (this.loading) {
                hide(this.loading);
            }
        }
    }
}