
## 需求

需要一个前端用于创建 book，bussiness 以及编辑 book 和 bussines 的关系，一个页面用于上传文本文件，该文本文件作为 ingest 数据。


## 技术栈

| Category | Technology | Version |
|----------|------------|---------|
| Framework | React | 18.2.0 |
| Routing | React Router DOM | 6.8.0 |
| UI Library | Ant Design | 5.2.0 |
| Icons | @ant-design/icons | 5.0.0 |
| HTTP Client | Axios | 1.3.0 |
| Build Tool | React Scripts (CRA) | 5.0.1 |
| Production Server | Caddy | Alpine |


## 答疑

1. 后端 API：是否有现成的 REST API 端点？比如 /api/books、/api/businesses 等？需要了解 API 结构。
参考 docs/REST_API.md


2. 数据结构：book 和 business 的字段分别是什么？它们之间的关系是多对多还是一对多？
请阅读文档接口


3. 现有代码：项目中是否已有前端代码或 API 定义文件可以参考？
目前没有前端代码，可以先制定方案


4. Ingest 流程：上传的文本文件是直接存储，还是需要进一步处理（如分块、向量化等）？
参考 projects/ingest_via_api.py


5. UI 设计：是否有设计稿或参考样式，还是自由发挥？
自由发挥

6. Ingest 文件格式：支持纯文本文件（每行一个文档）和 JSON 数组格式
7. 前端目录：frontend/
8. CORS 配置：使用 Caddy 反向代理
9. 认证：不需要

---

## 开发方案

### 目录结构

```
frontend/
├── public/
│   ├── index.html
│   └── favicon.ico
├── src/
│   ├── api/
│   │   └── index.js          # Axios 封装，API 调用
│   ├── components/
│   │   ├── AppLayout.jsx     # 通用布局（侧边栏 + 内容区）
│   │   └── index.js
│   ├── pages/
│   │   ├── Books/
│   │   │   └── index.jsx     # 书籍列表页
│   │   ├── Businesses/
│   │   │   ├── index.jsx     # 业务列表页
│   │   │   └── Detail.jsx    # 业务详情页（绑定书籍）
│   │   ├── Ingest/
│   │   │   └── index.jsx     # 文档上传页
│   │   └── Home/
│   │       └── index.jsx     # 首页/仪表盘
│   ├── App.jsx
│   ├── index.js
│   └── index.css
├── package.json
├── Dockerfile
└── Caddyfile
```

### 页面设计

#### 1. 首页 (Home)
- 显示系统状态（健康检查）
- 快速入口卡片（Books、Businesses、Ingest）

#### 2. Books 列表页
- 表格展示所有书籍
- 功能：
  - 创建 Book（输入 book_id）
  - 删除 Book（确认弹窗）
  - 显示 doc_count、status、created_at
- 调用 API：`GET /books`, `POST /book`, `DELETE /book`

#### 3. Businesses 列表页
- 表格展示所有业务
- 功能：
  - 创建 Business（business_id, name, description）
  - 编辑 Business（跳转详情页）
  - 删除 Business（确认弹窗）
  - 显示 book_count、status
- 调用 API：`GET /businesses`, `POST /business`, `DELETE /business/{id}`

#### 4. Business 详情页
- 显示 Business 基本信息
- 已绑定书籍列表（支持解绑）
- 可用书籍列表（支持绑定）
- 调用 API：`GET /business/{id}`, `GET /business/books`, `POST /business/bind`, `POST /business/unbind`

#### 5. Ingest 上传页
- 选择 Book（下拉框）
- 上传文件（支持 .txt 和 .json）
- 文件解析：
  - .txt：按行分割，每行一个文档
  - .json：解析为字符串数组
- 显示解析预览（前 5 条）
- 提交索引（调用 `POST /book/index/sync`）
- 显示索引进度/结果

### API 封装

```javascript
// src/api/index.js
import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || '/api',
  timeout: 30000,
});

// Books
export const getBooks = () => api.get('/books');
export const createBook = (book_id) => api.post('/book', { book_id });
export const deleteBook = (book_id) => api.delete(`/book?book_id=${book_id}`);
export const indexDocuments = (book_id, docs) => api.post('/book/index/sync', { book_id, docs });

// Businesses
export const getBusinesses = () => api.get('/businesses');
export const getBusiness = (business_id) => api.get(`/business/${business_id}`);
export const createBusiness = (data) => api.post('/business', data);
export const updateBusiness = (business_id, data) => api.put(`/business/${business_id}`, data);
export const deleteBusiness = (business_id) => api.delete(`/business/${business_id}`);
export const getBusinessBooks = (business_id) => api.get(`/business/books?business_id=${business_id}`);
export const bindBooks = (business_id, book_ids) => api.post('/business/bind', { business_id, book_ids });
export const unbindBooks = (business_id, book_ids) => api.post('/business/unbind', { business_id, book_ids });

// Health
export const checkHealth = () => api.get('/health');
```

### 路由配置

```javascript
// App.jsx
<Routes>
  <Route path="/" element={<Home />} />
  <Route path="/books" element={<Books />} />
  <Route path="/businesses" element={<Businesses />} />
  <Route path="/businesses/:id" element={<BusinessDetail />} />
  <Route path="/ingest" element={<Ingest />} />
</Routes>
```

### 部署配置

#### Dockerfile
```dockerfile
# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM caddy:alpine
COPY --from=builder /app/build /var/www/html
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 80
```

#### Caddyfile
```
:80 {
    root * /var/www/html
    encode gzip

    # SPA fallback
    try_files {path} /index.html
    file_server

    # API proxy with CORS
    handle /api/* {
        uri strip_prefix /api
        reverse_proxy host.docker.internal:8000 {
            header_up Host {host}
            header_up X-Real-IP {remote_host}
            header_up X-Forwarded-For {remote_host}
            header_up X-Forwarded-Proto {scheme}
        }
    }
}
```

### 开发环境

创建 `frontend/.env`:
```
REACT_APP_API_URL=http://localhost:8000
```

开发时运行：
```bash
cd frontend
npm start  # 默认代理到 localhost:8000
```

---

## 实现步骤

### Phase 1: 项目初始化
1. 使用 CRA 创建 React 项目
2. 安装依赖（antd, axios, react-router-dom, @ant-design/icons）
3. 配置项目结构
4. 创建 API 封装

### Phase 2: 基础组件
1. 实现 AppLayout（侧边栏导航）
2. 配置路由
3. 实现首页

### Phase 3: 核心页面
1. Books 列表页
2. Businesses 列表页
3. Business 详情页
4. Ingest 上传页

### Phase 4: 部署配置
1. 编写 Dockerfile
2. 编写 Caddyfile
3. 更新 docker-compose.yml
4. 测试生产构建
