import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Dashboard from './pages/Dashboard';
import ChatRooms from './pages/ChatRooms';
import Chat from './pages/Chat';
import ReportGeneration from './pages/report_generation'; // adjust path if needed
import VerifyOtp from './pages/VerifyOtp';
import AdminDashboard from './pages/AdminDashboard';
import PaymentPage from './pages/PaymentPage';
import TermsAndConditions from './pages/TermsAndConditions';
import UserHistory from './pages/UserHistory';
import ChatWidget from './components/ChatWidget/ChatWidget';
import './App.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  const checkAuth = () => {
    const token = localStorage.getItem('authToken');
    setIsAuthenticated(!!token);
    setLoading(false);
  };

  useEffect(() => {
    checkAuth();
  }, []);

  // Listen for storage changes (when login happens in another tab or same tab)
  useEffect(() => {
    const handleStorageChange = () => {
      checkAuth();
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  if (loading) {
    return <div className="app-loading">Loading...</div>;
  }

  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/login" element={!isAuthenticated ? <Login onLoginSuccess={checkAuth} /> : <Navigate to="/dashboard" />} />
          <Route path="/signup" element={!isAuthenticated ? <Signup /> : <Navigate to="/dashboard" />} />
          <Route 
            path="/dashboard" 
            element={isAuthenticated ? <Dashboard onLogout={checkAuth} /> : <Navigate to="/login" />} 
          />
          <Route 
            path="/payment" 
            element={isAuthenticated ? <PaymentPage /> : <Navigate to="/login" />} 
          />
          <Route 
            path="/chat-rooms" 
            element={isAuthenticated ? <ChatRooms /> : <Navigate to="/login" />} 
          />
          <Route 
            path="/chat/:roomId" 
            element={isAuthenticated ? <Chat /> : <Navigate to="/login" />} 
          />

         <Route 
           path="/report_generation" 
           element={isAuthenticated ? <ReportGeneration /> : <Navigate to="/login" />} 
          />

          <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} />} />

          <Route
            path="/verify-otp"
            element={!isAuthenticated ? <VerifyOtp /> : <Navigate to="/dashboard" />}
          />

          <Route
            path="/admin"
            element={isAuthenticated ? <AdminDashboard /> : <Navigate to="/login" />}
          />

        <Route
  path="/terms"
  element={isAuthenticated ? <TermsAndConditions /> : <Navigate to="/login" />}
/>

          <Route
            path="/history"
            element={isAuthenticated ? <UserHistory /> : <Navigate to="/login" />}
          />

         

        </Routes>
      </div>
    </Router>
  );
}

export default App;