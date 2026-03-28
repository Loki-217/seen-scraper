const API_BASE = window.location.port === '3000' ? 'http://127.0.0.1:8000' : '';

let robotId = null;
let robotData = null;
let lastRunData = null;

// Monitor state
let editingScheduleId = null; // null = create mode, string = edit mode
let monitorSchedules = [];    // cached schedule list

// ============ Init ============

document.addEventListener('DOMContentLoaded', () => {
  // Tab switching — bind FIRST, before any early returns
  document.querySelectorAll('.robot-tab').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  const params = new URLSearchParams(window.location.search);
  robotId = params.get('id');
  const autorun = params.get('autorun') === 'true';

  if (!robotId) {
    showToast('No robot ID specified.', 'error');
    setTimeout(() => { window.location.href = 'index.html'; }, 2000);
    return;
  }

  // Quick Setup bindings
  document.getElementById('robotNameInput').addEventListener('blur', saveName);
  document.getElementById('btnRun').addEventListener('click', runTask);
  document.getElementById('btnDelete').addEventListener('click', deleteRobot);
  document.getElementById('btnDownloadCSV').addEventListener('click', () => downloadFile('csv'));
  document.getElementById('btnDownloadJSON').addEventListener('click', () => downloadFile('json'));

  // Monitor bindings
  document.getElementById('btnCreateMonitor').addEventListener('click', () => openMonitorForm());
  document.getElementById('btnCancelMonitor').addEventListener('click', closeMonitorForm);
  document.getElementById('btnSaveMonitor').addEventListener('click', saveMonitor);
  document.getElementById('freqUnit').addEventListener('change', updateDynamicFields);
  document.getElementById('chkAnytimeBetween').addEventListener('change', toggleAnytimeBetween);
  document.getElementById('chkAnytimeAt').addEventListener('change', toggleAnytimeAt);
  document.getElementById('weekdayToggleAll').addEventListener('click', toggleAllWeekdays);

  // Weekday buttons
  document.querySelectorAll('.weekday-btn').forEach(btn => {
    btn.addEventListener('click', () => btn.classList.toggle('selected'));
  });

  // Init timezone dropdown
  initTimezoneSelect();

  loadRobot(autorun);
});

// ============ Tab Switching ============

function switchTab(tabName) {
  // 1. Toggle tab button active state
  document.querySelectorAll('.robot-tab').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === tabName);
  });

  // 2. Hide all tab contents, show the target
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.remove('active');
    content.style.display = 'none';
  });
  const target = document.getElementById('tab-' + tabName);
  if (target) {
    target.classList.add('active');
    target.style.display = 'block';
  }

  // 3. Lazy-load data
  if (tabName === 'monitor') loadMonitors();
  if (tabName === 'history') loadHistory();
}

// ============ Quick Setup (existing) ============

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

  if (lastRunData) return;

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

    lastRunData = data.items || [];
    const runTime = new Date().toISOString();

    document.getElementById('reviewDesc').textContent =
      'The robot just ran a task. Please review the results below.';
    document.getElementById('emptyState').style.display = 'none';

    showRunInfo({
      success: data.success,
      originUrl: robotData.origin_url,
      time: runTime,
      itemsExtracted: data.items_extracted || lastRunData.length,
      pagesScraped: data.pages_scraped || 0,
      error: data.error,
    });

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
  document.getElementById('runInfoTime').innerHTML = `\u25CF ${formatRelativeTime(time)}`;
  document.getElementById('runInfoStats').innerHTML =
    `\u2261 ${itemsExtracted} items &nbsp; \uD83D\uDCC4 ${pagesScraped} pages`;
}

