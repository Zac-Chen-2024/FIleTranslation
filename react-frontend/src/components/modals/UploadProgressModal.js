import React from 'react';
import styles from './Modal.module.css';

const UploadProgressModal = ({ isOpen, progress, onClose }) => {
  if (!isOpen) return null;

  const { current, total, message } = progress;
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;

  return (
    <div className={styles.overlay}>
      <div className={`${styles.modal} ${styles.progressModal}`}>
        <div className={styles.header}>
          <h3 className={styles.title}>文件上传中</h3>
        </div>
        
        <div className={styles.body}>
          <div className={styles.uploadProgressContainer}>
            <div className={styles.progressIcon}>
              <div className={styles.spinner}></div>
            </div>
            
            <div className={styles.progressInfo}>
              <p className={styles.progressMessage}>
                {message || '正在上传文件...'}
              </p>
              
              <div className={styles.progressBarContainer}>
                <div className={styles.progressBar}>
                  <div 
                    className={styles.progressFill}
                    style={{ width: `${percentage}%` }}
                  ></div>
                </div>
                <div className={styles.progressStats}>
                  <span className={styles.progressText}>
                    {current} / {total}
                  </span>
                  <span className={styles.progressPercent}>
                    {percentage}%
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          {percentage === 100 && (
            <div className={styles.completionMessage}>
              <span className={styles.successIcon}>✅</span>
              上传完成！正在处理...
            </div>
          )}
        </div>
        
        {percentage === 100 && (
          <div className={styles.footer}>
            <button 
              className={`${styles.btn} ${styles.btnPrimary}`}
              onClick={onClose}
            >
              完成
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UploadProgressModal;

