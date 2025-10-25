# services/api/app/routers/runs.py
from __future__ import annotations

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from pydantic import BaseModel, Field
from bs4 import BeautifulSoup
import subprocess
import sys
import os
import json

from ..db import session_scope
from .. import crud, schemas

# 两个路由
router = APIRouter(prefix="/runs", tags=["runs"])
router_jobs = APIRouter(prefix="/runs/jobs", tags=["runs"])

# ---------- 请求/响应模型 ----------
class RunJobReq(BaseModel):
    url: str = Field(..., description="起始 URL（可覆盖 job.start_url）")
    limit: int = Field(20, ge=1, le=200, description="每个 selector 最大提取条数")

class RunStartResp(BaseModel):
    run_id: int
    status: str

# ---------- 🔥 新增：使用 Crawl4AI 爬取 ----------
def _crawl_with_crawler_runner(url: str, config: Optional[Dict] = None) -> str:
    """使用 crawler_runner_v2.py 爬取页面

    Args:
        url: 要爬取的 URL
        config: 爬虫配置（auto_scroll, use_stealth 等），如果为 None 则使用默认配置
    """
    runner_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'crawler_runner_v2.py'
    )

    # 默认配置
    if config is None:
        config = {
            "auto_scroll": True,
            "use_stealth": False,
            "wait_for": None
        }

    print(f"[Run] 使用配置: {config}")

    # 检查文件是否存在
    if not os.path.exists(runner_path):
        # 降级到旧版
        runner_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'crawler_runner.py'
        )
        print(f"[Run] 使用旧版爬虫: {runner_path}（不支持配置）")

        # 旧版只支持 URL
        result = subprocess.run(
            [sys.executable, runner_path, url],
            capture_output=True,
            timeout=120  # 增加超时时间
        )
    else:
        # 新版支持配置
        print(f"[Run] 使用新版爬虫: {runner_path}")
        params = json.dumps({
            "url": url,
            "config": config
        })

        # 根据滚动配置动态调整超时时间
        timeout = 120  # 默认 2 分钟
        if config.get('auto_scroll'):
            max_scrolls = config.get('max_scrolls', 20)
            scroll_delay = config.get('scroll_delay', 2000)
            # 估算需要的时间：滚动次数 * 滚动延迟 + 额外时间
            estimated_time = (max_scrolls * scroll_delay / 1000) + 60
            timeout = max(timeout, int(estimated_time))

        print(f"[Run] 超时时间: {timeout} 秒")

        result = subprocess.run(
            [sys.executable, runner_path, params],
            capture_output=True,
            timeout=timeout
        )
    
    if result.returncode != 0:
        error_msg = result.stderr.decode('utf-8', errors='ignore')
        print(f"[Run] 爬虫错误: {error_msg}")
        raise Exception(f"爬虫失败: {error_msg[:200]}")
    
    # 解析输出
    try:
        output_text = result.stdout.decode('utf-8')
    except UnicodeDecodeError:
        try:
            output_text = result.stdout.decode('gbk')
        except:
            output_text = result.stdout.decode('utf-8', errors='ignore')
    
    try:
        data = json.loads(output_text)
    except json.JSONDecodeError as e:
        print(f"[Run] JSON 解析错误: {e}")
        raise Exception(f"JSON 解析失败: {str(e)}")
    
    if not data.get('success'):
        raise Exception(f"爬取失败: {data.get('error', 'Unknown error')}")
    
    return data.get('html', '')


