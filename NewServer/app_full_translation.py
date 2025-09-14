# 完整版翻译功能集成后端
# 基于app_with_translation.py，添加完整的翻译功能

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, get_jwt
from sqlalchemy import text
import os
import time
import base64
import re
import json
import math
import asyncio
import subprocess
import argparse
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

# 尝试导入翻译相关的库
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

try:
    from pyppeteer import launch
    from PIL import Image
    PYPPETEER_AVAILABLE = True
except ImportError:
    PYPPETEER_AVAILABLE = False
    print("⚠️ 警告: pyppeteer 或 PIL 未安装，部分PDF生成功能可能不可用")

# 创建Flask应用
app = Flask(__name__)
CORS(app)

# 配置
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///translation_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-this-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# 初始化扩展
db = SQLAlchemy(app)
jwt = JWTManager(app)

# 创建必要的文件夹
os.makedirs('downloads', exist_ok=True)
os.makedirs('original_snapshot', exist_ok=True)
os.makedirs('translated_snapshot', exist_ok=True)
os.makedirs('poster_output', exist_ok=True)
os.makedirs('web_translation_output', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('image_translation_output', exist_ok=True)
os.makedirs('formula_output', exist_ok=True)


# JWT Token黑名单存储
blacklisted_tokens = set()

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    return jwt_payload['jti'] in blacklisted_tokens

# ========== 工具函数 ========== 

def log_message(message, level="INFO"):
    """统一的日志输出函数"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

def load_api_keys():
    """加载API密钥"""
    keys = {}
    
    # 首先从老后端方式的单独文件读取百度API密钥
    baidu_files = {
        'BAIDU_API_KEY': 'config/baidu_api_key.txt',
        'BAIDU_SECRET_KEY': 'config/baidu_secret_key.txt'
    }
    
    for key_name, file_path in baidu_files.items():
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    value = f.read().strip()
                    if value:
                        keys[key_name] = value
                        log_message(f"从 {file_path} 加载了 {key_name}", "INFO")
            except Exception as e:
                log_message(f"读取 {file_path} 失败: {e}", "WARNING")
    
    # 然后从config.env文件加载其他配置
    config_path = "config.env"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#') and line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # 如果百度密钥还没有从单独文件读取到，则从config.env读取
                        if key not in keys:
                            keys[key] = value
            log_message(f"从配置文件 config.env 加载了额外配置", "INFO")
        except Exception as e:
            log_message(f"读取配置文件失败: {e}", "WARNING")
    
    # 从环境变量加载（优先级更高）
    keys.update({
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', keys.get('OPENAI_API_KEY', '')),
        'BAIDU_API_KEY': os.getenv('BAIDU_API_KEY', keys.get('BAIDU_API_KEY', '')),
        'BAIDU_SECRET_KEY': os.getenv('BAIDU_SECRET_KEY', keys.get('BAIDU_SECRET_KEY', ''))
    })
    
    # 打印配置状态（不显示实际密钥）
    log_message(f"OpenAI API: {'已配置' if keys.get('OPENAI_API_KEY') else '未配置'}", "INFO")
    log_message(f"百度API: {'已配置' if keys.get('BAIDU_API_KEY') else '未配置'}", "INFO")
    
    return keys

# ========== 数据库模型 ========== 

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    clients = db.relationship('Client', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'uid': self.id,
            'name': self.name,
            'email': self.email,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    case_type = db.Column(db.String(100))
    case_date = db.Column(db.String(20))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    materials = db.relationship('Material', backref='client', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'cid': self.id,
            'name': self.name,
            'caseType': self.case_type,
            'caseDate': self.case_date,
            'createdAt': self.created_at.isoformat(),
            'updatedAt': self.updated_at.isoformat()
        }

class Material(db.Model):
    __tablename__ = 'materials'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), default='待处理')
    confirmed = db.Column(db.Boolean, default=False)
    selected_result = db.Column(db.String(20), default='latex')
    original_filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    url = db.Column(db.String(1000))
    # 翻译结果字段
    translated_image_path = db.Column(db.String(500))  # 翻译后的图片路径
    translation_text_info = db.Column(db.Text)  # JSON格式的文本信息
    translation_error = db.Column(db.Text)  # API翻译错误信息
    latex_translation_result = db.Column(db.Text)  # LaTeX翻译结果
    latex_translation_error = db.Column(db.Text)  # LaTeX翻译错误信息
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        # 解析翻译文本信息
        text_info = None
        if self.translation_text_info:
            try:
                import json
                text_info = json.loads(self.translation_text_info)
            except:
                text_info = None
        
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'status': self.status,
            'confirmed': self.confirmed,
            'selectedResult': self.selected_result,
            'originalFilename': self.original_filename,
            'url': self.url,
            'clientId': self.client_id,
            'createdAt': self.created_at.isoformat(),
            'updatedAt': self.updated_at.isoformat(),
            # 翻译结果
            'translatedImagePath': self.translated_image_path,
            'translationTextInfo': text_info,
            'translationError': self.translation_error,
            'latexTranslationResult': self.latex_translation_result,
            'latexTranslationError': self.latex_translation_error
        }

class PosterTranslator:
    """海报翻译类，处理从图像到PDF的完整流程（增强版）"""
    
    def __init__(self, api_key=None, pdflatex_path=None):
        """
        初始化海报翻译器
        
        Args:
            api_key (str): OpenAI API密钥
            pdflatex_path (str): pdflatex.exe的路径，如果为None则使用默认路径
        """
        # 配置API密钥
        self.api_key = api_key or self._load_api_key()
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
            self.log("✅ OpenAI API密钥已配置", "SUCCESS")
        else:
            self.client = None
            self.log("⚠️ OpenAI API密钥未设置", "WARNING")
        
        # 智能检测pdflatex路径
        self.pdflatex_path = self._detect_pdflatex_path(pdflatex_path)
        
        # 定义海报转LaTeX的详细提示词
        self.custom_prompt = """
Upload a poster image and generate \"directly compilable LaTeX code\" that faithfully reproduces the layout of the poster, including all poster information. The requirements are as follows:

Layout Reproduction:
Analyze each image individually and accurately reproduce its geometric layout and content distribution. Do not omit any poster information. For guest photos, preserve the original geometric structure (e.g., horizontal row, triangular layout, etc.) by using rectangular boxes as placeholders with the word \"Photo\" centered inside. Ensure that each photo placeholder is immediately followed by the corresponding guest's name and title (and any additional provided information) in a clearly arranged manner. Arrange these photo blocks in a visually balanced way, ensuring minimal but sufficient spacing.

Text and Typography:
Translate all content into English, including the title, event time, agenda table, guest information, and placeholder descriptions. The title's font size should be slightly larger than the body text to maintain visual hierarchy (use \large or \Large, but not \huge or \Huge). Keep the overall layout compact by avoiding excessive vertical skips. Bold guest names and titles moderately. The body text and agenda table must remain clear and easy to read.

Complete Page Layout:
Ensure that all content fits within the page boundaries without overflowing. Keep margins and line spacing balanced so that the final design is neither too cramped nor too sparse. Avoid large empty spaces and big gaps between sections. Ensure the poster retains a single-page layout if possible.

Image and Text Alignment:
Ensure that guest photos and their corresponding names/titles are strictly aligned. Even if some guest descriptions are longer, maintain a neat and well-aligned overall appearance.

Table Formatting:
Use reasonable column widths and clear lines for the agenda table. To avoid odd line breaks, you can use packages such as tabularx or array if needed. All table content must be in English, with accurate times and topics. Avoid splitting rows across lines and ensure consistent horizontal and vertical alignment.

Additional Table Formatting Precautions:
When formatting tables, ensure that multi-line content within any table cell is enclosed in braces (e.g., { ... }) or placed inside a minipage. This prevents the line break command (\\) used within a cell from being mistaken as the end of a row, avoiding extra alignment tab errors.

Placeholder Consistency:
Use rectangular boxes for guest photos, with the word \"Photo\" centered inside, and if a QR code is present, use a rectangular box labeled \"QR Code\" centered inside. Absolutely do not use \"Image\" or any other text label for these placeholders. Each placeholder must read \"Photo\" to indicate a person's picture. Keep placeholders sized appropriately so they align well with the text.

Strict No-External-Files Policy:
The generated LaTeX code must be 100% self-contained. It must NOT under any circumstances reference external files.
- Absolutely forbid the use of the \includegraphics command.
- All visual elements, including placeholders for photos and QR codes, must be drawn using native LaTeX commands.
- For a photo placeholder, you MUST use a `\\fbox` or `\\framebox` containing the word \"Photo\". For example: `\\fbox{\\parbox[c][1.5cm][c]{2.5cm}{\\centering Photo}}`. Do not use any other method.
- The final output must compile without needing any external image files like .jpg, .png, etc. The entire PDF must be generated from this single .tex file alone.

Special Character Escaping:
Ensure that all special characters, especially the ampersand (&) within any text, are properly escaped (for example, replace any \"&\" with \\&\\) so that the generated LaTeX code compiles without errors.

Style Restrictions:
Do not use any color commands (such as \\extcolor, \\color, or \\usepackage{xcolor}) in the generated LaTeX code. Additionally, do not use the commands \\huge or \\Huge anywhere in the code; if emphasis is needed, only use \\large or \\Large. This is to ensure the layout remains compact, elegant, and adheres strictly to the design guidelines.

Only return the raw LaTeX code. Do not enclose it in triple backticks, markdown, or any additional formatting. The output should start with \documentclass and end with \end{document} exactly, with no extra characters or quotes.

Output Requirement:
Output complete LaTeX source code that the user can compile directly without any modifications. The layout must be compact and aesthetically pleasing, while also exuding a sense of grandeur and elegance. Ensure refined margins, minimal whitespace, and balanced spacing so that the final design is both tight and visually imposing.
"""

    def _detect_pdflatex_path(self, custom_path=None):
        """智能检测pdflatex路径"""
        self.log("正在检测pdflatex路径...", "DEBUG")
        
        # 如果提供了自定义路径，先尝试
        if custom_path and os.path.exists(custom_path):
            self.log(f"使用自定义pdflatex路径: {custom_path}", "SUCCESS")
            return custom_path
        
        # 常见的MiKTeX安装路径（Windows）
        common_paths = [
            r"F:\\tex\\miktex\\bin\\x64\\pdflatex.exe",  # 原始路径
            r"C:\\Program Files\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe",
            r"C:\\Users\\{}\\AppData\\Local\\Programs\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe".format(os.getenv('USERNAME', '')),
            r"C:\\Program Files (x86)\\MiKTeX\\miktex\\bin\\pdflatex.exe",
            r"D:\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe",
            r"E:\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe"
        ]
        
        # 检查常见路径
        for path in common_paths:
            if os.path.exists(path):
                self.log(f"找到pdflatex: {path}", "SUCCESS")
                return path
        
        # 检查系统PATH
        try:
            result = subprocess.run(["pdflatex", "--version"], 
                                 check=True, capture_output=True, text=True, timeout=10)
            self.log("在系统PATH中找到pdflatex", "SUCCESS")
            return "pdflatex"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # 如果都找不到，返回默认路径并记录警告
        default_path = r"F:\\tex\\miktex\\bin\\x64\\pdflatex.exe"
        self.log(f"未找到pdflatex，使用默认路径: {default_path}", "WARNING")
        return default_path

    def log(self, message, level="INFO"):
        """详细状态日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ️",
            "SUCCESS": "✅", 
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }
        print(f"[{timestamp}] {prefix.get(level, 'ℹ️')} {message}")

    def _load_api_key(self):
        """从环境变量或配置文件加载API密钥"""
        self.log("正在查找OpenAI API密钥...", "DEBUG")
        
        # 尝试从环境变量获取
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            self.log("从环境变量获取API密钥", "DEBUG")
            return api_key
        
        # 尝试从配置文件获取
        # config_files = ['api_key.txt', 'openai_key.txt', 'config.json']
        config_files = ['config/openai_api_key.txt', 'api_key.txt', 'openai_key.txt', 'config.json']
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    self.log(f"尝试从 {config_file} 读取API密钥", "DEBUG")
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if config_file.endswith('.json'):
                            data = json.loads(content)
                            return data.get('openai_api_key') or data.get('api_key')
                        else:
                            return content
                except Exception as e:
                    self.log(f"读取配置文件 {config_file} 失败: {e}", "WARNING")
        
        self.log("未找到API密钥配置", "WARNING")
        return None

    def check_requirements(self):
        """详细检查运行环境和要求"""
        self.log("🔍 开始详细环境检查...", "INFO")
        
        check_results = {
            "api_key": {"status": False, "details": [], "solutions": []},
            "pdflatex": {"status": False, "details": [], "solutions": []},
            "python_modules": {"status": False, "details": [], "solutions": []},
            "file_permissions": {"status": False, "details": [], "solutions": []}
        }
        
        # 1. 详细检查API密钥
        self.log("步骤1: 检查OpenAI API密钥配置", "DEBUG")
        api_check = self._check_api_key_detailed()
        check_results["api_key"] = api_check
        
        # 2. 详细检查pdflatex
        self.log("步骤2: 检查LaTeX环境", "DEBUG")
        latex_check = self._check_pdflatex_detailed()
        check_results["pdflatex"] = latex_check
        
        # 3. 检查Python模块
        self.log("步骤3: 检查Python模块依赖", "DEBUG")
        modules_check = self._check_python_modules()
        check_results["python_modules"] = modules_check
        
        # 4. 检查文件权限
        self.log("步骤4: 检查文件系统权限", "DEBUG")
        permissions_check = self._check_file_permissions()
        check_results["file_permissions"] = permissions_check
        
        # 汇总检查结果
        all_passed = all(result["status"] for result in check_results.values())
        
        if all_passed:
            self.log("🎉 所有环境检查通过!", "SUCCESS")
            return True
        else:
            self._generate_detailed_error_report(check_results)
            return False

    def _check_api_key_detailed(self):
        """详细检查API密钥配置"""
        result = {"status": False, "details": [], "solutions": []}
        
        # 检查环境变量
        env_key = os.getenv('OPENAI_API_KEY')
        if env_key:
            result["details"].append("✅ 环境变量 OPENAI_API_KEY 存在")
            if len(env_key.strip()) > 0:
                result["details"].append(f"✅ 密钥长度: {len(env_key)} 字符")
                if env_key.startswith('sk-'):
                    result["details"].append("✅ 密钥格式正确 (以sk-开头)")
                    result["status"] = True
                else:
                    result["details"].append("⚠️ 密钥格式可能有误 (不以sk-开头)")
                    result["solutions"].append("检查密钥是否为有效的OpenAI API密钥")
            else:
                result["details"].append("❌ 环境变量为空")
                result["solutions"].append("设置有效的OPENAI_API_KEY环境变量")
        else:
            result["details"].append("❌ 环境变量 OPENAI_API_KEY 未设置")
        
        # 检查配置文件
        config_files = [
            'config/openai_api_key.txt',
            'api_key.txt', 
            'openai_key.txt', 
            'config.json'
        ]
        
        found_config = False
        for config_file in config_files:
            if os.path.exists(config_file):
                found_config = True
                result["details"].append(f"✅ 找到配置文件: {config_file}")
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if config_file.endswith('.json'):
                            data = json.loads(content)
                            key = data.get('openai_api_key') or data.get('api_key')
                            if key:
                                result["details"].append("✅ JSON配置文件包含API密钥")
                                if not result["status"] and key.startswith('sk-'):
                                    result["status"] = True
                            else:
                                result["details"].append("❌ JSON配置文件缺少API密钥字段")
                        else:
                            if content and content.startswith('sk-'):
                                result["details"].append("✅ 配置文件包含有效格式的API密钥")
                                if not result["status"]:
                                    result["status"] = True
                            else:
                                result["details"].append("❌ 配置文件密钥格式无效")
                except Exception as e:
                    result["details"].append(f"❌ 读取配置文件失败: {e}")
                    result["solutions"].append(f"检查文件 {config_file} 的权限和格式")
                break
        
        if not found_config and not env_key:
            result["details"].append("❌ 未找到任何API密钥配置")
            result["solutions"].extend([
                "方案1: 设置环境变量 OPENAI_API_KEY",
                "方案2: 创建 config/openai_api_key.txt 文件并写入密钥",
                "方案3: 创建 api_key.txt 文件并写入密钥",
                "请访问 https://platform.openai.com/account/api-keys 获取API密钥"
            ])
        
        return result

    def _check_pdflatex_detailed(self):
        """详细检查pdflatex环境"""
        result = {"status": False, "details": [], "solutions": []}
        
        # 检查配置的路径
        if self.pdflatex_path != "pdflatex":
            result["details"].append(f"🔍 检查配置路径: {self.pdflatex_path}")
            if os.path.exists(self.pdflatex_path):
                result["details"].append("✅ 配置路径存在")
                # 检查文件权限
                if os.access(self.pdflatex_path, os.X_OK):
                    result["details"].append("✅ 文件具有执行权限")
                    try:
                        # 测试执行
                        proc = subprocess.run([self.pdflatex_path, "--version"], 
                                            capture_output=True, text=True, timeout=10)
                        if proc.returncode == 0:
                            version_info = proc.stdout.split('\n')[0] if proc.stdout else "未知版本"
                            result["details"].append(f"✅ pdflatex版本: {version_info}")
                            result["status"] = True
                        else:
                            result["details"].append(f"❌ pdflatex执行失败: {proc.stderr}")
                            result["solutions"].append("检查pdflatex安装是否完整")
                    except subprocess.TimeoutExpired:
                        result["details"].append("❌ pdflatex执行超时")
                        result["solutions"].append("检查pdflatex是否响应")
                    except Exception as e:
                        result["details"].append(f"❌ pdflatex执行异常: {e}")
                else:
                    result["details"].append("❌ 文件没有执行权限")
                    result["solutions"].append(f"授予执行权限: chmod +x {self.pdflatex_path}")
            else:
                result["details"].append("❌ 配置路径不存在")
                result["solutions"].append("检查路径是否正确或重新安装LaTeX")
        
        # 检查系统PATH
        result["details"].append("🔍 检查系统PATH中的pdflatex")
        try:
            proc = subprocess.run(["pdflatex", "--version"], 
                                capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                result["details"].append("✅ 系统PATH中找到pdflatex")
                version_info = proc.stdout.split('\n')[0] if proc.stdout else "未知版本"
                result["details"].append(f"✅ 系统pdflatex版本: {version_info}")
                if not result["status"]:
                    result["status"] = True
            else:
                result["details"].append("❌ 系统PATH中pdflatex执行失败")
        except subprocess.TimeoutExpired:
            result["details"].append("❌ 系统pdflatex执行超时")
        except FileNotFoundError:
            result["details"].append("❌ 系统PATH中未找到pdflatex")
        except Exception as e:
            result["details"].append(f"❌ 系统pdflatex检查异常: {e}")
        
        # 检查常见的LaTeX发行版
        common_latex_paths = [
            "C:\\Program Files\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe",
            "C:\\Users\\{username}\\AppData\\Local\\Programs\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe",
            "/usr/bin/pdflatex",
            "/usr/local/bin/pdflatex",
            "/Library/TeX/texbin/pdflatex"
        ]
        
        username = os.getenv('USERNAME', os.getenv('USER', ''))
        result["details"].append("🔍 检查常见LaTeX安装位置")
        found_latex = False
        
        for path_template in common_latex_paths:
            path = path_template.replace('{username}', username)
            if os.path.exists(path):
                result["details"].append(f"✅ 找到LaTeX安装: {path}")
                found_latex = True
                if not result["status"]:
                    # 更新配置建议
                    result["solutions"].append(f"可以手动设置路径: {path}")
                break
        
        if not found_latex:
            result["details"].append("❌ 未找到常见的LaTeX安装")
        
        # 添加安装建议
        if not result["status"]:
            result["solutions"].extend([
                "安装建议:",
                "Windows: 下载并安装 MiKTeX (https://miktex.org/download)",
                "macOS: 安装 MacTeX (https://www.tug.org/mactex/)",
                "Linux: sudo apt-get install texlive-latex-base",
                "安装后重启命令行或IDE",
                "确保LaTeX程序添加到系统PATH"
            ])
        
        return result

    def _check_python_modules(self):
        """检查Python模块依赖"""
        result = {"status": True, "details": [], "solutions": []}
        
        required_modules = [
            ('openai', 'OpenAI API客户端'),
            ('PIL', 'Python图像处理库'),
            ('pathlib', 'Python路径处理'),
            ('base64', 'Base64编码'),
            ('json', 'JSON处理'),
            ('subprocess', '子进程管理'),
            ('os', '操作系统接口')
        ]
        
        missing_modules = []
        for module_name, description in required_modules:
            try:
                __import__(module_name)
                result["details"].append(f"✅ {module_name}: {description}")
            except ImportError:
                result["details"].append(f"❌ {module_name}: {description} - 缺失")
                missing_modules.append(module_name)
        
        if missing_modules:
            result["status"] = False
            result["solutions"].append(f"安装缺失的模块: pip install {' '.join(missing_modules)}")
        
        return result

    def _check_file_permissions(self):
        """检查文件系统权限"""
        result = {"status": True, "details": [], "solutions": []}
        
        # 检查输出目录权限
        output_dirs = ['poster_output', 'uploads', 'downloads']
        
        for dir_name in output_dirs:
            try:
                os.makedirs(dir_name, exist_ok=True)
                # 测试写入权限
                test_file = os.path.join(dir_name, 'test_permission.tmp')
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)
                result["details"].append(f"✅ {dir_name}: 读写权限正常")
            except PermissionError:
                result["details"].append(f"❌ {dir_name}: 权限不足")
                result["status"] = False
                result["solutions"].append(f"授予目录写入权限: {dir_name}")
            except Exception as e:
                result["details"].append(f"❌ {dir_name}: 检查失败 - {e}")
                result["status"] = False
        
        return result

    def _generate_detailed_error_report(self, check_results):
        """生成详细的错误报告"""
        self.log("=" * 60, "ERROR")
        self.log("🚨 环境检查失败 - 详细报告", "ERROR")
        self.log("=" * 60, "ERROR")
        
        for category, result in check_results.items():
            status_icon = "✅" if result["status"] else "❌"
            category_name = {
                "api_key": "OpenAI API密钥",
                "pdflatex": "LaTeX环境",
                "python_modules": "Python模块",
                "file_permissions": "文件权限"
            }.get(category, category)
            
            self.log(f"\n{status_icon} {category_name}:", "ERROR" if not result["status"] else "SUCCESS")
            
            for detail in result["details"]:
                print(f"   {detail}")
            
            if result["solutions"] and not result["status"]:
                self.log("   💡 解决方案:", "WARNING")
                for i, solution in enumerate(result["solutions"], 1):
                    print(f"      {i}. {solution}")
        
        self.log("\n" + "=" * 60, "ERROR")
        self.log("请解决上述问题后重试", "ERROR")
        self.log("=" * 60, "ERROR")

    def check_requirements_with_details(self):
        """检查环境并返回详细结果（用于API响应）"""
        self.log("🔍 开始详细环境检查...", "INFO")
        
        check_results = {
            "api_key": {"status": False, "details": [], "solutions": []},
            "pdflatex": {"status": False, "details": [], "solutions": []},
            "python_modules": {"status": False, "details": [], "solutions": []},
            "file_permissions": {"status": False, "details": [], "solutions": []}
        }
        
        # 执行各项检查
        check_results["api_key"] = self._check_api_key_detailed()
        check_results["pdflatex"] = self._check_pdflatex_detailed()
        check_results["python_modules"] = self._check_python_modules()
        check_results["file_permissions"] = self._check_file_permissions()
        
        # 汇总结果
        all_passed = all(result["status"] for result in check_results.values())
        
        if all_passed:
            self.log("🎉 所有环境检查通过!", "SUCCESS")
            return {
                'success': True,
                'message': '环境检查通过'
            }
        else:
            # 生成详细报告
            self._generate_detailed_error_report(check_results)
            
            # 准备API响应数据
            error_summary = []
            all_details = {}
            all_solutions = []
            
            for category, result in check_results.items():
                category_name = {
                    "api_key": "OpenAI API密钥",
                    "pdflatex": "LaTeX环境", 
                    "python_modules": "Python模块",
                    "file_permissions": "文件权限"
                }.get(category, category)
                
                if not result["status"]:
                    error_summary.append(f"❌ {category_name}: 检查失败")
                    all_details[category_name] = {
                        'details': result["details"],
                        'solutions': result["solutions"]
                    }
                    all_solutions.extend(result["solutions"])
                else:
                    error_summary.append(f"✅ {category_name}: 正常")
            
            return {
                'success': False,
                'error_summary': '; '.join(error_summary),
                'details': all_details,
                'solutions': all_solutions
            }

    def validate_image_file(self, image_path):
        """验证图像文件"""
        self.log(f"验证图像文件: {image_path}", "DEBUG")
        
        if not os.path.exists(image_path):
            self.log(f"文件不存在: {image_path}", "ERROR")
            return False
        
        if not os.path.isfile(image_path):
            self.log(f"不是文件: {image_path}", "ERROR")
            return False
        
        file_size = os.path.getsize(image_path)
        if file_size == 0:
            self.log(f"文件大小为0: {image_path}", "ERROR")
            return False
        
        self.log(f"文件验证通过，大小: {file_size} bytes", "SUCCESS")
        return True

    def encode_image_to_base64(self, image_path):
        """
        将图像文件编码为base64格式
        
        Args:
            image_path (str): 图像文件路径
            
        Returns:
            str: base64编码的图像数据
        """
        try:
            self.log(f"编码图像文件: {image_path}", "DEBUG")
            
            if not self.validate_image_file(image_path):
                raise FileNotFoundError(f"图像文件验证失败: {image_path}")
            
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                image_base64 = base64.b64encode(image_data).decode("utf-8")
            
            self.log(f"图像编码成功，数据长度: {len(image_base64)} 字符", "SUCCESS")
            return image_base64
            
        except FileNotFoundError as e:
            self.log(f"文件未找到: {str(e)}", "ERROR")
            raise
        except Exception as e:
            self.log(f"图像编码失败: {str(e)}", "ERROR")
            raise Exception(f"图像编码失败: {str(e)}")

    def poster_to_latex(self, image_path, output_tex_file="output.tex"):
        """
        将海报图像转换为LaTeX代码
        
        Args:
            image_path (str): 海报图像路径
            output_tex_file (str): 输出的LaTeX文件名
            
        Returns:
            str: 生成的LaTeX代码
        """
        self.log(f"开始分析海报图像: {image_path}", "INFO")
        
        if not self.client:
            raise Exception("OpenAI API密钥未设置，无法生成LaTeX代码")
        
        # 编码图像
        image_base64 = self.encode_image_to_base64(image_path)
        
        # 确定图像MIME类型
        image_ext = Path(image_path).suffix.lower()
        if image_ext in ['.png']:
            mime_type = "image/png"
        elif image_ext in ['.jpg', '.jpeg']:
            mime_type = "image/jpeg"
        else:
            mime_type = "image/png"  # 默认为PNG
        
        self.log(f"图像类型: {mime_type}", "DEBUG")
        
        # 构建图像payload
        image_payload = {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{image_base64}"
            }
        }
        
        # 调用OpenAI API
        self.log("调用OpenAI API生成LaTeX代码...", "INFO")
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that outputs complete LaTeX code for poster layout recreation."
                    },
                    {"role": "user", "content": self.custom_prompt},
                    {"role": "user", "content": [image_payload]}
                ]
            )
            
            # latex_code = response.choices[0].message.content
            raw_response = response.choices[0].message.content

            # --- START: 这是我们新增的清理代码 ---
            self.log("正在清理AI返回的LaTeX代码...", "DEBUG")
            
            # 首先尝试移除Markdown代码块标记
            cleaned_code = re.sub(r'^```(latex)?\s*', '', raw_response, flags=re.MULTILINE)
            cleaned_code = re.sub(r'```\s*$', '', cleaned_code, flags=re.MULTILINE)
            
            # 如果AI返回的内容包含说明文字，尝试提取LaTeX代码部分
            # 查找 \documentclass 开始的位置
            documentclass_match = re.search(r'\\documentclass', cleaned_code)
            if documentclass_match:
                # 从 \documentclass 开始提取
                latex_start = documentclass_match.start()
                cleaned_code = cleaned_code[latex_start:]
                self.log("检测到说明文字，已提取LaTeX代码部分", "DEBUG")
            
            # 查找 \end{document} 结束的位置
            end_document_match = re.search(r'\\end\{document\}', cleaned_code)
            if end_document_match:
                # 提取到 \end{document} 结束
                latex_end = end_document_match.end()
                cleaned_code = cleaned_code[:latex_end]
                self.log("已截取到LaTeX代码结束位置", "DEBUG")
            
            # 移除开头和结尾可能存在的任何空白字符
            latex_code = cleaned_code.strip()
            # --- END: 清理代码结束 ---
            self.log("LaTeX代码生成成功!", "SUCCESS")
            
            # 保存LaTeX代码到文件
            try:
                with open(output_tex_file, "w", encoding="utf-8") as f:
                    f.write(latex_code)
                self.log(f"LaTeX代码已保存到: {output_tex_file}", "SUCCESS")
            except Exception as e:
                self.log(f"保存LaTeX文件失败: {e}", "ERROR")
                raise
            
            return latex_code
            
        except Exception as e:
            self.log(f"OpenAI API调用失败: {str(e)}", "ERROR")
            raise Exception(f"OpenAI API调用失败: {str(e)}")

    def compile_tex_to_pdf(self, tex_filename):
        """
        编译LaTeX文件为PDF（增强版）
        
        Args:
            tex_filename (str): LaTeX文件名
            
        Returns:
            str: 生成的PDF文件路径
        """
        try:
            self.log(f"开始编译LaTeX文件: {tex_filename}", "INFO")
            
            if not os.path.exists(tex_filename):
                raise FileNotFoundError(f"LaTeX文件不存在: {tex_filename}")
            
            # 检查LaTeX文件内容
            file_size = os.path.getsize(tex_filename)
            self.log(f"LaTeX文件大小: {file_size} bytes", "DEBUG")
            
            if file_size == 0:
                raise Exception("LaTeX文件为空")
            
            # 确定pdflatex命令
            pdflatex_cmd = self._get_pdflatex_command()
            
            # 编译LaTeX文件 - 获取文件所在目录
            tex_dir = os.path.dirname(os.path.abspath(tex_filename))
            tex_basename = os.path.basename(tex_filename)
            
            self.log("执行pdflatex编译...", "DEBUG")
            self.log(f"工作目录: {tex_dir}", "DEBUG")
            self.log(f"编译文件: {tex_basename}", "DEBUG")
            self.log(f"使用命令: {pdflatex_cmd}", "DEBUG")
            
            # 清理之前的辅助文件
            self._cleanup_before_compile(tex_filename)
            
            # 尝试编译（可能需要多次）
            max_attempts = 2
            for attempt in range(max_attempts):
                self.log(f"编译尝试 {attempt + 1}/{max_attempts}", "INFO")
                
                try:
                    result = subprocess.run(
                        [pdflatex_cmd, "-interaction=nonstopmode", "-halt-on-error", tex_basename], 
                        capture_output=True, text=True, cwd=tex_dir, timeout=60
                    )
                except UnicodeDecodeError:
                    # 如果出现编码问题，使用错误忽略模式
                    result = subprocess.run(
                        [pdflatex_cmd, "-interaction=nonstopmode", "-halt-on-error", tex_basename], 
                        capture_output=True, text=True, cwd=tex_dir, errors='ignore', timeout=60
                    )
                except subprocess.TimeoutExpired:
                    raise Exception("pdflatex编译超时（60秒）")
                
                # 详细的错误分析
                if result.returncode != 0:
                    self.log(f"编译尝试 {attempt + 1} 失败，返回码: {result.returncode}", "ERROR")
                    
                    # 分析错误类型
                    error_analysis = self._analyze_compilation_error(result.stdout, result.stderr)
                    
                    if error_analysis["is_miktex_update_issue"]:
                        raise Exception(
                            "MiKTeX需要更新。请按以下步骤操作：\n" 
                            "1. 打开 MiKTeX Console (管理员模式)\n" 
                            "2. 点击 'Check for updates'\n" 
                            "3. 安装所有可用更新\n" 
                            "4. 重启应用程序\n" 
                            f"详细错误: {error_analysis['error_message']}"
                        )
                    
                    if error_analysis["is_missing_package"]:
                        self.log(f"检测到缺失包: {error_analysis['missing_packages']}", "WARNING")
                        if attempt < max_attempts - 1:
                            self.log("尝试自动安装缺失包...", "INFO")
                            self._install_missing_packages(error_analysis['missing_packages'])
                            continue
                    
                    if attempt == max_attempts - 1:
                        # 最后一次尝试失败，输出详细错误
                        self._output_detailed_error(result.stdout, result.stderr, tex_filename)
                        raise Exception(f"pdflatex编译失败，返回码: {result.returncode}")
                else:
                    self.log("pdflatex编译成功!", "SUCCESS")
                    if result.stdout:
                        self.log(f"编译输出摘要: {result.stdout[:200]}...", "DEBUG")
                    break
            
            # 检查PDF是否生成
            pdf_filename = tex_filename.replace(".tex", ".pdf")
            if os.path.exists(pdf_filename):
                pdf_size = os.path.getsize(pdf_filename)
                self.log(f"PDF编译成功: {pdf_filename} ({pdf_size} bytes)", "SUCCESS")
                return pdf_filename
            else:
                raise Exception("PDF文件未生成，即使编译返回成功")
            
        except subprocess.CalledProcessError as e:
            self.log(f"编译过程出错: {e}", "ERROR")
            raise Exception(f"编译 {tex_filename} 时出错: {e}")

    def _get_pdflatex_command(self):
        """获取可用的pdflatex命令"""
        if self.pdflatex_path == "pdflatex":
            return "pdflatex"
        elif os.path.exists(self.pdflatex_path):
            return self.pdflatex_path
        else:
            # 最后尝试系统PATH
            try:
                subprocess.run(["pdflatex", "--version"], 
                             check=True, capture_output=True, text=True, timeout=5)
                return "pdflatex"
            except:
                raise FileNotFoundError(
                    f"pdflatex未找到。请检查MiKTeX安装或路径配置。\n" 
                    f"当前配置路径: {self.pdflatex_path}\n" 
                    "建议：\n" 
                    "1. 重新安装MiKTeX\n" 
                    "2. 确保MiKTeX添加到系统PATH\n" 
                    "3. 或者手动指定pdflatex.exe的完整路径"
                )

    def _cleanup_before_compile(self, tex_filename):
        """编译前清理辅助文件"""
        base_name = tex_filename.replace(".tex", "")
        cleanup_extensions = ["aux", "log", "out", "toc", "nav", "snm", "fdb_latexmk", "fls"]
        
        for ext in cleanup_extensions:
            aux_file = f"{base_name}.{ext}"
            try:
                if os.path.exists(aux_file):
                    os.remove(aux_file)
                    self.log(f"清理旧文件: {aux_file}", "DEBUG")
            except Exception as e:
                self.log(f"清理文件 {aux_file} 时出错: {e}", "WARNING")

    def _analyze_compilation_error(self, stdout, stderr):
        """分析编译错误"""
        analysis = {
            "is_miktex_update_issue": False,
            "is_missing_package": False,
            "missing_packages": [],
            "error_message": "",
            "suggestions": []
        }
        
        error_text = (stdout or "") + (stderr or "")
        error_text_lower = error_text.lower()
        
        # 检查MiKTeX更新问题
        miktex_update_keywords = [
            "you have not checked for miktex updates",
            "miktex update required",
            "miktex console",
            "check for updates"
        ]
        
        for keyword in miktex_update_keywords:
            if keyword in error_text_lower:
                analysis["is_miktex_update_issue"] = True
                analysis["error_message"] = error_text[:500]
                break
        
        # 检查缺失包
        import re
        package_patterns = [
            r"File `([^']+\.sty)' not found",
            r"LaTeX Error: File `([^']+)' not found",
            r"! Package (\\w+) Error"
        ]
        
        for pattern in package_patterns:
            matches = re.findall(pattern, error_text)
            for match in matches:
                package_name = match.replace('.sty', '')
                if package_name not in analysis["missing_packages"]:
                    analysis["missing_packages"].append(package_name)
                    analysis["is_missing_package"] = True
        
        return analysis

    def _install_missing_packages(self, packages):
        """尝试安装缺失的包"""
        for package in packages:
            try:
                self.log(f"尝试安装包: {package}", "INFO")
                # 使用MiKTeX包管理器安装
                subprocess.run(["mpm", "--install", package], 
                             check=True, capture_output=True, text=True, timeout=30)
                self.log(f"包安装成功: {package}", "SUCCESS")
            except Exception as e:
                self.log(f"包安装失败: {package} - {e}", "WARNING")

    def _output_detailed_error(self, stdout, stderr, tex_filename):
        """输出详细的错误信息"""
        self.log("=== 详细编译错误信息 ===", "ERROR")
        
        if stdout:
            self.log("编译输出 (stdout):", "DEBUG")
            # 输出最后1000个字符，这通常包含关键错误信息
            print(stdout[-1000:] if len(stdout) > 1000 else stdout)
        
        if stderr:
            self.log("编译错误 (stderr):", "DEBUG")
            print(stderr[-1000:] if len(stderr) > 1000 else stderr)
        
        # 尝试查找.log文件获取更多信息
        log_file = tex_filename.replace(".tex", ".log")
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    log_content = f.read()
                    # 查找错误行
                    lines = log_content.split('\n')
                    error_lines = [line for line in lines if 'error' in line.lower() or '!' in line]
                    if error_lines:
                        self.log("LaTeX日志中的错误行:", "DEBUG")
                        for line in error_lines[-10:]:
                            print(f"  {line}")
            except Exception as e:
                self.log(f"无法读取LaTeX日志文件: {e}", "WARNING")

    def clean_auxiliary_files(self, tex_filename):
        """
        清理编译过程中产生的辅助文件
        
        Args:
            tex_filename (str): LaTeX文件名
        """
        base_name = tex_filename.replace(".tex", "")
        auxiliary_extensions = ["aux", "log", "out", "toc", "nav", "snm"]
        
        cleaned_files = []
        for ext in auxiliary_extensions:
            aux_file = f"{base_name}.{ext}"
            try:
                if os.path.exists(aux_file):
                    os.remove(aux_file)
                    cleaned_files.append(aux_file)
            except Exception as e:
                self.log(f"清理文件 {aux_file} 时出错: {e}", "WARNING")
        
        if cleaned_files:
            self.log(f"已清理辅助文件: {', '.join(cleaned_files)}", "SUCCESS")

    def translate_poster_complete(self, image_path, output_base_name="output", clean_aux=True):
        """
        完整的海报翻译流程：图像 -> LaTeX -> PDF
        
        Args:
            image_path (str): 海报图像路径
            output_base_name (str): 输出文件基础名称
            clean_aux (bool): 是否清理辅助文件
            
        Returns:
            dict: 包含生成文件信息的字典
        """
        self.log("🚀 开始海报翻译流程...", "INFO")
        
        try:
            # 验证图像文件
            if not self.validate_image_file(image_path):
                raise FileNotFoundError(f"图像文件无效: {image_path}")
            
            # 第一步：生成LaTeX代码
            tex_filename = f"{output_base_name}.tex"
            self.log("第1步: 生成LaTeX代码", "INFO")
            latex_code = self.poster_to_latex(image_path, tex_filename)
            
            # 第二步：编译PDF
            self.log("第2步: 编译PDF", "INFO")
            pdf_filename = self.compile_tex_to_pdf(tex_filename)
            
            # 第三步：清理辅助文件（可选）
            if clean_aux:
                self.log("第3步: 清理辅助文件", "INFO")
                self.clean_auxiliary_files(tex_filename)
            
            result = {
                "success": True,
                "tex_file": tex_filename,
                "pdf_file": pdf_filename,
                "image_file": image_path,
                "latex_code_length": len(latex_code)
            }
            
            self.log("🎉 海报翻译完成!", "SUCCESS")
            self.log(f"   输入图像: {image_path}", "INFO")
            self.log(f"   LaTeX文件: {tex_filename}", "INFO")
            self.log(f"   PDF文件: {pdf_filename}", "INFO")
            
            return result
            
        except Exception as e:
            self.log(f"海报翻译失败: {str(e)}", "ERROR")
            return {
                "success": False,
                "error": str(e),
                "image_file": image_path
            }

