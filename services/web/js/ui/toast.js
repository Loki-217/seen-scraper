// services/web/js/ui/toast.js
/**
 * 🍞 Toast 消息提示组件
 */

import { CONFIG } from '../config.js';
import { createElement } from '../utils/dom.js';

export class Toast {
    static show(message, type = 'success', duration = CONFIG.UI.TOAST_DURATION) {
        // 创建 toast 元素
        const toast = createElement('div', {
            className: `toast ${type}`
        }, [message]);
        
        // 添加到页面
        document.body.appendChild(toast);
        
        // 自动移除
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);
        
        return toast;
    }
    
    static success(message, duration) {
        return this.show(`✅ ${message}`, 'success', duration);
    }
    
    static error(message, duration) {
        return this.show(`❌ ${message}`, 'error', duration);
    }
    
    static info(message, duration) {
        return this.show(`ℹ️ ${message}`, 'info', duration);
    }
    
    static warning(message, duration) {
        return this.show(`⚠️ ${message}`, 'warning', duration);
    }
}

export default Toast;