// Toast 提示组件
export class Toast {
    static show(message, type = 'success', duration = 3000) {
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            top: 90px;
            right: 20px;
            background: ${type === 'success' ? '#4CAF50' : type === 'error' ? '#f44336' : type === 'warning' ? '#fbbf24' : '#667eea'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            font-size: 0.95rem;
            animation: slideIn 0.3s ease;
        `;
        
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        
        toast.textContent = `${icons[type] || ''} ${message}`;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
    
    static success(message, duration) {
        this.show(message, 'success', duration);
    }
    
    static error(message, duration) {
        this.show(message, 'error', duration);
    }
    
    static warning(message, duration) {
        this.show(message, 'warning', duration);
    }
    
    static info(message, duration) {
        this.show(message, 'info', duration);
    }
}

// 添加动画样式
if (!document.querySelector('#toast-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-styles';
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(400px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(400px); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}