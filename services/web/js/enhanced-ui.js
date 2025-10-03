// services/web/js/enhanced-ui.js

class EnhancedUI {
    constructor() {
        this.hintElement = document.getElementById('smartHint');
        this.dialogContainer = document.getElementById('smartSelectDialog');
        this.setupEventListeners();
    }
    
    setupEventListeners() {
        // 设置全局鼠标悬停提示
        document.addEventListener('mousemove', (e) => {
            if (e.target.classList.contains('smart-select-preview')) {
                this.showHint(e.clientX, e.clientY, '点击确认选择所有相似元素');
            } else {
                this.hideHint();
            }
        });
    }
    
    showHint(x, y, text) {
        this.hintElement.textContent = text;
        this.hintElement.style.left = x + 'px';
        this.hintElement.style.top = (y - 40) + 'px';
        this.hintElement.style.display = 'block';
    }
    
    hideHint() {
        this.hintElement.style.display = 'none';
    }
    
    showConfirmDialog(result) {
        // 在这里创建对话框HTML
        const dialogHTML = this.createDialogHTML(result);
        this.dialogContainer.innerHTML = dialogHTML;
        this.dialogContainer.style.display = 'flex';
        
        // 添加动画
        setTimeout(() => {
            const dialog = this.dialogContainer.querySelector('.smart-select-dialog');
            if (dialog) {
                dialog.style.animation = 'slideUp 0.3s ease';
            }
        }, 10);
    }
    
    createDialogHTML(result) {
        return `
            <div class="smart-select-dialog">
                <!-- 对话框内容 -->
                <div class="dialog-header">
                    <h3>🎯 智能识别成功</h3>
                    <span class="count-badge">${result.count} 个元素</span>
                </div>
                
                <div class="preview-grid">
                    ${this.createPreviewItems(result)}
                </div>
                
                <div class="confidence-bar">
                    <div class="confidence-text">
                        置信度: ${Math.round(result.confidence * 100)}%
                    </div>
                    <div class="bar">
                        <div class="fill" style="width: ${result.confidence * 100}%"></div>
                    </div>
                </div>
                
                <div class="dialog-actions">
                    <button class="btn-confirm" onclick="confirmSelection(${JSON.stringify(result).replace(/"/g, '&quot;')})">
                        ✅ 确认选择
                    </button>
                    <button class="btn-adjust" onclick="adjustSelection()">
                        ✏️ 手动调整
                    </button>
                    <button class="btn-cancel" onclick="cancelSelection()">
                        取消
                    </button>
                </div>
            </div>
        `;
    }
    
    createPreviewItems(result) {
        // 创建预览项的HTML
        return result.samples.slice(0, 6).map((sample, index) => `
            <div class="preview-item">
                <span class="item-number">${index + 1}</span>
                <div class="item-content">${sample}</div>
            </div>
        `).join('');
    }
    
    showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span>${message}</span>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    }
}