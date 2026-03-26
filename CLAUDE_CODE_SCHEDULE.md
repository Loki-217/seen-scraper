# 定时调度功能：Monitor Tab + History Tab

> 完整指令，发给 Claude Code 执行

---

## ⚠️ 范围说明                                                  


**本任务是纯新增功能**，主要改动在 robot.html 前端 + scheduler.py 后端小修。

不动的：studio.html、studio.js、browser-canvas.js、session_manager.py（capture 流程）、robot_executor.py（执行逻辑）

---

## 背景：后端已就绪

以下后端代码 **已经存在且可用**，前端直接调 API 即可：

- **Schedule CRUD**: POST/GET/PUT/DELETE `/schedules` + `/schedules/{id}`
- **手动触发**: POST `/schedules/{id}/run`
- **执行历史**: GET `/schedules/{id}/runs`
- **单次运行详情**: GET `/runs/{run_id}` + GET `/runs/{run_id}/result` + GET `/runs/{run_id}/download`
- **Scheduler 核心**: `scheduler.py`，asyncio 轮询（60秒间隔），lifespan 中已 start/stop
- **数据模型**: ScheduleDB（15列）、ScheduledRunDB（13列）、完整的 Pydantic 请求/响应模型

**需要后端修的只有两处**：
1. 安装 croniter（`pip install croniter`）— 当前 CUSTOM cron 模式 fallback 到每天
2. Scheduler 的 retry 逻辑 — ScheduleDB 有 retry_count/retry_delay_seconds 字段但未实现

---

## 改动一：robot.html — 激活 Tab 系统

### 当前状态
- Tab 栏有 "Quick Setup"（active）和 "Monitor"（Coming soon，禁用）
- 没有 History tab

### 改造为

Tab 栏改为三个可切换的 tab：
```
Quick Setup | Monitor | History
```

- 去掉 "Coming soon" 标记
- 所有 tab 可点击切换
- Quick Setup 内容保持不变（现有的 robot name + 结果展示 + Run Task/Delete）
- Monitor 和 History 的内容区域各自独立

**Tab 切换逻辑**：点击 tab 切换对应内容区域的显示/隐藏（display:none/block），不跳页面。

---

## 改动二：Monitor Tab — 完整 UI

### 2.1 页面结构

```
Monitor Tab 内容区:
├── 标题 "Monitors List" + "+ Create New Monitor" 按钮（右上角）
├── 空状态提示（无 monitor 时显示）
│   "No monitors configured. Add a monitor to automatically run this robot on a schedule."
├── Monitor 列表（有 monitor 时显示）
│   └── Monitor 卡片 ×N
└── 创建/编辑表单（点击按钮或编辑时展开，内联在列表上方）
```

### 2.2 Monitor 卡片

每个 monitor 显示为一张卡片，布局参考 Browse.ai：

```
[🕐 图标] Monitor 名称    [✏️编辑] [⏸暂停] [🗑删除]    Last check: 5 days ago
    ✅ origin URL                                        Next check: in 2 hours
    Every week at around 10:00 (Asia/Shanghai)
```

**左侧**：
- 时钟图标 + monitor 名称
- 启用状态指示（绿色勾 = enabled，灰色 = paused）
- Origin URL（灰色小字，来自 robot 的 origin_url）
- 频率描述文字（人类可读格式，见下方规则）

**右侧**：
- 操作按钮：编辑（展开表单）、暂停/恢复（toggle enabled）、删除（确认弹窗）
- "Last check: {时间}"（来自 last_run_at）
- "Next check: {时间}"（来自 next_run_at）

**频率描述文字生成规则**：
- HOURLY: "Every {N} hour(s) on {星期几列表} between {start}-{end} ({timezone})"
- DAILY: "Every {N} day(s) at around {time} ({timezone})"
- WEEKLY: "Every {N} week(s) starting {weekday} at around {time} ({timezone})"
- MONTHLY: "Every {N} month(s) on day {date} at around {time} ({timezone})"

