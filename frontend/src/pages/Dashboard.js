import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ChatWidget from '../components/ChatWidget/ChatWidget'; // Default import
import './Dashboard.css';
const DEFAULT_ARCHITECTURE_URL = '/default_architecture.jpeg';

const Dashboard = ({ onLogout }) => {
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [reportData, setReportData] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [transformedFiles, setTransformedFiles] = useState([]);
  const [jobStatus, setJobStatus] = useState(null);
  const [transformMode, setTransformMode] = useState('manual');
  const [totalSizeBytes, setTotalSizeBytes] = useState(0);
  const [estimatedPrice, setEstimatedPrice] = useState(0);
  const [isAutoTransforming, setIsAutoTransforming] = useState(false);
  const [architectureFile, setArchitectureFile] = useState(null);
  const [architectureMode, setArchitectureMode] = useState('default');
  const [manualBid, setManualBid] = useState('');
  const [latestManualRequest, setLatestManualRequest] = useState(null);
  const [myManualRequests, setMyManualRequests] = useState([]);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showMyRequestsPanel, setShowMyRequestsPanel] = useState(false);
  const [myAutoTransforms, setMyAutoTransforms] = useState([]);
  const [showArchitecture, setShowArchitecture] = useState(false);
  const navigate = useNavigate();
  const storedUser = localStorage.getItem('user');
  const currentUser = storedUser ? JSON.parse(storedUser) : null;
  const isAdmin = currentUser?.role === 'admin';

  // Handle folder selection
  const handleFolderChange = (event) => {
    const files = Array.from(event.target.files);
    const excelFiles = files.filter((file) => /\.(xlsx|xls|csv)$/.test(file.name));
    setSelectedFiles(excelFiles);
    setSelectedFolder(event.target.files);

    const totalBytes = excelFiles.reduce((sum, file) => sum + (file.size || 0), 0);
    setTotalSizeBytes(totalBytes);

    const mb = totalBytes / (1024 * 1024);
    const stepSize = 0.01;
    const steps = mb > 0 ? Math.ceil(mb / stepSize) : 1;
    let price = steps * 10;
    if (price < 10) price = 10;

    setEstimatedPrice(parseFloat(price.toFixed(2)));
  };

  // Automatic Medallion transform
  const handleAutomaticTransform = async () => {
    if (selectedFiles.length === 0) {
      alert('Please select files to transform');
      return;
    }

    try {
      setIsAutoTransforming(true);
      const token = localStorage.getItem('authToken');

      const formData = new FormData();
      selectedFiles.forEach((file) => formData.append('files', file));

      const response = await fetch('http://localhost:5000/api/transform/automatic', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: formData,
      });

      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Automatic transform failed');
      }

      navigate(`/payment?autoId=${data.autoId}&type=auto&price=${data.price}`);
    } catch (e) {
      console.error(e);
      alert(e.message || 'Automatic transform failed');
    } finally {
      setIsAutoTransforming(false);
    }
  };

  // Create manual bid-based transform request
  const handleFolderUpload = async () => {
    if (selectedFiles.length === 0) {
      alert('Please select a folder with Excel files');
      return;
    }
    if (!manualBid) {
      alert('Please enter your bid amount');
      return;
    }
    if (architectureMode === 'custom' && !architectureFile) {
      alert('Please upload an architecture file or switch to default');
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();

      selectedFiles.forEach((file) => {
        formData.append('files', file);
      });
      formData.append('bidAmount', manualBid);
      formData.append('architectureMode', architectureMode);
      if (architectureMode === 'custom' && architectureFile) {
        formData.append('architectureFile', architectureFile);
      }

      const token = localStorage.getItem('authToken');

      const response = await fetch('http://localhost:5000/api/manual-requests', {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        body: formData,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || 'Failed to create manual request');
      }

      const data = await response.json();
      setUploadProgress(100);
      setLatestManualRequest({
        id: data.requestId,
        status: 'pending',
        bidAmount: parseFloat(manualBid),
        paymentStatus: 'unpaid',
      });
      alert('Manual request submitted successfully. An admin will review your bid.');
    } catch (error) {
      console.error('Error creating manual request:', error);
      alert(`Error: ${error.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const pollJobStatus = async (jobId, token) => {
    return new Promise((resolve, reject) => {
      const interval = setInterval(async () => {
        try {
          const response = await fetch(
            `http://localhost:5000/api/databricks/job-status/${jobId}`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            }
          );

          const data = await response.json();

          if (data.status === 'COMPLETED') {
            clearInterval(interval);
            setJobStatus({
              jobId: jobId,
              status: 'completed',
              outputPath: data.outputPath,
            });
            setIsUploading(false);

            fetchTransformedFiles(data.outputPath, token);
            resolve();
          } else if (data.status === 'FAILED') {
            clearInterval(interval);
            reject(new Error('Databricks job failed'));
          }
        } catch (error) {
          clearInterval(interval);
          reject(error);
        }
      }, 3000);
    });
  };

  const fetchTransformedFiles = async (folderPath, token) => {
    try {
      const response = await fetch('http://localhost:5000/api/azure/list-files', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ folderPath }),
      });

      const data = await response.json();
      setTransformedFiles(data.files || []);
    } catch (error) {
      console.error('Error fetching transformed files:', error);
    }
  };

  const handleDownloadFile = async (fileName) => {
    try {
      const token = localStorage.getItem('authToken');

      const response = await fetch('http://localhost:5000/api/azure/download-file', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ fileName }),
      });

      if (!response.ok) {
        throw new Error('Failed to download file');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading file:', error);
      alert('Error downloading file');
    }
  };

  const handleDownloadAll = async () => {
    try {
      const token = localStorage.getItem('authToken');

      const response = await fetch('http://localhost:5000/api/azure/download-folder', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          folderPath: jobStatus?.outputPath,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to download folder');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `transformed_files_${Date.now()}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading folder:', error);
      alert('Error downloading folder');
    }
  };

  const handleChatClick = () => {
    navigate('/chat-rooms');
  };

  const handleArchitectureFileChange = (event) => {
    const file =
      event.target.files && event.target.files[0] ? event.target.files[0] : null;
    setArchitectureFile(file);
    if (file) {
      setArchitectureMode('custom');
    }
  };

  const handleViewDefaultArchitecture = () => {
    window.open(DEFAULT_ARCHITECTURE_URL, '_blank');
  };

  const handleGoToPayment = () => {
    if (!latestManualRequest || !latestManualRequest.id) return;
    navigate(`/payment?requestId=${latestManualRequest.id}`);
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    if (onLogout) {
      onLogout();
    }
    navigate('/login');
  };

  useEffect(() => {
    const fetchMyData = async () => {
      try {
        const token = localStorage.getItem('authToken');
        if (!token) return;

        const resManual = await fetch('http://localhost:5000/api/manual-requests/my', {
          headers: { Authorization: `Bearer ${token}` },
        });
        const dataManual = await resManual.json();
        if (dataManual.success) {
          const all = dataManual.requests || [];
          const active = all.filter((r) => r.paymentStatus !== 'paid');
          setMyManualRequests(active);
          if (active.length > 0) {
            setLatestManualRequest(active[0]);
          } else {
            setLatestManualRequest(null);
          }
        }

        const resAuto = await fetch('http://localhost:5000/api/auto-transforms/my', {
          headers: { Authorization: `Bearer ${token}` },
        });
        const dataAuto = await resAuto.json();
        if (dataAuto.success) {
          setMyAutoTransforms(dataAuto.items || []);
        }
      } catch (e) {
        console.error(e);
      }
    };

    fetchMyData();
    const interval = setInterval(fetchMyData, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchMyRequests = async () => {
      try {
        const token = localStorage.getItem('authToken');
        if (!token) return;
        const res = await fetch('http://localhost:5000/api/manual-requests/my', {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });
        const data = await res.json();
        if (data.success) {
          const all = data.requests || [];
          const active = all.filter((r) => r.paymentStatus !== 'paid');
          setMyManualRequests(active);
          if (active.length > 0) {
            setLatestManualRequest(active[0]);
          } else {
            setLatestManualRequest(null);
          }
        }
      } catch (e) {
        console.error('Failed to fetch manual requests', e);
      }
    };

    fetchMyRequests();
    const interval = setInterval(fetchMyRequests, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard">
      <header
        className="dashboard-header"
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
      >
        <h1>Revenue Lens Dashboard</h1>
        <div
          style={{ display: 'flex', alignItems: 'center', gap: '12px', position: 'relative' }}
        >
          {/* Notifications */}
          <div style={{ position: 'relative' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowNotifications((prev) => !prev)}
              style={{ padding: '6px 10px' }}
            >
              🔔
              {myManualRequests.length > 0 && (
                <span
                  style={{
                    marginLeft: '4px',
                    backgroundColor: '#ef4444',
                    color: 'white',
                    borderRadius: '999px',
                    padding: '2px 6px',
                    fontSize: '0.75rem',
                  }}
                >
                  {myManualRequests.length}
                </span>
              )}
            </button>
            {showNotifications && (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  marginTop: '8px',
                  width: '280px',
                  maxHeight: '320px',
                  overflowY: 'auto',
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  boxShadow: '0 8px 20px rgba(0, 0, 0, 0.1)',
                  zIndex: 20,
                }}
              >
                <div
                  style={{
                    padding: '8px 12px',
                    borderBottom: '1px solid #e5e7eb',
                    fontWeight: 600,
                  }}
                >
                  Notifications
                </div>
                {myManualRequests.length === 0 ? (
                  <div style={{ padding: '10px 12px', fontSize: '0.9rem' }}>
                    No manual requests yet.
                  </div>
                ) : (
                  myManualRequests.map((req) => {
                    const createdLabel = req.createdAt
                      ? new Date(req.createdAt).toLocaleString()
                      : '';
                    let statusLabel = '';
                    if (req.status === 'pending')
                      statusLabel = 'Request submitted. Waiting for admin.';
                    else if (req.status === 'accepted')
                      statusLabel = 'Admin accepted your request.';
                    else if (req.status === 'rejected')
                      statusLabel = 'Admin rejected your request.';
                    else if (req.status === 'ready_for_payment')
                      statusLabel = 'Result ready. Please complete payment.';
                    else statusLabel = `Status: ${req.status}`;

                    const isClickable = req.status === 'ready_for_payment';

                    return (
                      <div
                        key={req._id}
                        style={{
                          padding: '8px 12px',
                          borderBottom: '1px solid #f3f4f6',
                          cursor: isClickable ? 'pointer' : 'default',
                          backgroundColor: isClickable ? '#f9fafb' : 'transparent',
                        }}
                        onClick={() => {
                          if (isClickable) {
                            navigate(`/payment?requestId=${req._id}`);
                            setShowNotifications(false);
                          }
                        }}
                      >
                        <div style={{ fontSize: '0.9rem', fontWeight: 500 }}>
                          Manual request - $
                          {req.bidAmount?.toFixed
                            ? req.bidAmount.toFixed(2)
                            : req.bidAmount}
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#4b5563' }}>
                          {statusLabel}
                        </div>
                        <div
                          style={{
                            fontSize: '0.75rem',
                            color: '#9ca3af',
                            marginTop: '2px',
                          }}
                        >
                          {createdLabel}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>

          {/* Admin shortcut */}
          {isAdmin && (
            <button className="btn btn-secondary" onClick={() => navigate('/admin')}>
              Admin
            </button>
          )}

          {/* Profile menu */}
          <div style={{ position: 'relative' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowProfileMenu((prev) => !prev)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 10px' }}
            >
              <span
                style={{
                  width: '28px',
                  height: '28px',
                  borderRadius: '999px',
                  backgroundColor: '#1f2937',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.9rem',
                  fontWeight: 600,
                }}
              >
                {currentUser?.name ? currentUser.name.charAt(0).toUpperCase() : 'U'}
              </span>
              <span style={{ fontSize: '0.9rem' }}>{currentUser?.name || 'Profile'}</span>
            </button>
            {showProfileMenu && (
              <div
                style={{
                  position: 'absolute',
                  right: 0,
                  marginTop: '8px',
                  width: '220px',
                  backgroundColor: 'white',
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  boxShadow: '0 8px 20px rgba(0, 0, 0, 0.1)',
                  zIndex: 20,
                }}
              >
                <div
                  style={{ padding: '10px 12px', borderBottom: '1px solid #e5e7eb' }}
                >
                  <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                    {currentUser?.name || 'User'}
                  </div>
                  <div style={{ fontSize: '0.8rem', color: '#6b7280' }}>
                    {currentUser?.email}
                  </div>
                </div>
                {/* <button
                  type="button"
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '8px 12px',
                    border: 'none',
                    background: 'transparent',
                    fontSize: '0.9rem',
                    cursor: 'pointer',
                  }}
                  onClick={() => {
                    setShowProfileMenu(false);
                    setShowMyRequestsPanel(true);
                  }}
                >
                  My Manual Requests
                </button> */}

                <button
                  type="button"
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '8px 12px',
                    border: 'none',
                    background: 'transparent',
                    fontSize: '0.9rem',
                    cursor: 'pointer',
                  }}
                  onClick={() => {
                    setShowProfileMenu(false);
                    navigate('/history');
                  }}
                >
                  History
                </button>

                <button
                  type="button"
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '8px 12px',
                    border: 'none',
                    background: 'transparent',
                    fontSize: '0.9rem',
                    cursor: 'pointer',
                  }}
                  onClick={() => {
                    setShowProfileMenu(false);
                    navigate('/terms');
                  }}
                >
                  Terms &amp; Conditions
                </button>
                <button
                  type="button"
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '8px 12px',
                    border: 'none',
                    background: 'transparent',
                    fontSize: '0.9rem',
                    cursor: 'pointer',
                  }}
                  onClick={() => {
                    setShowProfileMenu(false);
                    handleLogout();
                  }}
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* My Manual Requests panel */}
      {showMyRequestsPanel && (
        <section className="dashboard-section" style={{ marginBottom: '16px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '8px',
            }}
          >
            <h2 style={{ margin: 0 }}>My Manual Requests</h2>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => setShowMyRequestsPanel(false)}
            >
              Close
            </button>
          </div>

          {myManualRequests.length === 0 ? (
            <p style={{ fontSize: '0.9rem', color: '#4b5563' }}>
              You have no active manual transformation requests.
            </p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table
                style={{
                  width: '100%',
                  borderCollapse: 'collapse',
                  fontSize: '0.9rem',
                }}
              >
                <thead>
                  <tr>
                    <th
                      style={{
                        textAlign: 'left',
                        padding: '6px',
                        borderBottom: '1px solid #e5e7eb',
                      }}
                    >
                      Created
                    </th>
                    <th
                      style={{
                        textAlign: 'left',
                        padding: '6px',
                        borderBottom: '1px solid #e5e7eb',
                      }}
                    >
                      Bid ($)
                    </th>
                    <th
                      style={{
                        textAlign: 'left',
                        padding: '6px',
                        borderBottom: '1px solid #e5e7eb',
                      }}
                    >
                      Architecture
                    </th>
                    <th
                      style={{
                        textAlign: 'left',
                        padding: '6px',
                        borderBottom: '1px solid #e5e7eb',
                      }}
                    >
                      Files
                    </th>
                    <th
                      style={{
                        textAlign: 'left',
                        padding: '6px',
                        borderBottom: '1px solid #e5e7eb',
                      }}
                    >
                      Status
                    </th>
                    <th
                      style={{
                        textAlign: 'left',
                        padding: '6px',
                        borderBottom: '1px solid #e5e7eb',
                      }}
                    >
                      Payment
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {myManualRequests.map((req) => (
                    <tr key={req._id}>
                      <td
                        style={{
                          padding: '6px',
                          borderBottom: '1px solid #f3f4f6',
                        }}
                      >
                        {req.createdAt
                          ? new Date(req.createdAt).toLocaleString()
                          : ''}
                      </td>
                      <td
                        style={{
                          padding: '6px',
                          borderBottom: '1px solid #f3f4f6',
                        }}
                      >
                        {req.bidAmount?.toFixed
                          ? req.bidAmount.toFixed(2)
                          : req.bidAmount}
                      </td>
                      <td
                        style={{
                          padding: '6px',
                          borderBottom: '1px solid #f3f4f6',
                        }}
                      >
                        {req.architecture?.mode || 'default'}
                        {req.architecture?.mode === 'custom' &&
                          req.architecture?.originalName && (
                            <div
                              style={{
                                fontSize: '0.8rem',
                                color: '#6b7280',
                              }}
                            >
                              File: {req.architecture.originalName}
                            </div>
                          )}
                      </td>
                      <td
                        style={{
                          padding: '6px',
                          borderBottom: '1px solid #f3f4f6',
                        }}
                      >
                        {Array.isArray(req.files) && req.files.length > 0 ? (
                          req.files.map((f, idx) => (
                            <div key={idx}>{f.originalName}</div>
                          ))
                        ) : (
                          <span style={{ color: '#9ca3af' }}>No files</span>
                        )}
                      </td>
                      <td
                        style={{
                          padding: '6px',
                          borderBottom: '1px solid #f3f4f6',
                        }}
                      >
                        {req.status}
                      </td>
                      <td
                        style={{
                          padding: '6px',
                          borderBottom: '1px solid #f3f4f6',
                        }}
                      >
                        {req.paymentStatus}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <h2 style={{ marginTop: '24px' }}>My Automatic Transformations</h2>
          {myAutoTransforms.length === 0 ? (
            <p style={{ fontSize: '0.9rem', color: '#4b5563' }}>
              You have no automatic transformations yet.
            </p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left', padding: '6px', borderBottom: '1px solid #e5e7eb' }}>
                      Created
                    </th>
                    <th style={{ textAlign: 'left', padding: '6px', borderBottom: '1px solid #e5e7eb' }}>
                      Size (MB)
                    </th>
                    <th style={{ textAlign: 'left', padding: '6px', borderBottom: '1px solid #e5e7eb' }}>
                      Price ($)
                    </th>
                    <th style={{ textAlign: 'left', padding: '6px', borderBottom: '1px solid #e5e7eb' }}>
                      Payment
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {myAutoTransforms.map((t) => (
                    <tr key={t._id}>
                      <td style={{ padding: '6px', borderBottom: '1px solid #f3f4f6' }}>
                        {t.createdAt ? new Date(t.createdAt).toLocaleString() : ''}
                      </td>
                      <td style={{ padding: '6px', borderBottom: '1px solid #f3f4f6' }}>
                        {t.sizeMb
                          ? t.sizeMb.toFixed(2)
                          : ((t.sizeBytes || 0) / (1024 * 1024)).toFixed(2)}
                      </td>
                      <td style={{ padding: '6px', borderBottom: '1px solid #f3f4f6' }}>
                        {t.price?.toFixed ? t.price.toFixed(2) : t.price}
                      </td>
                      <td style={{ padding: '6px', borderBottom: '1px solid #f3f4f6' }}>
                        {t.paymentStatus}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <div className="dashboard-content">
        {/* Folder Upload Section */}
        <section className="dashboard-section">
          <h2> Upload & Transform Data</h2>

          {/* Mode toggle */}
          <div style={{ marginBottom: '16px', display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="btn btn-primary"
              style={{ opacity: transformMode === 'automatic' ? 1 : 0.6 }}
              onClick={() => setTransformMode('automatic')}
            >
              Automatic Transform
            </button>
            <button
              type="button"
              className="btn btn-primary"
              style={{ opacity: transformMode === 'manual' ? 1 : 0.6 }}
              onClick={() => setTransformMode('manual')}
            >
              Manual (Azure + Databricks)
            </button>
          </div>

          <div className="file-upload-container">
            <input
              type="file"
              multiple
              webkitdirectory="true"
              mozdirectory="true"
              onChange={handleFolderChange}
              className="file-input"
              accept=".csv,.xlsx,.xls"
              disabled={isUploading}
            />

            {/* Selected Files Info */}
            {selectedFiles.length > 0 && (
              <div className="files-info">
                <p>
                  <strong> {selectedFiles.length} files selected</strong>
                </p>
                <ul className="files-list">
                  {selectedFiles.slice(0, 5).map((file, idx) => (
                    <li key={idx}> {file.name}</li>
                  ))}
                  {selectedFiles.length > 5 && (
                    <li>... and {selectedFiles.length - 5} more files</li>
                  )}
                </ul>
              </div>
            )}

            {transformMode === 'manual' && (
              <div style={{ marginTop: '12px', marginBottom: '12px' }}>
                <p>
                  
                </p>
              </div>
            )}

            {/* Automatic mode price + action */}
            {transformMode === 'automatic' && (
              <div style={{ marginTop: '16px' }}>
                <p>
                  <strong>Total size:</strong>{' '}
                  {(totalSizeBytes / (1024 * 1024)).toFixed(2)} MB
                </p>
                <p>
                  <strong>Estimated price:</strong> ${estimatedPrice.toFixed(2)}
                </p>
                <button
                  onClick={handleAutomaticTransform}
                  className="btn btn-primary"
                  disabled={selectedFiles.length === 0 || isAutoTransforming}
                >
                  {isAutoTransforming
                    ? '⏳ Running Automatic Transform...'
                    : '⚙️ Run Automatic Transform'}
                </button>
              </div>
            )}

            {/* Manual mode */}
            {transformMode === 'manual' && (
              <div style={{ marginTop: '8px' }}>
                <div style={{ marginBottom: '12px' }}>
                  <label>
                    <span style={{ display: 'block', marginBottom: '4px' }}>
                      Your bid amount ($)
                    </span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={manualBid}
                      onChange={(e) => setManualBid(e.target.value)}
                      style={{ padding: '6px 8px', width: '200px' }}
                    />
                  </label>
                </div>

                <button
                  onClick={handleFolderUpload}
                  className="btn btn-primary"
                  disabled={selectedFiles.length === 0 || isUploading}
                >
                  {isUploading ? '⏳ Submitting request...' : '🚀 Submit Manual Request'}
                </button>

                <div
                  style={{
                    marginTop: '16px',
                    padding: '12px',
                    border: '1px solid #ccc',
                    borderRadius: '4px',
                  }}
                >
                  <h3 style={{ marginTop: 0, marginBottom: '8px' }}>
                    Manual Transformation Architecture
                  </h3>
                  <p style={{ marginBottom: '8px' }}>
                    View the default architecture for the manual Azure + Databricks
                    pipeline or upload your own architecture file (PDF/image) to
                    describe your transformation design.
                  </p>
                  <div
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: '8px',
                      alignItems: 'center',
                    }}
                  >
                    <button
                      type="button" 
                      className="btn btn-primary"
                      onClick={() => setShowArchitecture((prev) => !prev)}
                    >
                      View Default Architecture
                    </button>

                    {showArchitecture && (
                      <div
                        style={{
                          position: 'fixed',
                          inset: 0,
                          background: 'rgba(15,23,42,0.7)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          zIndex: 9999,
                        }}
                        onClick={() => setShowArchitecture(false)}
                      >
                        <img
                          src="/default_architecture.jpeg"
                          alt="Manual transformation default architecture"
                          style={{ maxWidth: '90%', maxHeight: '90%', borderRadius: '12px' }}
                        />
                      </div>
                    )}
                    <label style={{ display: 'block', width: '100%'}}>
                      <span className="btn btn-secondary">Upload Architecture File</span>
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg,.svg"
                        style={{ display: 'none' }}
                        onChange={handleArchitectureFileChange}
                      />
                    </label>
                    {architectureFile && (
                      <span style={{ fontSize: '0.9rem' }}>
                        Selected: {architectureFile.name}
                      </span>
                    )}
                  </div>
                </div>

                {latestManualRequest && (
                  <div
                    style={{
                      marginTop: '16px',
                      padding: '12px',
                      border: '1px solid #e5e7eb',
                      borderRadius: '4px',
                    }}
                  >
                    <h3 style={{ marginTop: 0, marginBottom: '4px' }}>
                      Manual Request Status
                    </h3>
                    <p style={{ margin: 0 }}>
                      Bid: $
                      {latestManualRequest.bidAmount?.toFixed
                        ? latestManualRequest.bidAmount.toFixed(2)
                        : latestManualRequest.bidAmount}
                    </p>
                    <p style={{ margin: 0 }}>Status: {latestManualRequest.status}</p>
                    <p style={{ margin: 0 }}>
                      Payment: {latestManualRequest.paymentStatus}
                    </p>
                    {latestManualRequest.status === 'ready_for_payment' &&
                      latestManualRequest.paymentStatus === 'unpaid' && (
                        <button
                          type="button"
                          className="btn btn-primary"
                          style={{ marginTop: '8px' }}
                          onClick={handleGoToPayment}
                        >
                          Go to Payment
                        </button>
                      )}
                  </div>
                )}
              </div>
            )}

            {/* Upload Progress */}
            {transformMode === 'manual' && isUploading && (
              <div className="progress-container">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
                <p className="progress-text">{uploadProgress}% Complete</p>
              </div>
            )}

            {/* Job Status (legacy) */}
            {jobStatus && (
              <div className={`job-status ${jobStatus.status}`}>
                <p>
                  <strong>Job ID:</strong> {jobStatus.jobId}
                </p>
                <p>
                  <strong>Status:</strong> {jobStatus.status.toUpperCase()}
                </p>
                {jobStatus.status === 'running' && (
                  <p className="status-running">
                    ⏳ Transformation in progress...
                  </p>
                )}
                {jobStatus.status === 'completed' && (
                  <p className="status-completed">
                    ✅ Transformation completed!
                  </p>
                )}
              </div>
            )}
          </div>
        </section>

        {/* Report Generation Section */}
        <section className="dashboard-section">
          <h2>📈 AI Report Generation</h2>

          <div className="report-container">
            <div className="status-description">
              Generate comprehensive AI-powered reports from your transformed data
              using advanced LLM technology.
            </div>
            <button onClick={() => navigate('/report_generation')}>
              ✨ Generate Report
            </button>
          </div>
        </section>

        {/* Transformed Files Download Section (legacy Azure) */}
        {transformedFiles.length > 0 && (
          <section
            className="dashboard-section"
            style={{ gridColumn: '1 / -1' }}
          >
            <h2>📥 Download Transformed Files</h2>
            <div className="transformed-files-container">
              <div className="files-grid">
                {transformedFiles.map((file, idx) => (
                  <div key={idx} className="file-card">
                    <div className="file-icon">📊</div>
                    <div className="file-details">
                      <p className="file-name">{file.name}</p>
                      <p className="file-size">
                        {(file.size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                    <button
                      onClick={() => handleDownloadFile(file.name)}
                      className="btn-download-small"
                    >
                      ⬇️ Download
                    </button>
                  </div>
                ))}
              </div>
              <button
                onClick={handleDownloadAll}
                className="btn-download-all"
              >
                📦 Download All as ZIP
              </button>
            </div>
          </section>
        )}
      </div>

      {/* ChatWidget Component */}
      <ChatWidget />

      {/* Chat Rooms Icon Button */}
      <button
        className="chat-icon-btn"
        onClick={handleChatClick}
        title="Open Chat Rooms"
      >
        💬
      </button>
    </div>
  );
};

export default Dashboard;