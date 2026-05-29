import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import './Auth.css';

const Signup = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState('user');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSignup = async (e) => {
    e.preventDefault();
    setError('');

    if (!name || !email || !password || !confirmPassword) {
      setError('Please fill in all fields');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch('http://localhost:5000/api/auth/signup', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // backend currently forces role = 'user', but we keep it in UI for future use
        body: JSON.stringify({ name, email, password })
      });

      const data = await response.json();

      if (data.success) {
        // After signup we only send OTP; user must verify it on the next screen
        navigate('/verify-otp', { state: { email } });
      } else {
        setError(data.message || 'Signup failed');
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
          <h1>Build modern analytics experiences</h1>
          <p>
            Set up collaborative workspaces, connect databases, and let AI generate
            the narratives, visualizations, and SQL you need.
          </p>
          <ul className="spotlight-list">
            <li>Guided onboarding & live schema explorer</li>
            <li>One-click PDF exports with branded visuals</li>
            <li>Enterprise-grade security & audit logs</li>
          </ul>
          <div className="spotlight-stats">
            <div className="stat-card">
              <span>120+</span>
              <p>Data teams onboarded</p>
            </div>
            <div className="stat-card">
              <span>4.9/5</span>
              <p>User satisfaction</p>
            </div>
          </div>
        </div>

        <div className="auth-card">
          <div className="auth-card-header">
            <h2>Create your account</h2>
            <p>Start with a free workspace—no credit card required</p>
          </div>

          {error && <div className="error-message">{error}</div>}

          <form onSubmit={handleSignup} className="auth-form">
            <div className="form-group">
              <label>Full Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your full name"
                required
              />
            </div>

            <div className="form-group">
              <label>Work Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                required
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 6 characters"
                  required
                />
              </div>
              <div className="form-group">
                <label>Confirm Password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label>Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled
              >
                <option value="user">User</option>
              </select>
              <small className="field-note">Additional roles can be added by admins in-app</small>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-full"
              disabled={loading}
            >
              {loading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>

          <p className="auth-footer">
            Already have an account? <Link to="/login">Login</Link>
          </p>
        </div>
      </div>
    </div>
  );
};

export default Signup;