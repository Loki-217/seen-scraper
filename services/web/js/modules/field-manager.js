// services/web/js/modules/field-manager.js
/**
 * 📋 字段管理模块
 */

import { $, empty, createElement } from '../utils/dom.js';
import { Toast } from '../ui/toast.js';

export class FieldManager {
    constructor(containerId = 'fieldsList') {
        this.container = $(containerId);
        this.fields = [];
        this.fieldIdCounter = 0;
    }
    
    /**
     * 添加字段
     */
    addField(fieldData) {
        // 检查是否已存在
        if (this.fields.some(f => f.selector === fieldData.selector)) {
            Toast.warning('该元素已经被选择');
            return null;
        }
        
        const field = {
            id: ++this.fieldIdCounter,
            name: fieldData.name || this.suggestFieldName(fieldData),
            selector: fieldData.selector,
            type: fieldData.type || 'text',
            attr: fieldData.attr || this.detectAttribute(fieldData),
            samples: fieldData.samples || [fieldData.text],
            ...fieldData
        };
        
        this.fields.push(field);
        this.render();
        Toast.success(`已添加字段: ${field.name}`);
        
        return field;
    }
    
    /**
     * 移除字段
     */
    removeField(fieldId) {
        this.fields = this.fields.filter(f => f.id !== fieldId);
        this.render();
    }
    
    /**
     * 更新字段名
     */
    updateFieldName(fieldId, newName) {
        const field = this.fields.find(f => f.id === fieldId);
        if (field) {
            field.name = newName;
        }
    }
    
    /**
     * 清空所有字段
     */
    clear() {
        if (this.fields.length > 0) {
            if (confirm('确定要清空所有字段吗？')) {
                this.fields = [];
                this.render();
                Toast.info('已清空所有字段');
            }
        }
    }
    
    /**
     * 获取所有字段
     */
    getFields() {
        return this.fields;
    }
    
    /**
     * 渲染字段列表
     */
    render() {
        if (!this.container) return;
        
        empty(this.container);
        
        if (this.fields.length === 0) {
            this.renderEmptyState();
            return;
        }
        
        const fieldsList = createElement('div', { className: 'fields-list' });
        
        this.fields.forEach(field => {
            const fieldItem = this.createFieldItem(field);
            fieldsList.appendChild(fieldItem);
        });
        
        this.container.appendChild(fieldsList);
    }
    
    /**
     * 创建字段项
     */
    createFieldItem(field) {
        const fieldItem = createElement('div', { className: 'field-item' });
        
        // 字段头部
        const fieldHeader = createElement('div', { className: 'field-header' });
        
        const nameInput = createElement('input', {
            type: 'text',
            className: 'field-name-input',
            value: field.name,
            placeholder: '字段名称',
            onchange: (e) => this.updateFieldName(field.id, e.target.value)
        });
        
        const typeBadge = createElement('span', {
            className: 'field-type-badge'
        }, [field.attr]);
        
        const removeBtn = createElement('button', {
            className: 'btn btn-danger btn-sm',
            onclick: () => this.removeField(field.id)
        }, ['删除']);
        
        fieldHeader.appendChild(nameInput);
        fieldHeader.appendChild(typeBadge);
        fieldHeader.appendChild(removeBtn);
        
        // 字段信息
        const fieldInfo = createElement('div', { className: 'field-info' });
        fieldInfo.innerHTML = `
            <div><strong>选择器:</strong> <code>${field.selector}</code></div>
            ${field.samples && field.samples.length > 0 ? 
                `<div style="margin-top: 0.25rem;"><strong>预览:</strong> ${field.samples[0] || '(空内容)'}</div>` 
                : ''}
        `;
        
        fieldItem.appendChild(fieldHeader);
        fieldItem.appendChild(fieldInfo);
        
        return fieldItem;
    }
    
    /**
     * 渲染空状态
     */
    renderEmptyState() {
        const emptyState = createElement('div', { className: 'empty-state' });
        emptyState.innerHTML = `
            <div class="empty-state-icon">📝</div>
            <p>还没有配置任何字段</p>
            <small>选择模式并开始分析页面</small>
        `;
        this.container.appendChild(emptyState);
    }
    
    /**
     * 智能命名建议
     */
    suggestFieldName(data) {
        const tag = (data.tagName || '').toLowerCase();
        const text = (data.text || '').toLowerCase();
        
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
            return `字段${this.fields.length + 1}`;
        }
    }
    
    /**
     * 检测属性
     */
    detectAttribute(data) {
        const tag = (data.tagName || '').toLowerCase();
        if (tag === 'img') return 'src';
        if (tag === 'a' && data.href) return 'href';
        return 'text';
    }
}

export default FieldManager;