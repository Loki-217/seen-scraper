/**
 * SeenFetch V2 - Browser Canvas (CDP Screencast Mode)
 *
 * Receives real-time JPEG frames via WebSocket from CDP Screencast.
 * User interactions are sent back through the same WebSocket.
 *
 * Left click  → select/deselect element (frontend only)
 * Right click → inject click into remote browser via CDP
 * Wheel       → inject scroll into remote browser via CDP
 */

const API_BASE = 'http://127.0.0.1:8000';

class BrowserCanvas {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Container not found: ${containerId}`);
        }

        this.ws = null;
        this.sessionId = null;
        this.elements = [];
        this.hoveredElement = null;
        this.selectedElements = [];
        this.isLoading = false;
        this.scale = 1;
        this._frameCount = 0;
        this._lastFrameTime = 0;
        this._fps = 0;
        this._fpsInterval = null;

        this._createDOM();
        this._bindEvents();
    }

    _createDOM() {
        this.container.innerHTML = '';

        // Wrapper
        this.wrapper = document.createElement('div');
        this.wrapper.className = 'browser-canvas-wrapper';
        this.wrapper.style.cssText = `
            position: relative;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: #1a1a1a;
        `;

        // Frame image (receives CDP Screencast JPEG frames)
        this.frameImg = document.createElement('img');
        this.frameImg.className = 'browser-frame';
        this.frameImg.style.cssText = `
            display: block;
            width: 100%;
            height: 100%;
            object-fit: contain;
            user-select: none;
            -webkit-user-drag: none;
        `;

        // Overlay canvas for element highlights
        this.overlay = document.createElement('canvas');
        this.overlay.className = 'browser-overlay';
        this.overlay.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
        `;
        this.ctx = this.overlay.getContext('2d');

        // Interaction layer (captures mouse/keyboard events)
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

        // Tooltip
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

        // Loading overlay
        this.loadingOverlay = document.createElement('div');
        this.loadingOverlay.className = 'browser-loading hidden';
        this.loadingOverlay.innerHTML = `
            <div class="spinner"></div>
            <p>Loading...</p>
        `;
        this.loadingOverlay.style.cssText = `
            position: absolute;
            top: 0; left: 0;
            width: 100%; height: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.9);
            z-index: 100;
        `;

