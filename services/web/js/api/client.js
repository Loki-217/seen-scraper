// services/web/js/api/client.js
/**
 * 🌐 API 客户端封装
 */

import { CONFIG } from '../config.js';

export class APIClient {
    constructor() {
        this.baseURL = CONFIG.API.BASE_URL;
        this.timeout = CONFIG.API.TIMEOUT;
    }
    
    /**
     * 通用请求方法
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        try {
            const response = await fetch(url, config);
            
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail?.error || error.detail || `HTTP ${response.status}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error(`[API] Request failed:`, error);
            throw error;
        }
    }
    
    /**
     * GET 请求
     */
    async get(endpoint, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const url = queryString ? `${endpoint}?${queryString}` : endpoint;
        return this.request(url, { method: 'GET' });
    }
    
    /**
     * POST 请求
     */
    async post(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    /**
     * DELETE 请求
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
    
    // ========== 具体 API 方法 ========== //
    
    /**
     * 健康检查
     */
    async healthCheck() {
        return this.get(CONFIG.API.ENDPOINTS.HEALTH);
    }
    
    /**
     * 渲染页面（通过代理）
     */
    async renderPage(url, options = {}) {
        return this.post(CONFIG.API.ENDPOINTS.RENDER, {
            url,
            timeout_ms: options.timeout_ms || CONFIG.DEFAULTS.TIMEOUT_MS,
            wait_for: options.wait_for || null
        });
    }
    
    /**
     * 智能分析页面
     */
    async analyzePage(url) {
        return this.post(`${CONFIG.API.ENDPOINTS.SMART_ANALYZE}?url=${encodeURIComponent(url)}`);
    }
    
    /**
     * AI 建议字段名
     */
    async suggestFieldName(element, context = {}) {
        return this.post(CONFIG.API.ENDPOINTS.AI_SUGGEST, {
            element,
            context
        });
    }
    
    /**
     * 创建采集任务
     */
    async createJob(jobData) {
        return this.post(CONFIG.API.ENDPOINTS.JOBS, jobData);
    }
    
    /**
     * 运行任务
     */
    async runJob(jobId, runData) {
        return this.post(`${CONFIG.API.ENDPOINTS.RUNS}/jobs/${jobId}/run`, runData);
    }
    
    /**
     * 获取运行结果
     */
    async getRunResult(runId) {
        return this.get(`${CONFIG.API.ENDPOINTS.RUNS}/${runId}`);
    }
    
    /**
     * 导出运行结果
     */
    getExportURL(runId, format = 'csv') {
        return `${this.baseURL}${CONFIG.API.ENDPOINTS.RUNS}/${runId}/export?format=${format}`;
    }
}

// 单例模式
export const apiClient = new APIClient();
export default apiClient;