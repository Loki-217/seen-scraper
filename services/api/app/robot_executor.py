# services/api/app/robot_executor.py
"""
Robot 执行器 - 负责执行 Robot 配置，抓取数据
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from .models_v2.schedule import Robot, Action, ActionType, FieldConfig, PaginationConfig


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    items: List[Dict[str, Any]] = field(default_factory=list)
    pages_scraped: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None


class RobotExecutor:
    """Robot 执行器 - 负责执行 Robot 配置，抓取数据"""

    # 超时配置
    PAGE_LOAD_TIMEOUT = 30000      # 页面加载超时：30秒
    EXTRACTION_TIMEOUT = 10000     # 单页提取超时：10秒
    TOTAL_TIMEOUT = 600            # 总执行超时：10分钟

    def __init__(self, robot: Robot):
        self.robot = robot
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.results: List[Dict[str, Any]] = []
        self.pages_scraped = 0
        self.start_time: Optional[float] = None

    async def execute(self) -> ExecutionResult:
        """执行 Robot，返回结果"""
        self.start_time = time.time()

        try:
            await self._init_browser()
            await self._navigate_to_origin()
            await self._replay_actions()
            await self._extract_data()

            if self.robot.pagination:
                await self._handle_pagination()

            return self._build_result(success=True)

        except asyncio.TimeoutError:
            return self._build_result(success=False, error="执行超时")
        except Exception as e:
            return self._build_result(success=False, error=str(e))
        finally:
            await self._cleanup()

    async def _init_browser(self):
        """初始化浏览器（带反检测配置）"""
        playwright = await async_playwright().start()

        # 反检测配置
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )

        # 创建上下文（带反检测）
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='zh-CN',
            timezone_id='Asia/Shanghai',
        )

        # 注入反检测脚本
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)

        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.PAGE_LOAD_TIMEOUT)

    async def _navigate_to_origin(self):
        """导航到起始URL"""
        await self.page.goto(self.robot.origin_url, wait_until='networkidle')
        await self._random_delay(500, 1500)

    async def _replay_actions(self):
        """重放录制的操作序列"""
        for action in self.robot.actions:
            # 检查总超时
            self._check_timeout()
            await self._execute_action(action)

    async def _execute_action(self, action: Action):
        """执行单个操作"""
        if action.type == ActionType.CLICK:
            if action.selector:
                await self.page.click(action.selector)
            elif action.x is not None and action.y is not None:
                await self.page.mouse.click(action.x, action.y)

        elif action.type == ActionType.SCROLL:
            if action.y:
                await self.page.evaluate(f'window.scrollBy(0, {action.y})')
            else:
                await self.page.evaluate('window.scrollBy(0, 500)')

        elif action.type == ActionType.INPUT:
            if action.selector and action.value:
                await self.page.fill(action.selector, action.value)

        elif action.type == ActionType.WAIT:
            wait_time = action.delay_ms if action.delay_ms else 1000
            await asyncio.sleep(wait_time / 1000)

        elif action.type == ActionType.HOVER:
            if action.selector:
                await self.page.hover(action.selector)

        elif action.type == ActionType.SELECT:
            if action.selector and action.value:
                await self.page.select_option(action.selector, action.value)

        # 操作后延迟
        if action.delay_ms:
            await asyncio.sleep(action.delay_ms / 1000)

    async def _extract_data(self) -> List[Dict[str, Any]]:
        """根据字段配置提取数据"""
        self._check_timeout()

        # 提取当前页数据
        page_data = await self._extract_page_data()
        self.results.extend(page_data)
        self.pages_scraped += 1

        return page_data

    async def _extract_page_data(self) -> List[Dict[str, Any]]:
        """提取当前页面的数据"""
        if not self.robot.item_selector or not self.robot.fields:
            return []

        print(f"[DEBUG] Extracting with fields: {[(f.name, f.selector) for f in self.robot.fields]}")
        # 构建提取脚本
        fields_config = [
            {
                'name': f.name,
                'selector': f.selector,
                'attr': f.attr,
                'regex': f.regex
            }
            for f in self.robot.fields
        ]

        data = await self.page.evaluate('''
            ({itemSelector, fields}) => {
                const items = document.querySelectorAll(itemSelector);
                const results = [];

                for (const item of items) {
                    const row = {};

                    for (const field of fields) {
                        const el = item.querySelector(field.selector);
                        if (el) {
                            let value = '';
                            if (field.attr === 'text') {
                                value = (el.textContent || '').trim();
                            } else if (field.attr === 'href') {
                                value = el.href || '';
                            } else if (field.attr === 'src') {
                                value = el.src || el.dataset.src || '';
                            } else {
                                value = el.getAttribute(field.attr) || '';
                            }

                            // 正则提取
                            if (field.regex && value) {
                                try {
                                    const match = value.match(new RegExp(field.regex));
                                    value = match ? (match[1] || match[0]) : value;
                                } catch(e) {}
                            }

                            row[field.name] = value;
                        } else {
                            row[field.name] = null;
                        }
                    }

                    results.push(row);
                }

                return results;
            }
        ''', {'itemSelector': self.robot.item_selector, 'fields': fields_config})

        return data

    async def _handle_pagination(self):
        """处理翻页"""
        if not self.robot.pagination:
            return

        pagination = self.robot.pagination
        max_pages = pagination.max_pages or 10

        for page_num in range(2, max_pages + 1):
            self._check_timeout()

            # 执行翻页
            success = await self._do_pagination(pagination)
            if not success:
                break

            # 等待加载
            await asyncio.sleep((pagination.wait_ms or 1000) / 1000)

            # 检查停止条件
            if pagination.stop_selector:
                try:
                    stop_el = await self.page.query_selector(pagination.stop_selector)
                    if stop_el:
                        break
                except:
                    pass

            # 提取数据
            page_data = await self._extract_page_data()
            if not page_data:
                break

            self.results.extend(page_data)
            self.pages_scraped += 1

            # 随机延迟
            await self._random_delay(500, 1500)

    async def _do_pagination(self, pagination: PaginationConfig) -> bool:
        """执行翻页操作"""
        try:
            if pagination.type == "click_next":
                if pagination.selector:
                    # 检查按钮是否存在且可点击
                    btn = await self.page.query_selector(pagination.selector)
                    if not btn:
                        return False

                    is_disabled = await btn.get_attribute('disabled')
                    if is_disabled:
                        return False

                    await btn.click()
                    await self.page.wait_for_load_state('networkidle', timeout=10000)
                    return True

            elif pagination.type == "scroll":
                # 滚动加载
                prev_count = await self.page.evaluate(
                    f'document.querySelectorAll("{self.robot.item_selector}").length'
                )
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(1)

                new_count = await self.page.evaluate(
                    f'document.querySelectorAll("{self.robot.item_selector}").length'
                )
                return new_count > prev_count

            elif pagination.type == "url_pattern":
                # URL 模式翻页（需要额外实现）
                pass

            return False

        except Exception as e:
            print(f"[RobotExecutor] Pagination error: {e}")
            return False

    def _check_timeout(self):
        """检查是否超时"""
        if self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed > self.TOTAL_TIMEOUT:
                raise asyncio.TimeoutError("执行超时")

    async def _random_delay(self, min_ms: int, max_ms: int):
        """随机延迟（模拟人类行为）"""
        import random
        delay = random.randint(min_ms, max_ms) / 1000
        await asyncio.sleep(delay)

    def _build_result(self, success: bool, error: Optional[str] = None) -> ExecutionResult:
        """构建执行结果"""
        duration = time.time() - self.start_time if self.start_time else 0

        return ExecutionResult(
            success=success,
            items=self.results,
            pages_scraped=self.pages_scraped,
            duration_seconds=round(duration, 2),
            error=error
        )

    async def _cleanup(self):
        """清理资源"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            print(f"[RobotExecutor] Cleanup error: {e}")


async def save_results_to_file(
    results: List[Dict[str, Any]],
    robot_name: str,
    output_dir: str = "data/results"
) -> str:
    """保存结果到 CSV 文件"""
    import csv

    # 创建目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() else "_" for c in robot_name)
    filename = f"{safe_name}_{timestamp}.csv"
    filepath = Path(output_dir) / filename

    # 写入 CSV 文件
    if results:
        # 获取所有字段名
        fieldnames = list(results[0].keys())

        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

    return str(filepath)
