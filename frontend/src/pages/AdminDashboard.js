import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './AdminDashboard.css';
const AdminDashboard = () => {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState('');
  const [manualRequests, setManualRequests] = useState([]);
  const [loadingRequests, setLoadingRequests] = useState(false);
  const [autoTransforms, setAutoTransforms] = useState([]);
const [loadingAuto, setLoadingAuto] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
  const storedUser = localStorage.getItem('user');
  const parsed = storedUser ? JSON.parse(storedUser) : null;
  if (!parsed || parsed.role !== 'admin') {
    setError('You are not authorized to view this page.');
    return;
  }

  const token = localStorage.getItem('authToken');
  if (!token) {
    navigate('/login');
    return;
  }

  const fetchSummary = async () => {
    try {
      const res = await fetch('http://localhost:5000/api/admin/summary', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      const data = await res.json();
      if (data.success) {
        setUsers(data.users || []);
      } else {
        setError(data.message || 'Failed to load admin summary');
      }
    } catch (e) {
      console.error(e);
      setError('Failed to connect to server');
    }
  };

  const fetchManualRequests = async () => {
    try {
      setLoadingRequests(true);
      const res = await fetch('http://localhost:5000/api/admin/manual-requests', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      const data = await res.json();
      if (data.success) {
        setManualRequests(data.requests || []);
      } else {
        console.error(data.message || 'Failed to load manual requests');
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingRequests(false);
    }
  };

  const fetchAutoTransforms = async () => {
  try {
    setLoadingAuto(true);
    const res = await fetch('http://localhost:5000/api/admin/auto-transforms', {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    const data = await res.json();
    if (data.success) {
      setAutoTransforms(data.items || []);
    } else {
      console.error(data.message || 'Failed to load automatic transforms');
    }
  } catch (e) {
    console.error(e);
  } finally {
    setLoadingAuto(false);
  }
};

   fetchSummary();
  fetchManualRequests();
  fetchAutoTransforms();

  const intervalId = setInterval(() => {
    fetchManualRequests();
    fetchAutoTransforms();
  }, 30000);

  return () => clearInterval(intervalId);
}, [navigate]);

  if (error) {
    return (
      <div className="admin-dashboard">
        <h1>Admin Dashboard</h1>
        <p>{error}</p>
      </div>
    );
  }


    
  const handleUpdateStatus = async (id, status) => {
    const token = localStorage.getItem('authToken');
    try {
      const res = await fetch(`http://localhost:5000/api/admin/manual-requests/${id}/status`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status }),
      });
      const data = await res.json();
      if (!data.success) {
        alert(data.message || 'Failed to update status');
        return;
      }
      setManualRequests((prev) =>
        prev.map((r) => (r._id === id ? { ...r, status } : r))
      );
    } catch (e) {
      console.error(e);
      alert('Failed to update status');
    }
  };

  const handleUpdateBid = async (id, newBid) => {
    const token = localStorage.getItem('authToken');
    try {
      const res = await fetch(`http://localhost:5000/api/admin/manual-requests/${id}/bid`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ bidAmount: newBid }),
      });
      const data = await res.json();
      if (!data.success) {
        alert(data.message || 'Failed to update bid');
        return;
      }
      setManualRequests((prev) =>
        prev.map((r) => (r._id === id ? { ...r, bidAmount: parseFloat(newBid) } : r))
      );
    } catch (e) {
      console.error(e);
      alert('Failed to update bid');
    }
  };

  const handleUploadResult = async (id, file) => {
    if (!file) {
      alert('Please select a result file to upload');
      return;
    }
    const token = localStorage.getItem('authToken');
    const formData = new FormData();
    formData.append('resultFile', file);

    try {
      const res = await fetch(`http://localhost:5000/api/admin/manual-requests/${id}/upload-result`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });
      const data = await res.json();
      if (!data.success) {
        alert(data.message || 'Failed to upload result');
        return;
      }
      setManualRequests((prev) =>
        prev.map((r) =>
          r._id === id ? { ...r, status: 'ready_for_payment' } : r
        )
      );
    } catch (e) {
      console.error(e);
      alert('Failed to upload result');
    }
  };


