// services/web/js/modules/manual-mode.js
/**
 * 👆 手动选择模式
 */

import { $, show, hide } from '../utils/dom.js';
import { apiClient } from '../api/client.js';
import { Toast } from '../ui/toast.js';
import { Loading } from '../ui/loading.js';

export class ManualMode {
    constructor(fieldManager) {
        this.fieldManager = fieldManager;
        this.iframe = $('previewFrame');
        this.container = $('manualMode');
        this.loading = new Loading('manualMode', '正在加载页面...');
        this.currentUrl = '';
        
        this.setupMessageListener();
    }
    
    /**
     * 加载页面
     */
    async loadPage(url) {
        if (!url) {
            Toast.error('请输入网页地址');
            return false;
        }
        
        // 简单的URL验证
        try {
            new URL(url);
        } catch {
            Toast.error('请输入有效的网址（包含 http:// 或 https://）');
            return false;
        }
        
        this.currentUrl = url;
        this.loading.show();
        
        try {
            console.log('[ManualMode] Loading:', url);
            
            const data = await apiClient.renderPage(url);
            
            console.log('[ManualMode] ✅ Data received, HTML length:', data.html?.length);
            
            // 加载到 iframe
            this.iframe.srcdoc = data.html;
            
            Toast.success('页面加载成功！现在可以点击选择要采集的内容');
            
            return true;
            
        } catch (error) {
            console.error('[ManualMode] ❌ Error:', error);
            Toast.error('加载失败: ' + error.message);
            return false;
        } finally {
            this.loading.hide();
        }
    }
    
    /**
     * 监听 iframe 消息
     */
    setupMessageListener() {
        window.addEventListener('message', async (event) => {
            if (event.data && event.data.type === 'element-clicked') {
                await this.handleElementClick(event.data.element);
            }
        });
        
        console.log('[ManualMode] Message listener registered');
    }
    
    /**
     * 处理元素点击
     */
    async handleElementClick(element) {
        console.log('[ManualMode] Element clicked:', element);
        
        // 🔥 调用 AI 建议字段名（可选）
        let fieldName = this.suggestFieldName(element);
        
        // 尝试获取 AI 建议
        try {
            Toast.info('🤖 AI 正在分析...');
            const aiResult = await apiClient.suggestFieldName({
                text: element.text || '',
                tagName: element.tagName || '',
                className: element.className || '',
                id: element.id || '',
                href: element.href || '',
                src: element.src || ''
            });
            
            if (aiResult.success) {
                fieldName = aiResult.fieldName;
                console.log('[AI] Suggested name:', fieldName, '(confidence:', aiResult.confidence, ')');
            }
        } catch (error) {
            console.warn('[AI] Failed:', error);
            // 降级到规则建议
        }
        
        // 确认添加
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
        }
    }
    
    /**
     * 简单的字段名建议
     */
    suggestFieldName(element) {
        const tag = (element.tagName || '').toLowerCase();
        const text = (element.text || '').toLowerCase();
        
        if (tag === 'h1' || tag === 'h2' || tag === 'h3') {
            return '标题';
        } else if (tag === 'a') {
            return '链接';
        } else if (tag === 'img') {
            return '图片';
        } else if (text.includes('￥') || text.includes('$') || text.includes('价')) {
            return '价格';
        } else if (text.includes('时间') || text.includes('日期')) {
            return '时间';
        } else {
            return `字段${this.fieldManager.fields.length + 1}`;
        }
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

export default ManualMode;