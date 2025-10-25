#!/usr/bin/env python3
"""
测试智能网站识别功能
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'api', 'app'))

from website_analyzer import get_analyzer
from db import session_scope


def test_local_rules():
    """测试本地规则匹配"""
    print("=" * 60)
    print("测试 1: 本地规则库匹配")
    print("=" * 60)

    test_urls = [
        "https://unsplash.com/",
        "https://pinterest.com/",
        "https://www.xiaohongshu.com/",
        "https://www.douban.com/",
    ]

    analyzer = get_analyzer()

    print(f"\n本地规则库包含 {len(analyzer.rules.get('rules', []))} 条规则\n")

    for url in test_urls:
        domain = analyzer._extract_domain(url)
        rule = analyzer._match_local_rules(url, domain)

        if rule:
            print(f"✓ {url}")
            print(f"  - 网站: {rule['site_name']}")
            print(f"  - 类型: {rule['site_type']}")
            print(f"  - 加载方式: {rule['load_type']}")
            print(f"  - 置信度: {rule['confidence']}")
            print(f"  - 配置: max_scrolls={rule['config'].get('max_scrolls')}, " +
                  f"delay={rule['config'].get('scroll_delay')}ms")
        else:
            print(f"✗ {url} - 未匹配")

        print()


def test_page_analysis():
    """测试页面分析（不需要 AI）"""
    print("=" * 60)
    print("测试 2: 快速页面分析")
    print("=" * 60)

    # 使用一个简单的测试网站
    test_url = "https://example.com"

    analyzer = get_analyzer()

    print(f"\n测试 URL: {test_url}")
    print("正在分析...")

    try:
        page_info = analyzer._quick_page_analysis(test_url)
        result = analyzer._detect_by_features(page_info)

        print(f"\n✓ 分析完成:")
        print(f"  - 网站: {result['site_name']}")
        print(f"  - 类型: {result['site_type']}")
        print(f"  - 加载方式: {result['load_type']}")
        print(f"  - 置信度: {result['confidence']}")
        print(f"  - 来源: {result['source']}")
        print(f"  - 理由: {result['reasoning']}")

    except Exception as e:
        print(f"✗ 分析失败: {e}")

    print()


def test_full_analysis():
    """测试完整分析流程（包括数据库缓存）"""
    print("=" * 60)
    print("测试 3: 完整分析流程（含缓存）")
    print("=" * 60)

    test_url = "https://unsplash.com/"

    analyzer = get_analyzer()

    print(f"\n测试 URL: {test_url}")
    print("正在分析（第一次，会匹配本地规则并缓存）...\n")

    try:
        with session_scope() as session:
            # 第一次分析
            result1 = analyzer.analyze(test_url, session)

            print(f"\n✓ 第一次分析完成:")
            print(f"  - 网站: {result1['site_name']}")
            print(f"  - 类型: {result1['site_type']}")
            print(f"  - 加载方式: {result1['load_type']}")
            print(f"  - 置信度: {result1['confidence']}")
            print(f"  - 来源: {result1['source']}")
            print(f"  - 配置: {result1['config']}")

            print("\n正在再次分析（第二次，应该从缓存读取）...\n")

            # 第二次分析（应该从缓存读取）
            result2 = analyzer.analyze(test_url, session)

            print(f"\n✓ 第二次分析完成:")
            print(f"  - 来源: {result2['source']}")

            if result1 == result2:
                print(f"  - ✓ 结果一致，缓存工作正常")
            else:
                print(f"  - ⚠ 结果不一致")

    except Exception as e:
        print(f"✗ 分析失败: {e}")
        import traceback
        traceback.print_exc()

    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("智能网站识别功能测试")
    print("=" * 60)
    print()

    try:
        # 测试 1: 本地规则匹配
        test_local_rules()

        # 测试 2: 页面分析
        test_page_analysis()

        # 测试 3: 完整流程（含缓存）
        test_full_analysis()

        print("=" * 60)
        print("✓ 所有测试完成")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n测试中断")
        sys.exit(1)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
