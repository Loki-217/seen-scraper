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

// 2. 监控 location.href 变化（简化版，避免兼容性问题）
try {
    const originalHref = location.href;
    let hrefCheckInterval = setInterval(() => {
        if (location.href !== originalHref) {
            console.error('%c[Debug] location.href 已改变: ' + location.href, 'color: red; font-weight: bold');
            clearInterval(hrefCheckInterval);
        }
    }, 100);
} catch (e) {
    console.warn('[Debug] 无法监控 location.href 变化:', e);
}

// 3. 监控 beforeunload 事件（页面即将卸载/刷新）
window.addEventListener('beforeunload', function(e) {
    console.error('%c[Debug] ⚠️⚠️⚠️ beforeunload 事件触发! 页面即将刷新/卸载', 'color: red; font-weight: bold; font-size: 16px');
    if (window.lastClickedButton) {
        console.error('%c[Debug] 最后点击的按钮:', 'color: orange; font-weight: bold', window.lastClickedButton);
    }
    console.trace('调用堆栈:');
});

// 4. 监控 unload 事件
window.addEventListener('unload', function(e) {
    console.error('%c[Debug] unload 事件触发!', 'color: orange; font-weight: bold');
});

// 5. 监控表单提交
document.addEventListener('submit', function(e) {
    console.error('%c[Debug] 表单提交被触发!', 'color: red; font-weight: bold');
    console.log('表单元素:', e.target);
    console.trace('调用堆栈:');
    e.preventDefault(); // 阻止默认提交行为
}, true);

// 6. 监控所有按钮点击
document.addEventListener('click', function(e) {
    const button = e.target.closest('button');
    if (button) {
        const buttonInfo = {
            text: button.innerText.trim().substring(0, 30),
            type: button.type,
            className: button.className,
            onclick: button.onclick ? 'has onclick' : 'no onclick',
            hasForm: !!button.closest('form'),
            timestamp: new Date().toISOString()
        };

        console.log('%c[Debug] 按钮被点击:', 'color: blue; font-weight: bold', buttonInfo);

        // 存储最后点击的按钮信息
        window.lastClickedButton = buttonInfo;

        // 检查是否有可能导致刷新的属性
        if (!button.type || button.type === 'submit') {
            console.warn('%c[Debug] ⚠️ 警告: 按钮没有 type="button" 或 type="submit"', 'color: orange; font-weight: bold');
        }

        if (button.closest('form')) {
            console.warn('%c[Debug] ⚠️ 警告: 按钮在 <form> 内', 'color: orange; font-weight: bold');
        }
    }
}, true);

// 7. 监控网络请求
const originalFetch = window.fetch;
window.fetch = function(...args) {
    const url = args[0];
    console.log('%c[Debug] 发起网络请求:', 'color: purple', url);
    return originalFetch.apply(this, args).then(response => {
        console.log('%c[Debug] 网络请求完成:', 'color: purple', url, 'Status:', response.status);
        return response;
    }).catch(error => {
        console.error('%c[Debug] 网络请求失败:', 'color: red', url, error);
        throw error;
    });
};

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
console.log('- 监控 beforeunload/unload 事件（页面刷新前会触发）');
console.log('- 监控表单提交');
console.log('- 监控按钮点击（显示type、class等信息）');
console.log('- 监控网络请求（fetch API）');
console.log('- 监控 loadPage() 调用');
console.log('- 按 Ctrl+L 清空控制台');
console.log('%c✅ 现在可以开始测试了！点击按钮后观察控制台输出', 'color: green; font-weight: bold; font-size: 14px');
