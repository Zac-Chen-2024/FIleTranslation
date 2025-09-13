import React from 'react';
import { useApp } from '../../contexts/AppContext';
import styles from './ProgressModal.module.css';

const ProgressModal = () => {
  const { state } = useApp();
  const { modals, progress } = state;

  if (!modals.progress) return null;

  return (
    <div className={styles.overlay}>
      <div className={styles.modal}>
        <h3 className={styles.title}>正在处理翻译...</h3>
        <div className={styles.progressContainer}>
          <div 
            className={styles.progressBar} 
            style={{ width: `${progress.percentage}%` }}
          />
        </div>
        <p className={styles.progressText}>
          {progress.text} ({Math.round(progress.percentage)}%)
        </p>
      </div>
    </div>
  );
};

export default ProgressModal;