        // Assemble
        this.wrapper.appendChild(this.frameImg);
        this.wrapper.appendChild(this.overlay);
        this.wrapper.appendChild(this.interactionLayer);
        this.wrapper.appendChild(this.loadingOverlay);
        this.container.appendChild(this.wrapper);
        document.body.appendChild(this.tooltip);
    }

    _bindEvents() {
        // Mouse move → find hovered element → update overlay + tooltip
        this.interactionLayer.addEventListener('mousemove', (e) => this._handleMouseMove(e));

        // Mouse leave
        this.interactionLayer.addEventListener('mouseleave', () => {
            this.hoveredElement = null;
            this._renderOverlay();
            this.tooltip.style.display = 'none';
        });

        // Left click → select/deselect element (frontend only, not sent to browser)
        this.interactionLayer.addEventListener('click', (e) => this._handleClick(e));

        // Right click → inject real click into remote browser via CDP
        this.interactionLayer.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this._handleRealClick(e);
        });

        // Wheel → inject scroll into remote browser via CDP
        this.interactionLayer.addEventListener('wheel', (e) => {
            e.preventDefault();
            this._handleWheel(e);
        });

        // Escape → clear selection
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.clearSelection();
            }
        });

        // Update overlay when frame loads (to sync canvas dimensions)
        this.frameImg.addEventListener('load', () => {
            this._renderOverlay();
        });
    }

    // ---------- Coordinate conversion ----------

    _getCoords(e) {
        const rect = this.frameImg.getBoundingClientRect();
        if (!this.frameImg.naturalWidth || !rect.width) return { x: 0, y: 0 };
        const scaleX = this.frameImg.naturalWidth / rect.width;
        const scaleY = this.frameImg.naturalHeight / rect.height;
        return {
            x: Math.round((e.clientX - rect.left) * scaleX),
            y: Math.round((e.clientY - rect.top) * scaleY)
        };
    }

    // ---------- Event handlers ----------

    _handleMouseMove(e) {
        if (!this.elements.length) return;

        const { x, y } = this._getCoords(e);
        const element = this._findElementAt(x, y);

        if (element !== this.hoveredElement) {
            this.hoveredElement = element;
            this._renderOverlay();
        }

        if (element) {
            this.tooltip.innerHTML = `
                <div><strong>${escapeHtml(element.tag)}</strong> ${escapeHtml(element.element_type)}</div>
                <div style="color: #aaa; font-size: 11px;">${escapeHtml(element.selector)}</div>
                ${element.text ? `<div style="margin-top: 4px;">"${escapeHtml(element.text)}"</div>` : ''}
            `;
            this.tooltip.style.display = 'block';
            this.tooltip.style.left = (e.clientX + 15) + 'px';
            this.tooltip.style.top = (e.clientY + 15) + 'px';
        } else {
            this.tooltip.style.display = 'none';
        }
    }

    _handleClick(e) {
        const { x, y } = this._getCoords(e);
        const element = this._findElementAt(x, y);

        if (element) {
            const index = this.selectedElements.findIndex(el => el.selector === element.selector);
            if (index >= 0) {
                this.selectedElements.splice(index, 1);
            } else {
                this.selectedElements.push(element);
            }
            this._renderOverlay();

            this.container.dispatchEvent(new CustomEvent('elementSelect', {
                detail: { element, selected: this.selectedElements }
            }));
        }
    }

    _handleRealClick(e) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        const { x, y } = this._getCoords(e);
        this.ws.send(JSON.stringify({ type: 'mousePressed', x, y, button: 'left', clickCount: 1 }));
        this.ws.send(JSON.stringify({ type: 'mouseReleased', x, y, button: 'left', clickCount: 1 }));
    }

    _handleWheel(e) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

        const { x, y } = this._getCoords(e);
        this.ws.send(JSON.stringify({
            type: 'mouseWheel',
            x, y,
            deltaX: e.deltaX,
            deltaY: e.deltaY
        }));
    }

    // ---------- Element lookup ----------

    _findElementAt(x, y) {
        // Search from back to front (later elements are on top)
        for (let i = this.elements.length - 1; i >= 0; i--) {
            const el = this.elements[i];
            const r = el.rect;
            if (x >= r.x && x <= r.x + r.width && y >= r.y && y <= r.y + r.height) {
                return el;
            }
        }
        return null;
    }

    // ---------- Overlay rendering ----------

    _renderOverlay() {
        if (!this.frameImg.naturalWidth) return;

        const width = this.frameImg.naturalWidth;
        const height = this.frameImg.naturalHeight;

        this.overlay.width = width;
        this.overlay.height = height;

        this.ctx.clearRect(0, 0, width, height);

        // All elements - light blue outline
        this.elements.forEach(el => {
            const r = el.rect;
            this.ctx.strokeStyle = 'rgba(102, 126, 234, 0.2)';
            this.ctx.lineWidth = 1;
            this.ctx.strokeRect(r.x, r.y, r.width, r.height);
        });

        // Selected elements - green fill + thick border
        this.selectedElements.forEach(el => {
            const r = el.rect;
            this.ctx.strokeStyle = 'rgba(16, 185, 129, 0.8)';
            this.ctx.fillStyle = 'rgba(16, 185, 129, 0.1)';
            this.ctx.lineWidth = 3;
            this.ctx.fillRect(r.x, r.y, r.width, r.height);
            this.ctx.strokeRect(r.x, r.y, r.width, r.height);
        });

        // Hovered element - blue fill + thick border
        if (this.hoveredElement) {
            const r = this.hoveredElement.rect;
            this.ctx.strokeStyle = 'rgba(102, 126, 234, 0.8)';
            this.ctx.fillStyle = 'rgba(102, 126, 234, 0.15)';
            this.ctx.lineWidth = 2;
            this.ctx.fillRect(r.x, r.y, r.width, r.height);
            this.ctx.strokeRect(r.x, r.y, r.width, r.height);
        }
    }

    // ---------- Loading ----------

    _showLoading(message = 'Loading...') {
        this.isLoading = true;
        this.loadingOverlay.querySelector('p').textContent = message;
        this.loadingOverlay.classList.remove('hidden');
    }

    _hideLoading() {
        this.isLoading = false;
        this.loadingOverlay.classList.add('hidden');
    }

    // ---------- WebSocket ----------

    _connectWebSocket() {
        const wsUrl = `ws://127.0.0.1:8000/sessions/ws/${this.sessionId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('[BrowserCanvas] WebSocket connected');
            // Request initial elements
            this.requestElements();
        };

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === 'frame') {
                this.frameImg.src = 'data:image/jpeg;base64,' + msg.data;
                this._frameCount++;
            } else if (msg.type === 'elements') {
                this.elements = msg.elements || [];
                this._renderOverlay();
                this.container.dispatchEvent(new CustomEvent('elementsUpdated', {
                    detail: { elements: this.elements, count: this.elements.length }
                }));
            } else if (msg.type === 'analyzeResult') {
                this.container.dispatchEvent(new CustomEvent('analyzeResult', {
                    detail: { lists: msg.lists, pagination: msg.pagination }
                }));
            } else if (msg.type === 'similarElements') {
                this.container.dispatchEvent(new CustomEvent('similarFound', {
                    detail: { selector: msg.selector, rects: msg.rects, count: msg.count }
                }));
            }
        };

        this.ws.onclose = () => {
            console.log('[BrowserCanvas] WebSocket disconnected');
        };

        this.ws.onerror = (err) => {
            console.error('[BrowserCanvas] WebSocket error:', err);
        };

        // FPS counter
        this._fpsInterval = setInterval(() => {
            this._fps = this._frameCount;
            this._frameCount = 0;
            this.container.dispatchEvent(new CustomEvent('fpsUpdate', {
                detail: { fps: this._fps }
            }));
        }, 1000);
    }

    // ============ Public API ============

    /**
     * Initialize session - load URL and connect WebSocket
     */
    async initSession(url, options = {}) {
        this._showLoading('Loading page...');

        try {
            const response = await fetch(`${API_BASE}/sessions`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    viewport_width: options.viewportWidth || 1280,
                    viewport_height: options.viewportHeight || 800,
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

            // Connect WebSocket for frame streaming
            this._connectWebSocket();

            // Fire sessionReady event
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
     * Close session and WebSocket
     */
    async closeSession() {
        if (this._fpsInterval) {
            clearInterval(this._fpsInterval);
            this._fpsInterval = null;
        }

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        if (this.sessionId) {
            try {
                await fetch(`${API_BASE}/sessions/${this.sessionId}`, { method: 'DELETE' });
            } catch (error) {
                console.error('Close session failed:', error);
            }
            this.sessionId = null;
        }

        this.elements = [];
        this.selectedElements = [];
        this.hoveredElement = null;
        this._renderOverlay();
    }

    /**
     * Clear element selection
     */
    clearSelection() {
        this.selectedElements = [];
        this._renderOverlay();
    }

    /**
     * Get currently selected elements
     */
    getSelectedElements() {
        return [...this.selectedElements];
    }

    /**
     * Request elements list from backend via WebSocket
     */
    requestElements() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'getElements' }));
        }
    }

    /**
     * Request smart analysis via WebSocket
     */
    requestAnalyze() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'analyze' }));
        }
    }

    /**
     * Find similar elements by selector via WebSocket
     */
    findSimilar(selector) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'findSimilar', selector }));
        }
    }

    /**
     * Destroy canvas and clean up
     */
    destroy() {
        this.closeSession();
        if (this.tooltip && this.tooltip.parentNode) {
            this.tooltip.parentNode.removeChild(this.tooltip);
        }
        this.container.innerHTML = '';
    }
}

// Utility
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Export
window.BrowserCanvas = BrowserCanvas;
