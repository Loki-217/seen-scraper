/**
 * SeenFetch V2 - Browser Canvas 交互层
 *
 * 功能:
 * - 显示后端返回的页面截图
 * - 渲染可交互元素高亮覆盖层
 * - 捕获用户点击/悬停事件
 * - 与后端 Session API 通信
 */

const API_BASE = 'http://127.0.0.1:8000';

class BrowserCanvas {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container not found: ${containerId}`);
        }

        this.sessionId = null;
        this.elements = [];
        this.hoveredElement = null;
        this.selectedElements = [];
        this.isLoading = false;
        this.scale = 1;

        // 创建 Canvas 结构
        this._createCanvas();
        this._bindEvents();
    }

    _createCanvas() {
        // 清空容器
        this.container.innerHTML = '';

        // 创建 wrapper
        this.wrapper = document.createElement('div');
        this.wrapper.className = 'browser-canvas-wrapper';
        this.wrapper.style.cssText = `
            position: relative;
            width: 100%;
            height: 100%;
            overflow: auto;
            background: #f5f5f5;
        `;

        // 创建截图显示层
        this.imageLayer = document.createElement('div');
        this.imageLayer.className = 'browser-canvas-image';
        this.imageLayer.style.cssText = `
            position: relative;
            display: inline-block;
            min-width: 100%;
            min-height: 100%;
        `;

        // 截图 img
        this.screenshotImg = document.createElement('img');
        this.screenshotImg.className = 'browser-screenshot';
        this.screenshotImg.style.cssText = `
            display: block;
            max-width: none;
            user-select: none;
            -webkit-user-drag: none;
        `;

        // 创建覆盖层 (用于高亮元素)
        this.overlayCanvas = document.createElement('canvas');
        this.overlayCanvas.className = 'browser-overlay';
        this.overlayCanvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            pointer-events: none;
        `;
        this.ctx = this.overlayCanvas.getContext('2d');

        // 创建交互层 (捕获点击)
        this.interactionLayer = document.createElement('div');
        this.interactionLayer.className = 'browser-interaction';
        this.interactionLayer.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            cursor: crosshair;
        `;

        // 创建加载层
        this.loadingLayer = document.createElement('div');
        this.loadingLayer.className = 'browser-loading hidden';
        this.loadingLayer.innerHTML = `
            <div class="spinner"></div>
            <p>正在加载...</p>
        `;
        this.loadingLayer.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.9);
            z-index: 100;
        `;

        // 创建信息提示
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'browser-tooltip';
        this.tooltip.style.cssText = `
            position: fixed;
            padding: 8px 12px;
            background: rgba(0,0,0,0.85);
            color: white;
            font-size: 12px;
            border-radius: 6px;
            pointer-events: none;
            z-index: 1000;
            display: none;
            max-width: 300px;
            word-break: break-all;
        `;

