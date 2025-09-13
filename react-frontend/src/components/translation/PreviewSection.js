import React, { useState, useCallback, useEffect } from 'react';
import { useApp } from '../../contexts/AppContext';
import { materialAPI } from '../../services/api';
import LaTeXEditModal from '../modals/LaTeXEditModal';
import LaTeXEditModalV2 from '../modals/LaTeXEditModalV2';
import styles from './PreviewSection.module.css';

const PreviewSection = () => {
  const { state, actions } = useApp();
  const { currentMaterial } = state;
  const [showLatexEditor, setShowLatexEditor] = useState(false);
  const [showLatexEditorV2, setShowLatexEditorV2] = useState(false);
  const [forceRefresh, setForceRefresh] = useState(0);

  // 监听currentMaterial变化，强制刷新预览
  useEffect(() => {
    console.log('PreviewSection: currentMaterial 变化:', currentMaterial);
    setForceRefresh(prev => prev + 1);
  }, [currentMaterial?.id, currentMaterial?.translatedImagePath, currentMaterial?.status]);

  const handleEdit = () => {
    if (!currentMaterial) return;
    setShowLatexEditor(true);
  };

  const handleEditV2 = () => {
    if (!currentMaterial) return;
    setShowLatexEditorV2(true);
  };

  const handleConfirm = async () => {
    if (!currentMaterial) return;
    
    try {
      const newConfirmedState = !currentMaterial.confirmed;
      
      // 本地更新状态
      actions.updateMaterial(currentMaterial.id, { 
        confirmed: newConfirmedState, 
        status: newConfirmedState ? '已确认' : '翻译完成' 
      });
      
      const message = newConfirmedState 
        ? `${currentMaterial.name} 已确认完成` 
        : `${currentMaterial.name} 已取消确认`;
      
      actions.showNotification(
        newConfirmedState ? '确认成功' : '取消确认成功', 
        message, 
        'success'
      );
      
      // 实际API调用
      // if (newConfirmedState) {
      //   await materialAPI.confirmMaterial(currentMaterial.id);
      // } else {
      //   await materialAPI.unconfirmMaterial(currentMaterial.id);
      // }
      
    } catch (error) {
      actions.showNotification('操作失败', error.message || '操作过程中出现错误', 'error');
    }
  };

  // 使用useCallback优化性能，避免不必要的重新渲染
  const handleSelectResult = useCallback(async (resultType) => {
    console.log('handleSelectResult called:', {
      materialId: currentMaterial?.id,
      currentSelected: currentMaterial?.selectedResult,
      newSelection: resultType
    });
    
    if (!currentMaterial || currentMaterial.selectedResult === resultType) return;
    
    try {
      // 本地更新状态
      actions.updateMaterial(currentMaterial.id, { selectedResult: resultType });
      
      actions.showNotification('选择成功', `已选择${resultType === 'latex' ? 'LaTeX' : 'API'}翻译结果`, 'success');
      
      // 实际API调用
      // await materialAPI.selectResult(currentMaterial.id, resultType);
      
    } catch (error) {
      actions.showNotification('选择失败', error.message || '选择结果时出现错误', 'error');
    }
  }, [currentMaterial, actions]);

  const handleRetryTranslation = useCallback(async (translationType) => {
    if (!currentMaterial) return;
    
    try {
      // 显示重试通知
      actions.showNotification('重新翻译', `正在重新进行${translationType === 'latex' ? 'LaTeX' : 'API'}翻译...`, 'info');
      
      if (translationType === 'api') {
        // 重新调用API翻译
        const { materialAPI } = await import('../../services/api');
        await materialAPI.startTranslation(currentMaterial.clientId);
        
        // 刷新材料列表
        setTimeout(async () => {
          try {
            const materialsData = await materialAPI.getMaterials(currentMaterial.clientId);
            actions.setMaterials(materialsData.materials || []);
          } catch (error) {
            console.error('刷新材料列表失败:', error);
          }
        }, 2000);
        
      } else if (translationType === 'latex') {
        // 这里可以添加LaTeX翻译的重试逻辑
        actions.showNotification('功能开发中', 'LaTeX翻译重试功能正在开发中', 'warning');
      }
      
    } catch (error) {
      actions.showNotification('重试失败', error.message || '重新翻译时出现错误', 'error');
    }
  }, [currentMaterial, actions]);

  if (!currentMaterial) {
    return (
      <div className={styles.previewSection}>
        <div className={styles.header}>
          <h3 className={styles.title}>翻译预览</h3>
        </div>
        <div className={styles.content}>
          <div className={styles.placeholder}>
            <div className={styles.placeholderIcon}>📄</div>
            <h4>选择材料查看翻译结果</h4>
            <p>请从左侧列表中选择要查看的材料</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.previewSection}>
      <div className={styles.header}>
        <h3 className={styles.title}>翻译预览</h3>
        <div className={styles.actions}>
          {(currentMaterial.type === 'image' || currentMaterial.type === 'pdf') && 
           currentMaterial.selectedResult === 'latex' && (
            <>
              <button 
                className={`${styles.actionBtn} ${styles.btnEdit}`}
                onClick={handleEdit}
              >
                编辑
              </button>
              <button 
                className={`${styles.actionBtn} ${styles.btnEditV2}`}
                onClick={handleEditV2}
                title="测试版：支持选中预览内容进行精确编辑"
              >
                🧪 V2编辑
              </button>
            </>
          )}
          <button 
            className={`${styles.actionBtn} ${currentMaterial.confirmed ? styles.btnUnconfirm : styles.btnConfirm}`}
            onClick={handleConfirm}
          >
            {currentMaterial.confirmed ? '取消确认' : '确认'}
          </button>
        </div>
      </div>
      
      <div className={styles.content}>
        {(currentMaterial.type === 'image' || currentMaterial.type === 'pdf') ? (
          <ComparisonView 
            key={`comparison-${currentMaterial.id}-${forceRefresh}`}
            material={currentMaterial} 
            onSelectResult={handleSelectResult}
          />
        ) : (
          <SinglePreview 
            key={`single-${currentMaterial.id}-${forceRefresh}`}
            material={currentMaterial} 
          />
        )}
      </div>

      {/* LaTeX编辑模态框 */}
      <LaTeXEditModal 
        isOpen={showLatexEditor}
        onClose={() => setShowLatexEditor(false)}
        material={currentMaterial}
      />

      {/* LaTeX编辑模态框 V2 */}
      <LaTeXEditModalV2 
        isOpen={showLatexEditorV2}
        onClose={() => setShowLatexEditorV2(false)}
        material={currentMaterial}
      />
    </div>
  );
};

