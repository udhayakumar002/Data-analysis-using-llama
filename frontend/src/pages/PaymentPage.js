import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const PaymentPage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [request, setRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [isPaying, setIsPaying] = useState(false);

  const params = new URLSearchParams(location.search);
  const priceParam = params.get('price');
  const requestId = params.get('requestId'); // manual
  const autoId = params.get('autoId');       // automatic
  const type = params.get('type') || 'manual';

  useEffect(() => {
    const fetchRequest = async () => {
      if (type === 'auto') {
        if (!autoId) {
          setError('Missing auto transform id');
          setLoading(false);
          return;
        }
        // Build a pseudo-request object from URL params
        const price = priceParam ? parseFloat(priceParam) : null;
        setRequest({
          bidAmount: price,
          status: 'completed',
          paymentStatus: 'unpaid',
        });
        setLoading(false);
        return;
      }

      // Manual flow (existing)
      if (!requestId) {
        setError('Missing request id');
        setLoading(false);
        return;
      }
      try {
        const token = localStorage.getItem('authToken');
        const res = await fetch(
          `http://localhost:5000/api/manual-requests/${requestId}`,
          {
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          }
        );
        const data = await res.json();
        if (!data.success) {
          setError(data.message || 'Failed to load request');
        } else {
          setRequest(data.request);
        }
      } catch (e) {
        console.error(e);
        setError('Failed to connect to server');
      } finally {
        setLoading(false);
      }
    };

    fetchRequest();
  }, [type, requestId, autoId, priceParam]);

  const handlePayAndDownload = async () => {
    setIsPaying(true);
    setError('');
    try {
      const token = localStorage.getItem('authToken');

      if (type === 'manual') {
        if (!requestId) {
          throw new Error('Missing request id');
        }

        // 1) Pay for manual request
        const payRes = await fetch(
          `http://localhost:5000/api/manual-requests/${requestId}/pay`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        const payData = await payRes.json();
        if (!payRes.ok || !payData.success) {
          throw new Error(payData.message || 'Payment failed');
        }

        // 2) Download manual result
        const dlRes = await fetch(
          `http://localhost:5000/api/manual-requests/${requestId}/download-result`,
          {
            method: 'GET',
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (!dlRes.ok) {
          const text = await dlRes.text();
          throw new Error(text || 'Failed to download result');
        }

        const blob = await dlRes.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `manual_result_${Date.now()}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        if (!autoId) {
          throw new Error('Missing auto transform id');
        }

        // 1) Pay for auto transform
        const payRes = await fetch(
          `http://localhost:5000/api/auto-transforms/${autoId}/pay`,
          {
            method: 'POST',
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        const payData = await payRes.json();
        if (!payRes.ok || !payData.success) {
          throw new Error(payData.message || 'Payment failed');
        }

        // 2) Download auto ZIP
        const dlRes = await fetch(
          `http://localhost:5000/api/auto-transforms/${autoId}/download-zip`,
          {
            method: 'GET',
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (!dlRes.ok) {
          const text = await dlRes.text();
          throw new Error(text || 'Failed to download result');
        }

        const blob = await dlRes.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `auto_transform_${Date.now()}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }

      navigate('/dashboard');
    } catch (e) {
      console.error(e);
      setError(e.message || 'Payment / download failed');
    } finally {
      setIsPaying(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '24px' }}>Loading...</div>;
  }

  if (error) {
    return (
      <div style={{ padding: '24px' }}>
        <h2>Payment</h2>
        <p style={{ color: 'red' }}>{error}</p>
        <button onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
      </div>
    );
  }

  if (!request) {
    return (
      <div style={{ padding: '24px' }}>
        <h2>Payment</h2>
        <p>Request not found.</p>
        <button onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
      </div>
    );
  }

  return (
    <div
      className="payment-page"
      style={{ padding: '24px', maxWidth: '600px', margin: '0 auto' }}
    >
      <h2>Complete Payment</h2>
      <div
        style={{
          marginTop: '16px',
          padding: '16px',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          backgroundColor: '#f9fafb',
        }}
      >
        <p>
          <strong>Bid amount:</strong>{' '}
          $
          {request.bidAmount?.toFixed
            ? request.bidAmount.toFixed(2)
            : request.bidAmount}
        </p>
        <p>
          <strong>Status:</strong> {request.status}
        </p>
        <p>
          <strong>Payment status:</strong> {request.paymentStatus}
        </p>
      </div>

      <p style={{ marginTop: '16px', fontSize: '0.9rem', color: '#4b5563' }}>
        Click “Pay now & download” to confirm payment for this{' '}
        {type === 'auto' ? 'automatic' : 'manual'} transformation request. Once
        payment is processed, your transformed file will be downloaded
        automatically.
      </p>

      <button
        type="button"
        onClick={handlePayAndDownload}
        disabled={isPaying}
        style={{
          marginTop: '16px',
          padding: '8px 16px',
          backgroundColor: '#2563eb',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: isPaying ? 'default' : 'pointer',
        }}
      >
        {isPaying ? 'Processing...' : 'Pay now & download'}
      </button>

      <button
        type="button"
        onClick={() => navigate('/dashboard')}
        style={{
          marginTop: '16px',
          marginLeft: '8px',
          padding: '8px 16px',
          backgroundColor: 'white',
          color: '#374151',
          border: '1px solid #d1d5db',
          borderRadius: '4px',
          cursor: 'pointer',
        }}
      >
        Cancel
      </button>
    </div>
  );
};

export default PaymentPage;