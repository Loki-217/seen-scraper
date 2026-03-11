// services/web/js/schedule-manager.js
/**
 * SeenFetch 调度管理器
 *
 * 功能：
 * - Robot 列表管理
 * - 定时任务配置
 * - 执行历史查看
 */

// API_BASE 已在 browser-canvas.js 中定义，这里不再重复声明

// ============ 状态 ============
let currentRobots = [];
let currentSchedules = [];
let selectedRobot = null;

// ============ Robot 管理 ============

async function loadRobots() {
    try {
        const response = await fetch(`${API_BASE}/robots`);
        const data = await response.json();
        currentRobots = data.items || [];
        renderRobotList();
    } catch (error) {
        console.error('加载 Robot 列表失败:', error);
        showToast('加载失败: ' + error.message, 'error');
    }
}

function renderRobotList() {
    const container = document.getElementById('robotList');
    if (!container) return;

    if (currentRobots.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无 Robot</p>
                <p class="text-muted">使用智能识别创建你的第一个 Robot</p>
            </div>
        `;
        return;
    }

    container.innerHTML = currentRobots.map(robot => `
        <div class="robot-card" data-id="${robot.id}" onclick="selectRobot('${robot.id}')">
            <div class="robot-header">
                <span class="robot-name">${robot.name}</span>
                <span class="robot-stats">${robot.run_count} 次执行</span>
            </div>
            <div class="robot-url">${robot.origin_url}</div>
            <div class="robot-meta">
                <span>${robot.fields?.length || 0} 个字段</span>
                ${robot.last_run_at ? `<span>上次: ${formatTime(robot.last_run_at)}</span>` : ''}
            </div>
            <div class="robot-actions">
                <button class="btn-sm btn-primary" onclick="event.stopPropagation(); runRobot('${robot.id}')">执行</button>
                <button class="btn-sm btn-secondary" onclick="event.stopPropagation(); showScheduleDialog('${robot.id}')">定时</button>
                <button class="btn-sm btn-danger" onclick="event.stopPropagation(); deleteRobot('${robot.id}')">删除</button>
            </div>
        </div>
    `).join('');
}

async function selectRobot(robotId) {
    selectedRobot = currentRobots.find(r => r.id === robotId);

    // 更新选中状态
    document.querySelectorAll('.robot-card').forEach(card => {
        card.classList.toggle('selected', card.dataset.id === robotId);
    });

    // 加载该 Robot 的调度
    await loadSchedulesForRobot(robotId);
}

async function runRobot(robotId) {
    showToast('正在执行 Robot...');

    try {
        const response = await fetch(`${API_BASE}/robots/${robotId}/run`, {
            method: 'POST'
        });
        const result = await response.json();

        if (result.success) {
            showToast(`执行成功！提取 ${result.items_extracted} 条数据`);
            loadRobots(); // 刷新列表
        } else {
            showToast('执行失败: ' + result.error, 'error');
        }
    } catch (error) {
        showToast('执行失败: ' + error.message, 'error');
    }
}

async function deleteRobot(robotId) {
    if (!confirm('确定删除此 Robot？相关的定时任务也会被删除。')) {
        return;
    }

    try {
        await fetch(`${API_BASE}/robots/${robotId}`, { method: 'DELETE' });
        showToast('Robot 已删除');
        loadRobots();
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
}

// ============ 保存 Robot ============

async function saveAsRobot(name, config) {
    /**
     * 将当前配置保存为 Robot
     *
     * @param {string} name - Robot 名称
     * @param {object} config - 配置 {origin_url, item_selector, fields, pagination}
     */
    try {
        const response = await fetch(`${API_BASE}/robots`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                description: '',
                origin_url: config.origin_url,
                actions: config.actions || [],
                item_selector: config.item_selector,
                fields: config.fields || [],
                pagination: config.pagination || null
            })
        });

        if (!response.ok) {
            throw new Error('保存失败');
        }

        const robot = await response.json();
        showToast(`Robot "${name}" 已保存`);
        loadRobots();
        return robot;
    } catch (error) {
        showToast('保存失败: ' + error.message, 'error');
        return null;
    }
}

// ============ Schedule 管理 ============

async function loadSchedules() {
    try {
        const response = await fetch(`${API_BASE}/schedules`);
        const data = await response.json();
        currentSchedules = data.items || [];
        renderScheduleList();
    } catch (error) {
        console.error('加载调度列表失败:', error);
    }
}

async function loadSchedulesForRobot(robotId) {
    try {
        const response = await fetch(`${API_BASE}/schedules?robot_id=${robotId}`);
        const data = await response.json();
        renderScheduleList(data.items || []);
    } catch (error) {
        console.error('加载调度失败:', error);
    }
}

function renderScheduleList(schedules = currentSchedules) {
    const container = document.getElementById('scheduleList');
    if (!container) return;

    if (schedules.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>暂无定时任务</p>
            </div>
        `;
        return;
    }

    container.innerHTML = schedules.map(schedule => `
        <div class="schedule-card ${schedule.enabled ? '' : 'disabled'}">
            <div class="schedule-header">
                <span class="schedule-status">${schedule.enabled ? '✅' : '⏸️'}</span>
                <span class="schedule-name">${schedule.name}</span>
            </div>
            <div class="schedule-info">
                <span>频率: ${formatFrequency(schedule.frequency)}</span>
                ${schedule.execute_at ? `<span>${schedule.execute_at}</span>` : ''}
            </div>
            <div class="schedule-meta">
                ${schedule.next_run_at ? `<span>下次: ${formatTime(schedule.next_run_at)}</span>` : ''}
                ${schedule.last_run_status ? `<span class="status-${schedule.last_run_status}">${formatStatus(schedule.last_run_status)}</span>` : ''}
            </div>
            <div class="schedule-actions">
                <button class="btn-sm btn-primary" onclick="runScheduleNow('${schedule.id}')">立即执行</button>
                <button class="btn-sm btn-secondary" onclick="toggleSchedule('${schedule.id}', ${!schedule.enabled})">${schedule.enabled ? '暂停' : '启用'}</button>
                <button class="btn-sm" onclick="showRunHistory('${schedule.id}')">历史</button>
                <button class="btn-sm btn-danger" onclick="deleteSchedule('${schedule.id}')">删除</button>
            </div>
        </div>
    `).join('');
}