const ComparisonView = ({ material, onSelectResult }) => {
  const { actions } = useApp();
  const isLatexSelected = material.selectedResult === 'latex';
  const isApiSelected = material.selectedResult === 'api';

  // 调试信息可以在问题解决后移除

  const handleRetryTranslation = useCallback(async (translationType) => {
    if (!material) return;
    
    try {
      actions.showNotification('重新翻译', `正在重新进行${translationType === 'latex' ? 'LaTeX' : 'API'}翻译...`, 'info');
      
      if (translationType === 'api') {
        const { materialAPI } = await import('../../services/api');
        const { state: currentState } = await import('../../contexts/AppContext');
        console.log('重新翻译API调用，材料ID:', material.id);
        const response = await materialAPI.startTranslation(material.clientId);
        console.log('重新翻译API响应:', response);
        
        // 使用与GlobalUploadProgress相同的实时更新机制
        if (response.data && response.data.translated_materials && response.data.translated_materials.length > 0) {
          console.log('重新翻译：使用API直接返回的翻译结果:', response.data.translated_materials);
          
          // 创建翻译结果映射
          const translatedMaterialsMap = new Map();
          response.data.translated_materials.forEach(tm => {
            translatedMaterialsMap.set(tm.id, tm);
          });
          
          // 检查当前材料是否被翻译
          const translatedCurrentMaterial = translatedMaterialsMap.get(material.id);
          if (translatedCurrentMaterial) {
            const updatedMaterial = {
              ...material,
              status: '翻译完成',
              translatedImagePath: translatedCurrentMaterial.translated_image_path,
              translationTextInfo: translatedCurrentMaterial.translation_text_info,
              translationError: null,
              updatedAt: new Date().toISOString()
            };
            console.log('重新翻译：立即更新当前材料:', updatedMaterial);
            actions.setCurrentMaterial(updatedMaterial);
            
            // 同时更新材料列表中的对应项
            actions.updateMaterial(material.id, {
              status: '翻译完成',
              translatedImagePath: translatedCurrentMaterial.translated_image_path,
              translationTextInfo: translatedCurrentMaterial.translation_text_info,
              translationError: null,
              updatedAt: new Date().toISOString()
            });
          }
          
          actions.showNotification(
            '重新翻译完成', 
            `成功翻译 ${response.data.translated_count} 个文件`, 
            'success'
          );
        } else {
          // 备用方案：刷新材料列表
          try {
            const materialsData = await materialAPI.getMaterials(material.clientId);
            console.log('重新翻译后刷新的材料数据:', materialsData.materials);
            actions.setMaterials(materialsData.materials || []);
            
            const updatedCurrentMaterial = materialsData.materials.find(
              m => m.id === material.id
            );
            if (updatedCurrentMaterial) {
              console.log('重新翻译后更新当前材料:', updatedCurrentMaterial);
              actions.setCurrentMaterial(updatedCurrentMaterial);
            }
            
            actions.showNotification('重新翻译完成', '翻译结果已更新', 'success');
          } catch (error) {
            console.error('刷新材料列表失败:', error);
            actions.showNotification('更新失败', '翻译完成，但获取结果时出错，请手动刷新', 'warning');
          }
        }
        
      } else if (translationType === 'latex') {
        actions.showNotification('功能开发中', 'LaTeX翻译重试功能正在开发中', 'warning');
      }
      
    } catch (error) {
      actions.showNotification('重试失败', error.message || '重新翻译时出现错误', 'error');
    }
  }, [material, actions]);

  // 调试日志 - 实际项目中可以移除
  console.log('ComparisonView render:', {
    materialId: material.id,
    selectedResult: material.selectedResult,
    isLatexSelected,
    isApiSelected,
    status: material.status,
    translatedImagePath: material.translatedImagePath,
    translationError: material.translationError,
    translationTextInfo: material.translationTextInfo,
    updatedAt: material.updatedAt,
    // 判断条件
    hasTranslatedImage: !!material.translatedImagePath,
    isTranslationComplete: material.status === '翻译完成',
    isTranslationFailed: material.status === '翻译失败',
    isUploaded: material.status === '已上传'
  });

  return (
    <div className={styles.comparisonView}>
      <div className={`${styles.comparisonPanel} ${isLatexSelected ? styles.selected : ''}`}>
        <div className={styles.panelHeader}>LaTeX 翻译</div>
        <div className={styles.panelContent}>
          {material.latexTranslationError ? (
            <div className={styles.errorContent}>
              <div className={styles.errorIcon}>❌</div>
              <p className={styles.errorMessage}>LaTeX翻译失败</p>
              <p className={styles.errorDetails}>{material.latexTranslationError}</p>
              <button 
                className={`${styles.retryBtn} ${styles.latexRetryBtn}`}
                onClick={() => handleRetryTranslation('latex')}
              >
                🔄 重新翻译
              </button>
            </div>
          ) : material.latexTranslationResult ? (
            <div className={styles.translationSuccess}>
              <div className={styles.successIcon}>✅</div>
              <p>LaTeX翻译完成</p>
              {/* 这里可以显示LaTeX内容预览 */}
            </div>
          ) : (
            <div className={styles.previewPlaceholder}>
              <div className={styles.placeholderIcon}>📄</div>
              <p>LaTeX 翻译预览</p>
            </div>
          )}
        </div>
        <div className={styles.panelActions}>
          <button 
            className={`${styles.selectBtn} ${isLatexSelected ? styles.selected : ''}`}
            onClick={() => onSelectResult('latex')}
            disabled={isLatexSelected}
          >
            {isLatexSelected ? '✓ 已选择' : '选择此结果'}
          </button>
        </div>
      </div>
      
      <div className={`${styles.comparisonPanel} ${isApiSelected ? styles.selected : ''}`}>
        <div className={styles.panelHeader}>API 翻译</div>
        <div className={styles.panelContent}>
          {material.translatedImagePath || material.status === '翻译完成' ? (
            <div className={styles.translationContent}>
              {/* 显示翻译后的图片 */}
              {material.translatedImagePath && (
                <div className={styles.translatedImage}>
                  <img 
                    key={`translated-${material.id}-${material.updatedAt || Date.now()}`}
                    src={`http://localhost:5000/download/image/${material.translatedImagePath}?t=${Date.now()}`}
                    alt="翻译后的图片"
                    style={{ maxWidth: '100%', height: 'auto' }}
                    onLoad={() => {
                      console.log('翻译图片加载成功:', material.translatedImagePath);
                    }}
                    onError={(e) => {
                      console.error('图片加载失败:', material.translatedImagePath);
                      console.error('完整URL:', e.target.src);
                      console.error('材料状态:', material.status);
                      console.error('翻译错误:', material.translationError);
                    }}
                  />
                </div>
              )}
              <div className={styles.translationSuccess}>
                <div className={styles.successIcon}>✅</div>
                <p>API翻译完成</p>
                {!material.translatedImagePath && (
                  <div className={styles.debugInfo}>
                    <p>调试信息：</p>
                    <p>状态: {material.status}</p>
                    <p>图片路径: {material.translatedImagePath || '无'}</p>
                    <p>翻译错误: {material.translationError || '无'}</p>
                    <p>材料ID: {material.id}</p>
                  </div>
                )}
              </div>
            </div>
          ) : material.status === '翻译失败' ? (
            <div className={styles.errorContent}>
              <div className={styles.errorIcon}>❌</div>
              <p className={styles.errorMessage}>API翻译失败</p>
              <p className={styles.errorDetails}>{material.translationError}</p>
              <button 
                className={`${styles.retryBtn} ${styles.apiRetryBtn}`}
                onClick={() => handleRetryTranslation('api')}
              >
                🔄 重新翻译
              </button>
            </div>
          ) : (
            <div className={styles.previewPlaceholder}>
              <div className={styles.placeholderIcon}>🤖</div>
              <p>等待API翻译结果</p>
            </div>
          )}
        </div>
        <div className={styles.panelActions}>
          <button 
            className={`${styles.selectBtn} ${isApiSelected ? styles.selected : ''}`}
            onClick={() => onSelectResult('api')}
            disabled={isApiSelected}
          >
            {isApiSelected ? '✓ 已选择' : '选择此结果'}
          </button>
        </div>
      </div>
    </div>
  );
};

const SinglePreview = ({ material }) => {
  return (
    <div className={styles.singlePreview}>
      <div className={styles.previewPlaceholder}>
        <div className="loading-spinner"></div>
        <h4>网页翻译预览</h4>
        <p>正在处理网页内容...</p>
      </div>
    </div>
  );
};

export default PreviewSection;


