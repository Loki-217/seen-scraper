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
let guideState = 'initial';   // 'initial' | 'captureType' | 'listSelect' | 'smartDetect' | 'manualSelect' | 'configuring'
let previewDockExpanded = false;
let recordedSteps = [];          // Recorded action steps
let lastRecordedUrl = '';        // Track URL changes to avoid duplicates
let maxRowsSetting = null;       // null | 10 | 100 | custom number

// ---------- DOM References ----------

const $ = (id) => document.getElementById(id);

// ---------- Session Management ----------

let _containerListenersBound = false;

function _bindContainerListeners(container) {
    if (_containerListenersBound) return;
    _containerListenersBound = true;

    container.addEventListener('sessionReady', (e) => {
        currentSession = {
            sessionId: e.detail.sessionId,
            pageInfo: e.detail.pageInfo
        };
        const pageUrl = e.detail.pageInfo?.url || $('urlInput')?.value || '';
        $('currentUrl').textContent = pageUrl;
        $('elementCount').textContent = e.detail.elements?.length || 0;
        setStatus('connected', 'Connected');
        lastRecordedUrl = pageUrl;
        recordStep('navigation', { url: pageUrl });
        setGuideState('initial');
    });

    container.addEventListener('elementsUpdated', (e) => {
        $('elementCount').textContent = e.detail.count || 0;
    });

    container.addEventListener('elementSelect', (e) => {
        const count = e.detail.selected?.length || 0;
        $('selectionCount').textContent = count;
    });

    container.addEventListener('fpsUpdate', (e) => {
        $('frameRate').textContent = e.detail.fps || 0;
    });

    container.addEventListener('analyzeResult', (e) => {
        if (_analyzeTimeout) { clearTimeout(_analyzeTimeout); _analyzeTimeout = null; }
        smartResult = e.detail;
        setGuideState('configuring');
    });

    container.addEventListener('analyzeError', (e) => {
        if (_analyzeTimeout) { clearTimeout(_analyzeTimeout); _analyzeTimeout = null; }
        showToast('Smart detect failed. Try "From a list" to select manually.', 'warning', 5000);
        setGuideState('captureType');
    });

    container.addEventListener('listCaptured', (e) => {
        const d = e.detail;
        if (d.error) {
            showToast(d.error, 'warning');
            return;
        }
        if (d.itemCount < 2) {
            showToast('No list detected at this position. Try hovering over a different item.', 'warning');
            return;
        }

        recordStep('captured_list', {
            name: 'List',
            selector: d.itemSelector,
            containerSelector: d.containerSelector,
            itemCount: d.itemCount,
            sampleItems: d.sampleItems || [],
            fields: []
        });
        renderRecordedSteps();
        showToast(`List captured: ${d.itemCount} items`, 'success');

        if (d.rawItemData && (d.rawItemData.texts?.length || d.rawItemData.links?.length || d.rawItemData.images?.length)) {
            _analyzeFieldsWithAI(d);
            return;
        }
        _buildFieldsFromLegacyData(d);
    });

    container.addEventListener('textCaptured', (e) => {
        const el = e.detail.element;
        const isSelected = e.detail.selected?.some(s =>
            s.selector === el.selector && s.rect.x === el.rect.x && s.rect.y === el.rect.y
        );
        if (!isSelected) {
            const idx = configuredFields.findIndex(f =>
                f.captureType === 'text' && f.selector === el.selector
            );
            if (idx >= 0) configuredFields.splice(idx, 1);
            closeTextPopup(false);
            renderGuidePanel();
            updateFinishBtn();
            return;
        }
        recordStep('captured_text', {
            selector: el.selector,
            sampleValue: el.text || '',
            tag: el.tag
        });
        renderRecordedSteps();
        if (shouldSkipPopup(el)) {
            const namePrefix = el.src ? 'image' : (el.href ? 'link' : 'text');
            const attr = el.src ? 'src' : (el.href ? 'href' : 'text');
            const sampleValue = attr === 'text' ? (el.text || '') : (attr === 'href' ? (el.href || '') : (el.src || ''));
            const count = configuredFields.filter(f => f.captureType === 'text' && f.attr === attr).length + 1;
            addField({
                name: `${namePrefix}_${count}`,
                selector: el.selector,
                attr,
                type: el.element_type || 'text',
                captureType: 'text',
                confidence: 1,
                sampleValues: sampleValue ? [sampleValue] : []
            });
            renderGuidePanel();
            updateFinishBtn();
            showToast(`Captured ${namePrefix}: "${(sampleValue || el.tag).substring(0, 25)}"`, 'success');
            return;
        }
        showTextPopup(el);
    });

    container.addEventListener('pageInfo', (e) => {
        const newUrl = e.detail.url;
        if (newUrl && newUrl !== lastRecordedUrl) {
            lastRecordedUrl = newUrl;
            $('currentUrl').textContent = newUrl;
            recordStep('navigation', { url: newUrl });
            renderRecordedSteps();
            if (canvas && canvas.getMode() === 'capture_list') {
                canvas.reinjectListDetection();
            }
        }
    });

    container.addEventListener('modeChange', () => {
        // no-op
    });

    container.addEventListener('navigateClick', (e) => {
        recordStep('interaction', {
            action: 'click',
            selector: e.detail.selector,
            x: e.detail.x,
            y: e.detail.y
        });
        renderRecordedSteps();
    });

    container.addEventListener('navigateInput', (e) => {
        // Deduplicate: if same selector already has an input step, update value in place
        const existingIdx = recordedSteps.findIndex(
            s => s.type === 'interaction' && s.details.action === 'input' && s.details.selector === e.detail.selector
        );
        if (existingIdx !== -1) {
            recordedSteps[existingIdx].details.value = e.detail.value;
        } else {
            recordStep('interaction', {
                action: 'input',
                selector: e.detail.selector,
                value: e.detail.value
            });
        }
        renderRecordedSteps();
    });

    container.addEventListener('similarFound', (e) => {
        showToast(`Found ${e.detail.count} similar items`, 'success');
    });

    container.addEventListener('sessionError', (e) => {
        showToast(`Error: ${e.detail.error}`, 'error');
        closeSession();
    });

    container.addEventListener('reconnecting', (e) => {
        setStatus('connecting', `Reconnecting (${e.detail.attempt}/${e.detail.max})...`);
    });

    container.addEventListener('connectionLost', () => {
        showToast('Connection lost. Please reload the page.', 'error', 10000);
        closeSession();
    });

    container.addEventListener('sessionExpired', () => {
        showToast('Session expired. Please start a new session.', 'warning', 5000);
        closeSession();
    });
}

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
        _bindContainerListeners(container);

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
    maxRowsSetting = null;
    recordedSteps = [];
    lastRecordedUrl = '';

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
    maxRowsSetting = null;
    smartResult = null;
    recordedSteps = [];
    lastRecordedUrl = currentSession?.pageInfo?.url || '';
    if (canvas) canvas.setMode('navigate');
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
        case 'listSelect':   renderListSelectGuide(panel); break;
        case 'smartDetect':  renderSmartDetectGuide(panel); break;
        case 'manualSelect': renderManualSelectGuide(panel); break;
        case 'configuring':  renderConfiguringGuide(panel); break;
        default:             renderInitialGuide(panel); break;
    }

    // Update footer buttons visibility
    updateFinishBtn();

    // Append recorded steps below guide content
    renderRecordedSteps();
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

        <button class="guide-btn" onclick="startListCapture()">
            <span class="guide-btn-icon">📋</span>
            <span class="guide-btn-text">From a list</span>
            <span class="guide-btn-arrow">›</span>
        </button>
        <div class="guide-hint">For repeating items like products, results</div>

        <button class="guide-btn" onclick="startTextCapture()">
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

