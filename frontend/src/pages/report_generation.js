import React, { useState, useEffect } from 'react';
import { Database, Upload, FolderOpen, Play, Download, Trash2, Plus, Check, X, Loader, BarChart3, FileText, Settings, AlertTriangle, Cloud, Zap, TrendingUp, CheckCircle } from 'lucide-react';
import './ReportGeneration.css'; 

const API_BASE = 'http://localhost:5000/api';

const ReportGeneration = () => {
    const [currentPage, setCurrentPage] = useState('connect');
    const [dbConfig, setDbConfig] = useState({
        host: 'localhost',
        user: 'root',
        password: '',
        database: '',
        port: '3306'
    });
    const [uploadedFiles, setUploadedFiles] = useState([]);
    const [isConnected, setIsConnected] = useState(false);
    const [schema, setSchema] = useState(null);
    const [predefinedQueries, setPredefinedQueries] = useState([]);
    const [customQueries, setCustomQueries] = useState([]);
    const [newQuery, setNewQuery] = useState('');
    const [selectedQueries, setSelectedQueries] = useState([]);
    const [results, setResults] = useState([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState('');
    const [activeTab, setActiveTab] = useState('predefined');
    const [dataSourceType, setDataSourceType] = useState(null); // 'user_db' or 'uploaded_files'
    const [databaseName, setDatabaseName] = useState(null);
    
    const renderConnectionStatus = () => {
        if (!connectionStatus) return null;

        const isError = connectionStatus.includes('Error') || connectionStatus.includes('failed');
        const isSuccess = connectionStatus.includes('Connected successfully') || connectionStatus.includes('Files uploaded');
        const isPending = !isError && !isSuccess;

        let icon = isError ? <X className="status-icon" /> : isSuccess ? <CheckCircle className="status-icon" /> : <Loader className="status-icon animate-spin" />;
        let classes = isError ? 'status-message error' : isSuccess ? 'status-message success' : 'status-message pending';

        return (
            <div className={classes}>
                {icon}
                <p>{connectionStatus}</p>
            </div>
        );
    };

    useEffect(() => {
        if (schema) {
            generatePredefinedQueries(schema);
        }
    }, [schema]);

    const generatePredefinedQueries = (schemaData) => {
        const queries = [
            { id: 1, text: "Show top 10 records by revenue", category: "Revenue Analysis", icon: "💰" },
            { id: 2, text: "Compare performance across all years", category: "Trend Analysis", icon: "📈" },
            { id: 3, text: "Customer purchase analysis", category: "Customer Insights", icon: "👥" },
            { id: 4, text: "Product category breakdown", category: "Product Analysis", icon: "📦" },
            { id: 5, text: "Monthly sales trends", category: "Trend Analysis", icon: "📊" },
            { id: 6, text: "Top performing products", category: "Product Analysis", icon: "🏆" },
            { id: 7, text: "Sales volume distribution", category: "Sales Analysis", icon: "📉" },
            { id: 8, text: "Customer segmentation by value", category: "Customer Insights", icon: "🎯" },
            { id: 9, text: "Seasonal patterns analysis", category: "Trend Analysis", icon: "🌤️" },
            { id: 10, text: "Cross-category performance", category: "Comparative Analysis", icon: "🔄" }
        ];
        setPredefinedQueries(queries);
    };

    const handleDbConnect = async () => {
        setConnectionStatus('Connecting to database...');
        try {
            const response = await fetch(`${API_BASE}/connect-db`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(dbConfig)
            });
            
            const data = await response.json();
            
            if (!response.ok) {
  setConnectionStatus(`Error: ${data.error}`);
  return;
}

setIsConnected(true);
setConnectionStatus('Connected. Fetching schema from database...');

// NEW
setDataSourceType('user_db');
setDatabaseName(dbConfig.database);

            try {
                const schemaResp = await fetch(`${API_BASE}/get-schema`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dbConfig })
                });
                const schemaData = await schemaResp.json();

                if (schemaResp.ok) {
                    setSchema(schemaData.schema);
                    setConnectionStatus('Connected successfully. Schema loaded!');
                } else {
                    setSchema(null);
                    setConnectionStatus(`Connected but schema fetch failed: ${schemaData.error}`);
                }
            } catch (err) {
                setSchema(null);
                setConnectionStatus(`Connected but schema fetch failed: ${err.message}`);
            }

            setTimeout(() => {
                setCurrentPage('analysis');
            }, 1500);
        } catch (error) {
            setConnectionStatus(`Connection failed: ${error.message}`);
        }
    };

   const handleFileUpload = async (event) => {
  const files = Array.from(event.target.files);
  setUploadedFiles(files);
  setConnectionStatus(`Processing ${files.length} file(s) and uploading...`);

  const formData = new FormData();
  files.forEach(file => formData.append('files', file));

  // Optional: if user filled DB creds and wants to use their own DB
  if (dbConfig.user && dbConfig.database) {
    formData.append('dbConfig', JSON.stringify(dbConfig));
  }

  const token = localStorage.getItem('authToken');
  if (!token) {
    setConnectionStatus('Upload failed: not authenticated. Please log in again.');
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/upload-files`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    const data = await response.json();

    if (response.ok && data.success) {
      setIsConnected(true);
      setDataSourceType('uploaded_files');
      setDatabaseName(data.databaseName || dbConfig.database || null);
      setSchema(data.schema);
      if (data.databaseName) {
        setDbConfig(prev => ({
          ...prev,
          host: prev.host || 'localhost',
          port: prev.port || '3306',
          user: prev.user || 'root',
          password: prev.password || '',
          database: data.databaseName,
        }));
      }
      setConnectionStatus('Files uploaded and processed! Redirecting...');
      setTimeout(() => {
        setCurrentPage('analysis');
      }, 1500);
    } else {
      setConnectionStatus(`Upload error: ${data.error || data.message}`);
    }
  } catch (error) {
    setConnectionStatus(`Upload failed: ${error.message}`);
  }
};

    const addCustomQuery = () => {
        if (newQuery.trim()) {
            const query = {
                id: Date.now(),
                text: newQuery,
                type: 'custom',
                timestamp: new Date().toISOString()
            };
            setCustomQueries([...customQueries, query]);
            setNewQuery('');
        }
    };

    const toggleQuerySelection = (queryId, type) => {
        const key = `${type}-${queryId}`;
        setSelectedQueries(prev => 
            prev.includes(key) 
                ? prev.filter(id => id !== key)
                : [...prev, key]
        );
    };

    const deleteCustomQuery = (queryId) => {
        setCustomQueries(prev => prev.filter(q => q.id !== queryId));
        setSelectedQueries(prev => prev.filter(id => id !== `custom-${queryId}`));
    };

    const processQueries = async () => {
        if (selectedQueries.length === 0) {
            alert('Please select at least one query');
            return;
        }

        setIsProcessing(true);
        setResults([]);

        const queriesToProcess = selectedQueries.map(key => {
            const [type, id] = key.split('-');
            if (type === 'predefined') {
                return predefinedQueries.find(q => q.id === parseInt(id, 10));
            } else {
                return customQueries.find(q => q.id === parseInt(id, 10));
            }
        });

        const newResults = [];

        for (const query of queriesToProcess) {
            if (!query) continue;

            try {
                const response = await fetch(`${API_BASE}/generate-insight`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
  query: query.text,
  dbConfig,
  source: dataSourceType,           // 'user_db' or 'uploaded_files'
  databaseName: databaseName || dbConfig.database,
}),
                });

                const insight = await response.json();

                if (response.ok) {
                    newResults.push({ query: query.text, insight });
                } else {
                    newResults.push({
                        query: query.text,
                        error: insight.error || 'Processing failed'
                    });
                }
            } catch (error) {
                newResults.push({
                    query: query.text,
                    error: error.message
                });
            }

            setResults([...newResults]);
        }

        setIsProcessing(false);
    };

    const downloadReport = async () => {
        if (results.length === 0) {
            alert('Run at least one query before downloading a report.');
            return;
        }

        const successfulInsights = results.filter(result => result.insight && !result.error);

        if (successfulInsights.length === 0) {
            alert('No successful insights available to include in the report.');
            return;
        }

        const payload = successfulInsights.map(result => ({
            query: result.query,
            insight: {
                ...result.insight,
                query: result.query
            }
        }));

        try {
            const response = await fetch(`${API_BASE}/download-full-report`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    results: payload,
    dataSourceType,
    databaseName: databaseName || dbConfig.database || null,
  }),
});

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                alert('Download failed: ' + (err.error || response.statusText));
                return;
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `AI_Insights_Report_${Date.now()}.pdf`;
            a.click();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            alert('Download failed: ' + error.message);
        }
    };

    // CONNECT PAGE
    if (currentPage === 'connect') {
        return (
            <div className="connect-page">
                <div className="connect-container">
                    <div className="connect-hero">
                        <div className="hero-badge">
                            <Zap className="hero-badge-icon" />
                            <span>AI-Powered Analytics</span>
                        </div>
                        <h1 className="hero-title">Connect Your Data Source</h1>
                        <p className="hero-subtitle">
                            Seamlessly integrate with your database or upload files to unlock powerful insights
                        </p>
                    </div>

                    <div className="connection-cards">
                        {/* Database Card */}
                        <div className="connection-card db-card">
                            <div className="card-header">
                                <div className="card-icon db-icon">
                                    <Database />
                                </div>
                                <div>
                                    <h2 className="card-title">Database Connection</h2>
                                    <p className="card-description">Connect directly to your MySQL database</p>
                                </div>
                            </div>

                            <div className="card-body">
                                <div className="form-group">
                                    <label className="form-label">Host Address</label>
                                    <input 
                                        type="text" 
                                        value={dbConfig.host} 
                                        onChange={(e) => setDbConfig({...dbConfig, host: e.target.value})} 
                                        className="form-input" 
                                        placeholder="localhost or IP address" 
                                    />
                                </div>

                                <div className="form-row">
                                    <div className="form-group">
                                        <label className="form-label">Port</label>
                                        <input 
                                            type="text" 
                                            value={dbConfig.port} 
                                            onChange={(e) => setDbConfig({...dbConfig, port: e.target.value})} 
                                            className="form-input" 
                                            placeholder="3306" 
                                        />
                                    </div>
                                    <div className="form-group">
                                        <label className="form-label">Username</label>
                                        <input 
                                            type="text" 
                                            value={dbConfig.user} 
                                            onChange={(e) => setDbConfig({...dbConfig, user: e.target.value})} 
                                            className="form-input" 
                                            placeholder="root" 
                                        />
                                    </div>
                                </div>

                                <div className="form-group">
                                    <label className="form-label">Password</label>
                                    <input 
                                        type="password" 
                                        value={dbConfig.password} 
                                        onChange={(e) => setDbConfig({...dbConfig, password: e.target.value})} 
                                        className="form-input" 
                                        placeholder="••••••••" 
                                    />
                                </div>

                                <div className="form-group">
                                    <label className="form-label">Database Name</label>
                                    <input 
                                        type="text" 
                                        value={dbConfig.database} 
                                        onChange={(e) => setDbConfig({...dbConfig, database: e.target.value})} 
                                        className="form-input" 
                                        placeholder="my_database" 
                                    />
                                </div>
                            </div>

                            <button onClick={handleDbConnect} className="btn btn-primary">
                                <Database className="btn-icon" />
                                Connect to Database
                            </button>
                        </div>

                        {/* File Upload Card */}
                        <div className="connection-card upload-card">
                            <div className="card-header">
                                <div className="card-icon upload-icon">
                                    <Cloud />
                                </div>
                                <div>
                                    <h2 className="card-title">Upload Files</h2>
                                    <p className="card-description">Import data from CSV or Excel files</p>
                                </div>
                            </div>

                            <div className="card-body">
                                <label className="upload-zone">
                                    <input
                                        type="file"
                                        multiple
                                        onChange={handleFileUpload}
                                        className="upload-input"
                                        accept=".csv,.xlsx,.xls"
                                    />
                                    <div className="upload-content">
                                        <FolderOpen className="upload-icon-large" />
                                        <p className="upload-text">Drag & drop files here</p>
                                        <p className="upload-subtext">or click to browse</p>
                                        <div className="upload-formats">
                                            <span className="format-badge">CSV</span>
                                            <span className="format-badge">XLSX</span>
                                            <span className="format-badge">XLS</span>
                                        </div>
                                    </div>
                                </label>

                                {uploadedFiles.length > 0 && (
                                    <div className="files-list">
                                        <p className="files-list-header">
                                            <CheckCircle className="files-icon" />
                                            {uploadedFiles.length} file{uploadedFiles.length > 1 ? 's' : ''} selected
                                        </p>
                                        <div className="files-items">
                                            {uploadedFiles.map((file, idx) => (
                                                <div key={idx} className="file-item">
                                                    <FileText className="file-icon" />
                                                    <span className="file-name">{file.name}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* <div className="upload-notice">
                                <AlertTriangle className="notice-icon" />
                                <p className="notice-text">Database credentials required for file import</p>
                            </div> */}

                            <div className="upload-notice">
  <AlertTriangle className="notice-icon" />
  <p className="notice-text">
    You can upload files directly (we will create a local test database),
    or provide database credentials above to import into your own database.
  </p>
</div>
                        </div>
                    </div>

                    {renderConnectionStatus()}
                </div>
            </div>
        );
    }

    // ANALYSIS PAGE
    return (
        <div className="analysis-page">
            <header className="analysis-header">
                <div className="header-content">
                    <div className="header-left">
                        <div className="header-icon">
                            <BarChart3 />
                        </div>
                        <div>
                            <h1 className="header-title">AI Report Generation</h1>
                            <p className="header-subtitle">
                                <span className="source-label">Source:</span>
                                <span className="source-name">{dbConfig.database || 'Uploaded Files'}</span>
                            </p>
                        </div>
                    </div>
                    <div className="header-actions">
                        <button onClick={() => {
                            setCurrentPage('connect');
                            setIsConnected(false);
                            setResults([]);
                            setSelectedQueries([]);
                        }} className="btn btn-secondary">
                            <Settings className="btn-icon" />
                            Change Source
                        </button>
                        <button onClick={downloadReport} disabled={results.length === 0} className="btn btn-success">
                            <Download className="btn-icon" />
                            Download Report
                        </button>
                    </div>
                </div>
            </header>

            <div className="analysis-content">
                <aside className="query-sidebar">
                    <div className="sidebar-header">
                        <FileText className="sidebar-icon" />
                        <h2 className="sidebar-title">Query Library</h2>
                    </div>

                    <div className="query-tabs">
                        <button onClick={() => setActiveTab('predefined')} className={`tab ${activeTab === 'predefined' ? 'active' : ''}`}>
                            Predefined
                            <span className="tab-badge">{predefinedQueries.length}</span>
                        </button>
                        <button onClick={() => setActiveTab('custom')} className={`tab ${activeTab === 'custom' ? 'active' : ''}`}>
                            Custom
                            <span className="tab-badge">{customQueries.length}</span>
                        </button>
                    </div>

                    <div className="queries-container">
                        {activeTab === 'predefined' && predefinedQueries.map(query => (
                            <div key={query.id} onClick={() => toggleQuerySelection(query.id, 'predefined')} className={`query-card ${selectedQueries.includes(`predefined-${query.id}`) ? 'selected' : ''}`}>
                                <div className="query-icon">{query.icon}</div>
                                <div className="query-content">
                                    <p className="query-text">{query.text}</p>
                                    <span className="query-category">{query.category}</span>
                                </div>
                                {selectedQueries.includes(`predefined-${query.id}`) && (
                                    <Check className="query-check" />
                                )}
                            </div>
                        ))}

                        {activeTab === 'custom' && (
                            customQueries.length > 0 ? (
                                customQueries.map(query => (
                                    <div key={query.id} className={`query-card custom ${selectedQueries.includes(`custom-${query.id}`) ? 'selected' : ''}`}>
                                        <div className="query-content" onClick={() => toggleQuerySelection(query.id, 'custom')}>
                                            <p className="query-text">{query.text}</p>
                                            <span className="query-timestamp">{new Date(query.timestamp).toLocaleDateString()}</span>
                                        </div>
                                        <div className="query-actions">
                                            {selectedQueries.includes(`custom-${query.id}`) && (
                                                <Check className="query-check" />
                                            )}
                                            <button onClick={(e) => {
                                                e.stopPropagation();
                                                deleteCustomQuery(query.id);
                                            }} className="btn-delete">
                                                <Trash2 />
                                            </button>
                                        </div>
                                    </div>
                                ))
                            ) : (
                                <div className="empty-state">
                                    <p>No custom queries yet</p>
                                </div>
                            )
                        )}
                    </div>
                </aside>

                <main className="analysis-main">
                    <div className="custom-query-section">
                        <div className="section-header">
                            <Plus className="section-icon" />
                            <h3 className="section-title">Create Custom Query</h3>
                        </div>
                        <div className="custom-query-input">
                            <input
                                type="text"
                                value={newQuery}
                                onChange={(e) => setNewQuery(e.target.value)}
                                onKeyPress={(e) => e.key === 'Enter' && addCustomQuery()}
                                placeholder="e.g., Show top 5 customers by revenue in 2023"
                                className="query-input"
                            />
                            <button onClick={addCustomQuery} disabled={!newQuery.trim()} className="btn btn-add">
                                <Plus className="btn-icon" />
                                Add Query
                            </button>
                        </div>
                    </div>

                    <div className="process-section">
                        <div className="process-card">
                            <div className="process-info">
                                <TrendingUp className="process-icon" />
                                <div>
                                    <h3 className="process-title">
                                        {selectedQueries.length} {selectedQueries.length === 1 ? 'Query' : 'Queries'} Selected
                                    </h3>
                                    <p className="process-subtitle">Ready to generate AI-powered insights</p>
                                </div>
                            </div>
                            <button onClick={processQueries} disabled={isProcessing || selectedQueries.length === 0} className="btn btn-process">
                                {isProcessing ? (
                                    <>
                                        <Loader className="btn-icon animate-spin" />
                                        Processing...
                                    </>
                                ) : (
                                    <>
                                        <Play className="btn-icon" />
                                        Generate Insights
                                    </>
                                )}
                            </button>
                        </div>
                    </div>

                    {results.length > 0 && (
                        <div className="results-section">
                            <div className="results-header">
                                <h2 className="results-title">Generated Insights</h2>
                                <span className="results-count">{results.length} result{results.length > 1 ? 's' : ''}</span>
                            </div>
                            {results.map((result, index) => {
                                const insightData = result.insight || {};
                                const summaryPoints = insightData.summary || [];
                                const insightPoints = insightData.insights || [];
                                const strategyPoints = insightData.strategy || insightData.recommendations || [];
                                const sqlQuery = insightData.sql_query || insightData.sql || insightData.query || '';
                                const visualizations = insightData.visualizations || {};
                                const chartOrder = visualizations.chart_order || Object.keys(visualizations).filter(key => !['primary', 'chart_order'].includes(key));
                                const dataRows = Array.isArray(insightData.rows) && insightData.rows.length
                                    ? insightData.rows
                                    : (Array.isArray(insightData.data) ? insightData.data : []);
                                const columns = Array.isArray(insightData.columns) && insightData.columns.length
                                    ? insightData.columns
                                    : (dataRows && dataRows.length ? Object.keys(dataRows[0]) : []);
                                const previewRows = columns.length ? dataRows.slice(0, 10) : [];
                                const processingTime = insightData.agent_stats?.processing_time || insightData.agent_stats?.processing_time_seconds;

                                const formatChartTitle = (key = '') =>
                                    key
                                        .replace(/_/g, ' ')
                                        .replace(/\b\w/g, char => char.toUpperCase());

                                const buildImageSrc = (imgString = '') =>
                                    imgString.startsWith('data:image') ? imgString : `data:image/png;base64,${imgString}`;

                                return (
                                    <div key={index} className="insight-card">
                                        <div className="insight-header">
                                            <h3 className="insight-query">{result.query}</h3>
                                            {processingTime && (
                                                <span className="insight-time">{processingTime}s</span>
                                            )}
                                        </div>

                                        {result.error ? (
                                            <div className="insight-error">
                                                <AlertTriangle className="error-icon" />
                                                <p>{result.error}</p>
                                            </div>
                                        ) : (
                                            <div className="insight-content">
                                                <div className="insight-panels">
                                                    <div className="insight-summary">
                                                        <h4 className="summary-title">Summary Highlights</h4>
                                                        {summaryPoints.length ? (
                                                            <ul className="summary-list">
                                                                {summaryPoints.map((summary, idx) => (
                                                                    <li key={idx}>{summary}</li>
                                                                ))}
                                                            </ul>
                                                        ) : (
                                                            <p className="summary-empty">No summary generated for this query.</p>
                                                        )}
                                                    </div>
                                                    <div className="insight-details-panel">
                                                        {insightPoints.length > 0 && (
                                                            <>
                                                                <h4 className="summary-title">Key Findings</h4>
                                                                <ul className="summary-list">
                                                                    {insightPoints.map((item, idx) => (
                                                                        <li key={`insight-${idx}`}>{item}</li>
                                                                    ))}
                                                                </ul>
                                                            </>
                                                        )}
                                                        {strategyPoints.length > 0 && (
                                                            <>
                                                                <h4 className="summary-title">Recommended Actions</h4>
                                                                <ul className="summary-list">
                                                                    {strategyPoints.map((item, idx) => (
                                                                        <li key={`strategy-${idx}`}>{item}</li>
                                                                    ))}
                                                                </ul>
                                                            </>
                                                        )}
                                                        {insightPoints.length === 0 && strategyPoints.length === 0 && (
                                                            <p className="summary-empty">No additional findings available.</p>
                                                        )}
                                                    </div>
                                                </div>

                                                {sqlQuery && (
                                                    <div className="insight-sql">
                                                        <h4 className="sql-title">SQL Query</h4>
                                                        <pre className="sql-code">
                                                            <code>{sqlQuery}</code>
                                                        </pre>
                                                    </div>
                                                )}

                                                <div className="insight-visualization">
                                                    <div className="viz-title-row">
                                                        <h4 className="viz-title">Visualizations</h4>
                                                        {chartOrder.length > 0 && (
                                                            <span className="viz-count">{chartOrder.length}</span>
                                                        )}
                                                    </div>
                                                    {chartOrder.length > 0 ? (
                                                        <div className="visualizations-grid">
                                                            {chartOrder.map((chartKey) => {
                                                                const chartData = visualizations[chartKey];
                                                                if (!chartData) return null;
                                                                const imageSrc = chartData.base64 || chartData.image;
                                                                if (!imageSrc) return null;
                                                                return (
                                                                    <div className="viz-card" key={`${index}-${chartKey}`}>
                                                                        <div className="viz-card-header">
                                                                            <h5>{chartData.title || formatChartTitle(chartKey)}</h5>
                                                                            {chartData.description && (
                                                                                <p className="viz-description">{chartData.description}</p>
                                                                            )}
                                                                        </div>
                                                                        <div className="viz-container">
                                                                            <img
                                                                                src={buildImageSrc(imageSrc)}
                                                                                alt={chartData.title || chartKey}
                                                                                className="viz-image"
                                                                            />
                                                                        </div>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    ) : (
                                                        <p className="viz-empty">No visualizations generated for this question.</p>
                                                    )}
                                                </div>

                                                {columns.length > 0 && previewRows.length > 0 && (
                                                    <div className="insight-data">
                                                        <h4 className="data-title">Data Preview</h4>
                                                        <div className="data-table-wrapper">
                                                            <table className="data-table">
                                                                <thead>
                                                                    <tr>
                                                                        {columns.map((col) => (
                                                                            <th key={col}>{col}</th>
                                                                        ))}
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    {previewRows.map((row, rowIdx) => (
                                                                        <tr key={rowIdx}>
                                                                            {columns.map((col) => (
                                                                                <td key={`${rowIdx}-${col}`}>{row[col]}</td>
                                                                            ))}
                                                                        </tr>
                                                                    ))}
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                        {dataRows.length > previewRows.length && (
                                                            <p className="data-note">
                                                                Showing first {previewRows.length} of {dataRows.length} rows
                                                            </p>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </main>
            </div>
        </div>
    );
};

export default ReportGeneration;