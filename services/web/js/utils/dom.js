// services/web/js/utils/dom.js
/**
 * 🎯 DOM 操作工具函数
 */

/**
 * 通过 ID 获取元素
 */
export function $(id) {
    return document.getElementById(id);
}

/**
 * 查询选择器
 */
export function $$(selector, parent = document) {
    return parent.querySelectorAll(selector);
}

/**
 * 创建元素
 */
export function createElement(tag, props = {}, children = []) {
    const element = document.createElement(tag);
    
    // 设置属性
    Object.entries(props).forEach(([key, value]) => {
        if (key === 'className') {
            element.className = value;
        } else if (key === 'style' && typeof value === 'object') {
            Object.assign(element.style, value);
        } else if (key.startsWith('on') && typeof value === 'function') {
            element.addEventListener(key.slice(2).toLowerCase(), value);
        } else {
            element.setAttribute(key, value);
        }
    });
    
    // 添加子元素
    children.forEach(child => {
        if (typeof child === 'string') {
            element.appendChild(document.createTextNode(child));
        } else if (child instanceof Node) {
            element.appendChild(child);
        }
    });
    
    return element;
}

/**
 * 显示/隐藏元素
 */
export function show(element) {
    if (typeof element === 'string') element = $(element);
    if (element) element.classList.remove('hidden');
}

export function hide(element) {
    if (typeof element === 'string') element = $(element);
    if (element) element.classList.add('hidden');
}

export function toggle(element) {
    if (typeof element === 'string') element = $(element);
    if (element) element.classList.toggle('hidden');
}

/**
 * 添加/移除类名
 */
export function addClass(element, className) {
    if (typeof element === 'string') element = $(element);
    if (element) element.classList.add(className);
}

export function removeClass(element, className) {
    if (typeof element === 'string') element = $(element);
    if (element) element.classList.remove(className);
}

export function toggleClass(element, className) {
    if (typeof element === 'string') element = $(element);
    if (element) element.classList.toggle(className);
}

/**
 * 清空元素内容
 */
export function empty(element) {
    if (typeof element === 'string') element = $(element);
    if (element) element.innerHTML = '';
}

/**
 * 设置 HTML 内容
 */
export function setHTML(element, html) {
    if (typeof element === 'string') element = $(element);
    if (element) element.innerHTML = html;
}

/**
 * 获取表单数据
 */
export function getFormData(formElement) {
    const formData = new FormData(formElement);
    const data = {};
    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }
    return data;
}

/**
 * 平滑滚动到元素
 */
export function scrollToElement(element, options = {}) {
    if (typeof element === 'string') element = $(element);
    if (element) {
        element.scrollIntoView({
            behavior: 'smooth',
            block: 'start',
            ...options
        });
    }
}

/**
 * 等待元素出现
 */
export function waitForElement(selector, timeout = 5000) {
    return new Promise((resolve, reject) => {
        const element = document.querySelector(selector);
        if (element) {
            resolve(element);
            return;
        }
        
        const observer = new MutationObserver(() => {
            const element = document.querySelector(selector);
            if (element) {
                observer.disconnect();
                resolve(element);
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        setTimeout(() => {
            observer.disconnect();
            reject(new Error(`Element ${selector} not found within ${timeout}ms`));
        }, timeout);
    });
}

/**
 * 防抖函数
 */
export function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 节流函数
 */
export function throttle(func, limit = 300) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

export default {
    $,
    $$,
    createElement,
    show,
    hide,
    toggle,
    addClass,
    removeClass,
    toggleClass,
    empty,
    setHTML,
    getFormData,
    scrollToElement,
    waitForElement,
    debounce,
    throttle
};