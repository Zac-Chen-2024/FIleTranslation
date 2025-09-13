from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, get_jwt
import os
import time
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 配置
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///translation_platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-change-this-in-production'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# 初始化扩展
db = SQLAlchemy(app)
jwt = JWTManager(app)

# 禁用Flask的自动URL重定向
app.url_map.strict_slashes = False

# 创建必要的文件夹
os.makedirs('downloads', exist_ok=True)
os.makedirs('uploads', exist_ok=True)
os.makedirs('user_files', exist_ok=True)

# JWT Token黑名单存储
blacklisted_tokens = set()

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    return jwt_payload['jti'] in blacklisted_tokens

# ========== 数据库模型 ==========

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
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
    
    # 关系
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
    type = db.Column(db.String(50), nullable=False)  # pdf, image, webpage, document
    status = db.Column(db.String(50), default='待处理')  # 待处理, 翻译中, 翻译完成, 已确认, 翻译失败
    confirmed = db.Column(db.Boolean, default=False)
    selected_result = db.Column(db.String(20), default='latex')  # latex, api
    original_filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    url = db.Column(db.String(1000))  # 用于网页类型材料
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

# ========== 认证相关路由 ==========

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """用户注册"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('name', 'email', 'password')):
            return jsonify({
                'success': False,
                'error': '请提供姓名、邮箱和密码'
            }), 400
        
        name = data['name'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        
        if len(name) < 2:
            return jsonify({
                'success': False,
                'error': '姓名至少需要2个字符'
            }), 400
        
        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': '密码至少需要6个字符'
            }), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({
                'success': False,
                'error': '该邮箱已被注册'
            }), 400
        
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
        print(f"❌ 注册失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '注册失败，请稍后重试'
        }), 500

@app.route('/api/auth/signin', methods=['POST'])
def signin():
    """用户登录"""
    try:
        data = request.get_json()
        
        if not data or not all(k in data for k in ('email', 'password')):
            return jsonify({
                'success': False,
                'error': '请提供邮箱和密码'
            }), 400
        
        email = data['email'].strip().lower()
        password = data['password']
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            return jsonify({
                'success': False,
                'error': '邮箱或密码错误'
            }), 401
        
        access_token = create_access_token(identity=user.id)
        
        print(f"✅ 用户登录成功: {user.email}")
        
        return jsonify({
            'success': True,
            'message': '登录成功',
            'user': user.to_dict(),
            'token': access_token
        })
        
    except Exception as e:
        print(f"❌ 登录失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '登录失败，请稍后重试'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    """用户登出"""
    try:
        jti = get_jwt()['jti']
        blacklisted_tokens.add(jti)
        
        print("✅ 用户登出成功")
        
        return jsonify({
            'success': True,
            'message': '登出成功'
        })
        
    except Exception as e:
        print(f"❌ 登出失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '登出失败'
        }), 500

@app.route('/api/auth/user', methods=['GET'])
@jwt_required()
def get_current_user():
    """获取当前用户信息"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': '用户不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'user': user.to_dict()
        })
        
    except Exception as e:
        print(f"❌ 获取用户信息失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取用户信息失败'
        }), 500

# ========== 客户管理路由 ==========

@app.route('/api/clients', methods=['GET'])
@jwt_required()
def get_clients():
    """获取客户列表"""
    try:
        user_id = get_jwt_identity()
        clients = Client.query.filter_by(user_id=user_id).order_by(Client.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'clients': [client.to_dict() for client in clients]
        })
        
    except Exception as e:
        print(f"❌ 获取客户列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取客户列表失败'
        }), 500

