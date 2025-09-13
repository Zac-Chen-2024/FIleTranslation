import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './contexts/AppContext';

// 页面组件
import WelcomePage from './pages/WelcomePage';
import SignInPage from './pages/SignInPage';
import SignUpPage from './pages/SignUpPage';
import DashboardPage from './pages/DashboardPage';
import TranslationPage from './pages/TranslationPage';

// 通用组件
import Notification from './components/common/Notification';
import ProgressModal from './components/common/ProgressModal';
import GlobalUploadProgress from './components/common/GlobalUploadProgress';
import ConfirmDialog from './components/common/ConfirmDialog';
import ProtectedRoute from './components/common/ProtectedRoute';

function App() {
  return (
    <AppProvider>
      <Router>
        <div className="App">
          <Routes>
            {/* 公开路由 */}
            <Route path="/" element={<WelcomePage />} />
            <Route path="/signin" element={<SignInPage />} />
            <Route path="/signup" element={<SignUpPage />} />
            
            {/* 受保护的路由 */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/client/:clientId" 
              element={
                <ProtectedRoute>
                  <TranslationPage />
                </ProtectedRoute>
              } 
            />
            
            {/* 重定向 */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          
          {/* 全局组件 */}
          <Notification />
          <ProgressModal />
          <GlobalUploadProgress />
          <ConfirmDialog />
        </div>
      </Router>
    </AppProvider>
  );
}

export default App;



