const express = require('express');
const path = require('path');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 80;
const API_URL = process.env.REACT_APP_API_URL || 'http://host.docker.internal:8000';

// API proxy
app.use('/api', createProxyMiddleware({
  target: API_URL,
  changeOrigin: true,
  pathRewrite: { '^/api': '' },
  onProxyReq: (proxyReq, req, res) => {
    console.log(`[Proxy] ${req.method} ${req.url} -> ${API_URL}`);
  },
}));

// Static files
app.use(express.static(path.join(__dirname, 'build')));

// SPA fallback - all other routes go to index.html
app.get('/{*splat}', (req, res) => {
  res.sendFile(path.join(__dirname, 'build', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend server running on port ${PORT}`);
  console.log(`API proxy: /api -> ${API_URL}`);
});
