// API Configuration
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

// Helper function to handle API requests
const apiRequest = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Add auth token if available
  const token = localStorage.getItem('authToken');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API Request Error:', error);
    throw error;
  }
};

// Authentication APIs
export const authAPI = {
  login: (email, password) =>
    apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  signup: (name, email, password) =>
    apiRequest('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ name, email, password }),
    }),

  logout: () => {
    localStorage.removeItem('authToken');
    return Promise.resolve();
  },
};

// File Upload APIs
export const fileAPI = {
  uploadFile: (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const token = localStorage.getItem('authToken');
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    return fetch(`${API_BASE_URL}/files/upload`, {
      method: 'POST',
      headers,
      body: formData,
    }).then(res => {
      if (!res.ok) throw new Error('Upload failed');
      return res.json();
    });
  },

  getTransformedData: (fileId) =>
    apiRequest(`/files/${fileId}/transform`),
};

// Report APIs
export const reportAPI = {
  generateReport: () =>
    apiRequest('/reports/generate', {
      method: 'POST',
    }),

  getReport: (reportId) =>
    apiRequest(`/reports/${reportId}`),

  downloadReport: (reportId) => {
    const token = localStorage.getItem('authToken');
    const headers = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    window.location.href = `${API_BASE_URL}/reports/${reportId}/download`;
  },

  getAllReports: () =>
    apiRequest('/reports'),
};

export default {
  authAPI,
  fileAPI,
  reportAPI,
};
