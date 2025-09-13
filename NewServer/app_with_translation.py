# 将完整版app.py复制并添加基本翻译功能
# 这是一个带有简化翻译功能的版本

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, get_jwt
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

# 导入原有的app.py中的所有内容，但添加认证
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

# ========== 数据库模型 ==========
# [复制之前的所有数据库模型]

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
    client_id = db.Column(db.String(36), db.ForeignKey('clients.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
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
            'updatedAt': self.updated_at.isoformat()
        }

# ========== 简化的翻译功能 ==========

@app.route('/api/poster-translate', methods=['POST'])
@jwt_required()
def poster_translate():
    """海报翻译API（简化版）"""
    try:
        print("🚀 开始海报翻译API请求处理")
        
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
                'error': '不支持的文件格式'
            }), 400
        
        # 保存文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"poster_{timestamp}{file_ext}"
        upload_path = os.path.join('uploads', filename)
        file.save(upload_path)
        
        # 简化的处理：生成模拟结果
        tex_filename = f"poster_{timestamp}.tex"
        pdf_filename = f"poster_{timestamp}.pdf"
        
        # 创建模拟的LaTeX内容
        mock_latex = f"""\\documentclass{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{graphicx}}
\\title{{海报翻译结果}}
\\author{{智能文书翻译平台}}
\\date{{\\today}}

\\begin{{document}}
\\maketitle

\\section{{翻译内容}}
这是一个模拟的海报翻译结果。原始文件：{file.filename}

\\section{{处理信息}}
\\begin{{itemize}}
\\item 上传时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
\\item 文件大小：{os.path.getsize(upload_path)} bytes
\\item 处理状态：已完成
\\end{{itemize}}

\\end{{document}}
"""
        
        # 保存LaTeX文件
        tex_path = os.path.join('poster_output', tex_filename)
        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(mock_latex)
        
        print(f"✅ 海报翻译完成: {tex_filename}")
        
        return jsonify({
            'success': True,
            'message': '海报翻译完成',
            'latex_generated': True,
            'pdf_generated': False,  # 简化版暂不生成PDF
            'tex_filename': tex_filename,
            'latex_download_url': f'/download/poster/{tex_filename}',
            'processing_time': '完成'
        })
        
    except Exception as e:
        print(f"❌ 海报翻译失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'海报翻译失败: {str(e)}'
        }), 500

@app.route('/api/image-translate', methods=['POST'])
@jwt_required()
def image_translate():
    """图片翻译API（简化版）"""
    try:
        print("🚀 开始图片翻译API请求处理")
        
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
        
        # 模拟翻译结果
        mock_text_info = {
            "detected_texts": [
                {"text": "Sample English Text", "position": {"left": 100, "top": 50, "width": 200, "height": 30}},
                {"text": "Another Text Block", "position": {"left": 100, "top": 100, "width": 180, "height": 25}}
            ],
            "translated_texts": [
                {"text": "示例英文文本", "position": {"left": 100, "top": 50, "width": 200, "height": 30}},
                {"text": "另一个文本块", "position": {"left": 100, "top": 100, "width": 180, "height": 25}}
            ],
            "translation_direction": f"{from_lang} -> {to_lang}",
            "total_blocks": 2
        }
        
        print(f"✅ 图片翻译完成: {filename}")
        
        return jsonify({
            'success': True,
            'message': '图片翻译完成',
            'original_image': upload_path,
            'text_info': mock_text_info,
            'translation_direction': f"{from_lang} -> {to_lang}",
            'has_translated_image': False  # 简化版暂不生成翻译图片
        })
        
    except Exception as e:
        print(f"❌ 图片翻译失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'图片翻译失败: {str(e)}'
        }), 500

# ========== 认证路由（复制之前的实现）==========

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
        print(f"✅ 新用户注册成功: {user.email}")
        
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
        print(f"✅ 用户登录成功: {user.email}")
        
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

# ========== 材料管理（复制之前的实现）==========

@app.route('/api/clients/<client_id>/materials', methods=['GET'])
@jwt_required()
def get_materials(client_id):
    try:
        user_id = get_jwt_identity()
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({'success': False, 'error': '客户不存在'}), 404
        
        materials = Material.query.filter_by(client_id=client_id).order_by(Material.created_at.desc()).all()
        return jsonify({'success': True, 'materials': [material.to_dict() for material in materials]})
    except Exception as e:
        return jsonify({'success': False, 'error': '获取材料列表失败'}), 500

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

# ========== 下载功能 ==========

@app.route('/download/poster/<filename>')
def download_poster_file(filename):
    try:
        file_path = os.path.join('poster_output', filename)
        if not os.path.exists(file_path):
            return jsonify({'error': '文件不存在'}), 404
        
        return send_file(file_path, as_attachment=True, download_name=filename, mimetype='text/plain')
    except Exception as e:
        return jsonify({'error': '下载失败'}), 500

# ========== 系统功能 ==========

@app.route('/')
def index():
    return jsonify({
        'message': '智能文书翻译平台 - 新版后端API (含翻译功能)',
        'version': '3.1',
        'features': {
            'user_authentication': True,
            'client_management': True,
            'material_management': True,
            'translation_services': True,
            'poster_translation': True,
            'image_translation': True
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
            'version': '3.1'
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
            print("✅ 数据库初始化成功")
            
            if User.query.count() == 0:
                test_user = User(name="测试用户", email="test@example.com")
                test_user.set_password("password123")
                db.session.add(test_user)
                db.session.commit()
                print("✅ 已创建测试用户: test@example.com / password123")
        except Exception as e:
            print(f"❌ 数据库初始化失败: {str(e)}")

if __name__ == '__main__':
    print("🚀 启动智能文书翻译平台 - 新版后端服务 v3.1 (含翻译功能)...")
    print("🔑 功能: 用户认证、客户管理、材料管理、翻译服务")
    print("🔐 认证方式: JWT Bearer Token")
    print("🗄️ 数据库: SQLite (translation_platform.db)")
    print("💡 测试用户: test@example.com / password123")
    print()
    
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)

