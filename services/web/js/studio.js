/**
 * SeenFetch Studio - Main Application Logic
 * Guide-based state machine UI
 */

// API_BASE is defined in browser-canvas.js (loaded first)

// ---------- Global State ----------

let canvas = null;
let currentSession = null;
let configuredFields = [];
let paginationConfig = null;
let smartResult = null;
let guideState = 'initial';   // 'initial' | 'captureType' | 'smartDetect' | 'manualSelect' | 'configuring'
let previewDockExpanded = false;

// ---------- DOM References ----------

const $ = (id) => document.getElementById(id);

// ---------- Session Management ----------

async function startSession() {
    const url = $('urlInput').value.trim();
    if (!url) {
        showToast('Please enter a URL', 'warning');
        return;
    }

    $('loadBtn').classList.add('hidden');
    $('closeBtn').classList.remove('hidden');
    $('emptyState')?.classList.add('hidden');
    setStatus('connecting', 'Connecting...');

    try {
        canvas = new BrowserCanvas('browserContainer');

        const container = $('browserContainer');
        container.addEventListener('sessionReady', (e) => {
            currentSession = {
                sessionId: e.detail.sessionId,
                pageInfo: e.detail.pageInfo
            };
            $('currentUrl').textContent = e.detail.pageInfo?.url || url;
            $('elementCount').textContent = e.detail.elements?.length || 0;
            setStatus('connected', 'Connected');
            setGuideState('initial');
        });

        container.addEventListener('elementsUpdated', (e) => {
            $('elementCount').textContent = e.detail.count || 0;
        });

        container.addEventListener('elementSelect', (e) => {
            const count = e.detail.selected?.length || 0;
            $('selectionCount').textContent = count;
            // In manual mode, auto-add selected element as field
            if (guideState === 'manualSelect' && e.detail.element) {
                const el = e.detail.element;
                const existing = configuredFields.findIndex(f => f.selector === el.selector);
                if (existing >= 0) {
                    configuredFields.splice(existing, 1);
                } else {
                    addField({
                        name: el.text?.substring(0, 20) || el.tag,
                        selector: el.selector,
                        attr: el.href ? 'href' : (el.src ? 'src' : 'text'),
                        type: el.element_type || 'text',
                        confidence: 0,
                        sampleValues: el.text ? [el.text] : [],
                        itemSelector: ''
                    });
                }
                renderGuidePanel();
                updateFinishBtn();
            }
        });

        container.addEventListener('fpsUpdate', (e) => {
            $('frameRate').textContent = e.detail.fps || 0;
        });

        container.addEventListener('analyzeResult', (e) => {
            smartResult = e.detail;
            setGuideState('configuring');
        });

        container.addEventListener('similarFound', (e) => {
            showToast(`Found ${e.detail.count} similar items`, 'success');
        });

        container.addEventListener('sessionError', (e) => {
            showToast(`Error: ${e.detail.error}`, 'error');
            closeSession();
        });

        await canvas.initSession(url);

    } catch (error) {
        showToast(`Failed to load: ${error.message}`, 'error');
        closeSession();
    }
}

async function closeSession() {
    if (canvas) {
        const c = canvas;
        canvas = null;
        await c.closeSession();
        c.destroy();
    }

    currentSession = null;
    smartResult = null;
    configuredFields = [];
    paginationConfig = null;

    $('loadBtn').classList.remove('hidden');
    $('closeBtn').classList.add('hidden');
    $('currentUrl').textContent = 'No page loaded';
    $('elementCount').textContent = '0';
    $('selectionCount').textContent = '0';
    $('frameRate').textContent = '0';
    setStatus('ready', 'Ready');
    $('finishBtn').disabled = true;

    // Restore empty state
    const container = $('browserContainer');
    if (!container.querySelector('.empty-state')) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.id = 'emptyState';
        empty.innerHTML = `
            <div class="empty-icon">👁️</div>
            <p>Enter a URL and click <strong>Load</strong> to start</p>
            <p class="text-muted">Real-time page preview with element detection</p>
        `;
        container.appendChild(empty);
    }

    setGuideState('initial');
}

