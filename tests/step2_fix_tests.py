#!/usr/bin/env python3
"""
Step 2: 修复测试文件并整理测试目录
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

def create_conftest():
    """创建 pytest 配置文件，添加项目根目录到 Python path"""
    conftest_content = '''"""
pytest 配置文件
添加项目根目录到 Python path，使测试可以导入 services 模块
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
'''
    
    conftest_path = PROJECT_ROOT / "tests" / "conftest.py"
    conftest_path.write_text(conftest_content, encoding='utf-8')
    print(f"✅ 创建: {conftest_path.relative_to(PROJECT_ROOT)}")

def fix_test_smart_extractor():
    """修复 test_smart_extractor.py 的导入错误"""
    test_file = PROJECT_ROOT / "tests" / "test_smart_extractor.py"
    
    if not test_file.exists():
        print(f"⚠️  文件不存在: {test_file}")
        return
    
    fixed_content = '''# tests/test_smart_extractor.py
import asyncio
import json
from services.api.app.smart_extractor_subprocess import SmartExtractor

async def test_analyze():
    """测试智能分析功能"""
    extractor = SmartExtractor()
    result = await extractor.analyze_page("https://example.com")
    
    assert result is not None
    assert "success" in result
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(test_analyze())
'''
    
    test_file.write_text(fixed_content, encoding='utf-8')
    print(f"✅ 修复: {test_file.relative_to(PROJECT_ROOT)}")

def create_init_files():
    """创建必要的 __init__.py 文件"""
    init_files = [
        PROJECT_ROOT / "tests" / "__init__.py",
    ]
    
    for init_file in init_files:
        if not init_file.exists():
            init_file.write_text("# pytest test package\n", encoding='utf-8')
            print(f"✅ 创建: {init_file.relative_to(PROJECT_ROOT)}")

def update_pytest_ini():
    """更新 pytest.ini 配置"""
    pytest_ini_content = '''[pytest]
# 自动检测异步测试
asyncio_mode = auto

# 添加项目根目录到 Python path
pythonpath = .

# 测试发现规则
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# 输出配置
addopts = 
    -v
    --tb=short
    --strict-markers

# 标记定义
markers =
    slow: 慢速测试
    integration: 集成测试
'''
    
    pytest_ini = PROJECT_ROOT / "pytest.ini"
    pytest_ini.write_text(pytest_ini_content, encoding='utf-8')
    print(f"✅ 更新: pytest.ini")

def main():
    print("=" * 60)
    print("🔧 步骤 2: 修复测试文件导入")
    print("=" * 60)
    print()
    
    # 1. 创建 conftest.py
    print("📝 创建 pytest 配置...")
    create_conftest()
    print()
    
    # 2. 创建 __init__.py
    print("📝 创建包文件...")
    create_init_files()
    print()
    
    # 3. 修复测试文件
    print("🔨 修复测试文件...")
    fix_test_smart_extractor()
    print()
    
    # 4. 更新 pytest.ini
    print("⚙️  更新 pytest 配置...")
    update_pytest_ini()
    print()
    
    print("=" * 60)
    print("✅ 步骤 2 完成！")
    print("=" * 60)
    print()
    print("📌 验证测试:")
    print("  pytest tests/ -v")
    print()

if __name__ == "__main__":
    main()