# 智能文书翻译平台 - 新版后端

专为律师设计的智能翻译解决方案后端服务，集成用户认证、客户管理、材料管理和多种翻译服务。

## 🚀 主要功能

### 🔐 用户认证系统
- JWT Token认证
- 用户注册/登录/登出
- 密码安全存储
- Token黑名单管理

### 👥 客户管理
- 添加/编辑/删除客户
- 案件类型管理
- 客户数据隔离

### 📄 材料管理
- 文件上传（PDF、图片、文档）
- 网页URL添加
- 材料状态跟踪
- 翻译结果选择
- 材料确认流程

### 🔄 翻译服务
- 海报翻译（LaTeX生成）
- 图片翻译（百度API）
- 网页翻译（Google/GPT）
- 多格式支持

### 📦 文件系统
- 安全文件存储
- 文件预览/下载
- 权限控制
- 自动清理

## 📦 快速开始

### 1. 安装依赖
```bash
cd NewServer
pip install -r requirements.txt
```

### 2. 配置环境（可选）
```bash
cp config_example.env .env
# 编辑 .env 文件，配置API密钥和路径
```

### 3. 启动服务
```bash
# 方式1：使用启动脚本（推荐）
python run_server.py

# 方式2：直接运行
python app.py
```

### 4. 测试API
```bash
python test_api.py
```

### 5. 访问服务
- 主页: http://localhost:5000
- API文档: http://localhost:5000
- 健康检查: http://localhost:5000/health

## 🔑 默认测试账户

启动服务后会自动创建测试账户：
- **邮箱**: test@example.com
- **密码**: password123

## 📁 文件结构

```
NewServer/
├── app.py                  # 主应用文件（Flask应用）
├── run_server.py          # 启动脚本（推荐使用）
├── test_api.py           # API测试脚本
├── requirements.txt      # Python依赖包
├── config_example.env    # 环境配置示例
├── server_config.py      # 服务器配置（来自原版）
└── README.md            # 说明文档

# 运行时自动创建的目录：
├── uploads/             # 用户上传文件
├── downloads/           # 下载文件
├── user_files/          # 用户文件存储
├── poster_output/       # 海报翻译输出
├── image_translation_output/  # 图片翻译输出
├── web_translation_output/    # 网页翻译输出
└── translation_platform.db   # SQLite数据库
```

## 🔧 核心特性

### 📊 数据库结构
- **users**: 用户表
- **clients**: 客户表  
- **materials**: 材料表
- **files**: 文件表
- **translation_jobs**: 翻译任务表

### 🛡️ 安全特性
- JWT Token认证
- 密码哈希存储
- 文件权限控制
- 用户数据隔离
- Token黑名单

### 🔌 API设计
- RESTful API设计
- 统一的响应格式
- 详细的错误信息
- 支持文件上传
- CORS跨域支持

## 📚 API接口示例

### 用户注册
```http
POST /api/auth/signup
Content-Type: application/json

{
  "name": "张律师",
  "email": "zhang@law.com", 
  "password": "password123"
}
```

### 用户登录
```http
POST /api/auth/signin
Content-Type: application/json

{
  "email": "zhang@law.com",
  "password": "password123"
}
```

### 添加客户
```http
POST /api/clients
Authorization: Bearer <your-jwt-token>
Content-Type: application/json

{
  "name": "李先生",
  "caseType": "移民签证",
  "caseDate": "2024-01-15"
}
```

### 上传文件
```http
POST /api/clients/{client_id}/materials/upload
Authorization: Bearer <your-jwt-token>
Content-Type: multipart/form-data

files: <file1>, <file2>, ...
```

## 🚀 与前端配合使用

这个后端完全兼容项目中的 React 前端，提供前端所需的所有API接口：

1. **认证系统**: 完整的注册/登录流程
2. **客户管理**: 客户的增删改查
3. **材料管理**: 文件上传、状态管理、确认流程
4. **翻译服务**: 集成原有的翻译功能
5. **文件下载**: 支持预览和下载

## 🔄 翻译功能集成

后端保留了原有的所有翻译接口：
- `/api/poster-translate` - 海报翻译
- `/api/image-translate` - 图片翻译  
- `/api/webpage-google-translate` - Google网页翻译
- `/api/webpage-gpt-translate` - GPT网页翻译

所有翻译接口都添加了JWT认证保护。

## 🛠️ 开发说明

### 环境要求
- Python 3.8+
- SQLite（内置）
- Chrome浏览器（用于PDF生成）
- MiKTeX（可选，用于LaTeX编译）

### 开发模式
```bash
# 启用开发模式
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py
```

### 生产部署
1. 修改 `app.py` 中的密钥配置
2. 配置反向代理（Nginx）
3. 使用WSGI服务器（Gunicorn）
4. 设置环境变量

## 🔍 故障排除

### 常见问题

1. **数据库错误**
   - 删除 `translation_platform.db` 重新初始化

2. **端口被占用**
   - 修改 `app.py` 中的端口号或杀死占用进程

3. **依赖安装失败**
   - 使用虚拟环境：`python -m venv venv && source venv/bin/activate`

4. **API测试失败**
   - 确认服务已启动：`curl http://localhost:5000/health`

### 日志查看
应用会在控制台输出详细的运行日志，包括：
- 数据库操作日志
- API请求日志
- 错误信息
- 用户操作日志

## 📞 技术支持

- 查看控制台日志获取详细错误信息
- 运行 `python test_api.py` 测试API连通性
- 检查 `requirements.txt` 确保依赖安装完整

## 🎯 下一步计划

1. **集成翻译功能**: 将原有翻译逻辑完全集成
2. **性能优化**: 添加缓存和异步处理
3. **监控告警**: 添加日志和监控系统
4. **扩展功能**: 支持更多文件格式和翻译服务

---

**版权所有 © 2024 智能文书翻译平台**