时间用 relative time 显示（"5 days ago", "in 2 hours"），可以用简单的 JS 函数计算。

### 2.3 创建/编辑表单 — 动态字段切换

表单标题："Add new monitor"（创建）/ "Edit monitor"（编辑）

**固定字段**（始终显示）：
- "Run once every" [数字输入框, 默认1] [频率下拉: 15 Minutes/Hour/Day/Week/Month]
  - 选 "15 Minutes" 时隐藏数字输入框
- "Monitor name" [文本输入框, 默认 "Default monitor"]
- "Origin URL" [只读文本, 显示 robot 的 origin_url]
- ☑ "Notify me by email if there is a change in a captured text" [disabled 复选框, 灰色, 旁边标注 "Coming soon"]
- Cancel / Save 按钮

**动态字段**（根据频率下拉切换）：

#### 选 Minute：
```
Run once every    [15 Minutes ▼]   ← 固定选项，不是自由输入
On   Monday  Tuesday  Wednesday  Thursday  Friday  Saturday  Sunday   Select All
Between  ☑ Anytime   [--:--]  And  [--:--]   [Asia/Shanghai ▼]
```
- **Minute 模式固定为每 15 分钟**，对应后端枚举 `15MIN`。不显示数字输入框，频率下拉直接显示 "15 Minutes" 作为一个整体选项
- 频率下拉完整选项列表：`15 Minutes | Hour | Day | Week | Month`
- 选中 "15 Minutes" 时隐藏 "Run once every [N]" 的数字输入框（因为间隔固定）
- "On": 星期几多选按钮（toggle 选中/取消）
- "Between": 勾选 Anytime 则禁用时间输入；取消勾选则需输入起止时间
- 时区下拉

#### 选 Hour：
```
Run once every [1] [Hour ▼]
On   Monday  Tuesday  Wednesday  Thursday  Friday  Saturday  Sunday   Select All
Between  ☑ Anytime   [--:--]  And  [--:--]   [Asia/Shanghai ▼]
```
（与 Minute 完全相同）

#### 选 Day：
```
Run once every [1] [Day ▼]
On   Monday  Tuesday  Wednesday  Thursday  Friday  Saturday  Sunday   Select All
At around  ☑ Anytime   [--:--]   [Asia/Shanghai ▼]
```
- "Between" 变成 "At around"（单个时间点，不是范围）
- Anytime 勾选则不指定时间

#### 选 Week：
```
Run once every [1] [Week ▼]
Start from  [Tuesday (Today) ▼]
At around  [10:00 🕐]   [Asia/Shanghai ▼]
```
- "On" 和 "Anytime" 消失，换成 "Start from" 下拉 + "At around" 必须指定时间
- **"Start from" 下拉内容是未来 7 天的实际日期**，不是纯星期几名称。格式：
  - `Tuesday (Today)` ← 今天
  - `Wednesday (March 25, 2026)`
  - `Thursday (March 26, 2026)`
  - `Friday (March 27, 2026)`
  - `Saturday (March 28, 2026)`
  - `Sunday (March 29, 2026)`
  - `Monday (March 30, 2026)`
- 用 JS 动态生成这 7 个选项，第一个标注 "(Today)"，其余显示完整日期
- 选中的值映射到星期几（用于 cron）+ 具体日期（用于 execute_at / first run）

#### 选 Month：
```
Run once every [1] [Month ▼]
Start from  [Tuesday (Today) ▼]
At around  [10:00 🕐]   [Asia/Shanghai ▼]
```
- **与 Week 完全相同的 UI 布局**："Start from" 下拉（未来 7 天）+ "At around" 时间 + 时区
- 差别仅在于提交时 frequency 为 MONTHLY，后端按月计算 next_run_at

### 2.4 表单 → API 请求的字段映射

表单提交时，将 UI 状态转换为 API 需要的 CreateScheduleRequest：

