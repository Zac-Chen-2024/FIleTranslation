# 智能文书翻译平台 - React前端

专为律师设计的智能翻译解决方案，提供精准、专业的法律文档翻译服务。

## 🚀 功能特性

### 核心功能
- **用户认证系统**: 完整的注册和登录流程
- **客户管理**: 添加、管理客户信息和案件类型
- **材料翻译**: 支持PDF、图片、网页等多种格式翻译
- **智能预览**: LaTeX和API翻译结果对比选择
- **AI编辑**: 自然语言描述的LaTeX代码编辑
- **批量导出**: 一键打包导出所有翻译文档

### 技术特性
- **React 18**: 使用最新的React功能
- **React Router 6**: 现代化的路由管理
- **Context API**: 全局状态管理
- **CSS Modules**: 模块化样式系统
- **Axios**: HTTP客户端
- **响应式设计**: 支持桌面和移动端

## 📦 安装和运行

### 前置要求
- Node.js (版本 16 或更高)
- npm 或 yarn

### 安装依赖
```bash
cd react-frontend
npm install
```

### 开发模式运行
```bash
npm start
```
应用将在 http://localhost:3000 启动

### 生产构建
```bash
npm run build
```

### 运行测试
```bash
npm test
```

## 🏗️ 项目结构

```
react-frontend/
├── public/
│   └── index.html
├── src/
│   ├── components/           # 可复用组件
│   │   ├── common/          # 通用组件
│   │   ├── modals/          # 模态框组件
│   │   └── translation/     # 翻译相关组件
│   ├── contexts/            # Context API状态管理
│   ├── pages/               # 页面组件
│   ├── services/            # API服务
│   ├── styles/              # 全局样式
│   ├── App.js              # 主应用组件
│   └── index.js            # 应用入口
├── package.json
└── README.md
```

## 🎨 设计系统

### 颜色变量
- **主色调**: 蓝色系 (#1e40af, #3b82f6)
- **辅助色**: 金色 (#f59e0b)
- **功能色**: 绿色(成功), 红色(错误)
- **中性色**: 灰色系 (#f8fafc - #0f172a)

### 组件样式
- 使用CSS Modules确保样式隔离
- 统一的设计token和变量
- 响应式设计支持多种屏幕尺寸

## 🔧 配置

### 环境变量
创建 `.env` 文件：
```env
REACT_APP_API_URL=https://filetrans2.0.drziangchen.uk
```

### API集成
- 完整的API服务层 (`src/services/api.js`)
- 自动token管理和错误处理
- 支持文件上传和进度跟踪

## 📱 页面说明

### 1. 欢迎页面 (`/`)
- 平台功能介绍
- 登录/注册入口

### 2. 认证页面 (`/signin`, `/signup`)
- 用户登录和注册
- 表单验证和错误处理

### 3. 主界面 (`/dashboard`)
- 客户列表管理
- 添加新客户

### 4. 翻译工作区 (`/client/:clientId`)
- 材料列表管理
- 翻译预览和编辑
- 导出功能

## 🔄 状态管理

### Context API结构
- **用户状态**: 登录信息、认证状态
- **客户状态**: 客户列表、当前客户
- **材料状态**: 材料列表、当前材料
- **UI状态**: 加载状态、通知、模态框

### Actions
- 用户相关: `setUser`, `logout`
- 客户相关: `setClients`, `addClient`, `setCurrentClient`
- 材料相关: `setMaterials`, `addMaterials`, `updateMaterial`
- UI控制: `showNotification`, `toggleModal`, `setProgress`

## 🛠️ 开发指南

### 添加新组件
1. 在适当的目录下创建组件文件
2. 创建对应的CSS Module文件
3. 在需要的地方导入和使用

### 添加新页面
1. 在 `src/pages/` 下创建页面组件
2. 在 `App.js` 中添加路由配置
3. 如需保护路由，使用 `ProtectedRoute` 组件

### API调用
1. 在 `src/services/api.js` 中添加API方法
2. 在组件中导入并使用
3. 使用try-catch处理错误

## 🔐 安全考虑

- JWT token自动管理
- 路由保护
- XSS防护
- CSRF防护

## 📧 支持

如有问题或建议，请联系开发团队。

## 📄 许可证

本项目仅供学习和演示使用。