function discardRobot() {
    configuredFields = [];
    paginationConfig = null;
    smartResult = null;
    updateFinishBtn();
    if (currentSession) {
        setGuideState('initial');
    } else {
        renderGuidePanel();
    }
    showToast('Configuration discarded', 'info');
}

function setStatus(state, text) {
    const dot = document.querySelector('.status-dot');
    const label = document.querySelector('.status-text');
    dot.className = 'status-dot' + (state === 'connected' ? ' connected' : '');
    label.textContent = text;
}

// ---------- Guide State Machine ----------

function setGuideState(state) {
    guideState = state;
    renderGuidePanel();
}

function renderGuidePanel() {
    const panel = $('guideContent');
    if (!panel) return;

    switch (guideState) {
        case 'initial':      renderInitialGuide(panel); break;
        case 'captureType':  renderCaptureTypeGuide(panel); break;
        case 'smartDetect':  renderSmartDetectGuide(panel); break;
        case 'manualSelect': renderManualSelectGuide(panel); break;
        case 'configuring':  renderConfiguringGuide(panel); break;
        default:             renderInitialGuide(panel); break;
    }
}

function renderInitialGuide(panel) {
    const url = currentSession?.pageInfo?.url || $('urlInput').value || '';
    const hasSession = !!currentSession;

    panel.innerHTML = `
        <div class="guide-title">What data do you want<br>to extract?</div>
        <div class="guide-subtitle">
            ${hasSession
                ? 'Page loaded. Choose an option below to start extracting data.'
                : 'To begin, navigate to the page you\'d like to extract data from. Then, choose an option below.'}
        </div>

        <button class="guide-btn" onclick="setGuideState('captureType')" ${hasSession ? '' : 'disabled'}>
            <span class="guide-btn-icon">T</span>
            <span class="guide-btn-text">Capture text</span>
            <span class="guide-btn-arrow">›</span>
        </button>

        <button class="guide-btn" disabled>
            <span class="guide-btn-icon">📷</span>
            <span class="guide-btn-text">Capture screenshot</span>
            <span class="guide-btn-arrow">›</span>
        </button>
        <div class="guide-hint">Coming soon</div>

        <hr class="guide-divider">

        <div class="recording-badge">
            <span class="recording-dot"></span>
            <span>Recording started</span>
        </div>
        <div class="recording-hint">Robot records all your actions in order to be trained.</div>

        <hr class="guide-divider">

        <div class="step-title">Step 1: Navigation</div>
        <div class="step-detail">▶ Navigating to ${escapeHtml(truncate(url, 50)) || '...'}</div>
    `;
}

function renderCaptureTypeGuide(panel) {
    panel.innerHTML = `
        <div class="guide-title">Choose a capture type</div>
        <div class="guide-subtitle">How would you like to select data from this page?</div>

        <button class="guide-btn" onclick="startSmartDetect()">
            <span class="guide-btn-icon">📋</span>
            <span class="guide-btn-text">From a list</span>
            <span class="guide-btn-arrow">›</span>
        </button>
        <div class="guide-hint">For repeating items like products, results</div>

        <button class="guide-btn" onclick="setGuideState('manualSelect')">
            <span class="guide-btn-icon">T</span>
            <span class="guide-btn-text">Just text</span>
            <span class="guide-btn-arrow">›</span>
        </button>
        <div class="guide-hint">For specific elements on the page</div>

        <button class="guide-btn guide-btn-success" onclick="startSmartDetect()">
            <span class="guide-btn-icon">🤖</span>
            <span class="guide-btn-text">Smart detect</span>
            <span class="guide-btn-arrow">›</span>
        </button>
        <div class="guide-hint">AI auto-detect lists and fields</div>
    `;
}

function startSmartDetect() {
    setGuideState('smartDetect');
    if (canvas) {
        canvas.requestAnalyze();
    }
}

function renderSmartDetectGuide(panel) {
    panel.innerHTML = `
        <div class="step-title">Step 2: Select Data</div>

        <div class="guide-loading">
            <div class="spinner"></div>
            <p>AI analyzing page structure...</p>
        </div>
    `;
}