# ========== 百度图片翻译类 ========== 

class BaiduImageTranslator:
    """百度图片翻译API封装类"""

    def __init__(self, api_key=None, secret_key=None):
        self.api_key = api_key or self._load_key_from_config('BAIDU_API_KEY')
        self.secret_key = secret_key or self._load_key_from_config('BAIDU_SECRET_KEY')
        self.access_token = None

    def _load_key_from_config(self, key_name):
        """从配置文件加载密钥（按照老后端的方式）"""
        # 按照老后端的方式，从单独的文本文件读取
        file_mapping = {
            'BAIDU_API_KEY': 'config/baidu_api_key.txt',
            'BAIDU_SECRET_KEY': 'config/baidu_secret_key.txt'
        }
        
        file_path = file_mapping.get(key_name)
        if file_path and os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    key = f.read().strip()
                    if key:
                        log_message(f"✅ 成功从 {file_path} 加载密钥", "INFO")
                        return key
            except Exception as e:
                log_message(f"⚠️ 警告: 无法从 {file_path} 读取密钥: {e}", "WARNING")
        
        # 如果文件读取失败，尝试从config.env读取
        config_path = "config.env"
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#') and line:
                            key, value = line.split('=', 1)
                            if key.strip() == key_name:
                                return value.strip()
            except Exception:
                pass
        
        return ''

    def log_status(self, message, level="INFO"):
        """状态日志"""
        log_message(message, level)
    
    def get_access_token(self):
        """获取百度AI平台的access_token"""
        if not self.api_key or not self.secret_key:
            self.log_status("百度API密钥未配置", "ERROR")
            return False
            
        self.log_status("正在获取百度API access_token...", "INFO")
        
        token_url = f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={self.api_key}&client_secret={self.secret_key}"
        
        try:
            response = requests.post(token_url, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "access_token" in result:
                    self.access_token = result["access_token"]
                    self.log_status(f"获取access_token成功: {self.access_token[:20]}...", "SUCCESS")
                    return True
                else:
                    self.log_status(f"获取token失败: {result}", "ERROR")
                    return False
            else:
                self.log_status(f"HTTP请求失败: {response.status_code} - {response.text}", "ERROR")
                return False
        except Exception as e:
            self.log_status(f"获取access_token异常: {e}", "ERROR")
            return False
    
    def call_image_translation_api(self, image_path, from_lang="en", to_lang="zh", paste_type=1):
        """调用百度图片翻译API"""
        if not self.access_token:
            self.log_status("请先获取access_token", "ERROR")
            return None
        
        api_url = f"https://aip.baidubce.com/file/2.0/mt/pictrans/v1?access_token={self.access_token}"
        
        try:
            if not os.path.exists(image_path):
                self.log_status(f"图片文件不存在: {image_path}", "ERROR")
                return None
            
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            self.log_status(f"正在翻译图片: {image_path}", "INFO")
            self.log_status(f"翻译方向: {from_lang} -> {to_lang}", "DEBUG")
            
            files = {
                'image': ('image.jpg', image_data, 'image/jpeg')
            }
            
            data = {
                'from': from_lang,
                'to': to_lang,
                'v': '3',
                'paste': str(paste_type)
            }
            
            response = requests.post(api_url, files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                self.log_status("API调用成功", "SUCCESS")
                return result
            else:
                self.log_status(f"API调用失败: {response.status_code} - {response.text}", "ERROR")
                return None
                
        except Exception as e:
            self.log_status(f"API调用异常: {e}", "ERROR")
            return None
    
    def save_translated_image(self, translation_result, output_path):
        """保存翻译后的图片"""
        try:
            if (translation_result and 
                translation_result.get("data") and 
                translation_result["data"].get("pasteImg")):
                
                encoded_image = translation_result["data"]["pasteImg"]
                
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                with open(output_path, "wb") as f:
                    f.write(base64.b64decode(encoded_image))
                
                self.log_status(f"翻译后的图片已保存到: {output_path}", "SUCCESS")
                return output_path
            else:
                self.log_status("翻译结果中没有包含翻译后的图片数据", "WARNING")
                return None
        except Exception as e:
            self.log_status(f"保存翻译后图片失败: {e}", "ERROR")
            return None
    
    def extract_text_info(self, translation_result):
        """提取翻译结果中的文本信息"""
        text_info = {
            "detected_texts": [],
            "translated_texts": [],
            "summary_src": "",
            "summary_dst": "",
            "translation_direction": "",
            "total_blocks": 0
        }
        
        if not translation_result or not translation_result.get("data"):
            return text_info
        
        data = translation_result["data"]
        
        from_lang = data.get("from", "")
        to_lang = data.get("to", "")
        text_info["translation_direction"] = f"{from_lang} -> {to_lang}"
        
        text_info["summary_src"] = data.get("sumSrc", "")
        text_info["summary_dst"] = data.get("sumDst", "")
        
        if data.get("content"):
            text_info["total_blocks"] = len(data["content"])
            
            for i, content in enumerate(data["content"]):
                src_text = content.get("src", "")
                dst_text = content.get("dst", "")
                rect_str = content.get("rect", "")
                
                position = {"left": 0, "top": 0, "width": 0, "height": 0}
                if rect_str and isinstance(rect_str, str):
                    try:
                        parts = rect_str.strip().split()
                        if len(parts) >= 4:
                            position = {
                                "left": int(parts[0]),
                                "top": int(parts[1]),
                                "width": int(parts[2]),
                                "height": int(parts[3])
                            }
                    except (ValueError, IndexError):
                        pass
                
                if src_text:
                    text_info["detected_texts"].append({
                        "text": src_text,
                        "position": position,
                        "block_index": i
                    })
                
                if dst_text:
                    text_info["translated_texts"].append({
                        "text": dst_text,
                        "position": position,
                        "block_index": i
                    })
        
        return text_info
    
    def translate_image_complete(self, image_path, from_lang="en", to_lang="zh", save_image=True):
        """完整的图片翻译流程"""
        result = {
            'success': False,
            'original_image': image_path,
            'translated_image': None,
            'text_info': {},
            'processing_time': None,
            'error': None
        }
        
        start_time = time.time()
        
        try:
            # 调用翻译API
            translation_result = self.call_image_translation_api(
                image_path, from_lang, to_lang, paste_type=1 if save_image else 0
            )
            
            if not translation_result:
                result['error'] = '翻译API调用失败'
                return result
            
            # 检查API响应（使用老前端的逻辑）
            error_code = translation_result.get("error_code")
            
            # 按照老前端的成功判断逻辑
            is_success = False
            if error_code is None:
                is_success = True  # 没有error_code字段，可能是成功
            elif isinstance(error_code, str):
                is_success = (error_code == "0" or error_code.lower() == "success")
            elif isinstance(error_code, int):
                is_success = (error_code == 0)
            else:
                # 尝试转换为整数比较
                try:
                    is_success = (int(error_code) == 0)
                except (ValueError, TypeError):
                    is_success = False
            
            if not is_success:
                error_msg = translation_result.get("error_msg", "未知错误")
                result['error'] = f"百度API错误 ({error_code}): {error_msg}"
                self.log_status(f"API返回错误: code={error_code}, msg={error_msg}", "ERROR")
                return result
            
            # 检查是否有数据（双重验证）
            if not translation_result.get("data"):
                result['error'] = "百度API未返回翻译数据"
                self.log_status("API响应中缺少data字段", "ERROR")
                return result
            
            self.log_status("百度API翻译成功", "SUCCESS")
            
            # 提取文本信息
            result['text_info'] = self.extract_text_info(translation_result)
            
            # 保存翻译后的图片
            if save_image and translation_result.get("data", {}).get("pasteImg"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"translated_{timestamp}.jpg"
                output_path = os.path.join('image_translation_output', output_filename)
                
                translated_image_path = self.save_translated_image(translation_result, output_path)
                if translated_image_path:
                    result['translated_image'] = translated_image_path
            
            result['success'] = True
            result['processing_time'] = f"{time.time() - start_time:.2f}秒"
            
            return result
            
        except Exception as e:
            result['error'] = f"翻译过程异常: {str(e)}"
            result['processing_time'] = f"{time.time() - start_time:.2f}秒"
            return result

# ========== 翻译功能类 ========== 

class SimpleTranslator:
    """简化的翻译器类，包含核心翻译功能"""
    
    def __init__(self, api_keys=None):
        self.api_keys = api_keys or load_api_keys()
        
        # 初始化OpenAI客户端
        if OPENAI_AVAILABLE and self.api_keys.get('OPENAI_API_KEY'):
            try:
                self.openai_client = OpenAI(api_key=self.api_keys['OPENAI_API_KEY'])
                log_message("OpenAI客户端初始化成功", "SUCCESS")
            except Exception as e:
                log_message(f"OpenAI客户端初始化失败: {e}", "ERROR")
                self.openai_client = None
        else:
            self.openai_client = None
            log_message("OpenAI不可用或API密钥未设置", "WARNING")
    
    def translate_poster(self, image_path, output_dir='poster_output'):
        """海报翻译功能（简化版）"""
        try:
            if not self.openai_client:
                return {
                    'success': False,
                    'error': 'OpenAI API未配置'
                }
            
            # 读取图片并编码为base64
            with open(image_path, 'rb') as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 构建请求
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请将这张海报翻译成LaTeX代码，要求：1. 翻译所有文字内容 2. 保持原有布局结构 3. 生成可直接编译的LaTeX代码 4. 不使用外部图片文件"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ]
            
            # 调用OpenAI API
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=4000
            )
            
            latex_content = response.choices[0].message.content
            
            # 保存LaTeX文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            tex_filename = f"poster_{timestamp}.tex"
            tex_path = os.path.join(output_dir, tex_filename)
            
            os.makedirs(output_dir, exist_ok=True)
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            log_message(f"海报翻译完成: {tex_filename}", "SUCCESS")
            
            return {
                'success': True,
                'message': '海报翻译完成',
                'tex_filename': tex_filename,
                'tex_path': tex_path,
                'latex_content': latex_content[:500] + '...' if len(latex_content) > 500 else latex_content
            }
            
        except Exception as e:
            log_message(f"海报翻译失败: {str(e)}", "ERROR")
            return {
                'success': False,
                'error': f'海报翻译失败: {str(e)}'
            }
    
    def translate_webpage_google(self, url):
        """Google网页翻译（简化版）"""
        try:
            if not SELENIUM_AVAILABLE:
                return {
                    'success': False,
                    'error': 'Selenium未安装，无法进行网页翻译'
                }
            
            # 设置Chrome选项
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            
            driver = None
            try:
                driver = webdriver.Chrome(options=chrome_options)
                
                # 访问Google翻译
                translate_url = f"https://translate.google.com/translate?sl=auto&tl=zh&u={url}"
                driver.get(translate_url)
                
                # 等待页面加载
                time.sleep(5)
                
                # 获取翻译后的内容
                page_source = driver.page_source
                
                # 解析内容
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # 保存结果
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"google_translate_{timestamp}.html"
                output_path = os.path.join('web_translation_output', output_filename)
                
                os.makedirs('web_translation_output', exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(page_source)
                
                log_message(f"Google网页翻译完成: {output_filename}", "SUCCESS")
                
                return {
                    'success': True,
                    'message': 'Google网页翻译完成',
                    'output_filename': output_filename,
                    'output_path': output_path,
                    'url': url
                }
                
            finally:
                if driver:
                    driver.quit()
            
        except Exception as e:
            log_message(f"Google网页翻译失败: {str(e)}", "ERROR")
            return {
                'success': False,
                'error': f'Google网页翻译失败: {str(e)}'
            }
    
    def translate_webpage_gpt(self, url):
        """GPT网页翻译（简化版）"""
        try:
            if not self.openai_client:
                return {
                    'success': False,
                    'error': 'OpenAI API未配置'
                }
            
            # 获取网页内容
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # 解析HTML内容
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 提取主要文本内容
            for script in soup(["script", "style"]):
                script.decompose()
            
            text_content = soup.get_text()
            text_content = '\n'.join(line.strip() for line in text_content.splitlines() if line.strip())
            
            # 限制文本长度
            if len(text_content) > 8000:
                text_content = text_content[:8000] + "..."
            
            # 使用GPT翻译
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的网页翻译助手。请将提供的网页内容翻译成中文，保持原有的结构和格式。"
                },
                {
                    "role": "user",
                    "content": f"请将以下网页内容翻译成中文：\n\n{text_content}"
                }
            ]
            
            gpt_response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=4000
            )
            
            translated_content = gpt_response.choices[0].message.content
            
            # 保存翻译结果
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"gpt_translate_{timestamp}.txt"
            output_path = os.path.join('web_translation_output', output_filename)
            
            os.makedirs('web_translation_output', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"原始URL: {url}\n")
                f.write("="*50 + "\n")
                f.write(translated_content)
            
            log_message(f"GPT网页翻译完成: {output_filename}", "SUCCESS")
            
            return {
                'success': True,
                'message': 'GPT网页翻译完成',
                'output_filename': output_filename,
                'output_path': output_path,
                'url': url,
                'translated_content': translated_content[:500] + '...' if len(translated_content) > 500 else translated_content
            }
            
        except Exception as e:
            log_message(f"GPT网页翻译失败: {str(e)}", "ERROR")
            return {
                'success': False,
                'error': f'GPT网页翻译失败: {str(e)}'
            }
    
    def translate_image_baidu(self, image_path, from_lang='en', to_lang='zh'):
        """百度图片翻译（完整版）"""
        try:
            log_message(f"开始百度图片翻译: {image_path}", "INFO")
            
            # 创建百度翻译器实例
            baidu_translator = BaiduImageTranslator(
                api_key=self.api_keys.get('BAIDU_API_KEY'),
                secret_key=self.api_keys.get('BAIDU_SECRET_KEY')
            )
            
            # 获取access token
            if not baidu_translator.get_access_token():
                return {
                    'success': False,
                    'error': '百度API密钥未配置或无效'
                }
            
            # 调用完整的翻译流程
            result = baidu_translator.translate_image_complete(
                image_path=image_path,
                from_lang=from_lang,
                to_lang=to_lang,
                save_image=True
            )
            
            if result['success']:
                log_message(f"百度图片翻译成功: {image_path}", "SUCCESS")
                return {
                    'success': True,
                    'message': '百度图片翻译完成',
                    'original_image': result['original_image'],
                    'translated_image': result.get('translated_image'),
                    'text_info': result['text_info'],
                    'translation_direction': f"{from_lang} -> {to_lang}",
                    'has_translated_image': bool(result.get('translated_image'))
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', '翻译失败')
                }
            
        except Exception as e:
            log_message(f"百度图片翻译失败: {str(e)}", "ERROR")
            return {
                'success': False,
                'error': f'百度图片翻译失败: {str(e)}'
            }

