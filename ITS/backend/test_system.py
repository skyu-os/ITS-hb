"""
系统测试脚本
验证增强系统的基本结构和功能
"""

import os
import sys
from pathlib import Path

def test_file_structure():
    """测试文件结构"""
    print("🔍 检查文件结构...")
    
    required_files = [
        'database.py',
        'data_collector.py', 
        'deep_learning_predictor.py',
        'enhanced_server.py',
        'start_enhanced_backend.py',
        'requirements.txt',
        '.env.example'
    ]
    
    missing_files = []
    for file in required_files:
        if Path(file).exists():
            print(f"  ✅ {file}")
        else:
            print(f"  ❌ {file}")
            missing_files.append(file)
    
    return len(missing_files) == 0

def test_python_imports():
    """测试Python导入"""
    print("\n🐍 测试Python导入...")
    
    try:
        # 测试标准库
        import json
        import asyncio
        import datetime
        import logging
        print("  ✅ 标准库导入成功")
    except Exception as e:
        print(f"  ❌ 标准库导入失败: {e}")
        return False
    
    # 测试第三方库（可能未安装）
    optional_modules = [
        ('sqlalchemy', 'SQLAlchemy'),
        ('pandas', 'Pandas'),
        ('numpy', 'NumPy'),
        ('tensorflow', 'TensorFlow'),
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn')
    ]
    
    for module, name in optional_modules:
        try:
            __import__(module)
            print(f"  ✅ {name}")
        except ImportError:
            print(f"  ⚠️  {name} (未安装)")
    
    return True

def test_config_files():
    """测试配置文件"""
    print("\n⚙️  测试配置文件...")
    
    # 检查.env.example
    if Path('.env.example').exists():
        print("  ✅ .env.example 存在")
        
        # 读取内容
        with open('.env.example', 'r', encoding='utf-8') as f:
            content = f.read()
            
        required_configs = [
            'DATABASE_URL',
            'REDIS_URL', 
            'AMAP_API_KEY',
            'API_SECRET'
        ]
        
        for config in required_configs:
            if config in content:
                print(f"  ✅ {config} 配置项存在")
            else:
                print(f"  ❌ {config} 配置项缺失")
    else:
        print("  ❌ .env.example 不存在")
        return False
    
    return True

def test_database_connection():
    """测试数据库连接（简化版）"""
    print("\n🗄️  测试数据库连接...")
    
    try:
        # 尝试使用SQLite
        import sqlite3
        conn = sqlite3.connect(':memory:')
        conn.close()
        print("  ✅ SQLite 连接测试成功")
        return True
    except Exception as e:
        print(f"  ❌ 数据库连接失败: {e}")
        return False

def test_basic_functionality():
    """测试基本功能"""
    print("\n🧪 测试基本功能...")
    
    try:
        # 测试JSON处理
        import json
        test_data = {"test": "data", "number": 123}
        json_str = json.dumps(test_data)
        parsed = json.loads(json_str)
        print("  ✅ JSON 处理正常")
        
        # 测试异步功能
        import asyncio
        import datetime
        
        async def test_async():
            await asyncio.sleep(0.001)
            return "async works"
        
        result = asyncio.run(test_async())
        if result == "async works":
            print("  ✅ 异步功能正常")
        
        # 测试时间处理
        now = datetime.datetime.now()
        formatted = now.isoformat()
        print("  ✅ 时间处理正常")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 基本功能测试失败: {e}")
        return False

def generate_setup_instructions():
    """生成安装说明"""
    print("\n📋 安装说明:")
    print("1. 安装Python依赖:")
    print("   pip install -r requirements.txt")
    print("\n2. 配置环境变量:")
    print("   cp .env.example .env")
    print("   # 编辑 .env 文件，添加您的API密钥")
    print("\n3. 初始化数据库:")
    print("   python database.py")
    print("\n4. 启动系统:")
    print("   python start_enhanced_backend.py")
    print("\n📚 详细文档请参考: ENHANCED_SYSTEM_README.md")

def main():
    """主函数"""
    print("🚀 智能交通预测系统 v2.0 - 系统测试")
    print("=" * 50)
    
    # 运行测试
    tests = [
        ("文件结构", test_file_structure),
        ("Python导入", test_python_imports), 
        ("配置文件", test_config_files),
        ("数据库连接", test_database_connection),
        ("基本功能", test_basic_functionality)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 显示测试结果摘要
    print("\n📊 测试结果摘要:")
    print("=" * 30)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:15} {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(results)} 项测试通过")
    
    # 生成建议
    if passed == len(results):
        print("\n🎉 系统结构完整，可以开始安装依赖！")
    else:
        print("\n⚠️  请检查失败的测试项")
    
    generate_setup_instructions()
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
