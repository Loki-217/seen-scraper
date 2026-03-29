// API_BASE is defined in auth.js (loaded first)

let allRobots = [];

document.addEventListener('DOMContentLoaded', () => {
  if (!requireAuth()) return;
  renderTopbarUser();

  document.getElementById('btnNewRobot').addEventListener('click', () => {
    window.location.href = 'studio.html';
  });

  document.getElementById('searchInput').addEventListener('input', (e) => {
    const query = e.target.value.trim().toLowerCase();
    if (!query) {
      renderRobots(allRobots);
    } else {
      const filtered = allRobots.filter(r =>
        (r.name || '').toLowerCase().includes(query)
      );
      renderRobots(filtered);
    }
  });

  loadRobots();
});

async function loadRobots() {
  try {
    const res = await authFetch(`${API_BASE}/robots`);
    const data = await res.json();
    allRobots = data.items || data.data || [];
    renderRobots(allRobots);
  } catch (err) {
    console.error('Failed to load robots:', err);
    document.getElementById('robotList').innerHTML =
      '<div class="empty-state">Failed to load robots. Is the API server running?</div>';
  }
}

function renderRobots(robots) {
  const listEl = document.getElementById('robotList');
  const badgeEl = document.getElementById('statsBadge');

  // Update stats badge with totals from allRobots (not filtered)
  const domains = new Set(allRobots.map(r => extractDomain(r.origin_url)));
  if (allRobots.length > 0) {
    badgeEl.textContent = `${allRobots.length} robot${allRobots.length !== 1 ? 's' : ''} \u00B7 ${domains.size} website${domains.size !== 1 ? 's' : ''}`;
    badgeEl.classList.add('visible');
  } else {
    badgeEl.classList.remove('visible');
  }

  // Empty state
  if (robots.length === 0) {
    listEl.innerHTML = allRobots.length === 0
      ? '<div class="empty-state">No robots yet. Click \'+ Build New Robot\' to get started.</div>'
      : '<div class="empty-state">No robots match your search.</div>';
    return;
  }

  // Group by domain
  const groups = {};
  for (const robot of robots) {
    const domain = extractDomain(robot.origin_url);
    if (!groups[domain]) groups[domain] = [];
    groups[domain].push(robot);
  }

  let html = '';
  for (const [domain, domainRobots] of Object.entries(groups)) {
    html += `<div class="domain-group">
      <div class="domain-header">
        <span>\uD83C\uDF10</span>
        <span class="domain-name">${escapeHtml(domain)}</span>
        <span>\uD83D\uDD17</span>
        <span class="domain-count">${domainRobots.length}</span>
      </div>
      <div class="domain-cards">`;

    for (const robot of domainRobots) {
      const subPath = extractSubPath(robot.origin_url);
      const timeStr = formatRelativeTime(robot.updated_at);
      const robotId = robot.id || robot._id || '';

      // Future: if (robot.monitor_enabled) { show monitor status icon }
      html += `<a class="robot-card" href="robot.html?id=${encodeURIComponent(robotId)}">
        <div class="robot-name">${escapeHtml(robot.name || 'Untitled Robot')}</div>
        <div class="robot-url">${escapeHtml(subPath)}</div>
        <div class="robot-footer">
          <span class="robot-time">${timeStr}</span>
          <span class="robot-view">View \u2192</span>
        </div>
      </a>`;
    }

    html += '</div></div>';
  }

  listEl.innerHTML = html;
}

function extractDomain(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return url || 'unknown';
  }
}

function extractSubPath(url) {
  try {
    const u = new URL(url);
    return u.hostname + u.pathname;
  } catch {
    return url || '';
  }
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
