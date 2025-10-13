// 加载组件
import { createElement } from '../utils/dom.js';

export class Loading {
    constructor(containerId, text = '加载中...') {
        this.container = document.getElementById(containerId);
        this.text = text;
        this.overlay = null;
    }
    
    show(text) {
        if (text) this.text = text;
        
        if (!this.overlay) {
            this.overlay = createElement('div', {
                className: 'loading-overlay'
            });
            
            const spinner = createElement('div', { className: 'spinner' });
            const loadingText = createElement('p', { className: 'loading-text' });
            loadingText.textContent = this.text;
            
            this.overlay.appendChild(spinner);
            this.overlay.appendChild(loadingText);
        } else {
            this.overlay.querySelector('.loading-text').textContent = this.text;
        }
        
        this.container.appendChild(this.overlay);
        return this;
    }
    
    hide() {
        if (this.overlay && this.overlay.parentNode) {
            this.overlay.parentNode.removeChild(this.overlay);
        }
        return this;
    }
    
    setText(text) {
        this.text = text;
        if (this.overlay) {
            const textEl = this.overlay.querySelector('.loading-text');
            if (textEl) textEl.textContent = text;
        }
        return this;
    }
}

export default Loading;