const handleDownloadInput = async (id) => {
  const token = localStorage.getItem('authToken');
  try {
    const res = await fetch(
      `http://localhost:5000/api/admin/manual-requests/${id}/download-input`,
      {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!res.ok) {
      const text = await res.text();
      alert(text || 'Failed to download input files');
      return;
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `manual_request_${id}_input.zip`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (e) {
    console.error(e);
    alert('Failed to download input files');
  }
};


const handleViewArchitecture = async (id) => {
  const token = localStorage.getItem('authToken');
  try {
    const res = await fetch(
      `http://localhost:5000/api/admin/manual-requests/${id}/architecture`,
      {
        method: 'GET',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    if (!res.ok) {
      alert('Failed to open architecture file');
      return;
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, '_blank');
  } catch (e) {
    console.error(e);
    alert('Failed to open architecture file');
  }
};
  return (
    <div className="admin-dashboard">
      <h1>Admin Dashboard</h1>

      <h2>Users</h2>
<div className="admin-table-wrapper">
  <table className="admin-table">
    <thead>
      <tr>
        <th>Name</th>
        <th>Email</th>
        <th>Role</th>
        <th>Chatrooms</th>
        <th>Reports</th>
        <th>Revenue</th>
      </tr>
    </thead>
    <tbody>
      {users.map((u) => (
        <tr key={u.id}>
          <td>{u.name}</td>
          <td>{u.email}</td>
          <td>{u.role}</td>
          <td>{u.chatroomCount}</td>
          <td>{u.reportCount}</td>
          <td>${(u.revenue ?? 0).toFixed ? u.revenue.toFixed(2) : u.revenue}</td>
        </tr>
      ))}
    </tbody>
  </table>
</div>

      <h2 style={{ marginTop: '24px' }}>Manual Transformation Requests</h2>
      {loadingRequests ? (
        <p>Loading manual requests...</p>
      ) : manualRequests.length === 0 ? (
        <p>No manual requests yet.</p>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>User Email</th>
              <th>Bid ($)</th>
              <th>Payment</th>
              <th>Architecture</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {manualRequests.map((r) => (
              <tr key={r._id}>
                <td>{r.userEmail}</td>
                <td>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    defaultValue={r.bidAmount}
                    onBlur={(e) => {
                      const val = e.target.value;
                      if (val && parseFloat(val) !== r.bidAmount) {
                        handleUpdateBid(r._id, val);
                      }
                    }}
                    style={{ width: '90px' }}
                  />
                </td>
               
                <td>{r.paymentStatus}</td>
                <td>
  {r.architecture?.mode || 'default'}
  {r.architecture?.mode === 'custom' && r.architecture?.originalName && (
    <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>
      File:{' '}
      <button
        type="button"
        onClick={() => handleViewArchitecture(r._id)}
        style={{
          border: 'none',
          background: 'none',
          padding: 0,
          margin: 0,
          color: '#2563eb',
          cursor: 'pointer',
          textDecoration: 'underline',
          fontSize: '0.8rem',
        }}
      >
        {r.architecture.originalName}
      </button>
    </div>
  )}
</td>
                <td>{r.createdAt ? new Date(r.createdAt).toLocaleString() : ''}</td>
                <td>
  <button
    type="button"
    onClick={() => handleDownloadInput(r._id)}
    style={{ marginRight: '8px' }}
  >
    Download input files
  </button>

  {r.status === 'pending' && (
    <>
      <button
        onClick={() => handleUpdateStatus(r._id, 'accepted')}
        style={{ marginRight: '4px' }}
      >
        Accept
      </button>
      <button onClick={() => handleUpdateStatus(r._id, 'rejected')}>
        Reject
      </button>
    </>
  )}
  {r.status === 'accepted' && (
    <div>
      <input
        type="file"
        onChange={(e) => {
          const file = e.target.files && e.target.files[0];
          if (file) {
            handleUploadResult(r._id, file);
            e.target.value = '';
          }

          
        }}
      />
    </div>
  )}
  {r.status === 'ready_for_payment' && r.paymentStatus !== 'paid' && (
    <span>Waiting for user payment</span>
  )}
  {r.paymentStatus === 'paid' && <span>Payment completed</span>}
  {r.status === 'rejected' && <span>Rejected</span>}
</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}


      <h2 style={{ marginTop: '24px' }}>Automatic Transformations</h2>
{loadingAuto ? (
  <p>Loading automatic transformations...</p>
) : autoTransforms.length === 0 ? (
  <p>No automatic transformations yet.</p>
) : (
  <div className="admin-table-wrapper">
    <table className="admin-table">
      <thead>
        <tr>
          <th>User Email</th>
          <th>Size (MB)</th>
          <th>Price ($)</th>
          <th>Status</th>
          <th>Payment</th>
          <th>Created</th>
        </tr>
      </thead>
      <tbody>
        {autoTransforms.map((t) => (
          <tr key={t._id}>
            <td>{t.userEmail}</td>
            <td>
              {t.sizeMb
                ? t.sizeMb.toFixed(2)
                : ((t.sizeBytes || 0) / (1024 * 1024)).toFixed(2)}
            </td>
            <td>{t.price?.toFixed ? t.price.toFixed(2) : t.price}</td>
            <td>{t.status}</td>
            <td>{t.paymentStatus}</td>
            <td>{t.createdAt ? new Date(t.createdAt).toLocaleString() : ''}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
)}
    </div>
  );
};



export default AdminDashboard;