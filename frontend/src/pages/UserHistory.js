import React, { useEffect, useState } from 'react';
import './UserHistory.css';

const UserHistory = () => {
  const [manualHistory, setManualHistory] = useState([]);
  const [autoHistory, setAutoHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reportHistory, setReportHistory] = useState([]);

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const token = localStorage.getItem('authToken');
        if (!token) {
          setError('Not authenticated');
          setLoading(false);
          return;
        }

        const headers = { Authorization: `Bearer ${token}` };

        const [resManual, resAuto, resReports] = await Promise.all([
          fetch('http://localhost:5000/api/manual-requests/my', { headers }),
          fetch('http://localhost:5000/api/auto-transforms/my', { headers }),
          fetch('http://localhost:5000/api/report-history/my', { headers }),
        ]);

        if (!resManual.ok || !resAuto.ok || !resReports.ok) {
          throw new Error('Failed to fetch history data');
        }

        const dataManual = await resManual.json();
        const dataAuto = await resAuto.json();
        const dataReports = await resReports.json();

        if (!dataManual.success) {
          throw new Error(dataManual.message || 'Failed to load manual history');
        }
        if (!dataAuto.success) {
          throw new Error(dataAuto.message || 'Failed to load automatic history');
        }
        if (!dataReports.success) {
          throw new Error(dataReports.message || 'Failed to load report history');
        }

        setManualHistory(dataManual.requests || []);
        setAutoHistory(dataAuto.items || []);
        setReportHistory(dataReports.items || []);
      } catch (e) {
        console.error('Error fetching history:', e);
        setError(e.message || 'Failed to load history');
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, []);

  const handleCancelManual = async (requestId) => {
    if (!window.confirm('Cancel this manual request?')) return;
    try {
      const token = localStorage.getItem('authToken');
      const res = await fetch(
        `http://localhost:5000/api/manual-requests/${requestId}/cancel`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      const data = await res.json();
      if (!data.success) {
        alert(data.message || 'Failed to cancel request');
        return;
      }
      setManualHistory((prev) =>
        prev.map((r) =>
          r._id === requestId
            ? { ...r, status: 'cancelled', paymentStatus: 'cancelled' }
            : r
        )
      );
    } catch (e) {
      console.error(e);
      alert(e.message || 'Failed to cancel request');
    }
  };

  const handleDownloadResult = async (requestId) => {
    try {
      const token = localStorage.getItem('authToken');
      const res = await fetch(
        `http://localhost:5000/api/manual-requests/${requestId}/download-result`,
        {
          method: 'GET',
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (!res.ok) {
        const data = await res.json();
        alert(data.message || 'Failed to download result');
        return;
      }

      // Get filename from Content-Disposition header or use default
      const contentDisposition = res.headers.get('Content-Disposition');
      let filename = 'transformed_result.zip';
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?(.+)"?/);
        if (match) filename = match[1];
      }

      // Download the file
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (e) {
      console.error('Download error:', e);
      alert(e.message || 'Failed to download result');
    }
  };

  if (loading) {
    return <div style={{ padding: '24px' }}>Loading history...</div>;
  }

  if (error) {
    return <div style={{ padding: '24px', color: 'red' }}>{error}</div>;
  }

  const formatDate = (value) => (value ? new Date(value).toLocaleString() : '');

  return (
    <div className="user-history-page">
      <div className="user-history-container">
        <header className="user-history-header">
          <h1 className="user-history-title">My History</h1>
          <span className="user-history-subtitle">
            Track your manual jobs, automatic transforms, and AI reports
          </span>
        </header>

        <div className="user-history-sections">
          {/* Manual */}
          <section className="user-history-card">
            <div className="user-history-card-header">
              <h2 className="user-history-card-title">Manual Transformations</h2>
              <span className="user-history-card-tag">MANUAL</span>
            </div>
            {manualHistory.length === 0 ? (
              <p className="user-history-empty">
                You have no manual transformation history.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="user-history-table">
                  <thead>
                    <tr>
                      <th>Created</th>
                      <th>Bid ($)</th>
                      <th>Status</th>
                      <th>Payment</th>
                      <th>Files</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {manualHistory.map((req) => {
                      const canCancel =
                        req.status === 'pending' &&
                        req.paymentStatus !== 'paid' &&
                        req.status !== 'cancelled';
                      const canDownload =
                        req.paymentStatus === 'paid' &&
                        req.resultFile &&
                        req.resultFile.storedPath;
                      
                      return (
                        <tr key={req._id}>
                          <td>{formatDate(req.createdAt)}</td>
                          <td>
                            {req.bidAmount?.toFixed
                              ? req.bidAmount.toFixed(2)
                              : req.bidAmount}
                          </td>
                          <td>
                            <span
                              className={`user-history-pill status-${req.status}`}
                            >
                              {req.status}
                            </span>
                          </td>
                          <td>
                            <span
                              className={`user-history-pill payment-${req.paymentStatus}`}
                            >
                              {req.paymentStatus}
                            </span>
                          </td>
                          <td>{Array.isArray(req.files) ? req.files.length : 0}</td>
                          <td className="user-history-actions">
                            {canCancel && (
                              <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={() => handleCancelManual(req._id)}
                              >
                                Cancel
                              </button>
                            )}
                            {canDownload && (
                              <button
                                type="button"
                                className="btn btn-primary"
                                onClick={() => handleDownloadResult(req._id)}
                                style={{ marginLeft: canCancel ? '8px' : '0' }}
                              >
                                Download
                              </button>
                            )}
                            {!canCancel && !canDownload && (
                              <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>
                                -
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Automatic */}
          <section className="user-history-card">
            <div className="user-history-card-header">
              <h2 className="user-history-card-title">Automatic Transformations</h2>
              <span className="user-history-card-tag">AUTOMATIC</span>
            </div>
            {autoHistory.length === 0 ? (
              <p className="user-history-empty">
                You have no automatic transformation history.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="user-history-table">
                  <thead>
                    <tr>
                      <th>Created</th>
                      <th>Size (MB)</th>
                      <th>Price ($)</th>
                      <th>Payment</th>
                    </tr>
                  </thead>
                  <tbody>
                    {autoHistory.map((t) => (
                      <tr key={t._id}>
                        <td>{formatDate(t.createdAt)}</td>
                        <td>
                          {t.sizeMb
                            ? t.sizeMb.toFixed(2)
                            : ((t.sizeBytes || 0) / (1024 * 1024)).toFixed(2)}
                        </td>
                        <td>
                          {t.price?.toFixed ? t.price.toFixed(2) : t.price}
                        </td>
                        <td>
                          <span
                            className={`user-history-pill payment-${t.paymentStatus}`}
                          >
                            {t.paymentStatus}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* AI Reports */}
          <section className="user-history-card">
            <div className="user-history-card-header">
              <h2 className="user-history-card-title">AI Report Generations</h2>
              <span className="user-history-card-tag">AI REPORTS</span>
            </div>
            {reportHistory.length === 0 ? (
              <p className="user-history-empty">
                You have not downloaded any AI reports yet.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="user-history-table">
                  <thead>
                    <tr>
                      <th>Generated At</th>
                      <th>Results Count</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reportHistory.map((r) => (
                      <tr key={r._id}>
                        <td>{formatDate(r.generatedAt)}</td>
                        <td>{r.resultsCount}</td>
                        <td>{r.sourceDatabase || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
};

export default UserHistory;