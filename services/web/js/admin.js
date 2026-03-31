// services/web/js/admin.js
// Admin dashboard — stats, users, invite codes, activity logs

document.addEventListener('DOMContentLoaded', () => {
    if (!requireAuth()) return;
    renderTopbarUser();

    // Admin role check
    const user = getCurrentUser();
    if (!user || user.role !== 'admin') {
        alert('Access denied: admin only');
        window.location.href = '/';
        return;
    }

    loadDashboard();
});

// ============ Panel switching ============

function switchPanel(name) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.sidebar-item').forEach(s => s.classList.remove('active'));

    const panel = document.getElementById(`panel-${name}`);
    if (panel) panel.classList.add('active');

    const item = document.querySelector(`.sidebar-item[data-panel="${name}"]`);
    if (item) item.classList.add('active');

    if (name === 'dashboard') loadDashboard();
    else if (name === 'users') loadUsers();
    else if (name === 'invite-codes') loadInviteCodes();
    else if (name === 'logs') loadActivityLogs(1);
}

// ============ Dashboard ============

async function loadDashboard() {
    try {
        const [statsResp, logsResp] = await Promise.all([
            authFetch(`${API_BASE}/admin/stats`),
            authFetch(`${API_BASE}/admin/activity-logs?page_size=10`),
        ]);

        if (!statsResp || !logsResp) return;
        const stats = await statsResp.json();
        const logs = await logsResp.json();

        renderStatCards(stats);
        renderBarChart(stats.daily_runs || []);
        renderRecentActivity(logs.items || []);
    } catch (e) {
        console.error('Failed to load dashboard:', e);
    }
}

function renderStatCards(stats) {
    const cards = [
        { label: 'Total Users', value: stats.total_users, sub: `${stats.today_active_users} active today` },
        { label: 'Total Robots', value: stats.total_robots, sub: `${stats.today_new_robots} new today` },
        { label: 'Total Runs', value: stats.total_runs, sub: `${stats.total_success} succeeded` },
        { label: 'Success Rate', value: `${stats.success_rate}%`, sub: `of ${stats.total_runs} runs` },
    ];
    document.getElementById('statCards').innerHTML = cards.map(c => `
        <div class="stat-card">
            <div class="stat-label">${c.label}</div>
            <div class="stat-value">${c.value}</div>
            <div class="stat-sub">${c.sub}</div>
        </div>
    `).join('');
}

function renderBarChart(dailyRuns) {
    if (!dailyRuns.length) {
        document.getElementById('barChart').innerHTML = '<span style="color:#9ca3af;font-size:13px;">No data</span>';
        return;
    }
    const max = Math.max(...dailyRuns.map(d => d.count), 1);
    document.getElementById('barChart').innerHTML = dailyRuns.map(d => {
        const pct = Math.max((d.count / max) * 100, 2);
        const label = d.date.slice(5); // MM-DD
        return `
            <div class="bar-col">
                <div class="bar-count">${d.count}</div>
                <div class="bar" style="height:${pct}%"></div>
                <div class="bar-label">${label}</div>
            </div>`;
    }).join('');
}

function renderRecentActivity(items) {
    const el = document.getElementById('recentActivity');
    if (!items.length) {
        el.innerHTML = '<div style="padding:16px;color:#9ca3af;font-size:13px;">No recent activity</div>';
        return;
    }
    el.innerHTML = items.map(item => {
        const time = item.created_at ? new Date(item.created_at).toLocaleString() : '';
        return `
            <div class="activity-item">
                <span class="activity-time">${time}</span>
                <span class="activity-user">${item.user_id ? item.user_id.slice(0, 8) : '-'}</span>
                <span>${formatAction(item.action)} ${item.target_url || ''}</span>
            </div>`;
    }).join('');
}

// ============ Users ============

let _usersCache = [];

async function loadUsers() {
    try {
        const resp = await authFetch(`${API_BASE}/admin/users`);
        if (!resp) return;
        const data = await resp.json();
        _usersCache = data.items || [];
        renderUsersTable(_usersCache);
    } catch (e) {
        console.error('Failed to load users:', e);
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById('usersTableBody');
    if (!users.length) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#9ca3af;padding:24px;">No users</td></tr>';
        return;
    }
    tbody.innerHTML = users.map(u => {
        const roleBadge = u.role === 'admin'
            ? '<span class="badge badge-admin">admin</span>'
            : '<span class="badge badge-info">user</span>';
        const statusBadge = u.is_active
            ? '<span class="badge badge-success">active</span>'
            : '<span class="badge badge-danger">disabled</span>';
        const lastActive = u.last_active ? new Date(u.last_active).toLocaleString() : '-';
        const toggleLabel = u.is_active ? 'Disable' : 'Enable';
        const toggleClass = u.is_active ? 'btn-danger-outline' : 'btn-outline';
        const isAdmin = u.role === 'admin';
        return `
            <tr class="${u.is_active ? '' : 'disabled'}">
                <td>${esc(u.username)}</td>
                <td>${esc(u.email || '-')}</td>
                <td>${roleBadge}</td>
                <td>${u.robot_count}</td>
                <td>${u.total_runs}</td>
                <td>${lastActive}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="btn btn-sm btn-outline" onclick="viewUserRobots('${u.id}','${esc(u.username)}')">Robots</button>
                    ${isAdmin ? '' : `<button class="btn btn-sm ${toggleClass}" onclick="toggleUserStatus('${u.id}',${!u.is_active})">${toggleLabel}</button>`}
                </td>
            </tr>`;
    }).join('');
}

