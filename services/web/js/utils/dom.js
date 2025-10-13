// DOM 操作工具函数

export function $(id) {
    return document.getElementById(id);
}

export function $$(selector, parent = document) {
    return Array.from(parent.querySelectorAll(selector));
}

export function createElement(tag, props = {}, children = []) {
    const element = document.createElement(tag);
    
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
    
    children.forEach(child => {
        if (typeof child === 'string') {
            element.appendChild(document.createTextNode(child));
        } else if (child instanceof Node) {
            element.appendChild(child);
        }
    });
    
    return element;
}

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