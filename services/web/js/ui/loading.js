// services/web/js/ui/loading.js
/**
 * ⏳ Loading 加载组件
 */

import { createElement, $ } from '../utils/dom.js';

export class Loading {
    constructor(container, text = '加载中...') {
        this.container = typeof container === 'string' ? $(container) : container;
        this.text = text;
        this.overlay = null;
    }
    
    show(text) {
        if (text) this.text = text;
        
        if (!this.overlay) {
            this.overlay = createElement('div', {
                className: 'loading-overlay'
            }, [
                createElement('div', { className: 'spinner' }),
                createElement('p', { className: 'loading-text' }, [this.text])
            ]);
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
            this.overlay.querySelector('.loading-text').textContent = text;
        }
        return this;
    }
}

export default Loading;