import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import './Auth.css';

const Login = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    
    if (!email || !password) {
      setError('Please fill in all fields');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch('http://localhost:5000/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();

      if (data.success) {
  // Save token and user data to localStorage
  localStorage.setItem('authToken', data.token);
  localStorage.setItem('user', JSON.stringify(data.user));

  const isAdmin = data.user && data.user.role === 'admin';

  if (onLoginSuccess) {
    onLoginSuccess();
  }

  navigate(isAdmin ? '/admin' : '/dashboard');
} else {
        setError(data.message || 'Login failed');
      }
    } catch (err) {
      setError('Failed to connect to server');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-layout">
        <div className="auth-spotlight">
          <div className="brand-chip">Revenue Lens</div>
          <h1>Turn raw data into revenue playbooks</h1>
          <p>
            AI copilots craft SQL, explain results, and visualize trends so your team can
            act on insights in minutes—not days.
          </p>
          <ul className="spotlight-list">
            <li>Agentic SQL generation with guardrails</li>
            <li>Beautiful reports with charts & strategy</li>
            <li>Secure role-based collaboration</li>
          </ul>
          <div className="spotlight-stats">
            <div className="stat-card">
              <span>500+</span>
              <p>Dashboards automated</p>
            </div>
            <div className="stat-card">
              <span>92%</span>
              <p>Faster decision cycles</p>
            </div>
          </div>
        </div>

        <div className="auth-card">
          <div className="auth-card-header">
            <h2>Welcome back</h2>
            <p>Sign in to access your workspaces</p>
          </div>

          {error && <div className="error-message">{error}</div>}

          <form onSubmit={handleLogin} className="auth-form">
            <div className="form-group">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
              />
            </div>

            <div className="form-group">
              <label>Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                required
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={loading}
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>

          <p className="auth-footer">
            Don't have an account? <Link to="/signup">Create one</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
