import React from 'react';
import { useNavigate } from 'react-router-dom';
import styles from './WelcomePage.module.css';

const WelcomePage = () => {
  const navigate = useNavigate();

  const features = [
    {
      icon: '📄',
      title: 'PDF精准翻译',
      description: '先进的OCR技术结合AI翻译，保持原文档格式和排版'
    },
    {
      icon: '🖼️',
      title: '图片智能识别',
      description: '支持扫描件、截图等图片格式，智能识别并翻译文本内容'
    },
    {
      icon: '🤖',
      title: 'AI辅助校对',
      description: '专业的法律词汇库和AI校对，确保翻译准确性和专业性'
    },
    {
      icon: '📦',
      title: '一键打包导出',
      description: '批量处理完成后，一键导出所有翻译文档，提高工作效率'
    }
  ];

  return (
    <div className={styles.welcome}>
      <div className={styles.container}>
        <div className={`${styles.logo} animate-float`}>⚖️</div>
        <h1 className={styles.title}>智能文书翻译平台</h1>
        <p className={styles.subtitle}>
          专为律师设计的智能翻译解决方案，提供精准、专业的法律文档翻译服务
        </p>
        
        <div className={styles.featuresGrid}>
          {features.map((feature, index) => (
            <div key={index} className={`${styles.featureCard} animate-fade-in`}>
              <div className={styles.featureIcon}>{feature.icon}</div>
              <h3 className={styles.featureTitle}>{feature.title}</h3>
              <p className={styles.featureDescription}>{feature.description}</p>
            </div>
          ))}
        </div>
        
        <div className={styles.authButtons}>
          <button 
            className={`${styles.authBtn} ${styles.btnSignin}`}
            onClick={() => navigate('/signin')}
          >
            登录
          </button>
          <button 
            className={`${styles.authBtn} ${styles.btnSignup}`}
            onClick={() => navigate('/signup')}
          >
            注册
          </button>
        </div>
      </div>
    </div>
  );
};

export default WelcomePage;



