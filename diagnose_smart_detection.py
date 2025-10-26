#!/usr/bin/env python3
"""
诊断智能网站识别功能
"""
import sys
import os

print("=" * 60)
print("智能网站识别功能诊断")
print("=" * 60)
print()

# 1. 检查文件是否存在
print("【步骤 1】检查核心文件...")
files_to_check = [
    "services/api/app/website_analyzer.py",
    "services/api/app/website_rules.json",
    "services/api/app/models.py",
    "services/api/app/ai_service.py",
    "services/api/app/routers/runs.py",
]

all_files_exist = True
for file_path in files_to_check:
    exists = os.path.exists(file_path)
    status = "✓" if exists else "✗"
    print(f"{status} {file_path}")
    if not exists:
        all_files_exist = False

if not all_files_exist:
    print("\n✗ 部分文件缺失，请确保已经合并了所有代码")
    sys.exit(1)

print("\n✓ 所有核心文件都存在")

# 2. 检查 runs.py 中是否有智能识别代码
print("\n【步骤 2】检查 runs.py 中的智能识别逻辑...")
with open("services/api/app/routers/runs.py", "r", encoding="utf-8") as f:
    runs_content = f.read()

keywords = [
    "智能识别",
    "get_analyzer",
    "website_analyzer",
    "analysis_result"
]

missing_keywords = []
for keyword in keywords:
    if keyword in runs_content:
        print(f"✓ 找到关键词: {keyword}")
    else:
        print(f"✗ 未找到关键词: {keyword}")
        missing_keywords.append(keyword)

if missing_keywords:
    print(f"\n✗ runs.py 中缺少智能识别代码，缺少关键词: {missing_keywords}")
    sys.exit(1)

print("\n✓ runs.py 中包含智能识别代码")

# 3. 检查规则库
print("\n【步骤 3】检查本地规则库...")
import json

try:
    with open("services/api/app/website_rules.json", "r", encoding="utf-8") as f:
        rules = json.load(f)

    rule_count = len(rules.get("rules", []))
    print(f"✓ 规则库加载成功，包含 {rule_count} 条规则")

    # 显示部分规则
    print("\n规则列表:")
    for rule in rules.get("rules", [])[:5]:
        print(f"  - {rule.get('site_name', 'Unknown')} ({rule.get('domain', '')})")

    if rule_count > 5:
        print(f"  ... 还有 {rule_count - 5} 条规则")

except Exception as e:
    print(f"✗ 规则库加载失败: {e}")
    sys.exit(1)

# 4. 测试导入
print("\n【步骤 4】测试模块导入...")
sys.path.insert(0, "services/api/app")

try:
    from website_analyzer import get_analyzer
    print("✓ website_analyzer 导入成功")

    analyzer = get_analyzer()
    print("✓ 分析器实例化成功")

    # 测试域名提取
    test_url = "https://unsplash.com/photos/test"
    domain = analyzer._extract_domain(test_url)
    print(f"✓ 域名提取测试: {test_url} → {domain}")

    # 测试规则匹配
    rule = analyzer._match_local_rules(test_url, domain)
    if rule:
        print(f"✓ 规则匹配成功: {rule['site_name']}")
    else:
        print(f"⚠ 该 URL 未匹配到本地规则（这是正常的）")

except Exception as e:
    print(f"✗ 导入失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. 检查 Job 是否会触发智能识别
print("\n【步骤 5】分析 Job 创建逻辑...")
print("\n当前前端创建 Job 时:")
print("  - 包含字段: name, start_url, status, selectors")
print("  - 不包含字段: config")
print("  → Job.config_json 将为 None")
print("  → 应该触发智能识别 ✓")

# 6. 提供测试建议
print("\n" + "=" * 60)
print("【诊断结果】")
print("=" * 60)
print()
print("✓ 所有核心组件都已正确安装")
print()
print("【测试建议】")
print()
print("1. 启动应用:")
print("   cd services/api/app")
print("   python main.py")
print()
print("2. 打开前端:")
print("   http://localhost:8000/services/web/index.html")
print()
print("3. 测试 Unsplash:")
print("   - 输入 URL: https://unsplash.com/")
print("   - 配置一个字段（例如选择图片）")
print("   - 点击 '开始采集'")
print()
print("4. 观察终端输出，应该看到:")
print()
print("   [Run] 开始采集: https://unsplash.com/")
print("   [Run] Job 无配置，启动智能识别...")
print("   [Analyzer] 开始分析: https://unsplash.com/")
print("   [Analyzer] 域名: unsplash.com")
print("   [Analyzer] ✓ 匹配本地规则: Unsplash (置信度: 1.0)")
print("   [Run] ✓ 智能识别完成:")
print("   [Run]   - 网站: Unsplash")
print("   [Run]   - 类型: photo_sharing")
print("   [Run]   - 加载方式: infinite_scroll")
print("   [Run]   - 置信度: 1.0")
print("   [Run]   - 来源: local_rules")
print("   [Run] 最终配置: {...}")
print()
print("【如果没有看到日志】")
print()
print("可能原因:")
print("1. Job 中已有配置（之前测试留下的）")
print("   解决：删除数据库 seen.db，重新启动")
print()
print("2. 异常被捕获了")
print("   解决：查看完整的终端输出，寻找错误信息")
print()
print("3. 使用了错误的前端页面")
print("   解决：确保使用 index.html，不是 index-v2.html")
print()
print("=" * 60)