# 延迟初始化翻译器实例
translator = None

def get_translator():
    """获取翻译器实例（延迟初始化）"""
    global translator
    if translator is None:
        translator = SimpleTranslator()
    return translator

# ========== 翻译API接口 ========== 

@app.route('/api/poster-translate', methods=['POST'])
@jwt_required()
def poster_translate():
    """海报翻译API（完整版）"""
    try:
        log_message("开始海报翻译API请求处理", "INFO")
        
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': '请上传海报图像文件'
            }), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '未选择文件'
            }), 400
        
        # 检查文件类型
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': '不支持的文件格式',
                'supported_formats': list(allowed_extensions)
            }), 400
        
        # 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"poster_{timestamp}{file_ext}"
        upload_path = os.path.join('uploads', filename)
        file.save(upload_path)
        
        log_message(f"文件已保存: {upload_path}", "INFO")
        
        # 调用翻译功能
        result = get_translator().translate_poster(upload_path)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'tex_filename': result['tex_filename'],
                'download_url': f'/download/poster/{result["tex_filename"]}',
                'processing_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            return jsonify(result), 500
        
    except Exception as e:
        log_message(f"海报翻译API失败: {str(e)}", "ERROR")
        return jsonify({
            'success': False,
            'error': f'海报翻译失败: {str(e)}'
        }), 500

