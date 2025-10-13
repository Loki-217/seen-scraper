// 字段管理模块
import { Toast } from '../ui/toast.js';

// 🔥 简化工具函数
function $(id) {
    return document.getElementById(id);
}

export class FieldManager {
    constructor() {
        this.fields = [];
        this.fieldIdCounter = 0;
        this.container = $('fieldsList');
    }
    
    addField(fieldData) {
        if (this.fields.some(f => f.selector === fieldData.selector)) {
            Toast.warning('该元素已被选择');
            return null;
        }
        
        const field = {
            id: ++this.fieldIdCounter,
            name: fieldData.name || `字段${this.fields.length + 1}`,
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
    
    removeField(fieldId) {
        this.fields = this.fields.filter(f => f.id !== fieldId);
        this.render();
    }
    
    updateFieldName(fieldId, newName) {
        const field = this.fields.find(f => f.id === fieldId);
        if (field) {
            field.name = newName;
            this.updateConfirmButton();
        }
    }
    
    clear() {
        if (this.fields.length > 0) {
            if (confirm('确定要清空所有字段吗？')) {
                this.fields = [];
                this.render();
                Toast.info('已清空所有字段');
            }
        }
    }
    
    getFields() {
        return this.fields;
    }
    
    render() {
        if (!this.container) return;
        
        if (this.fields.length === 0) {
            this.renderEmptyState();
            this.updateConfirmButton();
            return;
        }
        
        this.container.innerHTML = this.fields.map(field => `
            <div class="field-item">
                <div class="field-header">
                    <input class="field-name-input"
                           value="${field.name}"
                           data-field-id="${field.id}"
                           placeholder="字段名称">
                    <span class="field-type-badge">${field.attr}</span>
                    <button class="btn btn-danger btn-sm" data-field-id="${field.id}">
                        删除
                    </button>
                </div>
                <div class="field-info">
                    <strong>选择器:</strong> <code>${field.selector}</code>
                    ${field.samples && field.samples.length > 0 ? 
                        `<br><strong>预览:</strong> ${field.samples[0] || '(空内容)'}` 
                        : ''}
                </div>
            </div>
        `).join('');
        
        // 🔥 添加事件监听
        this.container.querySelectorAll('.field-name-input').forEach(input => {
            input.addEventListener('change', (e) => {
                const fieldId = parseInt(e.target.dataset.fieldId);
                this.updateFieldName(fieldId, e.target.value);
            });
        });
        
        this.container.querySelectorAll('.btn-danger').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const fieldId = parseInt(e.target.dataset.fieldId);
                this.removeField(fieldId);
            });
        });
        
        this.updateConfirmButton();
    }
    
    renderEmptyState() {
        if (!this.container) return;
        
        this.container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📝</div>
                <p>还没有配置任何字段</p>
                <small>选择模式并开始分析页面</small>
            </div>
        `;
    }
    
    updateConfirmButton() {
        const btn = $('confirmBtn');
        if (!btn) return;
        
        const allFieldsNamed = this.fields.every(f => f.name && f.name.trim() !== '');
        btn.disabled = this.fields.length === 0 || !allFieldsNamed;
    }
    
    detectAttribute(data) {
        const tag = (data.tagName || '').toLowerCase();
        if (tag === 'img') return 'src';
        if (tag === 'a' && data.href) return 'href';
        return 'text';
    }
}