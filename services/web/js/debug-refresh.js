/**
 * 页面刷新调试脚本
 * 用于追踪和定位导致页面意外刷新的原因
 */

console.log('%c[Debug] 刷新调试脚本已加载', 'color: green; font-weight: bold');

// 1. 监控所有可能导致刷新的事件
const originalReload = location.reload.bind(location);
location.reload = function(...args) {
    console.error('%c[Debug] location.reload() 被调用!', 'color: red; font-weight: bold');
    console.trace('调用堆栈:');
    return originalReload(...args);
};

// 2. 监控 location 变化
const originalLocationHref = Object.getOwnPropertyDescriptor(Location.prototype, 'href').set;
Object.defineProperty(location, 'href', {
    set: function(value) {
        console.error('%c[Debug] location.href 被修改为: ' + value, 'color: red; font-weight: bold');
        console.trace('调用堆栈:');
        return originalLocationHref.call(this, value);
    }
});

// 3. 监控 window.location 赋值
let locationValue = window.location;
Object.defineProperty(window, 'location', {
    get: function() {
        return locationValue;
    },
    set: function(value) {
        console.error('%c[Debug] window.location 被修改为: ' + value, 'color: red; font-weight: bold');
        console.trace('调用堆栈:');
        locationValue = value;
    }
});

// 4. 监控 beforeunload 事件
window.addEventListener('beforeunload', function(e) {
    console.error('%c[Debug] beforeunload 事件触发!', 'color: orange; font-weight: bold');
    console.trace('调用堆栈:');
});

// 5. 监控 unload 事件
window.addEventListener('unload', function(e) {
    console.error('%c[Debug] unload 事件触发!', 'color: orange; font-weight: bold');
});

// 6. 监控表单提交
document.addEventListener('submit', function(e) {
    console.error('%c[Debug] 表单提交被触发!', 'color: red; font-weight: bold');
    console.log('表单元素:', e.target);
    console.trace('调用堆栈:');
    e.preventDefault(); // 阻止默认提交行为
}, true);

// 7. 监控所有按钮点击
document.addEventListener('click', function(e) {
    const button = e.target.closest('button');
    if (button) {
        console.log('%c[Debug] 按钮被点击:', 'color: blue', {
            text: button.innerText.trim().substring(0, 30),
            type: button.type,
            className: button.className,
            onclick: button.onclick ? 'has onclick' : 'no onclick',
            hasForm: !!button.closest('form')
        });

        // 检查是否有可能导致刷新的属性
        if (!button.type || button.type === 'submit') {
            console.warn('%c[Debug] ⚠️ 警告: 按钮没有 type="button" 或 type="submit"', 'color: orange; font-weight: bold');
        }

        if (button.closest('form')) {
            console.warn('%c[Debug] ⚠️ 警告: 按钮在 <form> 内', 'color: orange; font-weight: bold');
        }
    }
}, true);

// 8. 监控 loadPage 函数调用
if (window.loadPage) {
    const originalLoadPage = window.loadPage;
    window.loadPage = function(...args) {
        console.warn('%c[Debug] loadPage() 被调用!', 'color: orange; font-weight: bold');
        console.trace('调用堆栈:');
        return originalLoadPage.apply(this, args);
    };
}

// 9. 监控 LoginSystem.detectLoginRequirement
if (window.LoginSystem && window.LoginSystem.detectLoginRequirement) {
    const originalDetect = window.LoginSystem.detectLoginRequirement;
    window.LoginSystem.detectLoginRequirement = async function(...args) {
        console.log('%c[Debug] LoginSystem.detectLoginRequirement 被调用', 'color: purple');
        return await originalDetect.apply(this, args);
    };
}

// 10. 添加快捷键清除日志
window.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.key === 'l') {
        console.clear();
        console.log('%c[Debug] 控制台已清空 (Ctrl+L)', 'color: green');
    }
});

console.log('%c[Debug] 调试功能:', 'color: blue; font-weight: bold');
console.log('- 监控 location.reload()');
console.log('- 监控 location.href 修改');
console.log('- 监控表单提交');
console.log('- 监控按钮点击');
console.log('- 监控 loadPage() 调用');
console.log('- 按 Ctrl+L 清空控制台');
console.log('%c现在可以开始测试了！', 'color: green; font-weight: bold');
