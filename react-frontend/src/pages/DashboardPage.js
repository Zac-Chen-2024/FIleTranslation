import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { clientAPI, authAPI } from '../services/api';
import AddClientModal from '../components/modals/AddClientModal';
import styles from './DashboardPage.module.css';

const DashboardPage = () => {
  const navigate = useNavigate();
  const { state, actions } = useApp();
  const { user, clients } = state;
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadClients();
  }, []);

  const loadClients = async () => {
    try {
      setLoading(true);
      // 直接从API加载客户列表
      const clientsData = await clientAPI.getClients();
      actions.setClients(clientsData.clients || []);
    } catch (error) {
      actions.showNotification('加载失败', '无法加载客户列表', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleClientClick = (client) => {
    actions.setCurrentClient(client);
    navigate(`/client/${client.cid}`);
  };

  const handleAddClient = () => {
    actions.toggleModal('addClient', true);
  };

  const handleDeleteClient = async (client, e) => {
    e.stopPropagation(); // 防止触发点击客户卡片
    
    actions.openConfirmDialog({
      title: '删除客户',
      message: `确定要删除客户 "${client.name}" 吗？这将同时删除该客户的所有材料。`,
      type: 'danger',
      confirmText: '删除',
      cancelText: '取消',
      onConfirm: async () => {
        try {
          await clientAPI.deleteClient(client.cid);
          actions.showNotification('删除成功', `客户 ${client.name} 已删除`, 'success');
          
          // 重新加载客户列表
          loadClients();
        } catch (error) {
          actions.showNotification('删除失败', error.message || '删除客户时出现错误', 'error');
        }
      }
    });
  };

  const handleLogout = async () => {
    try {
      await authAPI.logout();
      actions.logout();
      navigate('/');
    } catch (error) {
      console.error('Logout error:', error);
      // 即使logout API失败，也要清除本地状态
      actions.logout();
      navigate('/');
    }
  };

  const handleUserProfile = () => {
    actions.showNotification('功能开发中', '个人设置功能正在开发中', 'warning');
  };

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <div className="loading-spinner"></div>
        <p>加载中...</p>
      </div>
    );
  }

  return (
    <div className={styles.dashboard}>
      <div className={styles.header}>
        <h1 className={styles.title}>智能文书翻译平台</h1>
        <div className={styles.userMenu}>
          <div className={styles.userInfo}>
            <span className={styles.userName}>{user?.name}</span>
          </div>
          <div 
            className={styles.userAvatar}
            onClick={handleUserProfile}
            title="个人设置"
          >
            {user?.name?.charAt(0) || 'U'}
          </div>
          <button 
            className={styles.logoutBtn}
            onClick={handleLogout}
            title="退出登录"
          >
            退出
          </button>
        </div>
      </div>

      <div className={styles.content}>
        <div className={styles.clientsSection}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>客户列表</h2>
            <button 
              className={styles.addClientBtn}
              onClick={handleAddClient}
            >
              添加客户
            </button>
          </div>

          {clients.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>👥</div>
              <h3 className={styles.emptyTitle}>暂无客户</h3>
              <p className={styles.emptyDescription}>开始添加您的第一个客户</p>
              <button 
                className={styles.addClientBtn}
                onClick={handleAddClient}
              >
                添加客户
              </button>
            </div>
          ) : (
            <div className={styles.clientsList}>
              {clients.map((client) => (
                <div
                  key={client.cid}
                  className={styles.clientCard}
                  onClick={() => handleClientClick(client)}
                >
                  <div className={styles.clientContent}>
                    <div className={styles.clientName}>{client.name}</div>
                    <div className={styles.clientMeta}>
                      <span>案件类型: {client.caseType || '未指定'}</span>
                      <span>创建日期: {client.caseDate}</span>
                    </div>
                  </div>
                  <button
                    className={styles.deleteBtn}
                    onClick={(e) => handleDeleteClient(client, e)}
                    title="删除客户"
                  >
                    🗑️
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AddClientModal />
    </div>
  );
};

export default DashboardPage;





