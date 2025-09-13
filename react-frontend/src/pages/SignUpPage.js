import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { authAPI } from '../services/api';
import styles from './AuthPage.module.css';

const SignUpPage = () => {
  const navigate = useNavigate();
  const { actions } = useApp();
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: ''
  });
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (formData.password !== formData.confirmPassword) {
      actions.showNotification('注册失败', '两次输入的密码不一致', 'error');
      return;
    }

    setLoading(true);

    try {
      // 直接使用真实API注册
      const response = await authAPI.signup(formData.name, formData.email, formData.password);

      actions.setUser(response.user);
      actions.showNotification('注册成功', '欢迎使用智能文书翻译平台！', 'success');
      navigate('/dashboard');
      
    } catch (error) {
      actions.showNotification('注册失败', error.message || '注册过程中出现错误', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.authPage}>
      <button className={styles.backBtn} onClick={() => navigate('/')}>
        ← 返回
      </button>
      
      <div className={styles.authContainer}>
        <div className={styles.authHeader}>
          <h2 className={styles.authTitle}>注册</h2>
          <p className={styles.authSubtitle}>创建您的账户，开始使用智能翻译服务</p>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div className={styles.formGroup}>
            <label className={styles.formLabel} htmlFor="name">姓名</label>
            <input
              type="text"
              id="name"
              name="name"
              className={styles.formInput}
              placeholder="请输入您的姓名"
              value={formData.name}
              onChange={handleChange}
              required
            />
          </div>
          
          <div className={styles.formGroup}>
            <label className={styles.formLabel} htmlFor="email">邮箱地址</label>
            <input
              type="email"
              id="email"
              name="email"
              className={styles.formInput}
              placeholder="请输入您的邮箱"
              value={formData.email}
              onChange={handleChange}
              required
            />
          </div>
          
          <div className={styles.formGroup}>
            <label className={styles.formLabel} htmlFor="password">密码</label>
            <input
              type="password"
              id="password"
              name="password"
              className={styles.formInput}
              placeholder="请输入密码"
              value={formData.password}
              onChange={handleChange}
              required
            />
          </div>
          
          <div className={styles.formGroup}>
            <label className={styles.formLabel} htmlFor="confirmPassword">确认密码</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              className={styles.formInput}
              placeholder="请再次输入密码"
              value={formData.confirmPassword}
              onChange={handleChange}
              required
            />
          </div>
          
          <button 
            type="submit" 
            className={styles.submitBtn}
            disabled={loading}
          >
            {loading ? '注册中...' : '注册'}
          </button>
        </form>
        
        <div className={styles.authSwitch}>
          已有账户？<Link to="/signin">立即登录</Link>
        </div>
      </div>
    </div>
  );
};

export default SignUpPage;





