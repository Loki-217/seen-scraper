#!/usr/bin/env python3
"""
测试 Unsplash 瀑布流滚动加载
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'api', 'app'))

from crawler_runner_v2 import crawl_page_enhanced


async def test_unsplash_scroll():
    """测试 Unsplash 滚动加载"""

    print("=" * 60)
    print("测试 Unsplash 瀑布流滚动加载")
    print("=" * 60)

    url = "https://unsplash.com/"

    # 配置针对 Unsplash 优化的参数
    config = {
        'use_stealth': True,          # 启用隐身模式
        'auto_scroll': True,          # 启用自动滚动
        'max_scrolls': 30,            # 最多滚动 30 次（可根据需要调整）
        'scroll_delay': 3000,         # 每次滚动后等待 3 秒
        'stable_checks': 5,           # 连续 5 次无变化才停止
    }

    print(f"\n目标 URL: {url}")
    print(f"配置参数:")
    print(f"  - 隐身模式: {config['use_stealth']}")
    print(f"  - 最大滚动次数: {config['max_scrolls']}")
    print(f"  - 滚动延迟: {config['scroll_delay']}ms")
    print(f"  - 稳定性检查: {config['stable_checks']} 次")
    print()

    print("开始爬取...")
    result = await crawl_page_enhanced(url, config)

    print("\n" + "=" * 60)
    print("爬取结果:")
    print("=" * 60)
    print(f"成功: {result['success']}")

    if result['success']:
        html_length = len(result.get('html', ''))
        text_length = len(result.get('text', ''))
        word_count = result.get('word_count', 0)

        print(f"HTML 长度: {html_length:,} 字符")
        print(f"文本长度: {text_length:,} 字符")
        print(f"单词数: {word_count:,}")

        # 统计图片数量
        html = result.get('html', '')
        img_count = html.count('<img')
        figure_count = html.count('<figure')

        print(f"\n检测到的元素:")
        print(f"  - <img> 标签: {img_count}")
        print(f"  - <figure> 标签: {figure_count}")

        # 保存 HTML 用于调试
        output_file = "unsplash_result.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(result['html'])
        print(f"\nHTML 已保存到: {output_file}")

    else:
        print(f"错误: {result.get('error', 'Unknown error')}")

    print("\n" + "=" * 60)


async def test_with_different_configs():
    """测试不同配置对比"""

    print("\n" + "=" * 60)
    print("测试不同配置的效果对比")
    print("=" * 60)

    url = "https://unsplash.com/"

    configs = [
        {
            'name': '激进模式（快速）',
            'config': {
                'use_stealth': True,
                'auto_scroll': True,
                'max_scrolls': 10,
                'scroll_delay': 1500,
                'stable_checks': 2,
            }
        },
        {
            'name': '平衡模式（推荐）',
            'config': {
                'use_stealth': True,
                'auto_scroll': True,
                'max_scrolls': 20,
                'scroll_delay': 2500,
                'stable_checks': 3,
            }
        },
        {
            'name': '保守模式（最完整）',
            'config': {
                'use_stealth': True,
                'auto_scroll': True,
                'max_scrolls': 40,
                'scroll_delay': 3500,
                'stable_checks': 5,
            }
        },
    ]

    results = []

    for idx, test_case in enumerate(configs, 1):
        print(f"\n[{idx}/{len(configs)}] 测试 {test_case['name']}")
        print("-" * 60)

        result = await crawl_page_enhanced(url, test_case['config'])

        if result['success']:
            html_length = len(result.get('html', ''))
            img_count = result.get('html', '').count('<img')

            results.append({
                'name': test_case['name'],
                'html_length': html_length,
                'img_count': img_count,
            })

            print(f"✓ 成功")
            print(f"  HTML: {html_length:,} 字符")
            print(f"  图片: {img_count} 个")
        else:
            print(f"✗ 失败: {result.get('error')}")

    # 打印对比表格
    print("\n" + "=" * 60)
    print("结果对比:")
    print("=" * 60)
    print(f"{'模式':<20} {'HTML大小':<15} {'图片数量':<10}")
    print("-" * 60)
    for r in results:
        print(f"{r['name']:<20} {r['html_length']:>10,} 字符  {r['img_count']:>5} 个")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='测试 Unsplash 滚动加载')
    parser.add_argument('--compare', action='store_true',
                       help='对比测试不同配置')
    parser.add_argument('--max-scrolls', type=int, default=30,
                       help='最大滚动次数 (默认: 30)')
    parser.add_argument('--scroll-delay', type=int, default=3000,
                       help='滚动延迟毫秒数 (默认: 3000)')
    parser.add_argument('--stable-checks', type=int, default=5,
                       help='稳定性检查次数 (默认: 5)')

    args = parser.parse_args()

    if args.compare:
        asyncio.run(test_with_different_configs())
    else:
        # 使用命令行参数自定义配置
        if (args.max_scrolls != 30 or
            args.scroll_delay != 3000 or
            args.stable_checks != 5):

            print("使用自定义配置:")
            print(f"  max_scrolls: {args.max_scrolls}")
            print(f"  scroll_delay: {args.scroll_delay}ms")
            print(f"  stable_checks: {args.stable_checks}")
            print()

        asyncio.run(test_unsplash_scroll())
