#!/usr/bin/env python3
"""
智能文书翻译平台 - 新版后端安装脚本
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def print_banner():
    """打印安装横幅"""
    print("=" * 60)
    print("🚀 智能文书翻译平台 - 新版后端安装程序")
    print("=" * 60)
    print()

def check_python_version():
    """检查Python版本"""
    print("🔍 检查Python版本...")
    
    if sys.version_info < (3, 8):
        print("❌ 错误: 需要Python 3.8或更高版本")
        print(f"   当前版本: {sys.version}")
        return False
    
    print(f"✅ Python版本: {sys.version.split()[0]}")
    return True

def check_pip():
    """检查pip是否可用"""
    print("🔍 检查pip...")
    
    try:
        import pip
        print("✅ pip已安装")
        return True
    except ImportError:
        print("❌ pip未安装")
        return False

def install_dependencies():
    """安装Python依赖"""
    print("📦 安装Python依赖包...")
    
    try:
        # 升级pip
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                      check=True, capture_output=True)
        print("✅ pip已升级到最新版本")
        
        # 安装依赖
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True)
        print("✅ 所有依赖包安装完成")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 依赖安装失败: {e}")
        return False

def create_directories():
    """创建必要的目录"""
    print("📁 创建必要目录...")
    
    directories = [
        'uploads',
        'downloads', 
        'original_snapshot',
        'translated_snapshot',
        'poster_output',
        'web_translation_output',
        'image_translation_output',
        'user_files',
        'logs',
        'config'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ 创建目录: {directory}")

def create_config_file():
    """创建配置文件"""
    print("⚙️ 创建配置文件...")
    
    if not os.path.exists('.env'):
        if os.path.exists('config_example.env'):
            shutil.copy('config_example.env', '.env')
            print("✅ 已创建 .env 配置文件")
            print("💡 请编辑 .env 文件配置API密钥")
        else:
            print("⚠️ 配置模板文件不存在")
    else:
        print("ℹ️ 配置文件已存在，跳过创建")

def test_installation():
    """测试安装"""
    print("🧪 测试安装...")
    
    try:
        # 测试导入主要模块
        import flask
        import flask_sqlalchemy
        import flask_jwt_extended
        import requests
        import PIL
        print("✅ 核心模块导入成功")
        
        # 测试应用启动
        print("🔍 测试应用导入...")
        from app import app
        print("✅ 应用导入成功")
        
        return True
        
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 应用测试失败: {e}")
        return False

def print_next_steps():
    """打印后续步骤"""
    print("\n" + "=" * 60)
    print("🎉 安装完成！")
    print("=" * 60)
    print()
    print("📋 后续步骤:")
    print("1. 编辑 .env 文件配置API密钥（可选）")
    print("2. 启动服务: python run_server.py")
    print("3. 访问: http://localhost:5000")
    print("4. 测试API: python test_api.py")
    print()
    print("🔑 默认测试账户:")
    print("   邮箱: test@example.com")
    print("   密码: password123")
    print()
    print("📖 更多信息请查看 README.md")
    print()

def main():
    """主安装流程"""
    print_banner()
    
    # 检查Python版本
    if not check_python_version():
        sys.exit(1)
    
    # 检查pip
    if not check_pip():
        print("请先安装pip")
        sys.exit(1)
    
    # 安装依赖
    if not install_dependencies():
        print("依赖安装失败，请检查网络连接或手动安装")
        sys.exit(1)
    
    # 创建目录
    create_directories()
    
    # 创建配置文件
    create_config_file()
    
    # 测试安装
    if not test_installation():
        print("安装测试失败，请检查依赖是否正确安装")
        sys.exit(1)
    
    # 打印后续步骤
    print_next_steps()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ 安装被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 安装过程中发生错误: {e}")
        sys.exit(1)

