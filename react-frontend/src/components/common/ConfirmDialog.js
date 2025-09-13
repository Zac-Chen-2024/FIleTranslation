import React from 'react';
import { useApp } from '../../contexts/AppContext';
import styles from './ConfirmDialog.module.css';

const ConfirmDialog = () => {
  const { state, actions } = useApp();
  const { confirmDialog } = state;

  if (!confirmDialog.isOpen) return null;

  const handleConfirm = () => {
    if (confirmDialog.onConfirm) {
      confirmDialog.onConfirm();
    }
    actions.closeConfirmDialog();
  };

  const handleCancel = () => {
    if (confirmDialog.onCancel) {
      confirmDialog.onCancel();
    }
    actions.closeConfirmDialog();
  };

  return (
    <div className={styles.overlay}>
      <div className={styles.dialog}>
        <div className={styles.header}>
          <h3 className={styles.title}>
            {confirmDialog.type === 'warning' && '⚠️ '}
            {confirmDialog.type === 'danger' && '🗑️ '}
            {confirmDialog.type === 'info' && 'ℹ️ '}
            {confirmDialog.title || '确认操作'}
          </h3>
        </div>
        
        <div className={styles.body}>
          <p className={styles.message}>{confirmDialog.message}</p>
        </div>
        
        <div className={styles.footer}>
          <button 
            className={`${styles.btn} ${styles.btnCancel}`}
            onClick={handleCancel}
          >
            {confirmDialog.cancelText || '取消'}
          </button>
          <button 
            className={`${styles.btn} ${
              confirmDialog.type === 'danger' ? styles.btnDanger : styles.btnPrimary
            }`}
            onClick={handleConfirm}
          >
            {confirmDialog.confirmText || '确认'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;

