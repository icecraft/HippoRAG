import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api',
  timeout: 60000,
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

// Health
export const checkHealth = () => api.get('/health');

// Books
export const getBooks = () => api.get('/books');
export const createBook = (book_id) => api.post('/book', { book_id });
export const deleteBook = (book_id) => api.delete(`/book?book_id=${book_id}`);
export const indexDocuments = (book_id, docs) => api.post('/book/index/sync', { book_id, docs });

// Async indexing with SSE progress
export const indexDocumentsAsync = (book_id, docs) => api.post('/book/index', { book_id, docs });

// SSE progress tracking
export const createProgressEventSource = () => {
  const baseURL = process.env.REACT_APP_API_URL || '/api';
  return new EventSource(`${baseURL}/index/progress`);
};

// File upload for indexing
export const uploadFile = (file, onUploadProgress) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/index/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress,
    timeout: 300000, // 5 minutes for large files
  });
};

// Async document indexing (returns immediately, use SSE for progress)
export const indexDocumentsAsync = (book_id, docs) =>
  api.post('/book/index', { book_id, docs });

// Businesses
export const getBusinesses = () => api.get('/businesses');
export const getBusiness = (business_id) => api.get(`/business/${business_id}`);
export const createBusiness = (data) => api.post('/business', data);
export const updateBusiness = (business_id, data) => api.put(`/business/${business_id}`, data);
export const deleteBusiness = (business_id) => api.delete(`/business/${business_id}`);

// Business-Book binding
export const getBusinessBooks = (business_id) => api.get(`/business/books?business_id=${business_id}`);
export const bindBooks = (business_id, book_ids) => api.post('/business/bind', { business_id, book_ids });
export const unbindBooks = (business_id, book_ids) => api.post('/business/unbind', { business_id, book_ids });

// Query
export const retrieveByBusiness = (data) => api.post('/business/retrieve', data);
export const qaByBusiness = (data) => api.post('/business/qa', data);

export default api;
