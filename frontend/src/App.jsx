import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import AppLayout from './components/AppLayout';
import Home from './pages/Home';
import Books from './pages/Books';
import Businesses from './pages/Businesses';
import BusinessDetail from './pages/Businesses/Detail';
import Ingest from './pages/Ingest';
import Query from './pages/Query';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/books" element={<Books />} />
            <Route path="/businesses" element={<Businesses />} />
            <Route path="/businesses/:id" element={<BusinessDetail />} />
            <Route path="/ingest" element={<Ingest />} />
            <Route path="/query" element={<Query />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
