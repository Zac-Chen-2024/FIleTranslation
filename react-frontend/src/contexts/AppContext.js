import React, { createContext, useContext, useReducer, useEffect } from 'react';

// 初始状态
const initialState = {
  // 用户相关
  user: null,
  isAuthenticated: false,
  
  // 客户相关
  clients: [],
  currentClient: null,
  
  // 材料相关
  materials: [],
  currentMaterial: null,
  
  // UI状态
  loading: false,
  notification: null,
  modals: {
    addClient: false,
    addMaterial: false,
    progress: false,
  },
  
  // 进度相关
  progress: {
    percentage: 0,
    text: '',
  },
  
  // 上传状态
  uploadStatus: {
    isUploading: false,
    showModal: false, // 控制进度框显示/隐藏
    files: [],
    current: 0,
    total: 0,
    message: '',
    canCancel: true,
    uploadedMaterialIds: [], // 保存最近上传的材料ID
  },
  
  // 确认对话框状态
  confirmDialog: {
    isOpen: false,
    title: '',
    message: '',
    type: 'info', // 'info', 'warning', 'danger'
    confirmText: '确认',
    cancelText: '取消',
    onConfirm: null,
    onCancel: null,
  }
};

// Action 类型
export const ActionTypes = {
  // 用户相关
  SET_USER: 'SET_USER',
  LOGOUT: 'LOGOUT',
  
  // 客户相关
  SET_CLIENTS: 'SET_CLIENTS',
  ADD_CLIENT: 'ADD_CLIENT',
  SET_CURRENT_CLIENT: 'SET_CURRENT_CLIENT',
  
  // 材料相关
  SET_MATERIALS: 'SET_MATERIALS',
  ADD_MATERIALS: 'ADD_MATERIALS',
  UPDATE_MATERIAL: 'UPDATE_MATERIAL',
  SET_CURRENT_MATERIAL: 'SET_CURRENT_MATERIAL',
  
  // UI状态
  SET_LOADING: 'SET_LOADING',
  SET_NOTIFICATION: 'SET_NOTIFICATION',
  CLEAR_NOTIFICATION: 'CLEAR_NOTIFICATION',
  TOGGLE_MODAL: 'TOGGLE_MODAL',
  
  // 进度相关
  SET_PROGRESS: 'SET_PROGRESS',
  RESET_PROGRESS: 'RESET_PROGRESS',
  
  // 上传相关
  START_UPLOAD: 'START_UPLOAD',
  UPDATE_UPLOAD_PROGRESS: 'UPDATE_UPLOAD_PROGRESS',
  COMPLETE_UPLOAD: 'COMPLETE_UPLOAD',
  CANCEL_UPLOAD: 'CANCEL_UPLOAD',
  SET_UPLOADED_MATERIALS: 'SET_UPLOADED_MATERIALS',
  HIDE_UPLOAD_MODAL: 'HIDE_UPLOAD_MODAL',
  
  // 确认对话框相关
  OPEN_CONFIRM_DIALOG: 'OPEN_CONFIRM_DIALOG',
  CLOSE_CONFIRM_DIALOG: 'CLOSE_CONFIRM_DIALOG',
};

