import React from 'react';
import { useApp } from '../../contexts/AppContext';
import styles from './Notification.module.css';

const Notification = () => {
  const { state } = useApp();
  const { notification } = state;

  if (!notification) return null;

  const { title, message, type = 'success' } = notification;

  return (
    <div className={`${styles.notification} ${styles[type]} ${styles.show}`}>
      <div className={styles.title}>{title}</div>
      <div className={styles.message}>{message}</div>
    </div>
  );
};

export default Notification;



