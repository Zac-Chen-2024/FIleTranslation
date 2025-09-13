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
                        
                        # 将翻译结果添加到返回数据中
                        translated_materials.append({
                            'id': material.id,
                            'name': material.name,
                            'translated_image_path': material.translated_image_path,
                            'translation_text_info': result.get('text_info'),
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