@app.route('/api/image-translate', methods=['POST'])
@jwt_required()
def image_translate():
    """图片翻译API（完整版）"""
    try:
        log_message("开始图片翻译API请求处理", "INFO")
        
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': '请上传图像文件'
            }), 400
        
        file = request.files['image']
        from_lang = request.form.get('from_lang', 'en')
        to_lang = request.form.get('to_lang', 'zh')
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '未选择文件'
            }), 400
        
        # 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_ext = Path(file.filename).suffix.lower()
        filename = f"image_{timestamp}{file_ext}"
        upload_path = os.path.join('uploads', filename)
        file.save(upload_path)
        
        log_message(f"文件已保存: {upload_path}", "INFO")
        
        # 调用翻译功能
        result = get_translator().translate_image_baidu(upload_path, from_lang, to_lang)
        
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 500
        
    except Exception as e:
        log_message(f"图片翻译API失败: {str(e)}", "ERROR")
        return jsonify({
            'success': False,
            'error': f'图片翻译失败: {str(e)}'
        }), 500

@app.route('/api/webpage-google-translate', methods=['POST'])
@jwt_required()
def webpage_google_translate():
    """Google网页翻译API（完整版）"""
    try:
        log_message("开始Google网页翻译API请求处理", "INFO")
        
        data = request.get_json()
        if not data or not data.get('url'):
            return jsonify({
                'success': False,
                'error': '请提供网页URL'
            }), 400
        
        url = data['url'].strip()
        
        # 验证URL格式
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("无效的URL格式")
        except Exception:
            return jsonify({
                'success': False,
                'error': '无效的URL格式'
            }), 400
        
        # 调用翻译功能
        result = get_translator().translate_webpage_google(url)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'output_filename': result['output_filename'],
                'download_url': f'/download/web/{result["output_filename"]}',
                'url': url
            })
        else:
            return jsonify(result), 500
        
    except Exception as e:
        log_message(f"Google网页翻译API失败: {str(e)}", "ERROR")
        return jsonify({
            'success': False,
            'error': f'Google网页翻译失败: {str(e)}'
        }), 500

