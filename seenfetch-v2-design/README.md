# SeenFetch V2 快速参考指南

## 文档清单

| 文档 | 用途 | 位置 |
|-----|------|-----|
| ARCHITECTURE.md | 整体架构设计 | 本目录 |
| CLAUDE_CODE_SYSTEM_PROMPT.md | 项目级系统提示词 | 本目录 |
| prompts/P0_PAGINATION.md | 翻页功能开发提示词 | prompts/ |
| prompts/P1_SMART_DETECTION.md | 智能识别开发提示词 | prompts/ |
| prompts/P2_SCHEDULER.md | 定时任务开发提示词 | prompts/ |
| prompts/P3_MONITORING.md | 数据监控开发提示词 | prompts/ |

---

## 开发优先级

```
P0 翻页抓取 ──────────────────────────────────┐
  ├─ Session Manager                          │ 2-3周
  ├─ 前端 Canvas 化                           │
  └─ 翻页检测与执行                           │
                                              │
P1 智能识别增强 ──────────────────────────────┤
  ├─ 列表检测器                               │ 1-2周
  ├─ 字段类型推断                             │
  └─ 选择器优化                               │
                                              │
P2 定时任务 ──────────────────────────────────┤
  ├─ 调度器                                   │ 1-2周
  ├─ Robot 执行器                             │
  └─ 调度 API                                 │
                                              │
P3 数据变化监控 ──────────────────────────────┘
  ├─ 变化检测器                                 1周
  ├─ 快照存储
  └─ 变化通知

总计预估：6-8周
```

---

## Claude Code 使用方法

### 1. 设置项目级提示词

将 `CLAUDE_CODE_SYSTEM_PROMPT.md` 的内容添加到 Claude Code 的项目配置中。

### 2. 开发单个功能

打开对应的 prompts 文件，按顺序使用里面的 Prompt。

**示例：开发翻页功能**

```
1. 打开 prompts/P0_PAGINATION.md
2. 复制 "Prompt 1: Session Manager 基础实现"
3. 粘贴到 Claude Code 对话中
4. 等待 Claude 生成代码
5. 测试代码
6. 继续下一个 Prompt
```

### 3. 调试时使用

遇到问题时，可以把错误信息和相关代码一起发给 Claude，并说明：

```
我在开发 SeenFetch 的 Session Manager。
执行时遇到这个错误：[错误信息]
相关代码：[代码]
请帮我分析问题并修复。
```

---

## 核心架构速览

```
┌─────────────────────────────────────────────────────────┐
│                    用户浏览器                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Canvas 显示截图 + 可点击区域覆盖层               │   │
│  └─────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    FastAPI 后端                          │
│  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐ │
│  │Session Manager│  │Robot Executor │  │  Scheduler  │ │
│  │ (Playwright   │  │ (执行Robot    │  │ (定时触发)  │ │
│  │  会话池)      │  │  抓取数据)    │  │             │ │
│  └───────────────┘  └───────────────┘  └─────────────┘ │
│                            │                            │
│                            ▼                            │
│  ┌─────────────────────────────────────────────────┐   │
│  │              Playwright Browser                  │   │
│  │  - 加载目标网页                                  │   │
│  │  - 执行点击/滚动/输入                           │   │
│  │  - 返回截图和DOM信息                            │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**关键点**：
- 前端不显示目标网页的 HTML
- 前端显示的是后端生成的截图
- 所有交互在后端 Playwright 中执行
- 这样完全绕过 CORS/CSP 问题

---

## API 端点速览

### Session（训练模式）
```
POST   /sessions                    创建会话
POST   /sessions/{id}/actions       执行操作
GET    /sessions/{id}/state         获取状态
DELETE /sessions/{id}               关闭会话
```

### Robot（保存的配置）
```
GET    /robots                      列表
POST   /robots                      创建
GET    /robots/{id}                 详情
PUT    /robots/{id}                 更新
DELETE /robots/{id}                 删除
POST   /robots/{id}/run             立即执行
```

### Schedule（定时任务）
```
GET    /schedules                   列表
POST   /schedules                   创建
GET    /schedules/{id}              详情
PUT    /schedules/{id}              更新
DELETE /schedules/{id}              删除
POST   /schedules/{id}/run          手动触发
GET    /schedules/{id}/runs         执行历史
```

### Smart（智能识别）
```
POST   /api/smart/analyze           分析页面结构
POST   /api/smart/validate-selector 验证选择器
POST   /api/smart/suggest-name      建议字段名
```

---

## 常用命令

```bash
# 启动后端
cd services/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端
cd services/web
python -m http.server 3000

# 安装依赖
pip install playwright croniter
playwright install chromium

# 运行测试
pytest tests/ -v

# 查看 API 文档
open http://localhost:8000/api/docs
```

---

## 注意事项

1. **Windows 兼容性**
   ```python
   import asyncio
   if sys.platform == 'win32':
       asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
   ```

2. **截图大小优化**
   ```python
   # 使用 JPEG 格式，quality=80
   screenshot = await page.screenshot(type='jpeg', quality=80)
   ```

3. **Session 超时清理**
   ```python
   # 定期清理过期会话，避免内存泄漏
   async def cleanup_expired_sessions():
       # 30分钟未活动的会话应被清理
   ```

4. **错误处理原则**
   - 所有错误返回中文提示
   - 告诉用户可以做什么
   - 记录详细日志便于调试

---

## 下一步行动

1. **立即开始**：阅读 ARCHITECTURE.md 理解整体设计
2. **第一步开发**：按 P0_PAGINATION.md 的 Prompt 1 开始
3. **遇到问题**：参考现有代码 + 使用 Claude Code 调试


