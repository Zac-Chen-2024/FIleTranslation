import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useApp } from '../contexts/AppContext';
import { authAPI } from '../services/api';
import styles from './AuthPage.module.css';

const SignInPage = () => {
  const navigate = useNavigate();
  const { actions } = useApp();
  const [formData, setFormData] = useState({
    email: '',
    password: ''
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
    setLoading(true);

    try {
      // 直接使用真实API登录
      const response = await authAPI.signin(formData.email, formData.password);
      
      actions.setUser(response.user);
      actions.showNotification('登录成功', '欢迎回来！', 'success');
      navigate('/dashboard');
      
    } catch (error) {
      actions.showNotification('登录失败', error.message || '请检查邮箱和密码', 'error');
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
          <h2 className={styles.authTitle}>登录</h2>
          <p className={styles.authSubtitle}>欢迎回来，请登录您的账户</p>
        </div>
        
        <form onSubmit={handleSubmit}>
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
              placeholder="请输入您的密码"
              value={formData.password}
              onChange={handleChange}
              required
            />
          </div>
          
          <button 
            type="submit" 
            className={styles.submitBtn}
            disabled={loading}
          >
            {loading ? '登录中...' : '登录'}
          </button>
        </form>
        
        <div className={styles.authSwitch}>
          还没有账户？<Link to="/signup">立即注册</Link>
        </div>
      </div>
    </div>
  );
};

export default SignInPage;