function renderDataTable(items) {
  if (!items || items.length === 0) return;

  const keys = Object.keys(items[0]);
  const area = document.getElementById('dataArea');
  area.style.display = 'block';

  document.getElementById('dataTitle').textContent = robotData.name;
  document.getElementById('dataCount').textContent = `(${items.length})`;

  const thead = document.getElementById('dataTableHead');
  thead.innerHTML = '<tr>' + keys.map(k => `<th>${escapeHtml(k)}</th>`).join('') + '</tr>';

  const tbody = document.getElementById('dataTableBody');
  tbody.innerHTML = items.map(item =>
    '<tr>' + keys.map(k => `<td>${escapeHtml(String(item[k] ?? ''))}</td>`).join('') + '</tr>'
  ).join('');

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

// ============ Monitor Tab ============

async function loadMonitors() {
  try {
    const res = await fetch(`${API_BASE}/schedules?robot_id=${robotId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    monitorSchedules = data.items || [];
    renderMonitorList();
  } catch (err) {
    console.error('Failed to load monitors:', err);
    showToast('Failed to load monitors: ' + err.message, 'error');
  }
}

function renderMonitorList() {
  const emptyEl = document.getElementById('monitorEmptyState');
  const listEl = document.getElementById('monitorList');

  if (monitorSchedules.length === 0) {
    emptyEl.style.display = 'block';
    listEl.style.display = 'none';
    return;
  }

  emptyEl.style.display = 'none';
  listEl.style.display = 'flex';
  listEl.innerHTML = monitorSchedules.map(s => renderMonitorCard(s)).join('');

  // Bind card action buttons
  listEl.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = btn.dataset.id;
      const action = btn.dataset.action;
      if (action === 'edit') editMonitor(id);
      else if (action === 'toggle') toggleMonitorEnabled(id);
      else if (action === 'delete') deleteMonitor(id);
    });
  });
}

function renderMonitorCard(s) {
  const enabled = s.enabled;
  const pausedClass = enabled ? '' : ' paused';
  const dotClass = enabled ? 'enabled' : 'paused';
  const toggleLabel = enabled ? '\u23F8' : '\u25B6';
  const toggleTitle = enabled ? 'Pause' : 'Resume';
  const originUrl = robotData ? robotData.origin_url : '';

  return `
    <div class="monitor-card${pausedClass}">
      <div class="monitor-card-left">
        <span class="monitor-icon">\uD83D\uDD50</span>
        <div class="monitor-info">
          <div class="monitor-name-row">
            <span class="monitor-status-dot ${dotClass}"></span>
            <span class="monitor-name">${escapeHtml(s.name)}</span>
          </div>
          <div class="monitor-origin">${escapeHtml(originUrl)}</div>
          <div class="monitor-freq">${buildFreqDescription(s)}</div>
        </div>
      </div>
      <div class="monitor-card-right">
        <div class="monitor-actions">
          <button class="monitor-action-btn" data-action="edit" data-id="${s.id}" title="Edit">\u270F\uFE0F</button>
          <button class="monitor-action-btn" data-action="toggle" data-id="${s.id}" title="${toggleTitle}">${toggleLabel}</button>
          <button class="monitor-action-btn delete" data-action="delete" data-id="${s.id}" title="Delete">\uD83D\uDDD1</button>
        </div>
        <div class="monitor-timing">Last check: ${s.last_run_at ? formatRelativeTime(s.last_run_at) : 'never'}</div>
        <div class="monitor-timing">Next check: ${s.next_run_at ? formatFutureTime(s.next_run_at) : 'not scheduled'}</div>
      </div>
    </div>`;
}

function buildFreqDescription(s) {
  const tz = s.timezone || 'UTC';
  const time = s.execute_at || null;
  const freq = s.frequency;

  // Parse cron for weekday info
  const cron = s.cron_expression || '';
  const parts = cron.split(' ');

  if (freq === '15min') {
    const weekdays = parts[4] ? formatWeekdayList(parts[4]) : 'every day';
    if (parts[1] && parts[1] !== '*') {
      return `Every 15 minutes on ${weekdays} between ${parts[1].replace('-', ':00-')}:00 (${tz})`;
    }
    return `Every 15 minutes on ${weekdays} (${tz})`;
  }
  if (freq === 'hourly') {
    const interval = parts[1] ? parts[1].replace('*/', '') : '1';
    const weekdays = parts[4] ? formatWeekdayList(parts[4]) : 'every day';
    return `Every ${interval} hour(s) on ${weekdays} (${tz})`;
  }
  if (freq === 'daily') {
    const t = time || 'anytime';
    return `Every day at around ${t} (${tz})`;
  }
  if (freq === 'weekly') {
    const weekday = parts[4] ? dayNumberToName(parts[4]) : 'Monday';
    const t = time || '00:00';
    return `Every week on ${weekday} at around ${t} (${tz})`;
  }
  if (freq === 'monthly') {
    const dayOfMonth = parts[2] || '1';
    const t = time || '00:00';
    return `Every month on day ${dayOfMonth} at around ${t} (${tz})`;
  }
  return cron || freq;
}

function formatWeekdayList(cronWeekdays) {
  if (cronWeekdays === '*') return 'every day';
  const names = { '0': 'Sun', '1': 'Mon', '2': 'Tue', '3': 'Wed', '4': 'Thu', '5': 'Fri', '6': 'Sat' };
  return cronWeekdays.split(',').map(d => names[d] || d).join(', ');
}

function dayNumberToName(num) {
  const names = { '0': 'Sunday', '1': 'Monday', '2': 'Tuesday', '3': 'Wednesday', '4': 'Thursday', '5': 'Friday', '6': 'Saturday' };
  return names[String(num)] || 'Monday';
}

// ---- Monitor Form ----

function openMonitorForm(scheduleData) {
  editingScheduleId = scheduleData ? scheduleData.id : null;

  document.getElementById('monitorFormTitle').textContent =
    editingScheduleId ? 'Edit monitor' : 'Add new monitor';

  // Fill form
  if (scheduleData) {
    document.getElementById('monitorNameInput').value = scheduleData.name || 'Default monitor';
    fillFormFromSchedule(scheduleData);
  } else {
    document.getElementById('monitorNameInput').value = 'Default monitor';
    document.getElementById('freqUnit').value = 'daily';
    document.getElementById('freqInterval').value = '1';
    document.getElementById('chkAnytimeBetween').checked = true;
    document.getElementById('chkAnytimeAt').checked = true;
    toggleAnytimeBetween();
    toggleAnytimeAt();
    // Reset weekdays to Mon-Fri selected
    document.querySelectorAll('.weekday-btn').forEach(btn => {
      const d = parseInt(btn.dataset.day);
      btn.classList.toggle('selected', d >= 1 && d <= 5);
    });
  }

  document.getElementById('monitorOriginUrl').value = robotData ? robotData.origin_url : '';
  updateDynamicFields();

  document.getElementById('monitorFormWrapper').style.display = 'block';
}

function closeMonitorForm() {
  document.getElementById('monitorFormWrapper').style.display = 'none';
  editingScheduleId = null;
}

function fillFormFromSchedule(s) {
  // Map API frequency to form select value
  const freqMap = { '15min': '15min', 'hourly': 'hourly', 'daily': 'daily', 'weekly': 'weekly', 'monthly': 'monthly' };
  const freq = freqMap[s.frequency] || 'daily';
  document.getElementById('freqUnit').value = freq;

  // Parse cron to fill fields
  const parsed = parseCronForEdit(s.cron_expression || '', s.frequency);

  // Interval
  document.getElementById('freqInterval').value = parsed.interval || 1;

  // Weekdays
  if (parsed.weekdays) {
    document.querySelectorAll('.weekday-btn').forEach(btn => {
      btn.classList.toggle('selected', parsed.weekdays.includes(parseInt(btn.dataset.day)));
    });
  }

  // Between / At around
  if (freq === '15min' || freq === 'hourly') {
    if (parsed.startHour !== null && parsed.endHour !== null) {
      document.getElementById('chkAnytimeBetween').checked = false;
      document.getElementById('betweenStart').value = pad2(parsed.startHour) + ':00';
      document.getElementById('betweenEnd').value = pad2(parsed.endHour) + ':00';
    } else {
      document.getElementById('chkAnytimeBetween').checked = true;
    }
    toggleAnytimeBetween();
  } else if (freq === 'daily') {
    if (s.execute_at) {
      document.getElementById('chkAnytimeAt').checked = false;
      document.getElementById('atAroundTime').value = s.execute_at;
    } else {
      document.getElementById('chkAnytimeAt').checked = true;
    }
    toggleAnytimeAt();
  } else if (freq === 'weekly' || freq === 'monthly') {
    if (s.execute_at) {
      document.getElementById('fixedTime').value = s.execute_at;
    }
  }

  // Timezone
  if (s.timezone) {
    document.getElementById('timezoneSelect').value = s.timezone;
  }
}

function parseCronForEdit(cron, frequency) {
  const result = { interval: 1, weekdays: null, startHour: null, endHour: null };
  if (!cron) return result;

  const parts = cron.split(' ');
  if (parts.length < 5) return result;

  const [minute, hour, dayOfMonth, month, weekday] = parts;

  // Weekdays
  if (weekday && weekday !== '*') {
    result.weekdays = weekday.split(',').map(Number);
  } else {
    result.weekdays = [0, 1, 2, 3, 4, 5, 6];
  }

  // Interval from hour or day field
  if (frequency === 'hourly' && hour.startsWith('*/')) {
    result.interval = parseInt(hour.replace('*/', ''));
  } else if (frequency === 'daily' && dayOfMonth.startsWith('*/')) {
    result.interval = parseInt(dayOfMonth.replace('*/', ''));
  }

  // Between hours
  if (hour.includes('-')) {
    const [s, e] = hour.split('-').map(Number);
    result.startHour = s;
    result.endHour = e;
  }

  return result;
}

function updateDynamicFields() {
  const freq = document.getElementById('freqUnit').value;

  // Show/hide interval input (hidden for 15min)
  document.getElementById('freqInterval').style.display = freq === '15min' ? 'none' : '';

  // Dynamic field visibility
  const showWeekdays = ['15min', 'hourly', 'daily'].includes(freq);
  const showBetween = ['15min', 'hourly'].includes(freq);
  const showAtAround = freq === 'daily';
  const showStartFrom = ['weekly', 'monthly'].includes(freq);
  const showFixedTime = ['weekly', 'monthly'].includes(freq);

  document.getElementById('weekdayRow').style.display = showWeekdays ? '' : 'none';
  document.getElementById('betweenRow').style.display = showBetween ? '' : 'none';
  document.getElementById('atAroundRow').style.display = showAtAround ? '' : 'none';
  document.getElementById('startFromRow').style.display = showStartFrom ? '' : 'none';
  document.getElementById('fixedTimeRow').style.display = showFixedTime ? '' : 'none';

  // Populate Start From dropdown
  if (showStartFrom) populateStartFromSelect();
}

function populateStartFromSelect() {
  const sel = document.getElementById('startFromSelect');
  sel.innerHTML = '';
  const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const months = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  for (let i = 0; i < 7; i++) {
    const d = new Date();
    d.setDate(d.getDate() + i);
    const dayName = dayNames[d.getDay()];
    let label;
    if (i === 0) {
      label = `${dayName} (Today)`;
    } else {
      label = `${dayName} (${months[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()})`;
    }
    const opt = document.createElement('option');
    opt.value = d.toISOString().slice(0, 10); // YYYY-MM-DD
    opt.textContent = label;
    sel.appendChild(opt);
  }
}

function toggleAnytimeBetween() {
  const checked = document.getElementById('chkAnytimeBetween').checked;
  document.getElementById('betweenStart').disabled = checked;
  document.getElementById('betweenEnd').disabled = checked;
}

function toggleAnytimeAt() {
  const checked = document.getElementById('chkAnytimeAt').checked;
  document.getElementById('atAroundTime').disabled = checked;
}

function toggleAllWeekdays(e) {
  e.preventDefault();
  const btns = document.querySelectorAll('.weekday-btn');
  const allSelected = Array.from(btns).every(b => b.classList.contains('selected'));
  btns.forEach(b => b.classList.toggle('selected', !allSelected));
  document.getElementById('weekdayToggleAll').textContent = allSelected ? 'Select All' : 'Deselect All';
}

function initTimezoneSelect() {
  const sel = document.getElementById('timezoneSelect');
  let tzList;
  try {
    tzList = Intl.supportedValuesOf('timeZone');
  } catch {
    tzList = [
      'Asia/Shanghai','Asia/Tokyo','Asia/Seoul','Asia/Singapore','Asia/Kolkata',
      'Europe/London','Europe/Paris','Europe/Berlin','America/New_York',
      'America/Chicago','America/Denver','America/Los_Angeles','Pacific/Auckland',
      'Australia/Sydney','UTC'
    ];
  }

  const userTz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  tzList.forEach(tz => {
    const opt = document.createElement('option');
    opt.value = tz;
    opt.textContent = tz === userTz ? `${tz} (Your timezone)` : tz;
    sel.appendChild(opt);
  });

  sel.value = userTz || 'Asia/Shanghai';
}

// ---- Cron Builder ----

function buildCronExpression() {
  const freq = document.getElementById('freqUnit').value;
  const interval = parseInt(document.getElementById('freqInterval').value) || 1;

  if (freq === '15min' || freq === 'hourly') {
    const weekdays = getSelectedWeekdays();
    const wd = weekdays.length === 7 ? '*' : weekdays.join(',');

    if (freq === '15min') {
      if (!document.getElementById('chkAnytimeBetween').checked) {
        const sh = parseInt(document.getElementById('betweenStart').value.split(':')[0]);
        const eh = parseInt(document.getElementById('betweenEnd').value.split(':')[0]);
        return `*/15 ${sh}-${eh} * * ${wd}`;
      }
      return `*/15 * * * ${wd}`;
    }

    // hourly
    const hourPart = interval > 1 ? `*/${interval}` : '*';
    if (!document.getElementById('chkAnytimeBetween').checked) {
      const sh = parseInt(document.getElementById('betweenStart').value.split(':')[0]);
      const eh = parseInt(document.getElementById('betweenEnd').value.split(':')[0]);
      return `0 ${sh}-${eh}/${interval} * * ${wd}`;
    }
    return `0 ${hourPart} * * ${wd}`;
  }

  if (freq === 'daily') {
    const weekdays = getSelectedWeekdays();
    const wd = weekdays.length === 7 ? '*' : weekdays.join(',');
    const dayPart = interval > 1 ? `*/${interval}` : '*';

    if (!document.getElementById('chkAnytimeAt').checked) {
      const t = document.getElementById('atAroundTime').value;
      const [h, m] = t.split(':').map(Number);
      return `${m} ${h} ${dayPart} * ${wd}`;
    }
    return `0 0 ${dayPart} * ${wd}`;
  }

  if (freq === 'weekly') {
    const dateStr = document.getElementById('startFromSelect').value;
    const d = new Date(dateStr + 'T00:00:00');
    const weekday = d.getDay(); // 0=Sun
    const t = document.getElementById('fixedTime').value || '10:00';
    const [h, m] = t.split(':').map(Number);
    return `${m} ${h} * * ${weekday}`;
  }

  if (freq === 'monthly') {
    const dateStr = document.getElementById('startFromSelect').value;
    const d = new Date(dateStr + 'T00:00:00');
    const dayOfMonth = d.getDate();
    const monthPart = interval > 1 ? `*/${interval}` : '*';
    const t = document.getElementById('fixedTime').value || '10:00';
    const [h, m] = t.split(':').map(Number);
    return `${m} ${h} ${dayOfMonth} ${monthPart} *`;
  }

  return '0 0 * * *';
}

function getSelectedWeekdays() {
  return Array.from(document.querySelectorAll('.weekday-btn.selected'))
    .map(b => parseInt(b.dataset.day));
}

function getExecuteAt() {
  const freq = document.getElementById('freqUnit').value;
  if (freq === 'daily') {
    if (!document.getElementById('chkAnytimeAt').checked) {
      return document.getElementById('atAroundTime').value || null;
    }
    return null;
  }
  if (freq === 'weekly' || freq === 'monthly') {
    return document.getElementById('fixedTime').value || null;
  }
  return null;
}

function getFrequencyValue() {
  const map = { '15min': '15min', 'hourly': 'hourly', 'daily': 'daily', 'weekly': 'weekly', 'monthly': 'monthly' };
  return map[document.getElementById('freqUnit').value] || 'daily';
}

// ---- Monitor CRUD ----

async function saveMonitor() {
  const name = document.getElementById('monitorNameInput').value.trim();
  if (!name) {
    showToast('Monitor name is required.', 'warning');
    return;
  }

  const freq = document.getElementById('freqUnit').value;

  // Validate: weekly/monthly must have time
  if ((freq === 'weekly' || freq === 'monthly') && !document.getElementById('fixedTime').value) {
    showToast('Please specify a time for weekly/monthly schedule.', 'warning');
    return;
  }

  const payload = {
    robot_id: robotId,
    name: name,
    frequency: getFrequencyValue(),
    cron_expression: buildCronExpression(),
    timezone: document.getElementById('timezoneSelect').value,
    execute_at: getExecuteAt(),
    enabled: true,
    retry_count: 3,
    retry_delay_seconds: 60,
  };

  try {
    let res;
    if (editingScheduleId) {
      // Update — don't send robot_id
      const { robot_id, ...updatePayload } = payload;
      res = await fetch(`${API_BASE}/schedules/${editingScheduleId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatePayload),
      });
    } else {
      res = await fetch(`${API_BASE}/schedules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    showToast(editingScheduleId ? 'Monitor updated.' : 'Monitor created.', 'success');
    closeMonitorForm();
    await loadMonitors();
  } catch (err) {
    console.error('Failed to save monitor:', err);
    showToast('Failed to save monitor: ' + err.message, 'error');
  }
}

function editMonitor(id) {
  const schedule = monitorSchedules.find(s => s.id === id);
  if (!schedule) return;
  openMonitorForm(schedule);
}

async function toggleMonitorEnabled(id) {
  const schedule = monitorSchedules.find(s => s.id === id);
  if (!schedule) return;

  try {
    const res = await fetch(`${API_BASE}/schedules/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !schedule.enabled }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    showToast(schedule.enabled ? 'Monitor paused.' : 'Monitor resumed.', 'success');
    await loadMonitors();
  } catch (err) {
    console.error('Failed to toggle monitor:', err);
    showToast('Failed to toggle monitor: ' + err.message, 'error');
  }
}

async function deleteMonitor(id) {
  if (!confirm('Are you sure you want to delete this monitor?')) return;

  try {
    const res = await fetch(`${API_BASE}/schedules/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    showToast('Monitor deleted.', 'success');
    await loadMonitors();
  } catch (err) {
    console.error('Failed to delete monitor:', err);
    showToast('Failed to delete monitor: ' + err.message, 'error');
  }
}

// ============ History Tab ============

async function loadHistory() {
  const emptyEl = document.getElementById('historyEmptyState');
  const noteEl = document.getElementById('historyNote');
  const tableWrapper = document.getElementById('historyTableWrapper');
  const tbody = document.getElementById('historyTableBody');

  try {
    // Get all schedules for this robot
    const schedRes = await fetch(`${API_BASE}/schedules?robot_id=${robotId}`);
    if (!schedRes.ok) throw new Error(`HTTP ${schedRes.status}`);
    const schedData = await schedRes.json();
    const schedules = schedData.items || [];

    if (schedules.length === 0) {
      emptyEl.style.display = 'block';
      emptyEl.textContent = 'No execution history yet. Run the task or set up a monitor to see results here.';
      noteEl.style.display = 'none';
      tableWrapper.style.display = 'none';
      return;
    }

    // Fetch runs for each schedule
    let allRuns = [];
    for (const sched of schedules) {
      const runsRes = await fetch(`${API_BASE}/schedules/${sched.id}/runs?limit=100`);
      if (runsRes.ok) {
        const runsData = await runsRes.json();
        allRuns = allRuns.concat(runsData.items || []);
      }
    }

    // Sort by started_at descending
    allRuns.sort((a, b) => {
      const ta = a.started_at ? new Date(a.started_at).getTime() : 0;
      const tb = b.started_at ? new Date(b.started_at).getTime() : 0;
      return tb - ta;
    });

    if (allRuns.length === 0) {
      emptyEl.style.display = 'block';
      emptyEl.textContent = 'No execution history yet. Run the task or set up a monitor to see results here.';
      noteEl.style.display = 'none';
      tableWrapper.style.display = 'none';
      return;
    }

    emptyEl.style.display = 'none';
    noteEl.style.display = 'block';
    tableWrapper.style.display = 'block';

    tbody.innerHTML = allRuns.map(run => {
      const statusBadge = renderStatusBadge(run.status);
      const trigger = run.trigger_type === 'manual' ? 'Manual' : 'Scheduled';
      const started = run.started_at ? formatLocalTime(run.started_at) : '-';
      const duration = run.duration_seconds != null ? `${run.duration_seconds.toFixed(1)}s` : '-';
      const pages = run.pages_scraped || 0;
      const items = run.items_extracted || 0;

      let actions = '';
      if (run.result_file) {
        actions += `<button class="history-action-btn" onclick="downloadRunResult('${run.id}')" title="Download CSV">\uD83D\uDCE5</button>`;
        actions += `<button class="history-action-btn" onclick="viewRunResult('${run.id}')" title="View JSON">\uD83D\uDCC4</button>`;
      }

      return `<tr>
        <td>${statusBadge}</td>
        <td>${trigger}</td>
        <td>${started}</td>
        <td>${duration}</td>
        <td>${pages}</td>
        <td>${items}</td>
        <td>${actions || '-'}</td>
      </tr>`;
    }).join('');

  } catch (err) {
    console.error('Failed to load history:', err);
    emptyEl.style.display = 'block';
    emptyEl.textContent = 'Failed to load execution history.';
    noteEl.style.display = 'none';
    tableWrapper.style.display = 'none';
  }
}

function renderStatusBadge(status) {
  const map = {
    succeeded: { label: '\u2705 Succeeded', cls: 'succeeded' },
    failed:    { label: '\u274C Failed',    cls: 'failed' },
    running:   { label: '\u23F3 Running',   cls: 'running' },
    pending:   { label: '\uD83D\uDD50 Pending',  cls: 'pending' },
    cancelled: { label: '\u26D4 Cancelled', cls: 'failed' },
  };
  const info = map[status] || { label: status, cls: 'pending' };
  return `<span class="status-badge ${info.cls}">${info.label}</span>`;
}

async function downloadRunResult(runId) {
  window.open(`${API_BASE}/runs/${runId}/download`, '_blank');
}

async function viewRunResult(runId) {
  try {
    const res = await fetch(`${API_BASE}/runs/${runId}/result`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    window.open(url, '_blank');
  } catch (err) {
    showToast('Failed to load result: ' + err.message, 'error');
  }
}

// ============ Utility Functions ============

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

function formatFutureTime(isoString) {
  if (!isoString) return '';
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diffMs = then - now;
  if (isNaN(diffMs) || diffMs < 0) return 'overdue';

  const minutes = Math.floor(diffMs / 60000);
  const hours = Math.floor(diffMs / 3600000);
  const days = Math.floor(diffMs / 86400000);

  if (minutes < 1) return 'any moment';
  if (minutes < 60) return `in ${minutes} minute${minutes !== 1 ? 's' : ''}`;
  if (hours < 24) return `in ${hours} hour${hours !== 1 ? 's' : ''}`;
  if (days < 7) return `in ${days} day${days !== 1 ? 's' : ''}`;

  return new Date(isoString).toLocaleDateString();
}

function formatLocalTime(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return d.toLocaleString();
}

function pad2(n) {
  return String(n).padStart(2, '0');
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