@app.route('/api/webpage-gpt-translate', methods=['POST'])
@jwt_required()
def webpage_gpt_translate():
    """GPT网页翻译API（完整版）"""
    try:
        log_message("开始GPT网页翻译API请求处理", "INFO")
        
        data = request.get_json()
        if not data or not data.get('url'):
            return jsonify({
                'success': False,
                'error': '请提供网页URL'
            }), 400
        
        url = data['url'].strip()
        
        # 验证URL格式
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("无效的URL格式")
        except Exception:
            return jsonify({
                'success': False,
                'error': '无效的URL格式'
            }), 400
        
        # 调用翻译功能
        result = get_translator().translate_webpage_gpt(url)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': result['message'],
                'output_filename': result['output_filename'],
                'download_url': f'/download/web/{result["output_filename"]}',
                'url': url,
                'preview': result.get('translated_content', '')
            })
        else:
            return jsonify(result), 500
        
    except Exception as e:
        log_message(f"GPT网页翻译API失败: {str(e)}", "ERROR")
        return jsonify({
            'success': False,
            'error': f'GPT网页翻译失败: {str(e)}'
        }), 500

# ========== LaTeX 翻译接口 ========== 

# 初始化海报翻译器
poster_translator = PosterTranslator(api_key=load_api_keys().get('OPENAI_API_KEY'))

