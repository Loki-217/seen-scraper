// services/web/js/core/manual-mode.js

import { state } from './state.js';
import { api } from './api.js';
import { showToast } from './utils.js';

export async function loadManualMode(url) {
    const loading = document.getElementById('loadingOverlay');
    loading.classList.remove('hidden');
    
    try {
        const response = await api.renderPage(url);
        
        if (!response.ok) {
            const errorData = await response.json();
            
            if (errorData.detail?.error?.includes('blocked') || 
                errorData.detail?.error?.includes('anti-bot') ||
                errorData.detail?.details?.includes('anti-scraping')) {
                showAntiScrapingModal(url);
                return;
            }
            
            throw new Error(errorData.detail?.error || 'Request failed');
        }
        
        const data = await response.json();
        document.getElementById('previewFrame').srcdoc = data.html;
        
    } catch (error) {
        const errorMsg = error.message.toLowerCase();
        if (errorMsg.includes('blocked') || 
            errorMsg.includes('connection') || 
            errorMsg.includes('failed')) {
            showAntiScrapingModal(url);
        } else {
            alert('加载失败: ' + error.message);
        }
    } finally {
        loading.classList.add('hidden');
    }
}

function showAntiScrapingModal(url) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay active';
    modal.innerHTML = `
        <div class="modal-content" style="max-width: 500px;">
            <div class="modal-header">
                <h3>🛡️ 检测到反爬虫保护</h3>
                <button class="close-btn" onclick="this.closest('.modal-overlay').remove()">✕</button>
            </div>
            <div class="modal-body">
                <p style="margin-bottom: 1rem; line-height: 1.6;">
                    该网站启用了反爬虫保护，<strong>手动模式</strong>无法正常访问。
                </p>
                <div style="background: #fff3cd; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                    <strong>💡 建议使用智能模式</strong><br>
                    智能模式配备了反反爬虫技术，可以绕过大多数网站的保护机制。
                </div>
                <p style="color: #666; font-size: 0.9rem;">
                    目标网址：<br>
                    <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px; word-break: break-all;">
                        ${url}
                    </code>
                </p>
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">
                    取消
                </button>
                <button class="btn btn-primary" onclick="switchToSmartMode('${url}')">
                    切换到智能模式
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}