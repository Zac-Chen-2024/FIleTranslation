import axios from 'axios';

// 创建 axios 实例
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 在发送请求之前做些什么
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    if (error.response?.status === 401) {
      // 未授权，清除本地存储并重定向到登录页
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_info');
      window.location.href = '/signin';
    }
    return Promise.reject(error);
  }
);

// API 服务
export const authAPI = {
  // 登录
  signin: async (email, password) => {
    const response = await api.post('/api/auth/signin', { email, password });
    if (response.token) {
      localStorage.setItem('auth_token', response.token);
      localStorage.setItem('user_info', JSON.stringify(response.user));
    }
    return response;
  },

  // 注册
  signup: async (name, email, password) => {
    const response = await api.post('/api/auth/signup', { name, email, password });
    if (response.token) {
      localStorage.setItem('auth_token', response.token);
      localStorage.setItem('user_info', JSON.stringify(response.user));
    }
    return response;
  },

  // 登出
  logout: async () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_info');
    return Promise.resolve();
  },

  // 获取当前用户信息
  getCurrentUser: () => {
    const userInfo = localStorage.getItem('user_info');
    return userInfo ? JSON.parse(userInfo) : null;
  },
};

export const clientAPI = {
  // 获取客户列表
  getClients: async () => {
    return await api.get('/api/clients');
  },

  // 添加客户
  addClient: async (clientData) => {
    return await api.post('/api/clients', clientData);
  },

  // 更新客户信息
  updateClient: async (clientId, updates) => {
    return await api.put(`/api/clients/${clientId}`, updates);
  },

  // 删除客户
  deleteClient: async (clientId) => {
    return await api.delete(`/api/clients/${clientId}`);
  },
};

export const materialAPI = {
  // 获取材料列表
  getMaterials: async (clientId) => {
    return await api.get(`/api/clients/${clientId}/materials`);
  },

  // 上传文件
  uploadFiles: async (clientId, files, onProgress) => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    return await api.post(`/api/clients/${clientId}/materials/upload`, formData, {
      headers: {
        // 不设置Content-Type，让浏览器自动设置multipart/form-data边界
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentage = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentage);
        }
      },
    });
  },

  // 上传网址
  uploadUrls: async (clientId, urls) => {
    return await api.post(`/api/clients/${clientId}/materials/urls`, { urls });
  },

  // 更新材料状态
  updateMaterial: async (materialId, updates) => {
    return await api.put(`/api/materials/${materialId}`, updates);
  },

  // 确认材料
  confirmMaterial: async (materialId) => {
    return await api.post(`/api/materials/${materialId}/confirm`);
  },

  // 编辑LaTeX
  editLatex: async (materialId, description) => {
    return await api.post(`/api/materials/${materialId}/edit`, { description });
  },

  // 选择翻译结果
  selectResult: async (materialId, resultType) => {
    return await api.post(`/api/materials/${materialId}/select`, { resultType });
  },
  
  // 删除材料
  deleteMaterial: async (materialId) => {
    return await api.delete(`/api/materials/${materialId}`);
  },
  
  // 开始翻译
  startTranslation: async (clientId) => {
    return await api.post(`/api/clients/${clientId}/materials/translate`);
  },
  
  // 取消上传
  cancelUpload: async (clientId, materialIds) => {
    return await api.post(`/api/clients/${clientId}/materials/cancel`, {
      material_ids: materialIds
    });
  },
};

export const translationAPI = {
  // 海报翻译
  translatePoster: async (imageFile, onProgress) => {
    const formData = new FormData();
    formData.append('image', imageFile);

    return await api.post('/api/poster-translate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentage = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentage);
        }
      },
    });
  },

  // 图片翻译
  translateImage: async (imageFile, fromLang, toLang, onProgress) => {
    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('from_lang', fromLang);
    formData.append('to_lang', toLang);
    formData.append('save_image', 'true');

    return await api.post('/api/image-translate', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentage = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentage);
        }
      },
    });
  },

  // 网页翻译（Google）
  translateWebpageGoogle: async (url) => {
    return await api.post('/api/webpage-google-translate', { url });
  },

  // 网页翻译（GPT）
  translateWebpageGPT: async (url) => {
    return await api.post('/api/webpage-gpt-translate', { url });
  },
};

export const exportAPI = {
  // 导出客户材料
  exportClientMaterials: async (clientId) => {
    const response = await api.get(`/api/clients/${clientId}/export`, {
      responseType: 'blob',
    });
    
    // 创建下载链接
    const blob = new Blob([response], { type: 'application/zip' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `client_materials_${clientId}_${new Date().toISOString().split('T')[0]}.zip`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
    return response;
  },
};

export const utilsAPI = {
  // 测试后端连接
  testConnection: async () => {
    return await api.get('/health');
  },

  // 获取翻译进度
  getTranslationProgress: async (taskId) => {
    return await api.get(`/api/translation/progress/${taskId}`);
  },
};

export default api;