@app.route('/api/latex/check-environment', methods=['GET'])
@jwt_required()
def check_latex_environment():
    """检查LaTeX翻译环境"""
    try:
        log_message("开始LaTeX环境检查", "INFO")
        
        # 运行详细检查
        check_result = poster_translator.check_requirements_with_details()
        
        if check_result['success']:
            return jsonify({
                'success': True,
                'message': 'LaTeX环境正常',
                'details': check_result
            })
        else:
            return jsonify({
                'success': False,
                'error': 'LaTeX环境存在问题',
                'details': check_result
            }), 500
            
    except Exception as e:
        log_message(f"LaTeX环境检查失败: {str(e)}", "ERROR")
        return jsonify({'success': False, 'error': f'环境检查异常: {str(e)}'}), 500

@app.route('/api/latex/translate-poster', methods=['POST'])
@jwt_required()
def latex_translate_poster():
    """
    海报翻译API - 接收图片，生成LaTeX代码，编译成PDF并返回
    """
    try:
        log_message("开始LaTeX海报翻译请求", "INFO")
        
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': '请上传海报图像文件'}), 400
        
        file = request.files['image']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': '未选择文件'}), 400
        
        # 验证文件类型
        allowed_extensions = {'.png', '.jpg', '.jpeg'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': f'不支持的文件格式: {file_ext}'}), 400
        
        # 保存上传的文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"latex_input_{timestamp}{file_ext}"
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
        
        log_message(f"图像文件已保存: {upload_path}", "INFO")
        
        # 定义输出文件基础名称
        output_base_name = f"poster_output/translated_{timestamp}"
        
        # 调用完整的翻译流程
        result = poster_translator.translate_poster_complete(
            image_path=upload_path,
            output_base_name=output_base_name,
            clean_aux=True
        )
        
        if result['success']:
            pdf_path = result['pdf_file']
            log_message(f"PDF生成成功: {pdf_path}", "SUCCESS")
            
            # 返回PDF文件
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=f"translated_poster_{timestamp}.pdf",
                mimetype='application/pdf'
            )
        else:
            log_message(f"LaTeX海报翻译失败: {result['error']}", "ERROR")
            return jsonify({
                'success': False,
                'error': result['error']
            }), 500
            
    except Exception as e:
        log_message(f"LaTeX海报翻译API异常: {str(e)}", "ERROR")
        # 打印更详细的堆栈跟踪
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': f'处理失败: {str(e)}'}), 500

