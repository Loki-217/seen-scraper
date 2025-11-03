#!/usr/bin/env python3
"""
测试程序：提取服务器最近一次上传给前端用于iframe渲染的HTML

这个脚本用于测试 /api/proxy/render 端点，提取并保存渲染后的HTML内容。

使用方法：
    python tests/test_iframe_html_extraction.py [URL]

示例：
    python tests/test_iframe_html_extraction.py https://example.com
    python tests/test_iframe_html_extraction.py --list  # 查看保存的HTML文件
    python tests/test_iframe_html_extraction.py --view output/latest.html  # 查看HTML内容
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx


# API配置
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
OUTPUT_DIR = Path("tests/output/iframe_html")
TIMEOUT = 60  # 60秒超时


class IframeHTMLExtractor:
    """iframe HTML提取器"""

    def __init__(self, api_base: str = API_BASE):
        self.api_base = api_base.rstrip('/')
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_html(self, url: str, timeout_ms: int = 30000) -> dict:
        """
        调用 /api/proxy/render 端点提取HTML

        Args:
            url: 目标网页URL
            timeout_ms: 渲染超时时间（毫秒）

        Returns:
            dict: 包含 success, html, url, title 等字段
        """
        endpoint = f"{self.api_base}/api/proxy/render"

        print(f"🔄 正在渲染: {url}")
        print(f"📡 API端点: {endpoint}")
        print(f"⏱️  超时设置: {timeout_ms}ms")

        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                response = client.post(
                    endpoint,
                    json={
                        "url": url,
                        "timeout_ms": timeout_ms
                    },
                    headers={"Content-Type": "application/json"}
                )

                response.raise_for_status()
                data = response.json()

                if data.get("success"):
                    print("✅ HTML提取成功")
                    print(f"📄 标题: {data.get('title', 'N/A')}")
                    print(f"📏 HTML大小: {len(data.get('html', ''))} 字符")
                else:
                    print(f"❌ 提取失败: {data.get('error', '未知错误')}")

                return data

        except httpx.TimeoutException:
            print(f"⏰ 请求超时（{TIMEOUT}秒）")
            return {"success": False, "error": "请求超时"}
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP错误: {e.response.status_code}")
            print(f"响应内容: {e.response.text[:500]}")
            return {"success": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            print(f"❌ 错误: {str(e)}")
            return {"success": False, "error": str(e)}

    def save_html(self, html: str, url: str, title: str = None) -> Path:
        """
        保存HTML到文件

        Args:
            html: HTML内容
            url: 原始URL
            title: 页面标题

        Returns:
            Path: 保存的文件路径
        """
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_url = url.replace("https://", "").replace("http://", "")
        safe_url = "".join(c if c.isalnum() or c in "._-" else "_" for c in safe_url)
        filename = f"{timestamp}_{safe_url[:50]}.html"

        filepath = self.output_dir / filename

        # 保存HTML
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        # 保存元数据
        meta_filepath = filepath.with_suffix(".json")
        metadata = {
            "url": url,
            "title": title,
            "timestamp": timestamp,
            "html_size": len(html),
            "filepath": str(filepath)
        }
        with open(meta_filepath, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"💾 HTML已保存: {filepath}")
        print(f"📋 元数据已保存: {meta_filepath}")

        # 创建latest软链接
        latest_link = self.output_dir / "latest.html"
        latest_meta_link = self.output_dir / "latest.json"

        if latest_link.exists():
            latest_link.unlink()
        if latest_meta_link.exists():
            latest_meta_link.unlink()

        os.symlink(filepath.name, latest_link)
        os.symlink(meta_filepath.name, latest_meta_link)

        print(f"🔗 最新文件链接: {latest_link}")

        return filepath

    def list_saved_html(self):
        """列出所有保存的HTML文件"""
        html_files = sorted(self.output_dir.glob("*.html"), reverse=True)

        if not html_files:
            print("📭 没有找到保存的HTML文件")
            return

        print(f"📚 找到 {len(html_files)} 个HTML文件:\n")

        for i, filepath in enumerate(html_files, 1):
            if filepath.name == "latest.html":
                continue

            meta_filepath = filepath.with_suffix(".json")
            if meta_filepath.exists():
                with open(meta_filepath, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    print(f"{i}. {filepath.name}")
                    print(f"   📄 标题: {metadata.get('title', 'N/A')}")
                    print(f"   🔗 URL: {metadata.get('url', 'N/A')}")
                    print(f"   📏 大小: {metadata.get('html_size', 0):,} 字符")
                    print(f"   🕒 时间: {metadata.get('timestamp', 'N/A')}")
                    print()
            else:
                print(f"{i}. {filepath.name}")
                print(f"   📏 大小: {filepath.stat().st_size:,} 字节")
                print()

    def view_html(self, filepath: str):
        """查看HTML文件内容摘要"""
        path = Path(filepath)

        if not path.exists():
            # 尝试在output_dir中查找
            path = self.output_dir / filepath
            if not path.exists():
                print(f"❌ 文件不存在: {filepath}")
                return

        print(f"📖 查看文件: {path}\n")

        # 读取元数据
        meta_path = path.with_suffix(".json")
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
                print("📋 元数据:")
                print(f"   🔗 URL: {metadata.get('url', 'N/A')}")
                print(f"   📄 标题: {metadata.get('title', 'N/A')}")
                print(f"   🕒 时间: {metadata.get('timestamp', 'N/A')}")
                print(f"   📏 大小: {metadata.get('html_size', 0):,} 字符")
                print()

        # 读取HTML并显示摘要
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

        print(f"📝 HTML内容摘要:")
        print(f"   总长度: {len(html):,} 字符")

        # 显示前500字符
        print(f"\n   前500字符预览:")
        print("   " + "=" * 70)
        print("   " + html[:500].replace("\n", "\n   "))
        print("   " + "=" * 70)

        # 分析HTML结构
        if "<html" in html.lower():
            print(f"\n   ✅ 包含 <html> 标签")
        if "<head" in html.lower():
            print(f"   ✅ 包含 <head> 标签")
        if "<body" in html.lower():
            print(f"   ✅ 包含 <body> 标签")
        if "<base" in html.lower():
            print(f"   ✅ 包含 <base> 标签（资源路径修复）")
        if "font-awesome" in html.lower():
            print(f"   ✅ 包含 Font Awesome CDN")
        if "seenElementClickListener" in html:
            print(f"   ✅ 包含注入的交互监听脚本")

        print(f"\n💡 使用浏览器打开: file://{path.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description="提取服务器渲染的iframe HTML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  %(prog)s https://example.com
  %(prog)s --list
  %(prog)s --view latest.html
  %(prog)s --api-base http://localhost:8000 https://example.com
        """
    )

    parser.add_argument(
        "url",
        nargs="?",
        help="要渲染的网页URL"
    )
    parser.add_argument(
        "--api-base",
        default=API_BASE,
        help=f"API服务器地址 (默认: {API_BASE})"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30000,
        help="渲染超时时间（毫秒，默认: 30000）"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有保存的HTML文件"
    )
    parser.add_argument(
        "--view",
        metavar="FILE",
        help="查看指定HTML文件的内容"
    )

    args = parser.parse_args()

    extractor = IframeHTMLExtractor(api_base=args.api_base)

    # 列出文件
    if args.list:
        extractor.list_saved_html()
        return 0

    # 查看文件
    if args.view:
        extractor.view_html(args.view)
        return 0

    # 提取HTML
    if not args.url:
        parser.print_help()
        print("\n❌ 错误: 请提供URL或使用 --list / --view 选项")
        return 1

    # 执行提取
    result = extractor.extract_html(args.url, timeout_ms=args.timeout)

    if result.get("success") and result.get("html"):
        # 保存HTML
        filepath = extractor.save_html(
            html=result["html"],
            url=result.get("url", args.url),
            title=result.get("title")
        )

        print(f"\n✨ 完成! 最近一次渲染的HTML已保存")
        print(f"📂 文件路径: {filepath}")
        print(f"💡 查看内容: python {sys.argv[0]} --view {filepath.name}")
        return 0
    else:
        print(f"\n❌ 提取失败: {result.get('error', '未知错误')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