```javascript
{
    robot_id: currentRobotId,           // 从页面 URL 获取
    name: monitorNameInput.value,
    frequency: frequencySelect.value,    // '15MIN'|'HOURLY'|'DAILY'|'WEEKLY'|'MONTHLY'
    cron_expression: buildCronExpression(), // 见下方
    timezone: timezoneSelect.value,      // 'Asia/Shanghai'
    execute_at: timeInput.value || null, // 'HH:MM' 或 null (Anytime)
    enabled: true,
    retry_count: 3,                      // 默认值
    retry_delay_seconds: 60              // 默认值
}
```

**buildCronExpression() 逻辑**：

根据频率和用户选择生成 cron 表达式。这个函数是前端最复杂的部分：

```
15 Minutes: 固定每 15 分钟 → frequency='15MIN'
    - Anytime: "*/15 * * * {weekdays}"
    - 有时间范围: "*/15 {start_hour}-{end_hour} * * {weekdays}"

Hour: 每 N 小时 → 类似 minute
    - "0 */N * * {weekdays}"（每 N 小时的整点）
    - 有时间范围: "0 */N * * {weekdays}"（配合 Between 约束）

Day: 每 N 天
    - 有具体时间: "0 {hour} */{N} * *"
    - Anytime: "0 0 */{N} * *"（默认 00:00）

Week: 每 N 周
    - "Start from" 选择的日期决定每周哪天执行（取该日期的 weekday）
    - "0 {hour} * * {weekday}"（每周某天某时）
    - 例：Start from Wednesday → weekday=3 → "0 10 * * 3"
    - N>1 的情况需要用 execute_at + 后端 interval 控制

Month: 每 N 月
    - "Start from" 选择的日期决定每月哪天执行（取该日期的 day of month）
    - "0 {hour} {day_of_month} */{N} *"
    - 例：Start from March 25 → day=25 → "0 10 25 */1 *"（每月 25 号 10:00）
```

⚠️ **注意**：cron 表达式不完美支持所有组合（比如"每 2 周"），但 ScheduleDB 有 frequency 字段可以辅助后端计算 next_run_at。重要的是 cron_expression 尽量表达用户意图，后端 Scheduler 可以综合 frequency + cron_expression + execute_at 来决定实际执行时间。

**星期几编码**：Monday=1, ..., Sunday=0（cron 标准）。多选时用逗号分隔："1,2,3,4,5"

### 2.5 时区下拉

**使用完整 IANA 时区数据库**（Browse.ai 用的就是全量列表）：

```javascript
// 获取完整时区列表
const timezones = Intl.supportedValuesOf('timeZone');
// 如果浏览器不支持 supportedValuesOf，fallback 到一个预定义的完整列表
```

- 下拉选项格式：`Asia/Shanghai`（纯 IANA 名称）
- 当前用户时区标注 "(Your timezone)"：用 `Intl.DateTimeFormat().resolvedOptions().timeZone` 获取
- 默认选中用户当前时区
- 列表较长，下拉框需要可滚动（`max-height` + `overflow-y: auto`）

### 2.6 表单交互细节

- "Select All" / "Deselect All" 切换所有星期几按钮
- 频率下拉切换时，动态显示/隐藏对应字段组，带简单过渡动画
- Save 时前端校验：频率 ≥ 1，Week/Month 模式必须选时间，Monitor 名称非空
- Save 成功 → 关闭表单，刷新列表
- Cancel → 关闭表单
- "Notify me by email" 复选框：始终 disabled，灰色显示，旁边小字 "Coming soon"

### 2.7 编辑时反向填充表单

编辑 monitor 时需要从 API 响应的 ScheduleResponse 中恢复表单状态。

**⚠️ 先执行侦察步骤**：在实现编辑功能之前，先读取以下文件，确认 API 响应里除了 `cron_expression` 之外是否有辅助字段（如 weekdays JSON、原始配置 JSON 等）：
- `app/models_v2/schedule.py` — ScheduleResponse 的完整字段列表
- `app/routers/schedules.py` — GET `/schedules/{id}` 返回的数据结构