async function toggleUserStatus(userId, newActive) {
    const action = newActive ? 'enable' : 'disable';
    if (!confirm(`Are you sure you want to ${action} this user?`)) return;
    try {
        const resp = await authFetch(`${API_BASE}/admin/users/${userId}/status`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: newActive }),
        });
        if (resp && resp.ok) loadUsers();
        else if (resp) {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Failed to update user status');
        }
    } catch (e) {
        console.error('toggleUserStatus error:', e);
    }
}

async function viewUserRobots(userId, username) {
    document.getElementById('robotsModalTitle').textContent = `Robots — ${username}`;
    const body = document.getElementById('robotsModalBody');
    body.innerHTML = '<span style="color:#9ca3af;">Loading...</span>';
    document.getElementById('robotsModal').style.display = 'flex';

    try {
        const resp = await authFetch(`${API_BASE}/admin/users/${userId}/robots`);
        if (!resp) return;
        const data = await resp.json();
        const robots = data.items || [];

        if (!robots.length) {
            body.innerHTML = '<span style="color:#9ca3af;">No robots</span>';
            return;
        }

        body.innerHTML = `<table style="width:100%;font-size:13px;border-collapse:collapse;">
            <thead><tr>
                <th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e5e7eb;">Name</th>
                <th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e5e7eb;">URL</th>
                <th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e5e7eb;">Runs</th>
                <th style="text-align:left;padding:6px 8px;border-bottom:1px solid #e5e7eb;">Last Run</th>
            </tr></thead>
            <tbody>${robots.map(r => `
                <tr>
                    <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;">${esc(r.name)}</td>
                    <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(r.origin_url)}">${esc(r.origin_url)}</td>
                    <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;">${r.run_count}</td>
                    <td style="padding:6px 8px;border-bottom:1px solid #f3f4f6;">${r.last_run_at ? new Date(r.last_run_at).toLocaleString() : '-'}</td>
                </tr>`).join('')}
            </tbody>
        </table>`;
    } catch (e) {
        body.innerHTML = '<span style="color:#dc2626;">Failed to load robots</span>';
    }
}

// ============ Invite Codes ============