@app.route('/api/clients', methods=['POST'])
@jwt_required()
def add_client():
    """添加新客户"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or not data.get('name', '').strip():
            return jsonify({
                'success': False,
                'error': '请提供客户姓名'
            }), 400
        
        client = Client(
            name=data['name'].strip(),
            case_type=data.get('caseType', '').strip(),
            case_date=data.get('caseDate', '').strip(),
            user_id=user_id
        )
        
        db.session.add(client)
        db.session.commit()
        
        print(f"✅ 新客户添加成功: {client.name}")
        
        return jsonify({
            'success': True,
            'message': '客户添加成功',
            'client': client.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ 添加客户失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '添加客户失败'
        }), 500

# ========== 材料管理路由 ==========

@app.route('/api/clients/<client_id>/materials', methods=['GET'])
@jwt_required()
def get_materials(client_id):
    """获取客户材料列表"""
    try:
        user_id = get_jwt_identity()
        
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': '客户不存在'
            }), 404
        
        materials = Material.query.filter_by(client_id=client_id).order_by(Material.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'materials': [material.to_dict() for material in materials]
        })
        
    except Exception as e:
        print(f"❌ 获取材料列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取材料列表失败'
        }), 500

@app.route('/api/clients/<client_id>/materials/urls', methods=['POST'])
@jwt_required()
def upload_urls(client_id):
    """添加网页材料"""
    try:
        user_id = get_jwt_identity()
        
        client = Client.query.filter_by(id=client_id, user_id=user_id).first()
        if not client:
            return jsonify({
                'success': False,
                'error': '客户不存在'
            }), 404
        
        data = request.get_json()
        if not data or not data.get('urls'):
            return jsonify({
                'success': False,
                'error': '请提供网页URL'
            }), 400
        
        urls = data['urls']
        if not isinstance(urls, list) or not urls:
            return jsonify({
                'success': False,
                'error': '请提供有效的网页URL列表'
            }), 400
        
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
        
        print(f"✅ 网页添加成功: {len(uploaded_materials)} 个网页")
        
        return jsonify({
            'success': True,
            'message': f'成功添加 {len(uploaded_materials)} 个网页',
            'materials': [material.to_dict() for material in uploaded_materials]
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ 网页添加失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '网页添加失败'
        }), 500

# ========== 系统功能 ==========

@app.route('/')
def index():
    return jsonify({
        'message': '智能文书翻译平台 - 新版后端API (简化版)',
        'version': '3.0-simple',
        'features': {
            'user_authentication': True,
            'client_management': True,
            'material_management': True,
            'database': 'SQLite with SQLAlchemy ORM'
        },
        'endpoints': {
            'auth': {
                'signup': 'POST /api/auth/signup',
                'signin': 'POST /api/auth/signin',
                'logout': 'POST /api/auth/logout',
                'user': 'GET /api/auth/user'
            },
            'clients': {
                'list': 'GET /api/clients',
                'create': 'POST /api/clients'
            },
            'materials': {
                'list': 'GET /api/clients/:id/materials',
                'urls': 'POST /api/clients/:id/materials/urls'
            }
        }
    })

@app.route('/health')
def health():
    """健康检查"""
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'version': '3.0-simple'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500

@app.route('/api/test', methods=['GET'])
def test_api():
    """测试API端点"""
    return jsonify({
        'success': True,
        'message': '新版后端API正常运行 (简化版)',
        'timestamp': datetime.now().isoformat(),
        'features': {
            'authentication': True,
            'database': True,
            'user_management': True,
            'client_management': True,
            'material_management': True
        }
    })

# ========== 数据库初始化 ==========

def init_database():
    """初始化数据库"""
    with app.app_context():
        try:
            db.create_all()
            print("✅ 数据库初始化成功")
            
            if User.query.count() == 0:
                test_user = User(
                    name="测试用户",
                    email="test@example.com"
                )
                test_user.set_password("password123")
                
                db.session.add(test_user)
                db.session.commit()
                
                print("✅ 已创建测试用户: test@example.com / password123")
                
        except Exception as e:
            print(f"❌ 数据库初始化失败: {str(e)}")

if __name__ == '__main__':
    print("🚀 启动智能文书翻译平台 - 新版后端服务 v3.0 (简化版)...")
    print("🔑 新增功能: 用户认证、客户管理、材料管理")
    print("📋 API分类:")
    print("   - 认证系统: /api/auth/*")
    print("   - 客户管理: /api/clients/*") 
    print("   - 材料管理: /api/materials/*")
    print()
    print("🔐 认证方式: JWT Bearer Token")
    print("🗄️ 数据库: SQLite (translation_platform.db)")
    print("🌐 跨域支持: 已启用")
    print()
    print("💡 测试用户: test@example.com / password123")
    print("🔧 健康检查: GET /health")
    print("📄 API文档: GET /")
    print()
    
    # 初始化数据库
    init_database()
    
    # 启动应用
    app.run(debug=True, host='0.0.0.0', port=5000)