**根据侦察结果选择方案**：
- **如果有辅助字段**（如 execute_at、额外 JSON 字段存了星期几和时间范围）：直接读辅助字段填充表单
- **如果只有 cron_expression + frequency + execute_at + timezone**：写一个 `parseCronForEdit(cron, frequency)` 函数，从 cron 表达式中反向提取星期几列表和时间信息：
  ```
  cron 格式: "分 时 日 月 星期"
  - 星期字段: "1,2,3,4,5" → 勾选 Mon-Fri
  - 时字段: "8-18" → Between 08:00 - 18:00
  - 时字段: "*" → Anytime
  - 分字段: "*/15" → 15 Minutes 模式
  - 日字段: "25" → Month 模式 Start from 某日
  ```
  这个解析不需要完美覆盖所有 cron 格式，只需要能解析 buildCronExpression() 生成的那几种格式即可（自己生成的自己能解析）。

---

## 改动三：History Tab — 执行历史

### 3.1 页面结构

```
History Tab 内容区:
├── 标题 "Execution History"
├── 空状态提示（无记录时）
│   "No execution history yet. Run the task or set up a monitor to see results here."
└── 执行记录表格
    ├── 表头: Status | Trigger | Started | Duration | Pages | Items | Actions
    └── 行 ×N（按时间倒序）
```

### 3.2 表格列说明

| 列 | 内容 | 来源 |
|---|------|------|
| Status | 状态标签（✅ Succeeded / ❌ Failed / ⏳ Running / 🕐 Pending） | run.status |
| Trigger | 触发方式（"Scheduled" / "Manual"） | run.trigger_type |
| Started | 开始时间（格式化为本地时间） | run.started_at |
| Duration | 耗时（"12.3s"） | run.duration_seconds |
| Pages | 爬取页数 | run.pages_scraped |
| Items | 提取条数 | run.items_extracted |
| Actions | 📥 下载 CSV / 📄 查看 JSON | GET /runs/{id}/download, /runs/{id}/result |

### 3.3 数据获取

History tab 激活时，调用 GET `/schedules/{id}/runs` 获取该 robot 下所有 schedule 的执行记录。

⚠️ **问题**：当前 API 是按 schedule_id 查询（`/schedules/{schedule_id}/runs`），不是按 robot_id。如果一个 robot 有多个 schedule（虽然少见），需要先获取该 robot 的所有 schedule，再逐个拉取 runs。

**简化方案**：先获取该 robot 的 schedules（GET `/schedules?robot_id={id}`），然后对每个 schedule 调 `/schedules/{schedule_id}/runs`，合并结果按 started_at 倒序。

### 3.4 Manual Run 也写入历史

**当前问题**：POST `/robots/{id}/run` 直接执行，不写 scheduled_runs 表。这导致手动执行不出现在 History 中。

**修复**（robots.py 的 run endpoint）：手动执行后，创建一条 ScheduledRunDB 记录，trigger_type 设为 "manual"，关联到该 robot 的第一个 schedule（如果有），或者创建一条无 schedule_id 的记录。

⚠️ 这涉及后端改动。如果 ScheduledRunDB 的 schedule_id 是必填外键，则需要先确认是否可以传 null。如果不行，有两个方案：
- A：手动执行时不写 scheduled_runs，History 只显示定时执行的记录（MVP 可接受）
- B：修改 ScheduledRunDB，让 schedule_id 可以为 null

**选方案 A**，最小改动。History tab 标注 "Showing scheduled execution history. Manual runs are displayed in Quick Setup tab."

---

## 改动四：后端 — 安装 croniter

在项目根目录或 services/api 下执行：
```bash
pip install croniter
```

确认 scheduler.py 中 croniter 的 import 不再 fallback：
```python
from croniter import croniter  # 应该已有 try/except，确保不再走 fallback
```

---

## 改动五：后端 — Scheduler retry 逻辑

**位置**：scheduler.py 的执行任务方法（大概是 `_execute_robot` 或 `_run_schedule`）

**当前行为**：执行失败直接标记 FAILED