function showScheduleDialog(robotId) {
    const robot = currentRobots.find(r => r.id === robotId);
    if (!robot) return;

    const dialog = document.getElementById('scheduleDialog');
    if (!dialog) {
        createScheduleDialog();
    }

    // 填充表单
    document.getElementById('scheduleRobotId').value = robotId;
    document.getElementById('scheduleRobotName').textContent = robot.name;
    document.getElementById('scheduleName').value = `${robot.name} 定时任务`;

    document.getElementById('scheduleDialog').style.display = 'flex';
}

function createScheduleDialog() {
    const dialog = document.createElement('div');
    dialog.id = 'scheduleDialog';
    dialog.className = 'dialog-overlay';
    dialog.innerHTML = `
        <div class="dialog">
            <div class="dialog-header">
                <h3>设置定时任务</h3>
                <button class="dialog-close" onclick="closeScheduleDialog()">&times;</button>
            </div>
            <div class="dialog-body">
                <input type="hidden" id="scheduleRobotId">
                <p>Robot: <strong id="scheduleRobotName"></strong></p>

                <div class="form-group">
                    <label>任务名称</label>
                    <input type="text" id="scheduleName" placeholder="输入任务名称">
                </div>

                <div class="form-group">
                    <label>执行频率</label>
                    <select id="scheduleFrequency">
                        <option value="once">仅执行一次</option>
                        <option value="15min">每15分钟</option>
                        <option value="hourly">每小时</option>
                        <option value="daily" selected>每天</option>
                        <option value="weekly">每周</option>
                        <option value="monthly">每月</option>
                        <option value="custom">自定义 (Cron)</option>
                    </select>
                </div>

                <div class="form-group" id="executeAtGroup">
                    <label>执行时间</label>
                    <input type="time" id="scheduleExecuteAt" value="08:00">
                </div>

                <div class="form-group" id="cronGroup" style="display: none;">
                    <label>Cron 表达式</label>
                    <input type="text" id="scheduleCron" placeholder="0 8 * * *">
                </div>

                <div class="form-group">
                    <label>时区</label>
                    <select id="scheduleTimezone">
                        <option value="Asia/Shanghai">亚洲/上海</option>
                        <option value="Asia/Tokyo">亚洲/东京</option>
                        <option value="UTC">UTC</option>
                    </select>
                </div>
            </div>
            <div class="dialog-footer">
                <button class="btn btn-secondary" onclick="closeScheduleDialog()">取消</button>
                <button class="btn btn-primary" onclick="saveSchedule()">保存并启用</button>
            </div>
        </div>
    `;
    document.body.appendChild(dialog);

    // 频率变化时显示/隐藏相关字段
    document.getElementById('scheduleFrequency').addEventListener('change', function() {
        const freq = this.value;
        document.getElementById('executeAtGroup').style.display =
            ['daily', 'weekly', 'monthly'].includes(freq) ? 'block' : 'none';
        document.getElementById('cronGroup').style.display =
            freq === 'custom' ? 'block' : 'none';
    });
}

function closeScheduleDialog() {
    document.getElementById('scheduleDialog').style.display = 'none';
}