# ========== 认证相关API（复制之前的实现）========== 

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        if not data or not all(k in data for k in ('name', 'email', 'password')):
            return jsonify({'success': False, 'error': '请提供姓名、邮箱和密码'}), 400
        
        name = data['name'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        
        if len(name) < 2:
            return jsonify({'success': False, 'error': '姓名至少需要2个字符'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': '密码至少需要6个字符'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'error': '该邮箱已被注册'}), 400
        
        user = User(name=name, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        access_token = create_access_token(identity=user.id)
        log_message(f"新用户注册成功: {user.email}", "SUCCESS")
        
        return jsonify({
            'success': True,
            'message': '注册成功',
            'user': user.to_dict(),
            'token': access_token
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': '注册失败，请稍后重试'}), 500

@app.route('/api/auth/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json()
        if not data or not all(k in data for k in ('email', 'password')):
            return jsonify({'success': False, 'error': '请提供邮箱和密码'}), 400
        
        email = data['email'].strip().lower()
        password = data['password']
        
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({'success': False, 'error': '邮箱或密码错误'}), 401
        
        access_token = create_access_token(identity=user.id)
        log_message(f"用户登录成功: {user.email}", "SUCCESS")
        
        return jsonify({
            'success': True,
            'message': '登录成功',
            'user': user.to_dict(),
            'token': access_token
        })
    except Exception as e:
        return jsonify({'success': False, 'error': '登录失败，请稍后重试'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        jti = get_jwt()['jti']
        blacklisted_tokens.add(jti)
        return jsonify({'success': True, 'message': '登出成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': '登出失败'}), 500

@app.route('/api/auth/user', methods=['GET'])
@jwt_required()
def get_current_user():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'error': '用户不存在'}), 404
        return jsonify({'success': True, 'user': user.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': '获取用户信息失败'}), 500

# ========== 客户管理（复制之前的实现）========== 

@app.route('/api/clients', methods=['GET'])
@jwt_required()
def get_clients():
    try:
        user_id = get_jwt_identity()
        clients = Client.query.filter_by(user_id=user_id).order_by(Client.created_at.desc()).all()
        return jsonify({'success': True, 'clients': [client.to_dict() for client in clients]})
    except Exception as e:
        return jsonify({'success': False, 'error': '获取客户列表失败'}), 500

@app.route('/api/clients', methods=['POST'])
@jwt_required()
def add_client():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        if not data or not data.get('name', '').strip():
            return jsonify({'success': False, 'error': '请提供客户姓名'}), 400
        
        client = Client(
            name=data['name'].strip(),
            case_type=data.get('caseType', '').strip(),
            case_date=data.get('caseDate', '').strip(),
            user_id=user_id
        )
        db.session.add(client)
        db.session.commit()
        
        return jsonify({'success': True, 'message': '客户添加成功', 'client': client.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': '添加客户失败'}), 500

@app.route('/api/clients/<client_id>', methods=['DELETE'])
@jwt_required()
def delete_client(client_id):
    """删除客户"""
    try:
        user_id = get_jwt_identity()
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({'success': False, 'error': '客户不存在'}), 404
        
        client_name = client.name
        
        # 删除客户（材料会因为外键约束自动删除）
        db.session.delete(client)
        db.session.commit()
        
        log_message(f"客户删除成功: {client_name}", "SUCCESS")
        
        return jsonify({'success': True, 'message': f'客户 {client_name} 删除成功'})
    except Exception as e:
        db.session.rollback()
        log_message(f"删除客户失败: {str(e)}", "ERROR")
        return jsonify({'success': False, 'error': '删除客户失败'}), 500

# ========== 材料管理（复制之前的实现）========== 

@app.route('/api/clients/<client_id>/materials', methods=['GET'])
@jwt_required()
def get_materials(client_id):
    try:
        user_id = get_jwt_identity()
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({'success': False, 'error': '客户不存在'}), 404
        
        # 强制刷新会话以获取最新数据
        db.session.expire_all()
        materials = Material.query.filter_by(client_id=client_id).order_by(Material.created_at.desc()).all()
        
        log_message(f"获取材料列表: 客户ID={client_id}, 找到{len(materials)}个材料", "INFO")
        for material in materials:
            log_message(f"材料详情: {material.name}, 状态={material.status}, 翻译图片={material.translated_image_path}", "DEBUG")
        
        return jsonify({'success': True, 'materials': [material.to_dict() for material in materials]})
    except Exception as e:
        log_message(f"获取材料列表失败: {str(e)}", "ERROR")
        return jsonify({'success': False, 'error': '获取材料列表失败'}), 500

@app.route('/api/clients/<client_id>/materials/upload', methods=['POST'])
@jwt_required()
def upload_files(client_id):
    """文件上传接口"""
    try:
        user_id = get_jwt_identity()
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({'success': False, 'error': '客户不存在'}), 404
        
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '没有上传文件'}), 400
        
        files = request.files.getlist('files')
        if not files or all(file.filename == '' for file in files):
            return jsonify({'success': False, 'error': '没有选择文件'}), 400
        
        uploaded_materials = []
        
        for file in files:
            if file.filename:
                # 保存文件
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_ext = Path(file.filename).suffix.lower()
                safe_filename = secure_filename(file.filename)
                filename = f"{timestamp}_{safe_filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                file.save(file_path)
                
                # 创建材料记录
                material = Material(
                    name=file.filename,
                    type=get_file_type(file.filename),
                    original_filename=file.filename,
                    file_path=file_path,
                    status='已上传',
                    client_id=client_id
                )
                db.session.add(material)
                uploaded_materials.append(material)
        
        db.session.commit()
        
        # 移除自动翻译，只上传文件不立即翻译
        # 翻译将在前端确认后通过单独的API触发
        
        log_message(f"成功上传 {len(uploaded_materials)} 个文件", "SUCCESS")
        
        return jsonify({
            'success': True,
            'message': f'成功上传 {len(uploaded_materials)} 个文件',
            'materials': [material.to_dict() for material in uploaded_materials]
        })
        
    except Exception as e:
        db.session.rollback()
        log_message(f"文件上传失败: {str(e)}", "ERROR")
        return jsonify({'success': False, 'error': '文件上传失败'}), 500

@app.route('/api/clients/<client_id>/materials/urls', methods=['POST'])
@jwt_required()
def upload_urls(client_id):
    try:
        user_id = get_jwt_identity()
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({'success': False, 'error': '客户不存在'}), 404
        
        data = request.get_json()
        if not data or not data.get('urls'):
            return jsonify({'success': False, 'error': '请提供网页URL'}), 400
        
        urls = data['urls']
        uploaded_materials = []
        
        for url in urls:
            if url.strip():
                material = Material(
                    name=url.strip(),
                    type='webpage',
                    url=url.strip(),
                    status='已添加',
                    client_id=client_id
                )
                db.session.add(material)
                uploaded_materials.append(material)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'成功添加 {len(uploaded_materials)} 个网页',
            'materials': [material.to_dict() for material in uploaded_materials]
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': '网页添加失败'}), 500

@app.route('/api/materials/<material_id>', methods=['DELETE'])
@jwt_required()
def delete_material(material_id):
    """删除材料"""
    try:
        user_id = get_jwt_identity()
        
        # 通过material找到client，验证用户权限
        material = Material.query.join(Client).filter(
            Material.id == material_id,
            Client.user_id == user_id
        ).first()
        
        if not material:
            return jsonify({'success': False, 'error': '材料不存在或无权限'}), 404
        
        material_name = material.name
        
        # 删除关联的文件
        if material.file_path and os.path.exists(material.file_path):
            try:
                os.remove(material.file_path)
                log_message(f"删除文件: {material.file_path}", "INFO")
            except Exception as e:
                log_message(f"删除文件失败: {material.file_path} - {str(e)}", "WARNING")
        
        # 删除数据库记录
        db.session.delete(material)
        db.session.commit()
        
        log_message(f"材料删除成功: {material_name}", "SUCCESS")
        
        return jsonify({'success': True, 'message': f'材料 {material_name} 删除成功'})
    except Exception as e:
        db.session.rollback()
        log_message(f"删除材料失败: {str(e)}", "ERROR")
        return jsonify({'success': False, 'error': '删除材料失败'}), 500

@app.route('/api/clients/<client_id>/materials/translate', methods=['POST'])
@jwt_required()
def start_translation(client_id):
    """开始翻译客户的材料"""
    try:
        user_id = get_jwt_identity()
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({'success': False, 'error': '客户不存在'}), 404
        
        # 获取该客户的所有图片材料
        materials = Material.query.filter_by(client_id=client_id, type='image').all()
        
        log_message(f"找到 {len(materials)} 个图片材料", "INFO")
        for m in materials:
            log_message(f"材料: {m.name}, 状态: {m.status}, ID: {m.id}", "INFO")
        
        if not materials:
            return jsonify({'success': False, 'error': '没有需要翻译的图片材料'}), 400
        
        translated_count = 0
        failed_count = 0
        translated_materials = []  # 存储翻译结果
        
        for material in materials:
            log_message(f"检查材料: {material.name}, 状态: {material.status}", "INFO")
            if material.status == '已上传':  # 只翻译未翻译的材料
                try:
                    log_message(f"开始翻译图片: {material.name}", "INFO")
                    
                    # 调用图片翻译功能 (中文到英文)
                    result = get_translator().translate_image_baidu(
                        image_path=material.file_path,
                        from_lang='zh',
                        to_lang='en'
                    )
                    
                    if result['success']:
                        material.status = '翻译完成'
                        # 保存翻译结果到数据库
                        if result.get('translated_image'):
                            material.translated_image_path = result['translated_image']
                        if result.get('text_info'):
                            import json
                            material.translation_text_info = json.dumps(result['text_info'], ensure_ascii=False)
                        material.translation_error = None
                        translated_count += 1
                        log_message(f"图片翻译完成: {material.name}", "SUCCESS")
                        
                        # 开始LaTeX翻译
                        try:
                            log_message(f"开始LaTeX翻译: {material.name}", "INFO")
                            
                            # 使用翻译后的图片进行LaTeX翻译
                            image_path_for_latex = material.translated_image_path if material.translated_image_path else material.file_path
                            
                            # 生成输出文件名
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            output_base_name = f"poster_output/latex_{material.id}_{timestamp}"
                            
                            # 调用LaTeX翻译
                            latex_result = poster_translator.translate_poster_complete(
                                image_path=image_path_for_latex,
                                output_base_name=output_base_name,
                                clean_aux=True
                            )
                            
                            if latex_result['success']:
                                # 保存LaTeX翻译结果到数据库
                                material.latex_translation_result = json.dumps({
                                    'tex_file': latex_result.get('tex_file'),
                                    'pdf_file': latex_result.get('pdf_file'),
                                    'latex_code_length': latex_result.get('latex_code_length', 0)
                                }, ensure_ascii=False)
                                material.latex_translation_error = None
                                log_message(f"LaTeX翻译完成: {material.name}", "SUCCESS")
                                log_message(f"  - LaTeX文件: {latex_result.get('tex_file')}", "INFO")
                                log_message(f"  - PDF文件: {latex_result.get('pdf_file')}", "INFO")
                            else:
                                material.latex_translation_error = latex_result.get('error', 'LaTeX翻译失败')
                                log_message(f"LaTeX翻译失败: {material.name} - {latex_result.get('error', '未知错误')}", "ERROR")
                                
                        except Exception as latex_e:
                            material.latex_translation_error = str(latex_e)
                            log_message(f"LaTeX翻译异常: {material.name} - {str(latex_e)}", "ERROR")
                        
                        # 将翻译结果添加到返回数据中
                        translated_materials.append({
                            'id': material.id,
                            'name': material.name,
                            'translated_image_path': material.translated_image_path,
                            'translation_text_info': result.get('text_info'),
                            'latex_translation_result': material.latex_translation_result,
                            'latex_translation_error': material.latex_translation_error,
                            'status': '翻译完成'
                        })
                    else:
                        material.status = '翻译失败'
                        material.translation_error = result.get('error', '未知错误')
                        failed_count += 1
                        log_message(f"图片翻译失败: {material.name} - {result.get('error', '未知错误')}", "ERROR")
                        
                except Exception as e:
                    material.status = '翻译失败'
                    material.translation_error = str(e)
                    failed_count += 1
                    log_message(f"图片翻译异常: {material.name} - {str(e)}", "ERROR")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'翻译完成：成功 {translated_count} 个，失败 {failed_count} 个',
            'translated_count': translated_count,
            'failed_count': failed_count,
            'translated_materials': translated_materials  # 直接返回翻译结果
        })
        
    except Exception as e:
        db.session.rollback()
        log_message(f"批量翻译失败: {str(e)}", "ERROR")
        return jsonify({'success': False, 'error': '批量翻译失败'}), 500

@app.route('/api/clients/<client_id>/materials/cancel', methods=['POST'])
@jwt_required()
def cancel_upload(client_id):
    """取消上传，删除最近上传的材料"""
    try:
        user_id = get_jwt_identity()
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({'success': False, 'error': '客户不存在'}), 404
        
        data = request.get_json()
        material_ids = data.get('material_ids', [])
        
        if not material_ids:
            return jsonify({'success': False, 'error': '没有指定要删除的材料'}), 400
        
        deleted_count = 0
        
        for material_id in material_ids:
            material = Material.query.filter_by(id=material_id, client_id=client_id).first()
            if material:
                # 删除关联文件
                if material.file_path and os.path.exists(material.file_path):
                    try:
                        os.remove(material.file_path)
                        log_message(f"删除文件: {material.file_path}", "INFO")
                    except Exception as e:
                        log_message(f"删除文件失败: {material.file_path} - {str(e)}", "WARNING")
                
                # 删除数据库记录
                db.session.delete(material)
                deleted_count += 1
        
        db.session.commit()
        
        log_message(f"取消上传，删除了 {deleted_count} 个材料", "SUCCESS")
        
        return jsonify({
            'success': True,
            'message': f'已删除 {deleted_count} 个材料',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        db.session.rollback()
        log_message(f"取消上传失败: {str(e)}", "ERROR")
        return jsonify({'success': False, 'error': '取消上传失败'}), 500

# ========== 文件下载端点 ========== 

@app.route('/download/image/<path:filename>')
def download_image(filename):
    """下载翻译后的图片"""
    try:
        # 支持完整路径和文件名
        if '/' in filename:
            # 如果包含路径，直接使用
            file_path = filename
        else:
            # 否则在image_translation_output目录中查找
            file_path = os.path.join('image_translation_output', filename)
        
        if os.path.exists(file_path):
            return send_file(file_path)
        else:
            log_message(f"图片文件不存在: {file_path}", "ERROR")
            return jsonify({'error': '文件不存在'}), 404
    except Exception as e:
        log_message(f"下载图片失败: {str(e)}", "ERROR")
        return jsonify({'error': '下载失败'}), 500

def get_file_type(filename):
    """根据文件名获取文件类型"""
    ext = filename.split('.').pop().lower()
    if ext in ['pdf']:
        return 'pdf'
    elif ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff']:
        return 'image'
    elif ext in ['doc', 'docx', 'txt', 'rtf']:
        return 'document'
    else:
        return 'document'

# ========== 下载功能 ========== 

@app.route('/download/poster/<filename>')
def download_poster_file(filename):
    try:
        file_path = os.path.join('poster_output', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': '下载失败'}), 500

@app.route('/preview/poster/<filename>')
def preview_poster_file(filename):
    """预览LaTeX生成的PDF文件"""
    try:
        file_path = os.path.join('poster_output', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        # 检查文件类型
        if not filename.lower().endswith('.pdf'):
            return jsonify({'error': '只能预览PDF文件'}), 400
        
        # 设置正确的MIME类型
        return send_file(file_path, mimetype='application/pdf')
    except Exception as e:
        log_message(f"PDF预览失败: {str(e)}", "ERROR")
        return jsonify({'error': '预览失败'}), 500

@app.route('/download/web/<filename>')
def download_web_file(filename):
    try:
        file_path = os.path.join('web_translation_output', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({'error': '下载失败'}), 500


# ========== 系统功能 ========== 

@app.route('/')
def index():
    return jsonify({
        'message': '智能文书翻译平台 - 完整版后端API',
        'version': '4.0',
        'features': {
            'user_authentication': True,
            'client_management': True,
            'material_management': True,
            'translation_services': True,
            'poster_translation': OPENAI_AVAILABLE,
            'image_translation': True,
            'webpage_translation': True,
            'gpt_translation': OPENAI_AVAILABLE,
            'google_translation': SELENIUM_AVAILABLE
        },
        'dependencies': {
            'openai': OPENAI_AVAILABLE,
            'selenium': SELENIUM_AVAILABLE,
            'beautifulsoup4': True,
            'requests': True
        }
    })

@app.route('/health')
def health():
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'version': '4.0',
            'translation_ready': OPENAI_AVAILABLE or SELENIUM_AVAILABLE
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500

# ========== 数据库初始化 ========== 

def init_database():
    with app.app_context():
        try:
            db.create_all()
            log_message("数据库初始化成功", "SUCCESS")
            
            if User.query.count() == 0:
                test_user = User(name="测试用户", email="test@example.com")
                test_user.set_password("password123")
                db.session.add(test_user)
                db.session.commit()
                log_message("已创建测试用户: test@example.com / password123", "SUCCESS")
        except Exception as e:
            log_message(f"数据库初始化失败: {str(e)}", "ERROR")

# ========== 错误处理 ========== 

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': '接口不存在'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({
        'success': False,
        'error': '服务器内部错误'
    }), 500

@app.errorhandler(Exception)
def handle_exception(e):
    log_message(f"未处理的异常: {str(e)}", "ERROR")
    db.session.rollback()
    return jsonify({
        'success': False,
        'error': '服务器内部错误',
        'message': str(e)
    }), 500

if __name__ == '__main__':
    # 确保工作目录在脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"工作目录: {os.getcwd()}")
    
    print("启动智能文书翻译平台 - 完整版后端服务 v4.0...")
    print("功能: 用户认证、客户管理、材料管理、完整翻译服务")
    print("认证方式: JWT Bearer Token")
    print("数据库: SQLite (translation_platform.db)")
    print("测试用户: test@example.com / password123")
    print(f"OpenAI可用: {OPENAI_AVAILABLE}")
    print(f"Selenium可用: {SELENIUM_AVAILABLE}")
    print()
    
    # 初始化数据库并添加新列
    with app.app_context():
        db.create_all()
        log_message("数据库初始化成功", "SUCCESS")
        
        # 添加新列（如果不存在）
        try:
            db.engine.execute(text("ALTER TABLE materials ADD COLUMN translated_image_path VARCHAR(500)"))
            log_message("添加translated_image_path列", "SUCCESS")
        except Exception:
            pass  # 列已存在
        
        try:
            db.engine.execute(text("ALTER TABLE materials ADD COLUMN translation_text_info TEXT"))
            log_message("添加translation_text_info列", "SUCCESS")
        except Exception:
            pass  # 列已存在
            
        try:
            db.engine.execute(text("ALTER TABLE materials ADD COLUMN translation_error TEXT"))
            log_message("添加translation_error列", "SUCCESS")
        except Exception:
            pass  # 列已存在
            
        try:
            db.engine.execute(text("ALTER TABLE materials ADD COLUMN latex_translation_result TEXT"))
            log_message("添加latex_translation_result列", "SUCCESS")
        except Exception:
            pass  # 列已存在
            
        try:
            db.engine.execute(text("ALTER TABLE materials ADD COLUMN latex_translation_error TEXT"))
            log_message("添加latex_translation_error列", "SUCCESS")
        except Exception:
            pass  # 列已存在
    
    app.run(debug=True, host='0.0.0.0', port=5000)
