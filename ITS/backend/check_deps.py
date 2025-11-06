#!/usr/bin/env python3
"""检查依赖包安装状态"""

import sys

def check_package(package_name):
    """检查单个包"""
    try:
        __import__(package_name)
        print(f"✅ {package_name} - 已安装")
        return True
    except ImportError:
        print(f"❌ {package_name} - 未安装")
        return False

def main():
    """主函数"""
    print("检查Python依赖包状态...")
    print("=" * 40)
    
    packages = [
        'fastapi',
        'uvicorn', 
        'pydantic',
        'sqlalchemy',
        'pandas',
        'numpy',
        'scikit_learn',  # 注意导入名是sklearn
        'tensorflow',
        'websockets',
        'redis',
        'celery',
        'python_dotenv',
        'aiofiles',
        'httpx',
        'schedule',
        'plotly',
        'seaborn',
        'matplotlib'
    ]
    
    installed = 0
    total = len(packages)
    
    for package in packages:
        # 处理特殊的包名映射
        import_name = {
            'scikit_learn': 'sklearn',
            'python_dotenv': 'dotenv'
        }.get(package, package)
        
        if check_package(import_name):
            installed += 1
    
    print("=" * 40)
    print(f"总计: {installed}/{total} 个包已安装")
    
    if installed < total:
        print("\n缺失的包将导致预测功能失败。")
        print("请运行以下命令安装依赖：")
        print("pip install -r requirements.txt")
        return False
    else:
        print("\n所有依赖包已正确安装！")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