# ---------- 🔥 修改：背景执行函数 ----------
def _execute_run(run_id: int, job_id: int, url: str, limit: int) -> None:
    with session_scope() as s:
        crud.set_run_running(s, run_id)

        job = crud.get_job(s, job_id)
        if not job:
            crud.finish_run(s, run_id, status="failed", stats={"error": "job not found"})
            return

        rows, pages = 0, 1
        try:
            print(f"[Run] 开始采集: {url}")

            # 🔥 解析 Job 的配置
            crawler_config = None
            if job.config_json:
                try:
                    crawler_config = json.loads(job.config_json)
                    print(f"[Run] 使用 Job 配置: {crawler_config}")
                except json.JSONDecodeError:
                    print(f"[Run] Job 配置解析失败，使用默认配置")

            # 🔥 使用 Crawl4AI 爬取（支持 JavaScript 渲染）
            html = _crawl_with_crawler_runner(url, crawler_config)

            print(f"[Run] 爬取成功，HTML 长度: {len(html)}")
            
            soup = BeautifulSoup(html, "lxml")

            # 提取数据
            for sel in job.selectors:
                css = sel.css
                attr = (sel.attr or "text").lower()
                maxn = sel.limit or limit
                
                print(f"[Run] 提取字段: {sel.name}, 选择器: {css}, 属性: {attr}")
                
                elements = soup.select(css)
                print(f"[Run] 找到 {len(elements)} 个元素")
                
                for idx, el in enumerate(elements[: min(maxn, limit)]):
                    if attr == "text":
                        val = el.get_text(strip=True)
                    else:
                        val = (el.get(attr) or "").strip()
                    
                    if val:  # 只保存非空值
                        crud.add_result(s, run_id, sel.name, idx, val, url)
                        rows += 1

            print(f"[Run] 采集完成，共 {rows} 条数据")
            crud.finish_run(s, run_id, status="succeeded", stats={"rows": rows, "pages": pages})
            
        except Exception as e:
            print(f"[Run] 采集失败: {e}")
            import traceback
            traceback.print_exc()
            crud.finish_run(s, run_id, status="failed", stats={"error": str(e)})


# ---------- 发起运行 ----------
@router_jobs.post("/{job_id}/run", response_model=RunStartResp, summary="Run Job")
def run_job(job_id: int, payload: RunJobReq, bg: BackgroundTasks):
    with session_scope() as s:
        job = crud.get_job(s, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        run = crud.create_run(s, job_id=job_id, status="queued")
        bg.add_task(_execute_run, run.id, job_id, payload.url or job.start_url, payload.limit)
        return RunStartResp(run_id=run.id, status="queued")

# ---------- 列表 / 详情 ----------
@router.get("", response_model=List[schemas.RunOut], summary="List Runs")
def list_runs(
    job_id: Optional[int] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    with session_scope() as s:
        items = crud.list_runs(s, job_id=job_id, limit=limit, offset=offset)
        return [schemas.RunOut.model_validate(i) for i in items]

@router.get("/{run_id}", response_model=schemas.RunOut, summary="Get Run")
def get_run(run_id: int):
    with session_scope() as s:
        run = crud.get_run(s, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="run not found")
        return schemas.RunOut.model_validate(run)

# ---------- 结果 / 导出 ----------
@router.get("/{run_id}/results", summary="Get Run Results")
def get_run_results(run_id: int) -> Dict[str, List[str]]:
    with session_scope() as s:
        if not crud.get_run(s, run_id):
            raise HTTPException(status_code=404, detail="run not found")
        return crud.list_results_rows(s, run_id)

@router.get("/{run_id}/export", summary="Export Run Results (CSV)")
def export_run_results(run_id: int, format: str = Query(default="csv")):
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="only csv is supported for now")
    with session_scope() as s:
        if not crud.get_run(s, run_id):
            raise HTTPException(status_code=404, detail="run not found")
        rows = crud.list_results_raw(s, run_id)

    lines = ["selector,row_idx,value,url"]
    for r in rows:
        selector = getattr(r, "selector", None) or getattr(r, "name", "")
        row_idx = getattr(r, "row_idx", None) or getattr(r, "row", 0)
        value = getattr(r, "value", None) or getattr(r, "text", "")
        url = getattr(r, "url", "")
        # 修复 f-string 语法问题：提前处理转义
        escaped_value = value.replace('"', '""')
        escaped_url = url.replace('"', '""')
        lines.append(f'{selector},{row_idx},"{escaped_value}","{escaped_url}"')

    return Response(
        content="\n".join(lines),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="run-{run_id}.csv"'},
    )