async function saveSchedule() {
    const robotId = document.getElementById('scheduleRobotId').value;
    const name = document.getElementById('scheduleName').value;
    const frequency = document.getElementById('scheduleFrequency').value;
    const executeAt = document.getElementById('scheduleExecuteAt').value;
    const cronExpression = document.getElementById('scheduleCron')?.value;
    const timezone = document.getElementById('scheduleTimezone').value;

    if (!name) {
        showToast('请输入任务名称', 'error');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/schedules`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                robot_id: robotId,
                name: name,
                frequency: frequency,
                cron_expression: frequency === 'custom' ? cronExpression : null,
                execute_at: executeAt,
                timezone: timezone,
                enabled: true
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '创建失败');
        }

        showToast('定时任务已创建');
        closeScheduleDialog();
        loadSchedules();
    } catch (error) {
        showToast('创建失败: ' + error.message, 'error');
    }
}

async function runScheduleNow(scheduleId) {
    showToast('正在执行...');

    try {
        const response = await fetch(`${API_BASE}/schedules/${scheduleId}/run`, {
            method: 'POST'
        });
        const result = await response.json();

        if (result.ok) {
            showToast('执行已开始');
        } else {
            showToast('执行失败', 'error');
        }
    } catch (error) {
        showToast('执行失败: ' + error.message, 'error');
    }
}

async function toggleSchedule(scheduleId, enabled) {
    try {
        await fetch(`${API_BASE}/schedules/${scheduleId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: enabled })
        });

        showToast(enabled ? '已启用' : '已暂停');
        loadSchedules();
    } catch (error) {
        showToast('操作失败: ' + error.message, 'error');
    }
}

async function deleteSchedule(scheduleId) {
    if (!confirm('确定删除此定时任务？')) return;

    try {
        await fetch(`${API_BASE}/schedules/${scheduleId}`, { method: 'DELETE' });
        showToast('定时任务已删除');
        loadSchedules();
    } catch (error) {
        showToast('删除失败: ' + error.message, 'error');
    }
}

async function showRunHistory(scheduleId) {
    try {
        const response = await fetch(`${API_BASE}/schedules/${scheduleId}/runs?limit=10`);
        const data = await response.json();

        const runs = data.items || [];

        let html = '<div class="run-history">';
        if (runs.length === 0) {
            html += '<p class="empty-state">暂无执行记录</p>';
        } else {
            html += runs.map(run => `
                <div class="run-item status-${run.status}">
                    <span class="run-status">${formatStatus(run.status)}</span>
                    <span class="run-time">${formatTime(run.started_at)}</span>
                    <span class="run-stats">${run.pages_scraped}页/${run.items_extracted}条</span>
                    <span class="run-duration">${run.duration_seconds?.toFixed(1) || '-'}秒</span>
                    ${run.result_file ? `<button class="btn-sm" onclick="downloadResult('${run.id}')">下载</button>` : ''}
                </div>
            `).join('');
        }
        html += '</div>';

        // 显示弹窗
        showModal('执行历史', html);
    } catch (error) {
        showToast('加载失败: ' + error.message, 'error');
    }
}

async function downloadResult(runId) {
    try {
        const response = await fetch(`${API_BASE}/runs/${runId}/result`);
        const data = await response.json();

        // 下载为 JSON 文件
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `result_${runId}.json`;
        a.click();
        URL.revokeObjectURL(url);
    } catch (error) {
        showToast('下载失败: ' + error.message, 'error');
    }
}

// ============ 辅助函数 ============

function formatFrequency(freq) {
    const map = {
        'once': '一次性',
        '15min': '每15分钟',
        'hourly': '每小时',
        'daily': '每天',
        'weekly': '每周',
        'monthly': '每月',
        'custom': '自定义'
    };
    return map[freq] || freq;
}

function formatStatus(status) {
    const map = {
        'pending': '等待中',
        'running': '执行中',
        'succeeded': '成功',
        'failed': '失败',
        'cancelled': '已取消'
    };
    return map[status] || status;
}

function formatTime(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function showModal(title, content) {
    let modal = document.getElementById('simpleModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'simpleModal';
        modal.className = 'dialog-overlay';
        modal.innerHTML = `
            <div class="dialog">
                <div class="dialog-header">
                    <h3 id="modalTitle"></h3>
                    <button class="dialog-close" onclick="closeModal()">&times;</button>
                </div>
                <div class="dialog-body" id="modalContent"></div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalContent').innerHTML = content;
    modal.style.display = 'flex';
}

function closeModal() {
    const modal = document.getElementById('simpleModal');
    if (modal) modal.style.display = 'none';
}

function showToast(message, type = 'info') {
    // 使用现有的 toast 函数或创建简单提示
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        console.log(`[${type}] ${message}`);
        alert(message);
    }
}

// ============ 初始化 ============

document.addEventListener('DOMContentLoaded', function() {
    // 如果页面有 Robot/Schedule 容器，则加载数据
    if (document.getElementById('robotList')) {
        loadRobots();
    }
    if (document.getElementById('scheduleList')) {
        loadSchedules();
    }
});

// 导出函数供外部调用
window.ScheduleManager = {
    loadRobots,
    loadSchedules,
    saveAsRobot,
    showScheduleDialog,
    runRobot,
    deleteRobot
};
