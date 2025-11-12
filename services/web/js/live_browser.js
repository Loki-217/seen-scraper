// services/web/js/live_browser.js
/**
 * 实时浏览模块 - 基于WebSocket + Canvas的流式浏览器
 */

class LiveBrowser {
    constructor(canvasId) {
        this.canvasId = canvasId;
        this.canvas = null;
        this.ctx = null;
        this.ws = null;
        this.sessionId = this.generateSessionId();
        this.isReady = false;
        this.isBrowseMode = false;  // 浏览模式开关
        this.currentUrl = '';

        // 缩放相关
        this.scale = 1.0;
        this.offsetX = 0;
        this.offsetY = 0;

        // 帧率统计
        this.frameCount = 0;
        this.lastFrameTime = Date.now();
        this.fps = 0;

        console.log('[LiveBrowser] 初始化，Session ID:', this.sessionId);
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    initCanvas() {
        const container = document.getElementById(this.canvasId);
        if (!container) {
            console.error('[LiveBrowser] 找不到容器:', this.canvasId);
            return false;
        }

        // 创建Canvas元素
        this.canvas = document.createElement('canvas');
        this.canvas.width = 1280;
        this.canvas.height = 720;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.cursor = 'pointer';
        this.canvas.style.background = '#000';
        this.canvas.tabIndex = 0;  // 使canvas可以接收键盘事件

        this.ctx = this.canvas.getContext('2d');

        // 清空容器并添加canvas
        container.innerHTML = '';
        container.appendChild(this.canvas);

        // 绑定交互事件
        this.bindEvents();

        console.log('[LiveBrowser] Canvas初始化完成');
        return true;
    }

    async connect(url) {
        if (!this.canvas) {
            if (!this.initCanvas()) {
                throw new Error('Canvas初始化失败');
            }
        }

        this.currentUrl = url;

        // 构建WebSocket URL
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = window.location.hostname;
        const wsPort = '8000';  // FastAPI端口
        const wsUrl = `${wsProtocol}//${wsHost}:${wsPort}/api/live/ws/browser/${this.sessionId}`;

        console.log('[LiveBrowser] 连接到:', wsUrl);

        // 显示加载状态
        this.showLoading('正在启动浏览器...');

        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(wsUrl);

            this.ws.onopen = () => {
                console.log('[LiveBrowser] WebSocket连接成功');

                // 发送初始化数据
                this.ws.send(JSON.stringify({
                    type: 'init',
                    url: url,
                    use_cookies: true
                }));
            };

            this.ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                this.handleMessage(message);

                if (message.type === 'ready') {
                    resolve();
                }
            };

            this.ws.onerror = (error) => {
                console.error('[LiveBrowser] WebSocket错误:', error);
                this.showError('连接失败');
                reject(error);
            };

            this.ws.onclose = () => {
                console.log('[LiveBrowser] WebSocket关闭');
                this.isReady = false;
                this.showError('连接已断开');
            };

            // 5秒超时
            setTimeout(() => {
                if (!this.isReady) {
                    reject(new Error('连接超时'));
                }
            }, 5000);
        });
    }

    handleMessage(message) {
        const type = message.type;

        if (type === 'ready') {
            console.log('[LiveBrowser] 浏览器就绪');
            this.isReady = true;
            this.hideLoading();

            // 聚焦canvas以接收键盘事件
            this.canvas.focus();

        } else if (type === 'frame') {
            // 渲染帧
            this.renderFrame(message.data);

            // 更新帧率
            this.frameCount++;
            const now = Date.now();
            if (now - this.lastFrameTime >= 1000) {
                this.fps = this.frameCount;
                this.frameCount = 0;
                this.lastFrameTime = now;
            }

        } else if (type === 'error') {
            console.error('[LiveBrowser] 服务器错误:', message.message);
            this.showError(message.message);

        } else if (type === 'cookies_saved') {
            console.log('[LiveBrowser] Cookie已保存:', message.count);
            showToast(`✓ 成功保存 ${message.count} 个Cookie`, 'success');

        } else if (type === 'page_info') {
            console.log('[LiveBrowser] 页面信息:', message.data);
        }
    }

    renderFrame(base64Data) {
        const img = new Image();

        img.onload = () => {
            // 清空Canvas
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

            // 绘制新帧
            this.ctx.save();
            this.ctx.translate(this.offsetX, this.offsetY);
            this.ctx.scale(this.scale, this.scale);
            this.ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
            this.ctx.restore();

            // 显示FPS（调试用）
            if (window.DEBUG_MODE) {
                this.ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                this.ctx.fillRect(10, 10, 80, 30);
                this.ctx.fillStyle = '#0f0';
                this.ctx.font = '14px monospace';
                this.ctx.fillText(`FPS: ${this.fps}`, 15, 30);
            }
        };

        img.onerror = () => {
            console.error('[LiveBrowser] 帧渲染失败');
        };

        img.src = 'data:image/jpeg;base64,' + base64Data;
    }

    bindEvents() {
        // 点击事件
        this.canvas.addEventListener('click', (e) => {
            if (!this.isReady) return;

            const coords = this.getCanvasCoordinates(e);
            this.sendAction({
                type: 'click',
                x: coords.x,
                y: coords.y
            });
        });

        // 键盘输入事件
        this.canvas.addEventListener('keydown', (e) => {
            if (!this.isReady) return;

            // 阻止默认行为（如空格滚动页面）
            e.preventDefault();

            if (e.key.length === 1) {
                // 单个字符
                this.sendAction({
                    type: 'type',
                    text: e.key
                });
            } else {
                // 特殊键（Enter, Backspace等）
                this.sendAction({
                    type: 'press',
                    key: e.key
                });
            }
        });

        // 滚轮事件
        this.canvas.addEventListener('wheel', (e) => {
            if (!this.isReady) return;

            e.preventDefault();

            this.sendAction({
                type: 'scroll',
                deltaY: e.deltaY
            });
        });

        // 鼠标悬停显示提示
        this.canvas.addEventListener('mouseenter', () => {
            if (this.isBrowseMode) {
                this.canvas.title = '真实浏览模式';
            } else {
                this.canvas.title = '爬取模式 - 点击元素提取数据';
            }
        });
    }

    getCanvasCoordinates(event) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;

        const x = (event.clientX - rect.left) * scaleX;
        const y = (event.clientY - rect.top) * scaleY;

        return { x: Math.round(x), y: Math.round(y) };
    }

    sendAction(action) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'action',
                data: action
            }));
        }
    }

    toggleBrowseMode(enabled) {
        this.isBrowseMode = enabled;

        if (this.isReady) {
            this.sendAction({
                type: 'toggle_browse_mode',
                enabled: enabled
            });
        }

        console.log('[LiveBrowser] 浏览模式:', enabled ? 'ON' : 'OFF');
    }

    async saveCookies() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'save_cookies'
            }));

            console.log('[LiveBrowser] 请求保存Cookie');
        }
    }

    navigate(url) {
        this.currentUrl = url;
        this.sendAction({
            type: 'navigate',
            url: url
        });
    }

    disconnect() {
        console.log('[LiveBrowser] 断开连接');

        if (this.ws) {
            this.ws.send(JSON.stringify({ type: 'close' }));
            this.ws.close();
            this.ws = null;
        }

        this.isReady = false;
    }

    showLoading(message = '加载中...') {
        if (!this.ctx) return;

        this.ctx.fillStyle = '#000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        this.ctx.fillStyle = '#fff';
        this.ctx.font = '20px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(message, this.canvas.width / 2, this.canvas.height / 2);

        // 加载动画
        const dots = ['', '.', '..', '...'];
        let dotIndex = 0;
        this._loadingInterval = setInterval(() => {
            if (!this.isReady && this.ctx) {
                this.ctx.fillStyle = '#000';
                this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

                this.ctx.fillStyle = '#fff';
                this.ctx.fillText(message + dots[dotIndex], this.canvas.width / 2, this.canvas.height / 2);

                dotIndex = (dotIndex + 1) % dots.length;
            }
        }, 500);
    }

    hideLoading() {
        if (this._loadingInterval) {
            clearInterval(this._loadingInterval);
            this._loadingInterval = null;
        }
    }

    showError(message) {
        if (!this.ctx) return;

        this.ctx.fillStyle = '#000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        this.ctx.fillStyle = '#f44336';
        this.ctx.font = '20px Arial';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('❌ ' + message, this.canvas.width / 2, this.canvas.height / 2);
    }

    destroy() {
        this.disconnect();
        this.hideLoading();

        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }

        this.canvas = null;
        this.ctx = null;

        console.log('[LiveBrowser] 已销毁');
    }
}

// 导出到全局
window.LiveBrowser = LiveBrowser;

console.log('[LiveBrowser] 模块加载完成');
