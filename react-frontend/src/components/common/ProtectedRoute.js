import React, { useEffect } from 'react';
import { Navigate } from 'react-router-dom';
import { useApp } from '../../contexts/AppContext';
import { authAPI } from '../../services/api';

const ProtectedRoute = ({ children }) => {
  const { state, actions } = useApp();
  const { isAuthenticated, user } = state;

  useEffect(() => {
    // 检查本地存储中的用户信息
    if (!user) {
      const storedUser = authAPI.getCurrentUser();
      if (storedUser) {
        actions.setUser(storedUser);
      }
    }
  }, [user, actions]);

  if (!isAuthenticated && !authAPI.getCurrentUser()) {
    return <Navigate to="/signin" replace />;
  }

  return children;
};

export default ProtectedRoute;



