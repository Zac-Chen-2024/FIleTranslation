import React from 'react';
import { useApp } from '../../contexts/AppContext';
import { materialAPI } from '../../services/api';
import styles from './MaterialsList.module.css';

const MaterialsList = () => {
  const { state, actions } = useApp();
  const { materials, currentClient, currentMaterial } = state;

  // 过滤并去重材料，优先显示已翻译完成的
  const clientMaterials = materials
    .filter(m => m.clientId === currentClient?.cid)
    .reduce((unique, material) => {
      const existing = unique.find(m => m.name === material.name);
      if (!existing) {
        unique.push(material);
      } else {
        // 如果有同名材料，优先保留翻译完成的或更新时间更晚的
        const shouldReplace = 
          (material.status === '翻译完成' && existing.status !== '翻译完成') ||
          (material.status === existing.status && new Date(material.updatedAt) > new Date(existing.updatedAt)) ||
          (material.translatedImagePath && !existing.translatedImagePath); // 优先显示有翻译图片的
        
        if (shouldReplace) {
          const index = unique.indexOf(existing);
          unique[index] = material;
          console.log('替换材料:', {
            oldMaterial: existing,
            newMaterial: material,
            reason: material.status === '翻译完成' ? '翻译完成' : material.translatedImagePath ? '有翻译图片' : '更新时间晚'
          });
        }
      }
      return unique;
    }, []);

  const handleMaterialSelect = (material) => {
    actions.setCurrentMaterial(material);
  };

  const handleAddMaterial = () => {
    actions.toggleModal('addMaterial', true);
  };

  const handleDeleteMaterial = async (material, e) => {
    e.stopPropagation(); // 防止触发选择材料
    
    actions.openConfirmDialog({
      title: '删除材料',
      message: `确定要删除材料 "${material.name}" 吗？`,
      type: 'danger',
      confirmText: '删除',
      cancelText: '取消',
      onConfirm: async () => {
        try {
          await materialAPI.deleteMaterial(material.id);
          actions.showNotification('删除成功', `材料 ${material.name} 已删除`, 'success');
          
          // 从本地状态中移除材料
          const updatedMaterials = materials.filter(m => m.id !== material.id);
          actions.setMaterials(updatedMaterials);
          
          // 如果删除的是当前选中的材料，清除选择
          if (currentMaterial?.id === material.id) {
            actions.setCurrentMaterial(null);
          }
        } catch (error) {
          actions.showNotification('删除失败', error.message || '删除材料时出现错误', 'error');
        }
      }
    });
  };

  if (clientMaterials.length === 0) {
    return (
      <div className={styles.materialsSection}>
        <h3 className={styles.title}>材料列表</h3>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>📄</div>
          <h4 className={styles.emptyTitle}>暂无材料</h4>
          <p className={styles.emptyDescription}>
            为 {currentClient?.name} 添加翻译材料
          </p>
          <button 
            className={styles.addBtn}
            onClick={handleAddMaterial}
          >
            添加材料
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.materialsSection}>
      <h3 className={styles.title}>材料列表</h3>
      <div className={styles.materialsList}>
        {clientMaterials.map((material) => (
          <div
            key={material.id}
            className={`${styles.materialItem} ${
              currentMaterial?.id === material.id ? styles.active : ''
            } ${material.confirmed ? styles.confirmed : ''}`}
            onClick={() => handleMaterialSelect(material)}
          >
            <div className={styles.materialContent}>
              <div className={styles.materialName}>{material.name}</div>
              <div className={styles.materialMeta}>
                <span className={styles.materialType}>{getTypeLabel(material.type)}</span>
                <span className={styles.materialStatus}>{material.status}</span>
              </div>
            </div>
            <button
              className={styles.deleteMaterialBtn}
              onClick={(e) => handleDeleteMaterial(material, e)}
              title="删除材料"
            >
              🗑️
            </button>
            {material.confirmed && (
              <div className={styles.confirmedIcon}>✓</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

const getTypeLabel = (type) => {
  const typeLabels = {
    pdf: 'PDF文档',
    image: '图片',
    webpage: '网页',
    document: '文档'
  };
  return typeLabels[type] || type;
};

export default MaterialsList;