function renderManualSelectGuide(panel) {
    let fieldsHtml = '';
    if (configuredFields.length) {
        fieldsHtml = configuredFields.map((f, i) => `
            <div class="field-card-dark">
                <div class="field-card-dark-top">
                    <input class="field-name-input-dark" value="${escapeAttr(f.name)}"
                           onchange="updateField(${i}, {name: this.value}); renderGuidePanel()" placeholder="Field name">
                    <span class="badge-dark">${escapeHtml(f.type || 'text')}</span>
                    <button class="field-delete-btn-dark" onclick="removeField(${i}); renderGuidePanel(); updateFinishBtn()" title="Remove">✕</button>
                </div>
                <div class="field-card-dark-meta">
                    <span class="field-selector-dark">${escapeHtml(f.selector)}</span>
                    <select class="field-attr-select-dark" onchange="updateField(${i}, {attr: this.value})">
                        ${['text', 'href', 'src', 'innerHTML'].map(opt =>
                            `<option value="${opt}" ${f.attr === opt ? 'selected' : ''}>${opt}</option>`
                        ).join('')}
                    </select>
                </div>
            </div>
        `).join('');
    }

    panel.innerHTML = `
        <div class="step-title">Step 2: Select Elements</div>
        <div class="guide-subtitle" style="text-align:left;">Click elements on the page to select them. Left-click to add/remove fields.</div>

        <div class="step-detail" style="margin-bottom:12px;">Selected fields (${configuredFields.length}):</div>
        ${fieldsHtml || '<div style="color:var(--panel-text-dim);font-size:13px;padding:12px 0;">No fields selected yet. Click elements on the page.</div>'}

        <hr class="guide-divider">
        ${renderPaginationSection()}
    `;
}