async function generateCodes() {
    const count = parseInt(document.getElementById('codeCount').value) || 1;
    try {
        const resp = await authFetch(`${API_BASE}/admin/invite-codes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ count }),
        });
        if (resp && resp.ok) {
            loadInviteCodes();
        } else if (resp) {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Failed to generate codes');
        }
    } catch (e) {
        console.error('generateCodes error:', e);
    }
}

async function loadInviteCodes() {
    try {
        const resp = await authFetch(`${API_BASE}/admin/invite-codes`);
        if (!resp) return;
        const data = await resp.json();
        renderCodesTable(data.items || []);
    } catch (e) {
        console.error('Failed to load invite codes:', e);
    }
}

function renderCodesTable(codes) {
    const tbody = document.getElementById('codesTableBody');
    if (!codes.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#9ca3af;padding:24px;">No invite codes</td></tr>';
        return;
    }
    tbody.innerHTML = codes.map(c => {
        const used = !!c.used_by;
        const statusBadge = used
            ? `<span class="badge badge-muted">used by ${esc(c.used_by)}</span>`
            : '<span class="badge badge-success">available</span>';
        const usedAt = c.used_at ? new Date(c.used_at).toLocaleString() : '-';
        const created = c.created_at ? new Date(c.created_at).toLocaleString() : '-';
        return `
            <tr>
                <td>
                    <div class="code-display">
                        <span>${esc(c.code)}</span>
                        <button class="btn btn-sm btn-outline" onclick="copyCode('${esc(c.code)}')" title="Copy">📋</button>
                    </div>
                </td>
                <td>${created}</td>
                <td>${statusBadge}</td>
                <td>${usedAt}</td>
                <td>
                    ${used ? '' : `<button class="btn btn-sm btn-danger-outline" onclick="deleteCode('${esc(c.code)}')">Delete</button>`}
                </td>
            </tr>`;
    }).join('');
}

function copyCode(code) {
    navigator.clipboard.writeText(code).then(() => {
        // Brief visual feedback — could be a toast, but keep it simple
    }).catch(() => {
        // Fallback: select text from a temp input
        const input = document.createElement('input');
        input.value = code;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
    });
}

async function deleteCode(code) {
    if (!confirm(`Delete invite code ${code}?`)) return;
    try {
        const resp = await authFetch(`${API_BASE}/admin/invite-codes/${code}`, { method: 'DELETE' });
        if (resp && resp.ok) loadInviteCodes();
        else if (resp) {
            const err = await resp.json().catch(() => ({}));
            alert(err.detail || 'Failed to delete code');
        }
    } catch (e) {
        console.error('deleteCode error:', e);
    }
}

// ============ Activity Logs ============

let _logsPage = 1;
const _logsPageSize = 20;

async function loadActivityLogs(page) {
    _logsPage = page || 1;

    const action = document.getElementById('filterAction').value;
    const status = document.getElementById('filterStatus').value;

    let url = `${API_BASE}/admin/activity-logs?page=${_logsPage}&page_size=${_logsPageSize}`;
    if (action) url += `&action=${encodeURIComponent(action)}`;
    if (status) url += `&status=${encodeURIComponent(status)}`;

    try {
        const resp = await authFetch(url);
        if (!resp) return;
        const data = await resp.json();
        renderLogsTable(data.items || []);
        renderLogsPagination(data.total || 0, data.page || 1, data.page_size || _logsPageSize);
    } catch (e) {
        console.error('Failed to load activity logs:', e);
    }
}

function renderLogsTable(items) {
    const tbody = document.getElementById('logsTableBody');
    if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#9ca3af;padding:24px;">No logs found</td></tr>';
        return;
    }
    tbody.innerHTML = items.map(item => {
        const time = item.created_at ? new Date(item.created_at).toLocaleString() : '';
        const statusBadge = item.status === 'success'
            ? '<span class="badge badge-success">success</span>'
            : '<span class="badge badge-danger">failed</span>';
        const target = item.target_url
            ? `<span title="${esc(item.target_url)}">${esc((item.target_url || '').substring(0, 40))}</span>`
            : (item.target_id ? item.target_id.slice(0, 8) : '-');
        let details = '';
        if (item.error_message) {
            details = `<span style="color:#dc2626;" title="${esc(item.error_message)}">${esc(item.error_message.substring(0, 40))}</span>`;
        } else if (item.details) {
            try {
                const d = typeof item.details === 'string' ? JSON.parse(item.details) : item.details;
                const parts = [];
                if (d.rows_extracted != null) parts.push(`${d.rows_extracted} rows`);
                if (d.pages_scraped != null) parts.push(`${d.pages_scraped} pages`);
                if (d.duration_seconds != null) parts.push(`${d.duration_seconds}s`);
                details = parts.join(', ') || '-';
            } catch {
                details = '-';
            }
        }
        return `
            <tr>
                <td>${time}</td>
                <td>${item.user_id ? item.user_id.slice(0, 8) : '-'}</td>
                <td>${formatAction(item.action)}</td>
                <td>${target}</td>
                <td>${statusBadge}</td>
                <td>${details || '-'}</td>
            </tr>`;
    }).join('');
}

function renderLogsPagination(total, page, pageSize) {
    const totalPages = Math.ceil(total / pageSize) || 1;
    const el = document.getElementById('logsPagination');
    el.innerHTML = `
        <button ${page <= 1 ? 'disabled' : ''} onclick="loadActivityLogs(${page - 1})">Prev</button>
        <span>Page ${page} / ${totalPages} (${total} total)</span>
        <button ${page >= totalPages ? 'disabled' : ''} onclick="loadActivityLogs(${page + 1})">Next</button>
    `;
}

// ============ Helpers ============

function formatAction(action) {
    const map = {
        user_register: '🆕 Register',
        user_login: '🔑 Login',
        user_login_failed: '🚫 Login Failed',
        robot_create: '🤖 Create Robot',
        robot_update: '✏️ Update Robot',
        robot_delete: '🗑️ Delete Robot',
        robot_run_success: '✅ Run OK',
        robot_run_failed: '❌ Run Fail',
        schedule_create: '📅 Create Schedule',
        schedule_update: '📅 Update Schedule',
        schedule_delete: '📅 Delete Schedule',
        schedule_run_success: '✅ Sched OK',
        schedule_run_failed: '❌ Sched Fail',
    };
    return map[action] || action;
}

function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
