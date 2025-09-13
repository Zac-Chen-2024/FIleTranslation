import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { materialAPI } from '../services/api';
import AddMaterialModal from '../components/modals/AddMaterialModal';
import MaterialsList from '../components/translation/MaterialsList';
import PreviewSection from '../components/translation/PreviewSection';
import styles from './TranslationPage.module.css';

const TranslationPage = () => {
  const navigate = useNavigate();
  const { clientId } = useParams();
  const { state, actions } = useApp();
  const { currentClient, materials, currentMaterial } = state;
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 如果没有当前客户，尝试从客户列表中查找
    if (!currentClient) {
      const client = state.clients.find(c => c.cid === clientId);
      if (client) {
        actions.setCurrentClient(client);
      } else {
        // 如果找不到客户，返回主界面
        navigate('/dashboard');
        return;
      }
    }
    
    loadMaterials();
  }, [clientId, currentClient]);

  const loadMaterials = async () => {
    try {
      setLoading(true);
      // 直接从API加载材料列表
      const materialsData = await materialAPI.getMaterials(clientId);
      actions.setMaterials(materialsData.materials || []);
    } catch (error) {
      actions.showNotification('加载失败', '无法加载材料列表', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleBackToDashboard = () => {
    navigate('/dashboard');
  };

  const handleAddMaterial = () => {
    actions.toggleModal('addMaterial', true);
  };

  const handleExport = async () => {
    const clientMaterials = materials.filter(m => m.clientId === clientId);
    const confirmedMaterials = clientMaterials.filter(m => m.confirmed);
    const unconfirmedCount = clientMaterials.length - confirmedMaterials.length;
    
    if (unconfirmedCount > 0) {
      const proceed = window.confirm(
        `您有 ${unconfirmedCount} 个文件尚未确认，本次导出的压缩包将不包含这些文件。是否继续？`
      );
      if (!proceed) return;
    }
    
    if (confirmedMaterials.length === 0) {
      actions.showNotification('导出失败', '没有已确认的材料可以导出', 'error');
      return;
    }
    
    try {
      actions.showNotification('导出开始', '正在打包文件...', 'success');
      
      // 模拟导出过程
      setTimeout(() => {
        // 创建虚拟下载链接
        const blob = new Blob(['模拟的ZIP文件内容'], { type: 'application/zip' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${currentClient?.name}_翻译材料_${new Date().toISOString().split('T')[0]}.zip`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        actions.showNotification('导出完成', `已导出 ${confirmedMaterials.length} 个文件`, 'success');
      }, 2000);
      
    } catch (error) {
      actions.showNotification('导出失败', error.message || '导出过程中出现错误', 'error');
    }
  };

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <div className="loading-spinner"></div>
        <p>加载中...</p>
      </div>
    );
  }

  if (!currentClient) {
    return (
      <div className={styles.loadingContainer}>
        <p>客户信息不存在</p>
        <button onClick={handleBackToDashboard}>返回主界面</button>
      </div>
    );
  }

  return (
    <div className={styles.translation}>
      <div className={styles.header}>
        <div className={styles.clientInfo}>
          <button 
            className={styles.backBtn}
            onClick={handleBackToDashboard}
          >
            ← 返回
          </button>
          <h2 className={styles.clientName}>{currentClient.name}</h2>
        </div>
        
        <div className={styles.actions}>
          <button 
            className={`${styles.actionBtn} ${styles.btnAdd}`}
            onClick={handleAddMaterial}
          >
            添加
          </button>
          <button 
            className={`${styles.actionBtn} ${styles.btnExport}`}
            onClick={handleExport}
          >
            导出
          </button>
        </div>
      </div>

      <div className={styles.content}>
        <MaterialsList />
        <PreviewSection />
      </div>

      <AddMaterialModal />
    </div>
  );
};

export default TranslationPage;





