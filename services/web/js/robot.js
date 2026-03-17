const API_BASE = 'http://127.0.0.1:8000';

let robotId = null;
let robotData = null;
let lastRunData = null;

document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(window.location.search);
  robotId = params.get('id');
  const autorun = params.get('autorun') === 'true';

  if (!robotId) {
    showToast('No robot ID specified.', 'error');
    setTimeout(() => { window.location.href = 'index.html'; }, 2000);
    return;
  }

  // Name input blur → save
  document.getElementById('robotNameInput').addEventListener('blur', saveName);

  // Buttons
  document.getElementById('btnRun').addEventListener('click', runTask);
  document.getElementById('btnDelete').addEventListener('click', deleteRobot);
  document.getElementById('btnDownloadCSV').addEventListener('click', () => downloadFile('csv'));
  document.getElementById('btnDownloadJSON').addEventListener('click', () => downloadFile('json'));

  loadRobot(autorun);
});

async function loadRobot(autorun) {
  try {
    const res = await fetch(`${API_BASE}/robots/${robotId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    robotData = await res.json();
  } catch (err) {
    console.error('Failed to load robot:', err);
    showToast('Failed to load robot: ' + err.message, 'error');
    setTimeout(() => { window.location.href = 'index.html'; }, 2000);
    return;
  }

  // Populate UI
  document.getElementById('topbarRobotName').textContent = '\uD83E\uDD16 ' + robotData.name;
  document.getElementById('robotNameInput').value = robotData.name;
  document.title = `SeenFetch - ${robotData.name}`;

  if (autorun) {
    await runTask();
  } else {
    renderReviewSection();
  }
}

function renderReviewSection() {
  const descEl = document.getElementById('reviewDesc');
  const emptyEl = document.getElementById('emptyState');

  if (lastRunData) {
    // We have run data in memory — already rendered by runTask
    return;
  }

  if (robotData.last_run_at) {
    descEl.textContent = 'This robot has been run before.';
    emptyEl.innerHTML =
      `Last run completed at ${formatRelativeTime(robotData.last_run_at)}. ` +
      `Click 'Run Task' to run again and see results.`;
    emptyEl.style.display = 'block';
    document.getElementById('dataArea').style.display = 'none';
  } else {
    descEl.textContent = '';
    emptyEl.textContent = "No task has been run yet. Click 'Run Task' to start.";
    emptyEl.style.display = 'block';
    document.getElementById('dataArea').style.display = 'none';
  }
}

async function runTask() {
  const overlay = document.getElementById('loadingOverlay');
  overlay.style.display = 'flex';
  document.getElementById('btnRun').disabled = true;

  try {
    const res = await fetch(`${API_BASE}/robots/${robotId}/run`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!data.success) {
      throw new Error(data.error || 'Robot execution failed.');
    }

    // Store run data
    lastRunData = data.items || [];
    const runTime = new Date().toISOString();

    // Update review section
    document.getElementById('reviewDesc').textContent =
      'The robot just ran a task. Please review the results below.';
    document.getElementById('emptyState').style.display = 'none';

    // Show run info card
    showRunInfo({
      success: data.success,
      originUrl: robotData.origin_url,
      time: runTime,
      itemsExtracted: data.items_extracted || lastRunData.length,
      pagesScraped: data.pages_scraped || 0,
      error: data.error,
    });

    // Render data table
    if (lastRunData.length > 0) {
      renderDataTable(lastRunData);
    } else {
      document.getElementById('dataArea').style.display = 'none';
      const emptyEl = document.getElementById('emptyState');
      emptyEl.textContent = 'Robot ran successfully but extracted 0 items.';
      emptyEl.style.display = 'block';
    }
  } catch (err) {
    console.error('Run failed:', err);
    document.getElementById('reviewDesc').textContent = '';
    const emptyEl = document.getElementById('emptyState');
    emptyEl.innerHTML =
      `<div style="color:#ef4444;margin-bottom:12px">Error: ${escapeHtml(err.message)}</div>` +
      `<button class="btn-run" onclick="runTask()" style="font-size:13px;padding:8px 20px">Retry</button>`;
    emptyEl.style.display = 'block';
    document.getElementById('dataArea').style.display = 'none';
    document.getElementById('runInfoCard').style.display = 'none';
  } finally {
    overlay.style.display = 'none';
    document.getElementById('btnRun').disabled = false;
  }
}

function showRunInfo({ success, originUrl, time, itemsExtracted, pagesScraped, error }) {
  const card = document.getElementById('runInfoCard');
  card.style.display = 'flex';

  document.getElementById('runInfoStatus').innerHTML = success
    ? '\uD83E\uDD16 Finished successfully.'
    : `\uD83E\uDD16 <span style="color:#ef4444">${escapeHtml(error || 'Failed')}</span>`;

  document.getElementById('runInfoUrl').textContent = originUrl || '';
  document.getElementById('runInfoTime').innerHTML = `● ${formatRelativeTime(time)}`;
  document.getElementById('runInfoStats').innerHTML =
    `≡ ${itemsExtracted} items &nbsp; 📄 ${pagesScraped} pages`;
}

function renderDataTable(items) {
  if (!items || items.length === 0) return;

  const keys = Object.keys(items[0]);
  const area = document.getElementById('dataArea');
  area.style.display = 'block';

  document.getElementById('dataTitle').textContent = robotData.name;
  document.getElementById('dataCount').textContent = `(${items.length})`;

  // Head
  const thead = document.getElementById('dataTableHead');
  thead.innerHTML = '<tr>' + keys.map(k => `<th>${escapeHtml(k)}</th>`).join('') + '</tr>';

  // Body
  const tbody = document.getElementById('dataTableBody');
  tbody.innerHTML = items.map(item =>
    '<tr>' + keys.map(k => `<td>${escapeHtml(String(item[k] ?? ''))}</td>`).join('') + '</tr>'
  ).join('');

  // Enable download buttons
  document.getElementById('btnDownloadCSV').disabled = false;
  document.getElementById('btnDownloadJSON').disabled = false;
}

async function saveName() {
  const newName = document.getElementById('robotNameInput').value.trim();
  if (!newName || newName === robotData.name) return;

  try {
    const res = await fetch(`${API_BASE}/robots/${robotId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    robotData.name = newName;
    document.getElementById('topbarRobotName').textContent = '\uD83E\uDD16 ' + newName;
    document.title = `SeenFetch - ${newName}`;
  } catch (err) {
    console.error('Failed to save name:', err);
  }
}

async function deleteRobot() {
  if (!confirm('Are you sure you want to delete this robot? This action cannot be undone.')) return;

  try {
    const res = await fetch(`${API_BASE}/robots/${robotId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    window.location.href = 'index.html';
  } catch (err) {
    console.error('Failed to delete robot:', err);
    showToast('Failed to delete robot: ' + err.message, 'error');
  }
}

function downloadFile(format) {
  if (!lastRunData || lastRunData.length === 0) return;

  let blob, filename;

  if (format === 'csv') {
    const keys = Object.keys(lastRunData[0]);
    const quoteCsv = (val) => {
      const s = String(val ?? '');
      return s.includes(',') || s.includes('"') || s.includes('\n')
        ? '"' + s.replace(/"/g, '""') + '"'
        : s;
    };
    const csvRows = [keys.map(quoteCsv).join(',')];
    for (const item of lastRunData) {
      csvRows.push(keys.map(k => quoteCsv(item[k])).join(','));
    }
    blob = new Blob(['\uFEFF' + csvRows.join('\n')], { type: 'text/csv;charset=utf-8' });
    filename = `${robotData.name || 'robot'}.csv`;
  } else {
    blob = new Blob([JSON.stringify(lastRunData, null, 2)], { type: 'application/json' });
    filename = `${robotData.name || 'robot'}.json`;
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function formatRelativeTime(isoString) {
  if (!isoString) return '';
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = now - then;
  if (isNaN(diffMs)) return '';

  const minutes = Math.floor(diffMs / 60000);
  const hours = Math.floor(diffMs / 3600000);
  const days = Math.floor(diffMs / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
  if (hours < 24) return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
  if (days < 7) return `${days} day${days !== 1 ? 's' : ''} ago`;

  return new Date(isoString).toLocaleDateString();
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function showToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = 'position:fixed;top:16px;right:16px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
    document.body.appendChild(container);
  }
  const colors = { info: '#3b82f6', success: '#10b981', warning: '#f59e0b', error: '#ef4444' };
  const toast = document.createElement('div');
  toast.style.cssText = `padding:10px 16px;border-radius:8px;color:#fff;font-size:13px;background:${colors[type] || colors.info};box-shadow:0 2px 8px rgba(0,0,0,0.2);opacity:0;transition:opacity 0.3s;max-width:360px;`;
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => { toast.style.opacity = '1'; });
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}