        // 组装
        this.imageLayer.appendChild(this.screenshotImg);
        this.imageLayer.appendChild(this.overlayCanvas);
        this.imageLayer.appendChild(this.interactionLayer);
        this.wrapper.appendChild(this.imageLayer);
        this.wrapper.appendChild(this.loadingLayer);
        this.container.appendChild(this.wrapper);
        document.body.appendChild(this.tooltip);
    }

    _bindEvents() {
        // 鼠标移动 - 高亮元素
        this.interactionLayer.addEventListener('mousemove', (e) => this._handleMouseMove(e));

        // 鼠标离开
        this.interactionLayer.addEventListener('mouseleave', () => {
            this.hoveredElement = null;
            this._renderOverlay();
            this.tooltip.style.display = 'none';
        });

        // 点击
        this.interactionLayer.addEventListener('click', (e) => this._handleClick(e));

        // 右键 - 执行真实点击
        this.interactionLayer.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this._handleRealClick(e);
        });

        // 滚轮 - 滚动页面或缩放
        this.interactionLayer.addEventListener('wheel', (e) => {
            e.preventDefault();
            if (e.ctrlKey) {
                // Ctrl + 滚轮缩放
                const delta = e.deltaY > 0 ? -0.1 : 0.1;
                this.scale = Math.max(0.5, Math.min(2, this.scale + delta));
                this._applyScale();
            } else {
                // 普通滚轮 - 滚动远程页面
                this._handleWheel(e);
            }
        });

        // 键盘事件
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.selectedElements = [];
                this._renderOverlay();
            }
        });
    }

    _getCoordinates(e) {
        const rect = this.screenshotImg.getBoundingClientRect();
        const x = (e.clientX - rect.left) / this.scale;
        const y = (e.clientY - rect.top) / this.scale;
        return { x: Math.round(x), y: Math.round(y) };
    }

    _handleMouseMove(e) {
        if (!this.elements.length) return;

        const { x, y } = this._getCoordinates(e);

        // 查找鼠标下的元素
        const element = this._findElementAt(x, y);

        if (element !== this.hoveredElement) {
            this.hoveredElement = element;
            this._renderOverlay();
        }

        // 更新 tooltip
        if (element) {
            this.tooltip.innerHTML = `
                <div><strong>${element.tag}</strong> ${element.element_type}</div>
                <div style="color: #aaa; font-size: 11px;">${element.selector}</div>
                ${element.text ? `<div style="margin-top: 4px;">"${element.text}"</div>` : ''}
            `;
            this.tooltip.style.display = 'block';
            this.tooltip.style.left = (e.clientX + 15) + 'px';
            this.tooltip.style.top = (e.clientY + 15) + 'px';
        } else {
            this.tooltip.style.display = 'none';
        }
    }

    _handleClick(e) {
        const { x, y } = this._getCoordinates(e);
        const element = this._findElementAt(x, y);

        if (element) {
            // 切换选中状态
            const index = this.selectedElements.findIndex(el => el.selector === element.selector);
            if (index >= 0) {
                this.selectedElements.splice(index, 1);
            } else {
                this.selectedElements.push(element);
            }
            this._renderOverlay();

            // 触发自定义事件
            this.container.dispatchEvent(new CustomEvent('elementSelect', {
                detail: { element, selected: this.selectedElements }
            }));
        }
    }

    async _handleRealClick(e) {
        if (!this.sessionId) return;

        const { x, y } = this._getCoordinates(e);
        this._showLoading('正在执行点击...');

        try {
            const result = await this.executeAction({
                type: 'click',
                x: x,
                y: y
            });

            if (result.success) {
                // 触发页面变化事件
                this.container.dispatchEvent(new CustomEvent('pageChange', {
                    detail: { url: result.url, title: result.title }
                }));
            }
        } catch (error) {
            console.error('Click failed:', error);
        }

        this._hideLoading();
    }

    // 处理滚轮滚动 - 节流处理避免频繁请求
    _scrollThrottleTimer = null;
    _pendingScrollY = 0;

    _handleWheel(e) {
        if (!this.sessionId) return;

        // 累积滚动距离
        this._pendingScrollY += e.deltaY;

        // 节流：100ms 内只发送一次请求
        if (this._scrollThrottleTimer) return;

        this._scrollThrottleTimer = setTimeout(async () => {
            const distance = Math.abs(this._pendingScrollY);
            const direction = this._pendingScrollY > 0 ? 'down' : 'up';

            // 重置
            this._pendingScrollY = 0;
            this._scrollThrottleTimer = null;

            // 最小滚动距离
            if (distance < 50) return;

            try {
                await this.executeAction({
                    type: 'scroll',
                    direction: direction,
                    distance: Math.min(distance, 500)  // 最大单次滚动 500px
                });
            } catch (error) {
                console.error('Scroll failed:', error);
            }
        }, 50);
    }

    _findElementAt(x, y) {
        // 从后往前找（后面的元素在上层）
        for (let i = this.elements.length - 1; i >= 0; i--) {
            const el = this.elements[i];
            const r = el.rect;
            if (x >= r.x && x <= r.x + r.width && y >= r.y && y <= r.y + r.height) {
                return el;
            }
        }
        return null;
    }

    _renderOverlay() {
        if (!this.screenshotImg.naturalWidth) return;

        const width = this.screenshotImg.naturalWidth;
        const height = this.screenshotImg.naturalHeight;

        this.overlayCanvas.width = width;
        this.overlayCanvas.height = height;
        this.overlayCanvas.style.width = width * this.scale + 'px';
        this.overlayCanvas.style.height = height * this.scale + 'px';

        this.ctx.clearRect(0, 0, width, height);

        // 绘制所有可交互元素（淡色）
        this.elements.forEach(el => {
            const r = el.rect;
            this.ctx.strokeStyle = 'rgba(102, 126, 234, 0.2)';
            this.ctx.lineWidth = 1;
            this.ctx.strokeRect(r.x, r.y, r.width, r.height);
        });

        // 绘制选中的元素（绿色）
        this.selectedElements.forEach(el => {
            const r = el.rect;
            this.ctx.strokeStyle = 'rgba(76, 175, 80, 0.8)';
            this.ctx.fillStyle = 'rgba(76, 175, 80, 0.1)';
            this.ctx.lineWidth = 3;
            this.ctx.fillRect(r.x, r.y, r.width, r.height);
            this.ctx.strokeRect(r.x, r.y, r.width, r.height);
        });

        // 绘制悬停的元素（蓝色高亮）
        if (this.hoveredElement) {
            const r = this.hoveredElement.rect;
            this.ctx.strokeStyle = 'rgba(102, 126, 234, 0.8)';
            this.ctx.fillStyle = 'rgba(102, 126, 234, 0.15)';
            this.ctx.lineWidth = 2;
            this.ctx.fillRect(r.x, r.y, r.width, r.height);
            this.ctx.strokeRect(r.x, r.y, r.width, r.height);
        }
    }

    _applyScale() {
        const width = this.screenshotImg.naturalWidth * this.scale;
        const height = this.screenshotImg.naturalHeight * this.scale;

        this.screenshotImg.style.width = width + 'px';
        this.screenshotImg.style.height = height + 'px';
        this.overlayCanvas.style.width = width + 'px';
        this.overlayCanvas.style.height = height + 'px';
    }

    _showLoading(message = '正在加载...') {
        this.isLoading = true;
        this.loadingLayer.querySelector('p').textContent = message;
        this.loadingLayer.classList.remove('hidden');
    }

    _hideLoading() {
        this.isLoading = false;
        this.loadingLayer.classList.add('hidden');
    }

    // ============ 公共 API ============

    /**
     * 初始化会话 - 加载 URL
     */
    async initSession(url, options = {}) {
        this._showLoading('正在加载页面...');

        try {
            const response = await fetch(`${API_BASE}/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    viewport_width: options.viewportWidth || 1920,
                    viewport_height: options.viewportHeight || 1080,
                    wait_for: options.waitFor || null,
                    timeout_ms: options.timeout || 30000
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();

            this.sessionId = data.session_id;
            this.elements = data.elements || [];

            // 显示截图
            this._renderScreenshot(data.screenshot);

            // 触发加载完成事件
            this.container.dispatchEvent(new CustomEvent('sessionReady', {
                detail: {
                    sessionId: this.sessionId,
                    pageInfo: data.page_info,
                    elements: this.elements
                }
            }));

            return data;

        } catch (error) {
            console.error('Init session failed:', error);
            this.container.dispatchEvent(new CustomEvent('sessionError', {
                detail: { error: error.message }
            }));
            throw error;
        } finally {
            this._hideLoading();
        }
    }

    /**
     * 渲染截图
     */
    _renderScreenshot(base64Image) {
        return new Promise((resolve) => {
            this.screenshotImg.onload = () => {
                const width = this.screenshotImg.naturalWidth;
                const height = this.screenshotImg.naturalHeight;

                // 设置交互层尺寸
                this.interactionLayer.style.width = width + 'px';
                this.interactionLayer.style.height = height + 'px';

                this._applyScale();
                this._renderOverlay();
                resolve();
            };

            // 处理 base64 前缀
            if (!base64Image.startsWith('data:')) {
                base64Image = `data:image/jpeg;base64,${base64Image}`;
            }
            this.screenshotImg.src = base64Image;
        });
    }

    /**
     * 执行操作
     */
    async executeAction(action) {
        if (!this.sessionId) {
            throw new Error('No active session');
        }

        try {
            const response = await fetch(`${API_BASE}/sessions/${this.sessionId}/actions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(action)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            const result = await response.json();

            if (result.success) {
                // 更新截图和元素
                await this._renderScreenshot(result.screenshot_base64);
                this.elements = result.elements || [];
                this._renderOverlay();
            }

            return result;

        } catch (error) {
            console.error('Execute action failed:', error);
            throw error;
        }
    }

    /**
     * 滚动页面
     */
    async scroll(direction = 'down', distance = 300) {
        this._showLoading('正在滚动...');
        try {
            return await this.executeAction({
                type: 'scroll',
                direction: direction,
                distance: distance
            });
        } finally {
            this._hideLoading();
        }
    }

    /**
     * 刷新状态
     */
    async refreshState() {
        if (!this.sessionId) return;

        this._showLoading('正在刷新...');

        try {
            const response = await fetch(`${API_BASE}/sessions/${this.sessionId}/state`);
            if (!response.ok) throw new Error('Failed to get state');

            const state = await response.json();

            await this._renderScreenshot(state.screenshot);
            this.elements = state.elements || [];
            this._renderOverlay();

            return state;
        } finally {
            this._hideLoading();
        }
    }

    /**
     * 关闭会话
     */
    async closeSession() {
        if (!this.sessionId) return;

        try {
            await fetch(`${API_BASE}/sessions/${this.sessionId}`, {
                method: 'DELETE'
            });
        } catch (error) {
            console.error('Close session failed:', error);
        }

        this.sessionId = null;
        this.elements = [];
        this.selectedElements = [];
    }

    /**
     * 获取选中的元素
     */
    getSelectedElements() {
        return [...this.selectedElements];
    }

    /**
     * 清除选中
     */
    clearSelection() {
        this.selectedElements = [];
        this._renderOverlay();
    }

    /**
     * 根据选择器查找并高亮相似元素
     */
    highlightBySelector(selector) {
        const matching = this.elements.filter(el => {
            // 简单匹配 - 可以扩展
            return el.selector === selector ||
                   el.selector.includes(selector) ||
                   selector.includes(el.tag);
        });

        this.selectedElements = matching;
        this._renderOverlay();

        return matching;
    }

    /**
     * 销毁
     */
    destroy() {
        this.closeSession();
        if (this.tooltip && this.tooltip.parentNode) {
            this.tooltip.parentNode.removeChild(this.tooltip);
        }
        this.container.innerHTML = '';
    }
}

// 导出到全局
window.BrowserCanvas = BrowserCanvas;