**改为**：
```python
async def _execute_schedule(self, schedule):
    max_retries = schedule.retry_count or 0
    delay = schedule.retry_delay_seconds or 60

    for attempt in range(max_retries + 1):
        try:
            result = await executor.execute()
            # 成功 → 记录 SUCCEEDED → break
            run.status = RunStatus.SUCCEEDED
            break
        except Exception as e:
            if attempt < max_retries:
                run.retry_attempt = attempt + 1
                await asyncio.sleep(delay)
                continue
            else:
                # 最终失败 → 记录 FAILED
                run.status = RunStatus.FAILED
                run.error_message = str(e)
```

ScheduledRunDB 已有 `retry_attempt` 列，记录当前是第几次重试。

---

## 改动六：样式

Monitor tab 和 History tab 的样式与现有 robot.html 的白色/浅灰主题保持一致。

**参考 Browse.ai 截图的视觉风格**：
- 表单卡片：白底、浅灰边框、圆角
- 星期几按钮：选中时蓝色文字（或主题色），未选中灰色
- "Select All" / "Deselect All" 链接样式（蓝色文字）
- Save 按钮：主题色（紫色/蓝色实心）
- Cancel：灰色文字按钮
- Monitor 卡片：类似列表项，hover 时微浮起
- 状态标签：成功绿色、失败红色、运行中蓝色
- 时间输入框用 `<input type="time">`

---

## 验证清单

### Monitor Tab
1. Tab 切换正常：Quick Setup / Monitor / History 三个 tab 点击切换
2. 空状态：无 monitor 时显示提示文字
3. 创建 monitor：点击 "+ Create New Monitor" → 表单展开
4. 频率切换：依次选 Minute/Hour/Day/Week/Month → 对应字段组正确显示/隐藏
5. 星期几多选：点击 toggle，Select All / Deselect All 工作
6. Anytime 切换：勾选禁用时间输入，取消勾选启用
7. Save：提交到 POST `/schedules` → 成功 → 列表刷新，新卡片出现
8. 卡片信息：名称、URL、频率描述、last/next check 正确显示
9. 编辑：点编辑 → 表单展开并预填 → 修改 → Save → PUT `/schedules/{id}`
10. 暂停/恢复：点暂停 → enabled 变 false → 卡片状态变灰 → 再点恢复
11. 删除：点删除 → 确认弹窗 → DELETE `/schedules/{id}` → 卡片消失

### History Tab
12. 无记录时显示空状态
13. 有定时执行记录时表格正确展示
14. CSV 下载：点击 📥 → GET `/runs/{id}/download` → 文件下载
15. JSON 查看：点击 📄 → GET `/runs/{id}/result` → 展示或新窗口打开

### 后端
16. croniter 安装成功，CUSTOM cron 不再 fallback
17. 创建一个 HOURLY schedule → 等待 Scheduler 轮询 → 确认 next_run_at 正确计算
18. 模拟执行失败 → 确认 retry 逻辑工作（重试 N 次后最终 FAILED）

### 不受影响
19. Quick Setup tab 的所有功能不变（Run Task、结果展示、Delete Robot）
20. Studio 页面（capture 流程）不受影响

---

## 文件改动预期

| 文件 | 改动类型 | 内容 |
|------|---------|------|
| robot.html | 大改 | 三 tab 切换、Monitor tab 完整 UI（表单+列表）、History tab（表格） |
| robot.html 内联 JS 或新建 robot.js | 新增 | Monitor CRUD 逻辑、动态表单切换、cron 表达式生成、API 调用、History 数据加载 |
| robot.html 内联 CSS 或新建 robot.css | 新增 | Monitor 表单样式、卡片样式、History 表格样式 |
| scheduler.py | 小改 | retry loop 实现 |
| requirements.txt 或手动安装 | 小改 | 添加 croniter |
| robots.py | 不改（方案 A）| 手动执行不写历史表 |
| studio.html / studio.js / browser-canvas.js | 不改 | |
| robot_executor.py | 不改 | |