function renderConfiguringGuide(panel) {
    const lists = smartResult?.lists || [];

    let listsHtml = '';
    if (!lists.length) {
        listsHtml = '<div style="color:var(--panel-text-dim);font-size:13px;padding:12px 0;">No data lists detected. Try selecting elements manually.</div>';
    } else {
        lists.forEach((list, listIdx) => {
            const fields = list.suggested_fields || list.fields || [];
            const itemCount = list.item_count || list.count || '?';
            listsHtml += `
                <div class="detect-card-dark">
                    <div class="detect-card-dark-header">
                        <strong>${escapeHtml(list.name || 'List ' + (listIdx + 1))}</strong>
                        <span class="badge-dark">${itemCount} items</span>
                    </div>
                    <div class="detect-card-dark-body">
                        <div class="detect-selector-dark">${escapeHtml(list.item_selector || '')}</div>
                        ${fields.map((f, fIdx) => `
                            <div class="detect-field-row-dark">
                                <span class="detect-field-name-dark">${escapeHtml(f.name || f.field_name || 'field_' + fIdx)}</span>
                                <span class="detect-field-type-dark">${escapeHtml(f.attr || f.extract_type || 'text')}</span>
                                <span class="detect-field-sample-dark">${escapeHtml(truncate(f.sample_values?.[0] || f.sample || '', 30))}</span>
                                <button class="detect-field-add-dark" onclick="addFieldFromDetect(${listIdx}, ${fIdx})">+</button>
                            </div>
                        `).join('')}
                        <button class="guide-btn" style="margin-top:8px;padding:10px 14px;font-size:13px;" onclick="addAllFields(${listIdx})">Add All Fields</button>
                    </div>
                </div>
            `;
        });
    }

    // Configured fields
    let fieldsHtml = '';
    if (configuredFields.length) {
        fieldsHtml = `
            <div class="step-detail" style="margin-bottom:8px;">Configured fields (${configuredFields.length}):</div>
            ${configuredFields.map((f, i) => `
                <div class="field-card-dark">
                    <div class="field-card-dark-top">
                        <input class="field-name-input-dark" value="${escapeAttr(f.name)}"
                               onchange="updateField(${i}, {name: this.value}); renderGuidePanel()" placeholder="Field name">
                        <span class="badge-dark">${escapeHtml(f.type || 'text')}</span>
                        <button class="field-delete-btn-dark" onclick="removeField(${i}); renderGuidePanel(); updateFinishBtn()" title="Remove">✕</button>
                    </div>
                    <div class="field-card-dark-meta">
                        <span class="field-selector-dark">${escapeHtml(f.selector)}</span>
                        <select class="field-attr-select-dark" onchange="updateField(${i}, {attr: this.value})">
                            ${['text', 'href', 'src', 'innerHTML'].map(opt =>
                                `<option value="${opt}" ${f.attr === opt ? 'selected' : ''}>${opt}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
            `).join('')}
        `;
    }

    panel.innerHTML = `
        <div class="step-title">Step 2: Select Data</div>
        ${listsHtml}

        ${fieldsHtml ? '<hr class="guide-divider">' + fieldsHtml : ''}

        <hr class="guide-divider">
        ${renderPaginationSection()}

        <hr class="guide-divider">
        <button class="guide-btn guide-btn-success" onclick="runPreview()" ${configuredFields.length ? '' : 'disabled'}>
            <span class="guide-btn-icon">👁</span>
            <span class="guide-btn-text">Preview Data</span>
            <span class="guide-btn-arrow">›</span>
        </button>
    `;
}

function renderPaginationSection() {
    let paginationHtml = '';
    if (paginationConfig) {
        const types = ['none', 'click_next', 'load_more', 'infinite_scroll', 'url_pattern'];
        paginationHtml = `
            <div class="pagination-type-group-dark">
                ${types.map(t => `
                    <button class="pagination-type-btn-dark ${t === paginationConfig.type ? 'active' : ''}"
                            onclick="selectPaginationType('${t}')">${formatPaginationType(t)}</button>
                `).join('')}
            </div>
            <div id="paginationFields"></div>
        `;
        // Render fields after innerHTML
        setTimeout(() => renderPaginationFields(), 0);
    }

    return `
        <div class="step-title">Step 3: Pagination</div>
        <button class="guide-btn" onclick="detectPagination()" style="padding:10px 14px;font-size:13px;margin-bottom:8px;">
            <span class="guide-btn-icon">📄</span>
            <span class="guide-btn-text">Auto Detect</span>
            <span class="guide-btn-arrow">›</span>
        </button>
        ${paginationHtml}
    `;
}

function renderPaginationFields() {
    const container = $('paginationFields');
    if (!container || !paginationConfig) return;

    let html = '';
    const cfg = paginationConfig;

    if (cfg.type === 'click_next' || cfg.type === 'load_more') {
        html += `
            <div class="pagination-form-group-dark">
                <label>Button Selector</label>
                <input value="${escapeAttr(cfg.next_button_selector || cfg.selector || '')}"
                       onchange="paginationConfig.next_button_selector = this.value" placeholder="e.g. .next-btn, a[rel=next]">
            </div>
        `;
    } else if (cfg.type === 'url_pattern') {
        html += `
            <div class="pagination-form-group-dark">
                <label>URL Pattern</label>
                <input value="${escapeAttr(cfg.url_pattern || '')}"
                       onchange="paginationConfig.url_pattern = this.value" placeholder="e.g. page={n}">
            </div>
        `;
    }

    if (cfg.type !== 'none') {
        html += `
            <div class="pagination-form-group-dark">
                <label>Max Pages</label>
                <input type="number" value="${cfg.max_pages || 5}" min="1" max="100"
                       onchange="paginationConfig.max_pages = parseInt(this.value)">
            </div>
            <div class="pagination-form-group-dark">
                <label>Wait Between Pages (ms)</label>
                <input type="number" value="${cfg.wait_ms || 1000}" min="0" max="10000" step="500"
                       onchange="paginationConfig.wait_ms = parseInt(this.value)">
            </div>
        `;
    }

    container.innerHTML = html;
}

// ---------- Field Management ----------

function addFieldFromDetect(listIdx, fieldIdx) {
    const lists = smartResult?.lists || [];
    if (!lists[listIdx]) return;

    const list = lists[listIdx];
    const fields = list.suggested_fields || list.fields || [];
    const f = fields[fieldIdx];
    if (!f) return;

    addField({
        name: f.name || f.field_name || 'field_' + fieldIdx,
        selector: f.selector || f.css_selector || '',
        attr: f.attr || f.extract_type || 'text',
        type: f.type || 'text',
        confidence: f.confidence || 0,
        sampleValues: f.sample_values || (f.sample ? [f.sample] : []),
        itemSelector: list.item_selector || ''
    });

    showToast(`Added field: ${f.name || f.field_name}`, 'success');
    renderGuidePanel();
    updateFinishBtn();
}

function addAllFields(listIdx) {
    const lists = smartResult?.lists || [];
    if (!lists[listIdx]) return;

    const list = lists[listIdx];
    const fields = list.suggested_fields || list.fields || [];
    fields.forEach((f, fIdx) => {
        addField({
            name: f.name || f.field_name || 'field_' + fIdx,
            selector: f.selector || f.css_selector || '',
            attr: f.attr || f.extract_type || 'text',
            type: f.type || 'text',
            confidence: f.confidence || 0,
            sampleValues: f.sample_values || (f.sample ? [f.sample] : []),
            itemSelector: list.item_selector || ''
        });
    });

    showToast(`Added ${fields.length} fields`, 'success');
    renderGuidePanel();
    updateFinishBtn();
}

function addField(field) {
    if (configuredFields.some(f => f.selector === field.selector && f.attr === field.attr)) return;
    configuredFields.push(field);
}

function removeField(index) {
    configuredFields.splice(index, 1);
}

function updateField(index, changes) {
    Object.assign(configuredFields[index], changes);
}

function updateFinishBtn() {
    $('finishBtn').disabled = configuredFields.length === 0;
}

// ---------- Pagination ----------

async function detectPagination() {
    if (!currentSession) return;

    showToast('Detecting pagination...', 'info');

    try {
        const res = await fetch(`${API_BASE}/sessions/${currentSession.sessionId}/detect-pagination`, {
            method: 'POST'
        });
        const data = await res.json();

        if (data.success && data.detected?.length) {
            const rec = data.recommended || data.detected[0]?.config || {};
            paginationConfig = {
                type: rec.type || data.detected[0]?.type || 'click_next',
                next_button_selector: rec.next_button_selector || rec.selector || '',
                max_pages: rec.max_pages || 5,
                wait_ms: rec.wait_ms || 1000,
                ...rec
            };
            showToast(`Detected ${data.detected.length} pagination method(s)`, 'success');
        } else {
            paginationConfig = { type: 'none', max_pages: 5, wait_ms: 1000 };
            showToast('No pagination detected', 'warning');
        }
        renderGuidePanel();
    } catch (error) {
        showToast(`Detection failed: ${error.message}`, 'error');
    }
}

function selectPaginationType(type) {
    if (type === 'none') {
        paginationConfig = null;
    } else {
        paginationConfig = { type, max_pages: paginationConfig?.max_pages || 5, wait_ms: paginationConfig?.wait_ms || 1000 };
    }
    renderGuidePanel();
}

function formatPaginationType(type) {
    const map = {
        'none': 'None',
        'click_next': 'Next Button',
        'load_more': 'Load More',
        'infinite_scroll': 'Scroll',
        'url_pattern': 'URL Pattern'
    };
    return map[type] || type;
}

// ---------- Preview ----------

async function runPreview() {
    if (!currentSession || !configuredFields.length) {
        showToast('Configure fields first', 'warning');
        return;
    }

    showToast('Extracting preview data...', 'info');

    // Expand dock
    previewDockExpanded = true;
    $('previewDock').className = 'preview-dock expanded';

    try {
        const itemSelector = configuredFields[0]?.itemSelector || smartResult?.lists?.[0]?.item_selector || '';
        const res = await fetch(`${API_BASE}/smart/extract-preview?session_id=${currentSession.sessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                item_selector: itemSelector,
                fields: configuredFields.map(f => ({
                    name: f.name,
                    selector: f.selector,
                    attr: f.attr
                }))
            })
        });
        const data = await res.json();

        const items = data.items || data.data || [];
        if (items.length) {
            updateDockPreview(items, configuredFields);
            showToast(`Extracted ${items.length} items`, 'success');
        } else {
            updateDockPreview([], []);
            showToast('No data found', 'warning');
        }
    } catch (error) {
        showToast(`Extract failed: ${error.message}`, 'error');
    }
}