// Reducer
const appReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_USER:
      return {
        ...state,
        user: action.payload,
        isAuthenticated: !!action.payload,
      };
      
    case ActionTypes.LOGOUT:
      return {
        ...state,
        user: null,
        isAuthenticated: false,
        clients: [],
        currentClient: null,
        materials: [],
        currentMaterial: null,
      };
      
    case ActionTypes.SET_CLIENTS:
      return {
        ...state,
        clients: action.payload,
      };
      
    case ActionTypes.ADD_CLIENT:
      return {
        ...state,
        clients: [...state.clients, action.payload],
      };
      
    case ActionTypes.SET_CURRENT_CLIENT:
      return {
        ...state,
        currentClient: action.payload,
        currentMaterial: null, // 切换客户时清空当前材料
      };
      
    case ActionTypes.SET_MATERIALS:
      return {
        ...state,
        materials: action.payload,
      };
      
    case ActionTypes.ADD_MATERIALS:
      return {
        ...state,
        materials: [...state.materials, ...action.payload],
      };
      
    case ActionTypes.UPDATE_MATERIAL:
      const updatedMaterials = state.materials.map(material =>
        material.id === action.payload.id
          ? { ...material, ...action.payload.updates }
          : material
      );
      
      // 如果更新的材料是当前选中的材料，也要更新currentMaterial
      const updatedCurrentMaterial = state.currentMaterial?.id === action.payload.id
        ? { ...state.currentMaterial, ...action.payload.updates }
        : state.currentMaterial;
      
      return {
        ...state,
        materials: updatedMaterials,
        currentMaterial: updatedCurrentMaterial,
      };
      
    case ActionTypes.SET_CURRENT_MATERIAL:
      return {
        ...state,
        currentMaterial: action.payload,
      };
      
    case ActionTypes.SET_LOADING:
      return {
        ...state,
        loading: action.payload,
      };
      
    case ActionTypes.SET_NOTIFICATION:
      return {
        ...state,
        notification: action.payload,
      };
      
    case ActionTypes.CLEAR_NOTIFICATION:
      return {
        ...state,
        notification: null,
      };
      
    case ActionTypes.TOGGLE_MODAL:
      return {
        ...state,
        modals: {
          ...state.modals,
          [action.payload.modalName]: action.payload.isOpen,
        },
      };
      
    case ActionTypes.SET_PROGRESS:
      return {
        ...state,
        progress: action.payload,
      };
      
    case ActionTypes.RESET_PROGRESS:
      return {
        ...state,
        progress: { percentage: 0, text: '' },
      };
      
    case ActionTypes.START_UPLOAD:
      return {
        ...state,
        uploadStatus: {
          ...action.payload,
          isUploading: true,
          showModal: true,
        }
      };
      
    case ActionTypes.UPDATE_UPLOAD_PROGRESS:
      return {
        ...state,
        uploadStatus: {
          ...state.uploadStatus,
          ...action.payload,
        }
      };
      
    case ActionTypes.COMPLETE_UPLOAD:
      return {
        ...state,
        uploadStatus: {
          isUploading: false,
          showModal: false, // 关闭进度框
          files: [],
          current: 0,
          total: 0,
          message: '已关闭',
          canCancel: false,
          uploadedMaterialIds: [],
        }
      };
      
    case ActionTypes.CANCEL_UPLOAD:
      return {
        ...state,
        uploadStatus: {
          isUploading: false,
          showModal: false, // 关闭进度框
          files: [],
          current: 0,
          total: 0,
          message: '上传已取消',
          canCancel: false,
          uploadedMaterialIds: [],
        }
      };
      
    case ActionTypes.SET_UPLOADED_MATERIALS:
      return {
        ...state,
        uploadStatus: {
          ...state.uploadStatus,
          uploadedMaterialIds: action.payload,
        }
      };
      
    case ActionTypes.HIDE_UPLOAD_MODAL:
      return {
        ...state,
        uploadStatus: {
          ...state.uploadStatus,
          showModal: false,
        }
      };
      
    case ActionTypes.OPEN_CONFIRM_DIALOG:
      return {
        ...state,
        confirmDialog: {
          ...action.payload,
          isOpen: true,
        }
      };
      
    case ActionTypes.CLOSE_CONFIRM_DIALOG:
      return {
        ...state,
        confirmDialog: {
          ...state.confirmDialog,
          isOpen: false,
          onConfirm: null,
          onCancel: null,
        }
      };
      
    default:
      return state;
  }
};

// Context
const AppContext = createContext();

