import React, { useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import './Auth.css';

const VerifyOtp = () => {
  const location = useLocation();
  const navigate = useNavigate();

  // If user came from Signup, email will be in route state
  const [email, setEmail] = useState(location.state?.email || '');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleVerify = async (e) => {
    e.preventDefault();
    setError('');

    if (!email || !otp) {
      setError('Please enter both email and OTP');
      return;
    }

    try {
      setLoading(true);
      const response = await fetch('http://localhost:5000/api/auth/verify-otp', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, otp }),
      });

      const data = await response.json();

      if (data.success) {
        // On successful verification, user is created and token returned
        localStorage.setItem('authToken', data.token);
        localStorage.setItem('user', JSON.stringify(data.user));
        navigate('/chat-rooms');
      } else {
        setError(data.message || 'OTP verification failed');
      }
    } catch (err) {
      console.error(err);
      setError('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <h1>Revenue Lens</h1>
        <h2>Verify OTP</h2>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleVerify} className="auth-form">
          <div className="form-group">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
            />
          </div>

          <div className="form-group">
            <label>OTP</label>
            <input
              type="text"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              placeholder="Enter the OTP sent to your email"
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-full"
            disabled={loading}
          >
            {loading ? 'Verifying...' : 'Verify OTP'}
          </button>
        </form>

        <p className="auth-footer">
          Already verified? <Link to="/login">Login here</Link>
        </p>
      </div>
    </div>
  );
};

export default VerifyOtp;