// ---------- Preview Dock ----------

function togglePreviewDock() {
    previewDockExpanded = !previewDockExpanded;
    const dock = $('previewDock');
    dock.className = 'preview-dock ' + (previewDockExpanded ? 'expanded' : 'collapsed');
}

function updateDockPreview(data, fields) {
    const container = $('dockPreviewTable');
    const countEl = $('previewItemCount');
    if (!container) return;

    if (!data || data.length === 0) {
        container.innerHTML = '<div class="dock-empty">It looks like you have not selected anything for extraction yet. Once you do, you will see a preview of your selections here.</div>';
        if (countEl) countEl.textContent = '';
        return;
    }

    if (countEl) countEl.textContent = data.length + ' items';

    const keys = fields.map(f => f.name);
    let html = '<table class="dock-table"><thead><tr>';
    keys.forEach(k => { html += '<th>' + escapeHtml(k) + '</th>'; });
    html += '</tr></thead><tbody>';
    data.forEach(row => {
        html += '<tr>';
        keys.forEach(k => {
            const val = String(row[k] || '');
            html += '<td title="' + escapeAttr(val) + '">' + escapeHtml(truncate(val, 80)) + '</td>';
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// ---------- Save Robot ----------

function saveAsRobot() {
    if (!currentSession) return;

    const url = currentSession.pageInfo?.url || $('urlInput').value;
    const fieldCount = configuredFields.length;
    const pgType = paginationConfig?.type || 'None';

    showModal('💾 Save Robot', `
        <div class="modal-form-group">
            <label>Robot Name</label>
            <input type="text" id="robotName" placeholder="My Robot" autofocus>
        </div>
        <div class="modal-form-group">
            <label>Description (optional)</label>
            <input type="text" id="robotDesc" placeholder="Extracts quotes from...">
        </div>
        <div class="modal-form-group">
            <label>Origin URL</label>
            <div class="readonly">${escapeHtml(url)}</div>
        </div>
        <div class="modal-form-group">
            <label>Fields</label>
            <div class="readonly">${fieldCount} configured</div>
        </div>
        <div class="modal-form-group">
            <label>Pagination</label>
            <div class="readonly">${formatPaginationType(pgType)}</div>
        </div>
    `, [
        { text: 'Cancel', class: 'btn btn-secondary', onclick: 'closeModal()' },
        { text: 'Save Robot', class: 'btn btn-primary', onclick: 'doSaveRobot()' }
    ]);
}

async function doSaveRobot() {
    const name = $('robotName')?.value?.trim();
    if (!name) {
        showToast('Please enter a robot name', 'warning');
        return;
    }

    const desc = $('robotDesc')?.value?.trim() || '';

    try {
        const res = await fetch(`${API_BASE}/robots`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                description: desc,
                origin_url: currentSession.pageInfo?.url || $('urlInput').value,
                item_selector: smartResult?.lists?.[0]?.item_selector || '',
                fields: configuredFields.map(f => ({ name: f.name, selector: f.selector, attr: f.attr })),
                pagination: paginationConfig ? {
                    type: paginationConfig.type,
                    selector: paginationConfig.next_button_selector || '',
                    max_pages: paginationConfig.max_pages || 5,
                    wait_ms: paginationConfig.wait_ms || 1000
                } : null,
                actions: []
            })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const robot = await res.json();
        closeModal();
        showToast('Robot saved!', 'success');

        showModal('Robot Saved', `
            <p style="text-align:center; margin-bottom:16px;">Run the robot now?</p>
        `, [
            { text: 'Later', class: 'btn btn-secondary', onclick: 'closeModal()' },
            { text: 'Run Now', class: 'btn btn-primary', onclick: `runRobot(${robot.id}); closeModal()` }
        ]);

    } catch (error) {
        showToast(`Save failed: ${error.message}`, 'error');
    }
}

async function runRobot(robotId) {
    showToast('Running robot...', 'info');

    try {
        const res = await fetch(`${API_BASE}/robots/${robotId}/run`, { method: 'POST' });
        const data = await res.json();

        if (data.success !== false) {
            const items = data.items || [];
            showModal('Complete!', `
                <div style="text-align:center;">
                    <p style="margin-bottom:16px;">Pages: ${data.pages_scraped || '?'} &nbsp; Items: ${items.length} &nbsp; Time: ${data.duration || '?'}s</p>
                </div>
            `, [
                { text: 'Download CSV', class: 'btn btn-success', onclick: `downloadAsCSV(${JSON.stringify(JSON.stringify(items))})` },
                { text: 'Download JSON', class: 'btn btn-primary', onclick: `downloadAsJSON(${JSON.stringify(JSON.stringify(items))})` },
                { text: 'Close', class: 'btn btn-secondary', onclick: 'closeModal()' }
            ]);
        } else {
            showToast(`Run failed: ${data.message || 'Unknown error'}`, 'error');
        }

    } catch (error) {
        showToast(`Run failed: ${error.message}`, 'error');
    }
}

// ---------- Export ----------

function exportData() {
    const table = document.querySelector('.dock-table');
    if (!table) {
        showToast('Run preview first to get data', 'warning');
        return;
    }

    const rows = Array.from(table.querySelectorAll('tbody tr'));
    const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent);
    const items = rows.map(row => {
        const cells = Array.from(row.querySelectorAll('td'));
        const obj = {};
        headers.forEach((h, i) => {
            obj[h] = cells[i]?.getAttribute('title') || cells[i]?.textContent || '';
        });
        return obj;
    });

    if (!items.length) {
        showToast('No data to export', 'warning');
        return;
    }

    showModal('📥 Export Data', `
        <p style="text-align:center; margin-bottom:16px;">${items.length} items ready to export</p>
    `, [
        { text: 'CSV', class: 'btn btn-success', onclick: `downloadAsCSV(${JSON.stringify(JSON.stringify(items))}); closeModal()` },
        { text: 'JSON', class: 'btn btn-primary', onclick: `downloadAsJSON(${JSON.stringify(JSON.stringify(items))}); closeModal()` },
        { text: 'Cancel', class: 'btn btn-secondary', onclick: 'closeModal()' }
    ]);
}

function downloadAsCSV(itemsJson) {
    const items = JSON.parse(itemsJson);
    if (!items.length) return;

    const headers = Object.keys(items[0]);
    const csvRows = [headers.join(',')];
    items.forEach(item => {
        csvRows.push(headers.map(h => {
            const val = String(item[h] || '').replace(/"/g, '""');
            return `"${val}"`;
        }).join(','));
    });

    downloadBlob(csvRows.join('\n'), 'seenfetch-data.csv', 'text/csv');
}

function downloadAsJSON(itemsJson) {
    const items = JSON.parse(itemsJson);
    downloadBlob(JSON.stringify(items, null, 2), 'seenfetch-data.json', 'application/json');
}

function downloadBlob(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
}

// ---------- Toast ----------

function showToast(message, type = 'info', duration = 3000) {
    const container = $('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ---------- Modal ----------

function showModal(title, bodyHtml, buttons = []) {
    closeModal();

    const buttonsHtml = buttons.map(b =>
        `<button class="${b.class}" onclick="${escapeAttr(b.onclick)}">${escapeHtml(b.text)}</button>`
    ).join('');

    const modal = document.createElement('div');
    modal.className = 'modal-backdrop';
    modal.id = 'modal';
    modal.innerHTML = `
        <div class="modal-card">
            <div class="modal-header">
                <h3>${title}</h3>
                <button class="modal-close" onclick="closeModal()">✕</button>
            </div>
            <div class="modal-body">${bodyHtml}</div>
            <div class="modal-footer">${buttonsHtml}</div>
        </div>
    `;

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });

    document.body.appendChild(modal);
}

function closeModal() {
    const modal = $('modal');
    if (modal) modal.remove();
}

// ---------- Utilities ----------

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function escapeAttr(str) {
    return (str || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function truncate(str, max) {
    if (!str || str.length <= max) return str || '';
    return str.substring(0, max) + '...';
}

// ---------- Keyboard Shortcuts ----------

document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && e.target.id === 'urlInput') {
        startSession();
    }
});

// ---------- Init ----------

document.addEventListener('DOMContentLoaded', () => {
    renderGuidePanel();
});

if (document.readyState !== 'loading') {
    renderGuidePanel();
}