function startListCapture() {
    if (canvas) canvas.setMode('capture_list');
    setGuideState('listSelect');
}

function renderListSelectGuide(panel) {
    // Show captured lists if any
    const capturedLists = recordedSteps.filter(s => s.type === 'captured_list' && s.details.itemCount >= 2);
    let capturedHtml = '';
    if (capturedLists.length) {
        capturedHtml = capturedLists.map((step, i) => {
            const d = step.details;
            return `
                <div class="detect-card-dark" style="margin-bottom:8px;">
                    <div class="detect-card-dark-header">
                        <strong>List ${i + 1}</strong>
                        <span class="badge-dark">${d.itemCount} items</span>
                    </div>
                    <div class="detect-card-dark-body">
                        <div class="detect-selector-dark">${escapeHtml(d.selector)}</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    panel.innerHTML = `
        <div class="step-title">Step 2: Select a List</div>
        <div class="guide-subtitle" style="text-align:left;">
            Hover over a list on the page. Similar items will be highlighted with dashed outlines.
            Click to confirm the list selection.
        </div>

        <div class="guide-hint" style="margin-top:12px;">
            <span style="color:var(--panel-text-muted);font-size:12px;">
                Tip: Hover over different items to see how the list detection changes.
                The dashed outlines show all detected siblings.
            </span>
        </div>

        ${capturedHtml}

        <hr class="guide-divider">
        <button class="guide-btn" onclick="switchToSmartDetect()" style="padding:10px 14px;font-size:13px;">
            <span class="guide-btn-icon">🤖</span>
            <span class="guide-btn-text">Use Smart Detect instead</span>
            <span class="guide-btn-arrow">›</span>
        </button>
    `;
}

function switchToSmartDetect() {
    // Keep capture_list mode but trigger AI analysis
    setGuideState('smartDetect');
    if (canvas) canvas.requestAnalyze();
}

function startTextCapture() {
    if (canvas) canvas.setMode('capture_text');
    setGuideState('manualSelect');
}

let _analyzeTimeout = null;

function startSmartDetect() {
    if (canvas) canvas.setMode('capture_list');
    setGuideState('smartDetect');
    if (canvas) canvas.requestAnalyze();
    // Timeout: if no result in 15s, fall back
    if (_analyzeTimeout) clearTimeout(_analyzeTimeout);
    _analyzeTimeout = setTimeout(() => {
        if (guideState === 'smartDetect') {
            showToast('Smart detect timed out. Try "From a list" to select manually.', 'warning', 5000);
            setGuideState('captureType');
        }
    }, 15000);
}

// ---------- AI Field Analysis ----------

async function _analyzeFieldsWithAI(d) {
    // Show loading state in configuring panel
    setGuideState('configuring');
    _showAnalyzingOverlay(true);

    try {
        const body = JSON.stringify({ rawItemData: d.rawItemData });
        const res = await fetch(`${API_BASE}/smart/analyze-fields`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body
        });
        const result = await res.json();

        _showAnalyzingOverlay(false);

        if (result.fields && result.fields.length > 0) {
            // Use AI-analyzed fields
            result.fields.forEach(f => {
                addField({
                    name: f.name,
                    selector: f.selector,
                    attr: f.attr,
                    type: f.attr === 'href' ? 'link' : (f.attr === 'src' ? 'image' : 'text'),
                    confidence: 0,
                    sampleValues: [],
                    itemSelector: d.itemSelector
                });
            });

            // Build smartResult for the configuring panel
            if (!smartResult) smartResult = { lists: [] };
            smartResult.lists.push({
                name: 'Captured List',
                item_selector: d.itemSelector,
                item_count: d.itemCount,
                suggested_fields: result.fields.map(f => ({
                    name: f.name,
                    selector: f.selector,
                    attr: f.attr,
                    type: f.attr === 'href' ? 'link' : (f.attr === 'src' ? 'image' : 'text'),
                    sample_values: []
                }))
            });

            const label = result.aiEnhanced ? 'AI analyzed' : 'Auto detected';
            showToast(`${label}: ${result.fields.length} fields`, 'success');
        } else {
            // AI returned no fields, fall back to legacy
            _buildFieldsFromLegacyData(d);
        }
    } catch (err) {
        console.warn('[Studio] AI analyze-fields failed:', err);
        _showAnalyzingOverlay(false);
        // Fallback to legacy detection
        _buildFieldsFromLegacyData(d);
        showToast('AI analysis unavailable, using basic detection', 'warning');
    }

    renderGuidePanel();
    updateFinishBtn();
}

function _buildFieldsFromLegacyData(d) {
    const autoFields = [];
    if (d.detectedFields && d.detectedFields.length > 0) {
        const sampleValues = d.sampleItems?.[0] || {};
        d.detectedFields.forEach(f => {
            const svKey = f.name === 'url' ? 'url' : f.name;
            const sv = sampleValues[svKey] || '';
            autoFields.push({
                name: f.name,
                selector: f.selector,
                attr: f.attr,
                type: f.type || 'text',
                confidence: 0,
                sampleValues: sv ? [sv] : [],
                itemSelector: d.itemSelector
            });
        });
    } else if (d.sampleItems && d.sampleItems.length > 0) {
        const sample = d.sampleItems[0];
        if (sample.title) autoFields.push({ name: 'title', selector: 'h1,h2,h3,h4,h5,h6,[class*="title"],[class*="name"]', attr: 'text', type: 'text', confidence: 0, sampleValues: [sample.title], itemSelector: d.itemSelector });
        if (sample.url) autoFields.push({ name: 'url', selector: 'a[href]', attr: 'href', type: 'link', confidence: 0, sampleValues: [sample.url], itemSelector: d.itemSelector });
        if (sample.image) autoFields.push({ name: 'image', selector: 'img', attr: 'src', type: 'image', confidence: 0, sampleValues: [sample.image], itemSelector: d.itemSelector });
    }

    if (autoFields.length > 0) {
        if (!smartResult) smartResult = { lists: [] };
        smartResult.lists.push({
            name: 'Captured List',
            item_selector: d.itemSelector,
            item_count: d.itemCount,
            suggested_fields: autoFields.map(f => ({
                name: f.name,
                selector: f.selector,
                attr: f.attr,
                type: f.type,
                sample_values: f.sampleValues
            }))
        });
    }

    setGuideState('configuring');
    updateFinishBtn();
}

function _showAnalyzingOverlay(show) {
    const panel = $('guidePanel');
    if (!panel) return;
    const existing = panel.querySelector('.ai-analyzing-overlay');
    if (show) {
        if (existing) return;
        const overlay = document.createElement('div');
        overlay.className = 'ai-analyzing-overlay';
        overlay.innerHTML = `
            <div class="guide-loading">
                <div class="spinner"></div>
                <p>Analyzing data structure...</p>
            </div>
        `;
        overlay.style.cssText = 'position:absolute;inset:0;background:rgba(17,24,39,0.85);display:flex;align-items:center;justify-content:center;z-index:10;border-radius:12px;';
        panel.style.position = 'relative';
        panel.appendChild(overlay);
    } else {
        if (existing) existing.remove();
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

    // Check if a list with >= 2 items has been captured
    const hasCapturedList = lists.some(l => (l.item_count || l.count || 0) >= 2);
    const listPaginationHtml = hasCapturedList ? `
        <hr class="guide-divider">
        ${renderListPaginationSection()}
    ` : '';

    panel.innerHTML = `
        <div class="step-title">Step 2: Select Data</div>
        ${listsHtml}

        ${fieldsHtml ? '<hr class="guide-divider">' + fieldsHtml : ''}

        ${listPaginationHtml}

        <hr class="guide-divider">
        <button class="guide-btn guide-btn-success" onclick="runPreview()" ${configuredFields.length ? '' : 'disabled'}>
            <span class="guide-btn-icon">👁</span>
            <span class="guide-btn-text">Preview Data</span>
            <span class="guide-btn-arrow">›</span>
        </button>
    `;
}

function renderListPaginationSection() {
    // Max rows selection
    const current = maxRowsSetting;
    const rowOptions = [10, 100];
    const isCustom = current !== null && !rowOptions.includes(current);

    let maxRowsHtml = `
        <div class="step-title">Step 3: Max Rows</div>
        <div class="guide-subtitle" style="text-align:left;margin-bottom:8px;">How many rows to extract?</div>
        <div class="pagination-type-group-dark">
            ${rowOptions.map(n => `
                <button class="pagination-type-btn-dark ${current === n ? 'active' : ''}"
                        onclick="selectMaxRows(${n})">${n}</button>
            `).join('')}
            <button class="pagination-type-btn-dark ${isCustom ? 'active' : ''}"
                    onclick="promptCustomMaxRows()">Custom</button>
        </div>
        ${isCustom ? `<div style="margin-top:6px;font-size:12px;color:var(--panel-text-muted);">Custom: ${current} rows</div>` : ''}
    `;

    // Pagination detection
    let paginationHtml = '';
    if (paginationConfig) {
        const types = ['none', 'click_next', 'load_more', 'infinite_scroll', 'url_pattern'];
        paginationHtml = `
            <div class="pagination-type-group-dark" style="margin-top:8px;">
                ${types.map(t => `
                    <button class="pagination-type-btn-dark ${t === paginationConfig.type ? 'active' : ''}"
                            onclick="selectPaginationType('${t}')">${formatPaginationType(t)}</button>
                `).join('')}
            </div>
            <div id="paginationFields"></div>
        `;
        setTimeout(() => renderPaginationFields(), 0);
    }

    return `
        ${maxRowsHtml}

        <div class="step-title" style="margin-top:16px;">Step 4: Pagination</div>
        <button class="guide-btn" onclick="detectPagination()" style="padding:10px 14px;font-size:13px;margin-bottom:8px;">
            <span class="guide-btn-icon">📄</span>
            <span class="guide-btn-text">Select Pagination Setting</span>
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
    // Deduplicate name: append _2, _3... if name already exists
    let name = field.name;
    const nameExists = configuredFields.some(f => f.name === name);
    if (nameExists) {
        let suffix = 2;
        while (configuredFields.some(f => f.name === `${name}_${suffix}`)) suffix++;
        name = `${name}_${suffix}`;
    }
    configuredFields.push({ ...field, name });
}

function removeField(index) {
    configuredFields.splice(index, 1);
}

function updateField(index, changes) {
    Object.assign(configuredFields[index], changes);
}

function updateFinishBtn() {
    $('finishBtn').disabled = configuredFields.length === 0;
    const moreBtn = $('captureMoreBtn');
    if (moreBtn) {
        moreBtn.style.display = configuredFields.length >= 1 ? '' : 'none';
    }
}

// ---------- Text Capture Popup ----------

let _activeTextPopup = null;
let _activePopupElement = null;

function shouldSkipPopup(el) {
    let optionCount = 0;
    if (el.text && el.text.trim()) optionCount++;
    if (el.href && el.href.trim()) optionCount++;
    if (el.src && el.src.trim()) optionCount++;
    // innerHTML is meaningful only if element has child elements
    if (el.hasChildElements || el.href || el.src) optionCount++;
    return optionCount <= 1;
}

function showTextPopup(elementData) {
    // Close any existing popup first (cancel previous)
    closeTextPopup(true);

    _activePopupElement = elementData;
    window.__textPopupOpen = true;

    // Build options based on element data
    const options = [];
    if (elementData.text) {
        const preview = elementData.text.length > 40 ? elementData.text.substring(0, 40) + '...' : elementData.text;
        options.push({ label: 'Visible Text', preview, attr: 'text', icon: '\u{1F4DD}' });
    }
    if (elementData.href) {
        const preview = elementData.href.length > 50 ? elementData.href.substring(0, 50) + '...' : elementData.href;
        options.push({ label: 'Link URL', preview, attr: 'href', icon: '\u{1F517}' });
    }
    if (elementData.src) {
        const preview = elementData.src.length > 50 ? elementData.src.substring(0, 50) + '...' : elementData.src;
        options.push({ label: 'Image URL', preview, attr: 'src', icon: '\u{1F5BC}' });
    }
    // innerHTML: show only if it differs from plain text (has child elements)
    const rawHtml = elementData.innerHTML || '';
    const htmlDiffers = rawHtml && rawHtml !== (elementData.text || '').substring(0, 100);
    if (htmlDiffers) {
        const preview = rawHtml.length > 50 ? rawHtml.substring(0, 50) + '...' : rawHtml;
        options.push({ label: 'Inner HTML', preview, attr: 'innerHTML', icon: '\u{1F4C4}' });
    }

    // Create popup element
    const popup = document.createElement('div');
    popup.className = 'text-capture-popup';

    popup.innerHTML = `
        <div class="tcp-header">
            <span class="tcp-title">SELECT DATA TO EXTRACT</span>
            <span class="tcp-tag">&lt;${escapeHtml(elementData.tag)}&gt;</span>
        </div>
        ${options.map(opt => `
            <div class="tcp-option" data-attr="${opt.attr}">
                <span class="tcp-icon">${opt.icon}</span>
                <div class="tcp-option-content">
                    <div class="tcp-option-label">${escapeHtml(opt.label)}</div>
                    <div class="tcp-option-preview">${escapeHtml(opt.preview)}</div>
                </div>
            </div>
        `).join('<div class="tcp-divider"></div>')}
    `;

    // Attach click handlers to options
    popup.querySelectorAll('.tcp-option').forEach(optEl => {
        optEl.addEventListener('click', (ev) => {
            ev.stopPropagation();
            const attr = optEl.dataset.attr;
            const namePrefix = { text: 'text', href: 'link', src: 'image', innerHTML: 'html' }[attr] || 'field';
            const count = configuredFields.filter(f => f.captureType === 'text' && f.attr === attr).length + 1;
            const sampleValue = attr === 'text' ? (elementData.text || '') :
                                attr === 'href' ? (elementData.href || '') :
                                attr === 'src' ? (elementData.src || '') :
                                attr === 'innerHTML' ? (elementData.innerHTML || '') : '';
            addField({
                name: `${namePrefix}_${count}`,
                selector: elementData.selector,
                attr,
                type: elementData.element_type || 'text',
                captureType: 'text',
                confidence: 1,
                sampleValues: sampleValue ? [sampleValue] : []
            });
            closeTextPopup(false);
            renderGuidePanel();
            updateFinishBtn();
            showToast(`Added ${namePrefix}: "${(sampleValue || elementData.tag).substring(0, 25)}"`, 'success');
        });
    });

    // Position popup near the clicked element on the canvas
    const canvasEl = document.getElementById('browserCanvas') || document.querySelector('canvas');
    const canvasRect = canvasEl ? canvasEl.getBoundingClientRect() : { left: 0, top: 0, right: window.innerWidth };
    const elRect = elementData.rect || {};

    document.body.appendChild(popup);

    let left = canvasRect.left + (elRect.x || 0) + (elRect.width || 0) + 10;
    let top = canvasRect.top + (elRect.y || 0) + window.scrollY;

    if (left + 300 > window.innerWidth) {
        left = canvasRect.left + (elRect.x || 0) - 310;
    }
    if (top + popup.offsetHeight > window.innerHeight + window.scrollY) {
        top = window.innerHeight + window.scrollY - popup.offsetHeight - 10;
    }
    if (left < 5) left = 5;
    if (top < 5) top = 5;

    popup.style.left = left + 'px';
    popup.style.top = top + 'px';

    _activeTextPopup = popup;

    // Close on click outside (delayed to avoid catching the triggering click)
    setTimeout(() => {
        document._tcpClickOutside = (ev) => {
            if (_activeTextPopup && !_activeTextPopup.contains(ev.target)) {
                closeTextPopup(true);
            }
        };
        document._tcpEscHandler = (ev) => {
            if (ev.key === 'Escape') closeTextPopup(true);
        };
        document.addEventListener('mousedown', document._tcpClickOutside);
        document.addEventListener('keydown', document._tcpEscHandler);
    }, 50);
}

function closeTextPopup(cancelled) {
    window.__textPopupOpen = false;
    if (document._tcpClickOutside) {
        document.removeEventListener('mousedown', document._tcpClickOutside);
        document._tcpClickOutside = null;
    }
    if (document._tcpEscHandler) {
        document.removeEventListener('keydown', document._tcpEscHandler);
        document._tcpEscHandler = null;
    }
    if (_activeTextPopup) {
        _activeTextPopup.remove();
        _activeTextPopup = null;
    }
    if (cancelled && _activePopupElement && canvas) {
        canvas.deselectElement(_activePopupElement);
    }
    _activePopupElement = null;
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

        const _prevMaxRows = paginationConfig?.max_rows ?? maxRowsSetting;
        if (data.success && data.detected?.length) {
            const rec = data.recommended || data.detected[0]?.config || {};
            paginationConfig = {
                type: rec.type || data.detected[0]?.type || 'click_next',
                next_button_selector: rec.next_button_selector || rec.selector || '',
                max_pages: rec.max_pages || 5,
                wait_ms: rec.wait_ms || 1000,
                max_rows: _prevMaxRows,
                ...rec
            };
            showToast(`Detected ${data.detected.length} pagination method(s)`, 'success');
        } else {
            paginationConfig = { type: 'none', max_pages: 5, wait_ms: 1000, max_rows: _prevMaxRows };
            showToast('No pagination detected', 'warning');
        }
        renderGuidePanel();
    } catch (error) {
        showToast(`Detection failed: ${error.message}`, 'error');
    }
}

function selectPaginationType(type) {
    const _prevMaxRows = paginationConfig?.max_rows ?? maxRowsSetting;
    if (type === 'none') {
        paginationConfig = null;
    } else {
        paginationConfig = { type, max_pages: paginationConfig?.max_pages || 5, wait_ms: paginationConfig?.wait_ms || 1000, max_rows: _prevMaxRows };
    }
    renderGuidePanel();
}

function selectMaxRows(n) {
    maxRowsSetting = n;
    if (!paginationConfig) {
        paginationConfig = { type: 'none', max_pages: 1, wait_ms: 1000 };
    }
    paginationConfig.max_rows = n;
    renderGuidePanel();
}

function promptCustomMaxRows() {
    const val = prompt('Enter max number of rows:', maxRowsSetting || 500);
    if (val === null) return;
    const num = parseInt(val, 10);
    if (!num || num < 1) {
        showToast('Please enter a valid number', 'warning');
        return;
    }
    selectMaxRows(num);
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

// ---------- Recording ----------

function recordStep(type, details) {
    recordedSteps.push({
        type,
        timestamp: new Date().toISOString(),
        details
    });
}

function renderRecordedSteps() {
    const container = $('recordedSteps');
    if (!container) return;

    if (!recordedSteps.length) {
        container.innerHTML = '';
        return;
    }

    const icons = {
        navigation: '\u25b6',       // ▶
        interaction: '\u2197',      // ↗
        captured_list: '\u2261',    // ≡
        captured_text: 'T',
        captured_screenshot: '\ud83d\udcf7'
    };

    const html = recordedSteps.map((step, i) => {
        const icon = icons[step.type] || '?';
        const desc = formatStepDescription(step);
        return `<div class="recorded-step">
            <span class="step-icon">${icon}</span>
            <span class="step-desc">${escapeHtml(desc)}</span>
        </div>`;
    }).join('');

    container.innerHTML = `
        <hr class="guide-divider">
        <div class="step-title">Recorded Steps (${recordedSteps.length})</div>
        <div class="recorded-steps-list">${html}</div>
    `;

    // Auto-scroll to bottom
    const list = container.querySelector('.recorded-steps-list');
    if (list) list.scrollTop = list.scrollHeight;
}

function formatStepDescription(step) {
    const d = step.details;
    switch (step.type) {
        case 'navigation':
            return 'Navigate to ' + truncate(d.url || '', 40);
        case 'interaction':
            if (d.action === 'click') {
                return d.selector
                    ? 'Click ' + truncate(d.selector, 35)
                    : `Click at (${d.x}, ${d.y})`;
            }
            if (d.action === 'scroll') return 'Scroll page';
            if (d.action === 'input') return 'Input: ' + truncate(d.selector || '', 20) + ' = "' + truncate(d.value || '', 15) + '"';
            return d.action || 'Interaction';
        case 'captured_list':
            return 'Capture list: ' + truncate(d.selector || d.name || '', 30) + (d.itemCount ? ` (${d.itemCount} items)` : '');
        case 'captured_text':
            return 'Capture text: ' + truncate(d.sampleValue || d.name || '', 30);
        case 'captured_screenshot':
            return 'Capture screenshot';
        default:
            return step.type;
    }
}

function getRecordingData() {
    return {
        steps: JSON.parse(JSON.stringify(recordedSteps)),
        fields: configuredFields.map(f => ({ name: f.name, selector: f.selector, attr: f.attr, itemSelector: f.itemSelector || '' })),
        pagination: paginationConfig ? { ...paginationConfig } : null,
        url: currentSession?.pageInfo?.url || $('urlInput')?.value || ''
    };
}

function loadRecordingData(data) {
    if (!data) return;
    recordedSteps = data.steps || [];
    if (data.fields) {
        configuredFields = data.fields.map(f => ({
            name: f.name,
            selector: f.selector,
            attr: f.attr || 'text',
            type: 'text',
            confidence: 0,
            sampleValues: [],
            itemSelector: f.itemSelector || ''
        }));
    }
    if (data.pagination) {
        paginationConfig = { ...data.pagination };
    }
    renderRecordedSteps();
    renderGuidePanel();
    updateFinishBtn();
}

function stepsToActions() {
    const validTypes = ['click', 'scroll', 'input', 'wait', 'hover', 'select', 'navigate'];
    const actions = [];
    let hasUserAction = false;

    for (const step of recordedSteps) {
        // Navigation steps: only keep those after user actions (skip initial auto-redirects)
        if (step.type === 'navigation') {
            if (!hasUserAction) continue;
            actions.push({ type: 'navigate', url: step.details.url || '' });
            continue;
        }

        if (step.type !== 'interaction') continue;

        const d = step.details;
        hasUserAction = true;

        if (d.action === 'click') {
            actions.push({ type: 'click', selector: d.selector || '', x: d.x, y: d.y });
        } else if (d.action === 'scroll') {
            actions.push({ type: 'scroll', x: d.x || 0, y: d.y || 0 });
        } else if (d.action === 'input') {
            actions.push({ type: 'input', selector: d.selector || '', value: d.value || '' });
        } else {
            actions.push({ type: d.action, selector: d.selector || '' });
        }
    }

    return actions.filter(a => validTypes.includes(a.type));
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
        // Resolve item_selector: prefer captured_list step, fallback to smartResult
        const capturedListStep = recordedSteps.find(s => s.type === 'captured_list' && s.details.itemCount >= 2);
        const itemSelector = capturedListStep?.details?.selector
            || smartResult?.lists?.[0]?.item_selector
            || '';

        const _paginationPayload = paginationConfig ? {
            type: paginationConfig.type,
            selector: paginationConfig.next_button_selector || paginationConfig.selector || '',
            max_pages: paginationConfig.max_pages || 5,
            wait_ms: paginationConfig.wait_ms || 1000,
            max_rows: paginationConfig.max_rows || null
        } : null;
        const res = await fetch(`${API_BASE}/robots`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name,
                description: desc,
                origin_url: currentSession.pageInfo?.url || $('urlInput').value,
                item_selector: itemSelector,
                fields: configuredFields.map(f => ({ name: f.name, selector: f.selector, attr: f.attr, captureType: f.captureType || 'list' })),
                pagination: paginationConfig ? {
                    type: paginationConfig.type,
                    selector: paginationConfig.next_button_selector || paginationConfig.selector || '',
                    max_pages: paginationConfig.max_pages || 5,
                    wait_ms: paginationConfig.wait_ms || 1000,
                    max_rows: paginationConfig.max_rows || null
                } : null,
                actions: stepsToActions()
            })
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const robot = await res.json();
        closeModal();
        if (canvas) canvas.setMode('navigate');

        // Dispatch recordingComplete event
        document.dispatchEvent(new CustomEvent('recordingComplete', {
            detail: { robotId: robot.id, ...getRecordingData() }
        }));

        showToast('Robot saved!', 'success');

        const robotId = robot.id;
        showModal('Robot Saved', `
            <p style="text-align:center; margin-bottom:16px;">What would you like to do next?</p>
        `, [
            { text: 'Later', class: 'btn btn-secondary', onclick: `closeModal(); window.location.href = 'index.html'` },
            { text: 'Set Schedule', class: 'btn btn-secondary', onclick: `closeModal(); openScheduleDialog('${robotId}')` },
            { text: 'Run Now', class: 'btn btn-primary', onclick: `closeModal(); window.location.href = 'robot.html?id=${robotId}&autorun=true'` }
        ]);

    } catch (error) {
        showToast(`Save failed: ${error.message}`, 'error');
    }
}

function openScheduleDialog(robotId) {
    // Redirect to robot page for schedule setup (not yet implemented in Studio)
    window.location.href = `robot.html?id=${robotId}`;
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
// BUILD: 20260323-popup-v2
