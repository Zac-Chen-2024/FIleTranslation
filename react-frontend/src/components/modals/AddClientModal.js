import React, { useState } from 'react';
import { useApp } from '../../contexts/AppContext';
import { clientAPI } from '../../services/api';
import styles from './Modal.module.css';

const AddClientModal = () => {
  const { state, actions } = useApp();
  const { modals } = state;
  const [formData, setFormData] = useState({
    name: '',
    caseType: '',
    caseDate: new Date().toISOString().split('T')[0]
  });
  const [loading, setLoading] = useState(false);

  const handleClose = () => {
    actions.toggleModal('addClient', false);
    setFormData({
      name: '',
      caseType: '',
      caseDate: new Date().toISOString().split('T')[0]
    });
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.name.trim()) {
      actions.showNotification('添加失败', '请输入客户姓名', 'error');
      return;
    }

    setLoading(true);

    try {
      // 通过API添加客户
      const response = await clientAPI.addClient({
        name: formData.name.trim(),
        caseType: formData.caseType.trim(),
        caseDate: formData.caseDate
      });
      actions.addClient(response.client);

      actions.showNotification('添加成功', `客户 ${formData.name} 已成功添加`, 'success');
      handleClose();
      
    } catch (error) {
      actions.showNotification('添加失败', error.message || '添加客户时出现错误', 'error');
    } finally {
      setLoading(false);
    }
  };

  if (!modals.addClient) return null;

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>添加新客户</h3>
          <button className={styles.closeBtn} onClick={handleClose}>
            &times;
          </button>
        </div>
        
        <div className={styles.body}>
          <form onSubmit={handleSubmit}>
            <div className={styles.formGroup}>
              <label className={styles.label} htmlFor="name">
                客户姓名 *
              </label>
              <input
                type="text"
                id="name"
                name="name"
                className={styles.input}
                placeholder="请输入客户姓名"
                value={formData.name}
                onChange={handleChange}
                required
              />
            </div>
            
            <div className={styles.formGroup}>
              <label className={styles.label} htmlFor="caseType">
                案件类型
              </label>
              <input
                type="text"
                id="caseType"
                name="caseType"
                className={styles.input}
                placeholder="例如：移民、商务、合同等"
                value={formData.caseType}
                onChange={handleChange}
              />
            </div>
            
            <div className={styles.formGroup}>
              <label className={styles.label} htmlFor="caseDate">
                案件创建日期
              </label>
              <input
                type="date"
                id="caseDate"
                name="caseDate"
                className={styles.input}
                value={formData.caseDate}
                onChange={handleChange}
              />
            </div>
          </form>
        </div>
        
        <div className={styles.footer}>
          <button 
            className={`${styles.btn} ${styles.btnSecondary}`}
            onClick={handleClose}
            disabled={loading}
          >
            取消
          </button>
          <button 
            className={`${styles.btn} ${styles.btnPrimary}`}
            onClick={handleSubmit}
            disabled={loading}
          >
            {loading ? '添加中...' : '添加'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default AddClientModal;





