#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
服务器配置文件
统一管理所有路径、依赖和配置
"""

import os
import sys
from pathlib import Path

# ========== 基础路径配置 ==========

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()

# 依赖目录配置
DEPENDENCIES_DIR = PROJECT_ROOT / "dependencies"
CHROME_DRIVER_DIR = DEPENDENCIES_DIR / "chrome_driver"
LATEX_DIR = DEPENDENCIES_DIR / "latex"
FONTS_DIR = DEPENDENCIES_DIR / "fonts"

# 输出目录配置
OUTPUT_DIR = PROJECT_ROOT / "output"
DOWNLOADS_DIR = OUTPUT_DIR / "downloads"
UPLOADS_DIR = OUTPUT_DIR / "uploads"
POSTER_OUTPUT_DIR = OUTPUT_DIR / "poster_output"
WEB_TRANSLATION_OUTPUT_DIR = OUTPUT_DIR / "web_translation_output"
IMAGE_TRANSLATION_OUTPUT_DIR = OUTPUT_DIR / "image_translation_output"
ORIGINAL_SNAPSHOT_DIR = OUTPUT_DIR / "original_snapshot"
TRANSLATED_SNAPSHOT_DIR = OUTPUT_DIR / "translated_snapshot"

# 日志目录
LOG_DIR = PROJECT_ROOT / "logs"

# 配置文件目录
CONFIG_DIR = PROJECT_ROOT / "config"

# ========== 创建必要目录 ==========

def create_directories():
    """创建所有必要的目录"""
    directories = [
        DEPENDENCIES_DIR,
        CHROME_DRIVER_DIR,
        LATEX_DIR,
        FONTS_DIR,
        OUTPUT_DIR,
        DOWNLOADS_DIR,
        UPLOADS_DIR,
        POSTER_OUTPUT_DIR,
        WEB_TRANSLATION_OUTPUT_DIR,
        IMAGE_TRANSLATION_OUTPUT_DIR,
        ORIGINAL_SNAPSHOT_DIR,
        TRANSLATED_SNAPSHOT_DIR,
        LOG_DIR,
        CONFIG_DIR
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✅ 创建目录: {directory}")

# ========== 系统依赖配置 ==========

# Chrome浏览器配置
CHROME_CONFIG = {
    "binary_location": "/usr/bin/google-chrome",  # Linux Chrome路径
    "driver_path": CHROME_DRIVER_DIR / "chromedriver",
    "headless": True,
    "no_sandbox": True,
    "disable_dev_shm_usage": True,
    "disable_gpu": True,
    "window_size": "1280,800"
}

# LaTeX配置
LATEX_CONFIG = {
    "pdflatex_path": "/usr/bin/pdflatex",  # Linux pdflatex路径
    "latexmk_path": "/usr/bin/latexmk",
    "texlive_path": "/usr/share/texlive",
    "miktex_path": None,  # Linux通常使用TeX Live
    "output_dir": LATEX_DIR,
    "temp_dir": LATEX_DIR / "temp"
}

# 字体配置
FONT_CONFIG = {
    "system_fonts": "/usr/share/fonts",
    "custom_fonts": FONTS_DIR,
    "default_font": "DejaVu Sans"
}

# ========== 环境变量配置 ==========

# 默认环境变量
DEFAULT_ENV = {
    "FLASK_ENV": "production",
    "FLASK_DEBUG": "0",
    "PORT": "8000",
    "HOST": "0.0.0.0",
    "WORKERS": "4",
    "TIMEOUT": "300",
    "MAX_REQUESTS": "1000",
    "MAX_REQUESTS_JITTER": "100"
}


# API密钥配置 (修正版)
API_CONFIG = {
    "openai_api_key_file": CONFIG_DIR / "openai_api_key.txt",
    "baidu_api_key_file": CONFIG_DIR / "baidu_api_key.txt",
    "baidu_secret_key_file": CONFIG_DIR / "baidu_secret_key.txt"
}

# ========== 服务器配置 ==========

# # Gunicorn配置
# GUNICORN_CONFIG = {
#     "bind": "0.0.0.0:8000",
#     "workers": 4,
#     "worker_class": "gevent",
#     "timeout": 300,
#     "max_requests": 1000,
#     "max_requests_jitter": 100,
#     "preload_app": True,
#     "access_logfile": LOG_DIR / "access.log",
#     "error_logfile": LOG_DIR / "error.log",
#     "loglevel": "info"
# }

# Gunicorn配置 (修正版)
GUNICORN_CONFIG = {
    "bind": "0.0.0.0:8000",
    "workers": 4,
    "worker_class": "gevent",
    "timeout": 300,
    "max_requests": 1000,
    "max_requests_jitter": 100,
    "preload_app": True,
    # --- 修改开始 ---
    # 直接使用字符串来定义路径，确保Gunicorn能正确解析
    "access_logfile": "logs/gunicorn_access.log",
    "error_logfile": "logs/gunicorn_error.log",
    # --- 修改结束 ---
    "loglevel": "info"
}


# 文件上传配置
UPLOAD_CONFIG = {
    "max_file_size": 50 * 1024 * 1024,  # 50MB
    "allowed_extensions": {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'},
    "upload_folder": UPLOADS_DIR
}

# ========== 日志配置 ==========

LOG_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": LOG_DIR / "app.log",
    "max_bytes": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5
}

# ========== 系统检查函数 ==========

def check_system_dependencies():
    """检查系统依赖是否安装"""
    import subprocess
    import shutil
    
    dependencies = {
        "Google Chrome": "/usr/bin/google-chrome",
        "ChromeDriver": get_chrome_driver_path(),
        "pdflatex": "/usr/bin/pdflatex",
        "latexmk": "/usr/bin/latexmk",
        "python3": shutil.which("python3"),
        "pip3": shutil.which("pip3")
    }
    
    missing = []
    available = []
    
    for name, path in dependencies.items():
        if path and (os.path.exists(path) or shutil.which(path)):
            available.append(name)
            print(f"✅ {name}: 已安装")
        else:
            missing.append(name)
            print(f"❌ {name}: 未找到")
    
    return available, missing

def check_python_dependencies():
    """检查Python依赖"""
    import importlib
    
    required_packages = [
        "flask", "selenium", "openai", "PIL", "requests", 
        "bs4", "gunicorn", "gevent", "psutil"
    ]
    
    missing = []
    available = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            available.append(package)
            print(f"✅ Python包 {package}: 已安装")
        except ImportError:
            missing.append(package)
            print(f"❌ Python包 {package}: 未安装")
    
    return available, missing

# ========== 路径获取函数 ==========

# def get_chrome_driver_path():
#     """获取ChromeDriver路径"""
#     driver_path = CHROME_DRIVER_DIR / "chromedriver"
#     if not driver_path.exists():
#         # 尝试从系统PATH查找
#         import shutil
#         system_driver = shutil.which("chromedriver")
#         if system_driver:
#             return system_driver
#     return str(driver_path)

def get_chrome_driver_path():
    return "/usr/local/bin/chromedriver"

def get_pdflatex_path():
    """获取pdflatex路径"""
    # 优先使用配置的路径
    if LATEX_CONFIG["pdflatex_path"] and os.path.exists(LATEX_CONFIG["pdflatex_path"]):
        return LATEX_CONFIG["pdflatex_path"]
    
    # 尝试从系统PATH查找
    import shutil
    system_pdflatex = shutil.which("pdflatex")
    if system_pdflatex:
        return system_pdflatex
    
    # 返回默认路径
    return "/usr/bin/pdflatex"

def get_output_path(file_type):
    """根据文件类型获取输出路径"""
    path_map = {
        "poster": POSTER_OUTPUT_DIR,
        "web_translation": WEB_TRANSLATION_OUTPUT_DIR,
        "image_translation": IMAGE_TRANSLATION_OUTPUT_DIR,
        "downloads": DOWNLOADS_DIR,
        "uploads": UPLOADS_DIR,
        "original_snapshot": ORIGINAL_SNAPSHOT_DIR,
        "translated_snapshot": TRANSLATED_SNAPSHOT_DIR
    }
    return path_map.get(file_type, OUTPUT_DIR)

# ========== 初始化函数 ==========

def initialize_server():
    """初始化服务器环境"""
    print("🚀 初始化服务器环境...")
    
    # 创建目录
    create_directories()
    
    # 检查系统依赖
    print("\n📋 检查系统依赖...")
    available_deps, missing_deps = check_system_dependencies()
    
    # 检查Python依赖
    print("\n📋 检查Python依赖...")
    available_packages, missing_packages = check_python_dependencies()
    
    # 输出检查结果
    if missing_deps:
        print(f"\n⚠️ 缺少系统依赖: {', '.join(missing_deps)}")
        print("请运行安装脚本: ./install_dependencies.sh")
    
    if missing_packages:
        print(f"\n⚠️ 缺少Python包: {', '.join(missing_packages)}")
        print("请运行: pip3 install -r requirements_server.txt")
    
    if not missing_deps and not missing_packages:
        print("\n✅ 所有依赖检查通过!")
    
    return len(missing_deps) == 0 and len(missing_packages) == 0

if __name__ == "__main__":
    initialize_server() 