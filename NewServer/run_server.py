#!/usr/bin/env python3
"""
智能文书翻译平台 - 新版后端启动脚本
"""

import os
import sys
from pathlib import Path

def setup_environment():
    """设置环境"""
    print("🔧 设置运行环境...")
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("❌ 错误: 需要Python 3.8或更高版本")
        sys.exit(1)
    
    print(f"✅ Python版本: {sys.version}")
    
    # 检查必要的目录
    directories = [
        'uploads',
        'downloads', 
        'original_snapshot',
        'translated_snapshot',
        'poster_output',
        'web_translation_output',
        'image_translation_output',
        'user_files'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 目录检查: {directory}")
    
    print("✅ 目录结构准备完成")

def check_dependencies():
    """检查依赖包"""
    print("\n📦 检查依赖包...")
    
    required_packages = [
        'flask',
        'flask_cors',
        'flask_sqlalchemy', 
        'flask_migrate',
        'flask_jwt_extended',
        'selenium',
        'requests',
        'openai',
        'PIL'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            if package == 'PIL':
                import PIL
            else:
                __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - 缺失")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️ 缺失依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements_new.txt")
        return False
    
    print("✅ 所有依赖包检查完成")
    return True

def main():
    """主函数"""
    print("=" * 60)
    print("🚀 智能文书翻译平台 - 新版后端启动脚本")
    print("=" * 60)
    
    # 设置环境
    setup_environment()
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请安装缺失的包后重试")
        sys.exit(1)
    
    print("\n🌟 环境检查完成，启动后端服务...")
    print("💡 浏览器访问: http://localhost:5000")
    print("📖 API文档: http://localhost:5000")
    print("🔧 健康检查: http://localhost:5000/health")
    print("🧪 测试接口: http://localhost:5000/api/test")
    print()
    print("🔑 测试用户:")
    print("   邮箱: test@example.com")
    print("   密码: password123")
    print()
    print("按 Ctrl+C 停止服务")
    print("-" * 60)
    
    # 启动应用
    try:
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()
