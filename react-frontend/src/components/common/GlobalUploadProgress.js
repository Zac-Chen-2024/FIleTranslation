import React, { useCallback } from 'react';
import { useApp } from '../../contexts/AppContext';
import styles from './GlobalUploadProgress.module.css';

const GlobalUploadProgress = () => {
  const { state, actions } = useApp();
  const { uploadStatus } = state;

  const progressPercentage = uploadStatus.total > 0 ? 
    Math.round((uploadStatus.current / uploadStatus.total) * 100) : 0;
  
  const isComplete = uploadStatus.current === uploadStatus.total && uploadStatus.total > 0;

  // 移除格式化时间函数，不再需要倒计时

  const handleComplete = useCallback(async () => {
    if (isComplete) {
      // 立即关闭进度框，不等待任何操作
      actions.hideUploadModal();
      
      // 后台启动翻译进程
      try {
        const { currentClient } = state;
        const { materialAPI } = await import('../../services/api');
        
        actions.showNotification('翻译开始', '正在翻译图片，请稍候...', 'success');
        
        // 启动翻译（等待完成）
        console.log('启动翻译，客户端ID:', currentClient.cid);
        try {
          const response = await materialAPI.startTranslation(currentClient.cid);
          console.log('翻译API响应:', response);
          
          // 方案1: 如果API直接返回了翻译结果，立即使用
          if (response.data && response.data.translated_materials && response.data.translated_materials.length > 0) {
            console.log('使用API直接返回的翻译结果:', response.data.translated_materials);
            
            // 1. 先更新每个翻译成功的材料在全局状态中
            const translatedMaterialsMap = new Map();
            response.data.translated_materials.forEach(tm => {
              translatedMaterialsMap.set(tm.id, tm);
            });
            
            console.log('翻译结果映射:', translatedMaterialsMap);
            
            // 2. 更新材料列表，将翻译结果直接应用到对应材料
            const currentMaterials = state.materials.map(material => {
              const translatedData = translatedMaterialsMap.get(material.id);
              if (translatedData) {
                console.log('更新材料翻译状态:', material.id, translatedData);
                return {
                  ...material,
                  status: '翻译完成',
                  translatedImagePath: translatedData.translated_image_path,
                  translationTextInfo: translatedData.translation_text_info,
                  translationError: null,
                  updatedAt: new Date().toISOString() // 更新时间戳确保最新
                };
              }
              return material;
            });
            
            // 3. 立即应用更新后的材料列表
            console.log('应用更新后的材料列表:', currentMaterials);
            actions.setMaterials(currentMaterials);
            
            // 4. 如果当前选中的材料被翻译了，立即更新预览
            if (state.currentMaterial) {
              const translatedCurrentMaterial = translatedMaterialsMap.get(state.currentMaterial.id);
              if (translatedCurrentMaterial) {
                const updatedCurrentMaterial = {
                  ...state.currentMaterial,
                  status: '翻译完成',
                  translatedImagePath: translatedCurrentMaterial.translated_image_path,
                  translationTextInfo: translatedCurrentMaterial.translation_text_info,
                  translationError: null,
                  updatedAt: new Date().toISOString()
                };
                console.log('立即更新当前材料翻译状态:', updatedCurrentMaterial);
                actions.setCurrentMaterial(updatedCurrentMaterial);
              }
            }
            
            actions.showNotification(
              '翻译完成', 
              `成功翻译 ${response.data.translated_count} 个文件，失败 ${response.data.failed_count || 0} 个`, 
              'success'
            );
          } else {
            // 方案2: 没有直接结果，按原来的方式刷新材料列表
            console.log('API未返回直接结果，刷新材料列表');
            const materialsData = await materialAPI.getMaterials(currentClient.cid);
            actions.setMaterials(materialsData.materials || []);
            
            // 强制刷新当前材料状态
            if (state.currentMaterial) {
              const updatedCurrentMaterial = materialsData.materials.find(
                m => m.id === state.currentMaterial.id
              );
              if (updatedCurrentMaterial) {
                actions.setCurrentMaterial(updatedCurrentMaterial);
              }
            }
            
            actions.showNotification('翻译完成', '翻译结果已更新，请查看预览区域', 'info');
          }
        } catch (error) {
          console.error('翻译API调用失败:', error);
          actions.showNotification('翻译失败', error.message || '启动翻译时出现错误', 'error');
        }
        
      } catch (error) {
        actions.showNotification('翻译失败', error.message || '启动翻译时出现错误', 'error');
      }
    }
  }, [isComplete, state, actions]);

  // 手动关闭进度框
  const handleManualClose = useCallback(() => {
    actions.hideUploadModal();
  }, [actions]);

  const handleCancel = async () => {
    if (isComplete) {
      // 撤销上传：删除已上传的文件
      actions.openConfirmDialog({
        title: '撤销上传',
        message: '确定要撤销这次上传吗？所有文件将被删除。',
        type: 'danger',
        confirmText: '撤销删除',
        cancelText: '保留文件',
        onConfirm: async () => {
          try {
            const { currentClient, uploadStatus } = state;
            if (uploadStatus.uploadedMaterialIds && uploadStatus.uploadedMaterialIds.length > 0) {
              // 调用后端API删除文件
              const { materialAPI } = await import('../../services/api');
              await materialAPI.cancelUpload(currentClient.cid, uploadStatus.uploadedMaterialIds);
              
              // 更新本地状态
              const updatedMaterials = state.materials.filter(m => 
                !uploadStatus.uploadedMaterialIds.includes(m.id)
              );
              actions.setMaterials(updatedMaterials);
              actions.showNotification('撤销成功', '已删除上传的文件', 'success');
            }
          } catch (error) {
            actions.showNotification('撤销失败', error.message || '删除文件时出现错误', 'error');
          }
          actions.cancelUpload();
        }
      });
    } else if (uploadStatus.canCancel) {
      // 取消上传中的过程
      actions.openConfirmDialog({
        title: '取消上传',
        message: '确定要取消上传吗？',
        type: 'warning',
        confirmText: '取消上传',
        cancelText: '继续上传',
        onConfirm: () => {
          actions.cancelUpload();
        }
      });
    }
  };

  // 移除自动倒计时，用户手动确认
  // 进度条框作为用户确认界面，不自动消失

  // 如果进度框不应该显示，不显示组件
  if (!uploadStatus.showModal) return null;

  return (
    <div className={styles.overlay}>
      <div className={styles.modal}>
        <div className={styles.header}>
          <h3 className={styles.title}>文件上传</h3>
          {isComplete && (
            <button 
              className={styles.closeBtn}
              onClick={handleManualClose}
              title="关闭进度框"
            >
              ✕
            </button>
          )}
        </div>
        
        <div className={styles.body}>
          {/* 简化的进度条 */}
          <div className={styles.progressBarContainer}>
            <div className={styles.progressBar}>
              <div 
                className={styles.progressFill}
                style={{ width: `${progressPercentage}%` }}
              ></div>
            </div>
            <div className={styles.progressText}>
              {uploadStatus.current}/{uploadStatus.total} 文件 ({progressPercentage}%)
            </div>
          </div>
          
          {/* 完成后的确认提示 */}
          {isComplete && (
            <div className={styles.completionMessage}>
              ✅ 文件已上传到服务器！请选择下一步操作，或点击右上角 ✕ 关闭此框。
            </div>
          )}
        </div>
        
        {/* 简化的按钮 */}
        <div className={styles.footer}>
          {isComplete ? (
            <div className={styles.buttonGroup}>
              <button 
                className={`${styles.btn} ${styles.btnDanger}`}
                onClick={handleCancel}
              >
                撤销删除
              </button>
              <button 
                className={`${styles.btn} ${styles.btnPrimary}`}
                onClick={handleComplete}
              >
                完成并翻译
              </button>
            </div>
          ) : (
            <div className={styles.buttonGroup}>
              <button 
                className={`${styles.btn} ${styles.btnCancel}`}
                onClick={handleCancel}
                disabled={!uploadStatus.canCancel}
              >
                取消上传
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default GlobalUploadProgress;