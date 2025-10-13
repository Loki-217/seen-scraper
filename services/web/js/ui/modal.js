// 弹窗组件 - 用于未来扩展
import { createElement } from '../utils/dom.js';

export class Modal {
    constructor(options = {}) {
        this.title = options.title || '提示';
        this.content = options.content || '';
        this.onConfirm = options.onConfirm || null;
        this.onCancel = options.onCancel || null;
        this.modal = null;
    }
    
    show() {
        if (this.modal) {
            this.modal.classList.add('active');
            return;
        }
        
        // 创建遮罩
        this.modal = createElement('div', { className: 'modal-overlay' });
        
        // 创建弹窗内容
        const modalContent = createElement('div', { className: 'modal-content' });
        
        // 标题
        const header = createElement('div', { className: 'modal-header' });
        const titleEl = createElement('h3', {}, [this.title]);
        const closeBtn = createElement('button', {
            className: 'close-btn',
            onclick: () => this.hide()
        }, ['✕']);
        header.appendChild(titleEl);
        header.appendChild(closeBtn);
        
        // 内容
        const body = createElement('div', { className: 'modal-body' });
        if (typeof this.content === 'string') {
            body.innerHTML = this.content;
        } else {
            body.appendChild(this.content);
        }
        
        // 底部按钮
        const footer = createElement('div', { className: 'modal-footer' });
        
        if (this.onConfirm) {
            const confirmBtn = createElement('button', {
                className: 'btn btn-primary',
                onclick: () => {
                    if (this.onConfirm) this.onConfirm();
                    this.hide();
                }
            }, ['确定']);
            footer.appendChild(confirmBtn);
        }
        
        if (this.onCancel) {
            const cancelBtn = createElement('button', {
                className: 'btn btn-secondary',
                onclick: () => {
                    if (this.onCancel) this.onCancel();
                    this.hide();
                }
            }, ['取消']);
            footer.appendChild(cancelBtn);
        }
        
        // 组装
        modalContent.appendChild(header);
        modalContent.appendChild(body);
        if (footer.children.length > 0) {
            modalContent.appendChild(footer);
        }
        
        this.modal.appendChild(modalContent);
        
        // 点击遮罩关闭
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) this.hide();
        });
        
        document.body.appendChild(this.modal);
        setTimeout(() => this.modal.classList.add('active'), 10);
    }
    
    hide() {
        if (this.modal) {
            this.modal.classList.remove('active');
            setTimeout(() => {
                if (this.modal && this.modal.parentNode) {
                    this.modal.parentNode.removeChild(this.modal);
                }
                this.modal = null;
            }, 300);
        }
    }
}

// 快捷方法
Modal.alert = function(message, title = '提示') {
    return new Promise((resolve) => {
        const modal = new Modal({
            title,
            content: message,
            onConfirm: resolve
        });
        modal.show();
    });
};

Modal.confirm = function(message, title = '确认') {
    return new Promise((resolve) => {
        const modal = new Modal({
            title,
            content: message,
            onConfirm: () => resolve(true),
            onCancel: () => resolve(false)
        });
        modal.show();
    });
};

export default Modal;