// Provider 组件
export const AppProvider = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, initialState);

  // 自动清除通知
  useEffect(() => {
    if (state.notification) {
      const timer = setTimeout(() => {
        dispatch({ type: ActionTypes.CLEAR_NOTIFICATION });
      }, 4000);
      return () => clearTimeout(timer);
    }
  }, [state.notification]);

  // Action creators
  const actions = {
    // 用户相关
    setUser: (user) => {
      dispatch({ type: ActionTypes.SET_USER, payload: user });
    },
    
    logout: () => {
      dispatch({ type: ActionTypes.LOGOUT });
    },
    
    // 客户相关
    setClients: (clients) => {
      dispatch({ type: ActionTypes.SET_CLIENTS, payload: clients });
    },
    
    addClient: (client) => {
      dispatch({ type: ActionTypes.ADD_CLIENT, payload: client });
    },
    
    setCurrentClient: (client) => {
      dispatch({ type: ActionTypes.SET_CURRENT_CLIENT, payload: client });
    },
    
    // 材料相关
    setMaterials: (materials) => {
      dispatch({ type: ActionTypes.SET_MATERIALS, payload: materials });
    },
    
    addMaterials: (materials) => {
      dispatch({ type: ActionTypes.ADD_MATERIALS, payload: materials });
    },
    
    updateMaterial: (id, updates) => {
      dispatch({ type: ActionTypes.UPDATE_MATERIAL, payload: { id, updates } });
    },
    
    setCurrentMaterial: (material) => {
      dispatch({ type: ActionTypes.SET_CURRENT_MATERIAL, payload: material });
    },
    
    // UI状态
    setLoading: (loading) => {
      dispatch({ type: ActionTypes.SET_LOADING, payload: loading });
    },
    
    showNotification: (title, message, type = 'success') => {
      dispatch({ 
        type: ActionTypes.SET_NOTIFICATION, 
        payload: { title, message, type } 
      });
    },
    
    clearNotification: () => {
      dispatch({ type: ActionTypes.CLEAR_NOTIFICATION });
    },
    
    toggleModal: (modalName, isOpen) => {
      dispatch({ 
        type: ActionTypes.TOGGLE_MODAL, 
        payload: { modalName, isOpen } 
      });
    },
    
    // 进度相关
    setProgress: (percentage, text) => {
      dispatch({ 
        type: ActionTypes.SET_PROGRESS, 
        payload: { percentage, text } 
      });
    },
    
    resetProgress: () => {
      dispatch({ type: ActionTypes.RESET_PROGRESS });
    },
    
    // 上传相关
    startUpload: (files, message = '准备上传...') => {
      dispatch({ 
        type: ActionTypes.START_UPLOAD, 
        payload: { 
          files: files, 
          total: files.length, 
          current: 0, 
          message: message,
          canCancel: true 
        } 
      });
    },
    
    updateUploadProgress: (current, message, canCancel = true, isUploading = null) => {
      const payload = { current, message, canCancel };
      if (isUploading !== null) {
        payload.isUploading = isUploading;
      }
      dispatch({ 
        type: ActionTypes.UPDATE_UPLOAD_PROGRESS, 
        payload 
      });
    },
    
    completeUpload: () => {
      dispatch({ type: ActionTypes.COMPLETE_UPLOAD });
    },
    
    cancelUpload: () => {
      dispatch({ type: ActionTypes.CANCEL_UPLOAD });
    },
    
    setUploadedMaterials: (materialIds) => {
      dispatch({ type: ActionTypes.SET_UPLOADED_MATERIALS, payload: materialIds });
    },
    
    hideUploadModal: () => {
      dispatch({ type: ActionTypes.HIDE_UPLOAD_MODAL });
    },
    
    // 确认对话框
    openConfirmDialog: (config) => {
      dispatch({ type: ActionTypes.OPEN_CONFIRM_DIALOG, payload: config });
    },
    
    closeConfirmDialog: () => {
      dispatch({ type: ActionTypes.CLOSE_CONFIRM_DIALOG });
    },
  };

  const value = {
    state,
    actions,
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
};

// Hook
export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};