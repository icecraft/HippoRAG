# HippoRAG 部署指南

本文档提供了 HippoRAG 在生产环境中部署的完整指南。

## 目录

- [系统要求](#系统要求)
- [安装](#安装)
- [环境配置](#环境配置)
- [数据库部署](#数据库部署)
- [Docker 部署](#docker-部署)
- [Kubernetes 部署](#kubernetes-部署)
- [监控和日志](#监控和日志)
- [性能优化](#性能优化)
- [安全最佳实践](#安全最佳实践)

---

## 系统要求

### 最低要求

| 组件 | 最低配置 |
|------|----------|
| CPU | 4 核 |
| 内存 | 8 GB |
| 存储 | 20 GB |
| Python | 3.9+ |
| GPU | 可选 |

### 推荐配置（生产环境）

| 组件 | 推荐配置 |
|------|----------|
| CPU | 16+ 核 |
| 内存 | 32+ GB |
| 存储 | 100+ GB SSD |
| Python | 3.10 |
| GPU | NVIDIA GPU（本地模型） |

### 大规模部署

| 组件 | 配置 |
|------|------|
| CPU | 32+ 核 |
| 内存 | 128+ GB |
| 存储 | 1TB+ SSD |
| GPU | 多卡配置 |

---

## 安装

### 使用 pip 安装

```bash
# 创建虚拟环境
python -m venv hipporag_env
source hipporag_env/bin/activate

# 安装
pip install hipporag

# 精简版已内置 pgvector 和 pydgraph 依赖
```

### 从源码安装

```bash
git clone https://github.com/OSU-NLP-Group/HippoRAG.git
cd HippoRAG

pip install -e .
```

### Docker 安装

```bash
# 构建镜像
docker build -t hipporag:latest .

# 运行容器
docker run -d \
  --name hipporag \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your_key \
  -v /path/to/data:/data \
  hipporag:latest
```

---

## 环境配置

### 环境变量

创建 `.env` 文件：

```bash
# LLM 配置
OPENAI_API_KEY=sk-xxxxxxxxxxxxx
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# 嵌入配置
EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_API_URL=https://api.example.com/v1

# 数据存储
HIPPORAG_SAVE_DIR=/data/hipporag
USE_PGVECTOR=true
PGVECTOR_HOST=localhost
PGVECTOR_PORT=5432
PGVECTOR_DATABASE=hipporag
PGVECTOR_USER=hipporag_user
PGVECTOR_PASSWORD=secure_password

# 图数据库
DGRAPH_HOST=localhost
DGRAPH_PORT=9080

# 性能配置
EMBEDDING_BATCH_SIZE=32
RETRIEVAL_TOP_K=200
MAX_QA_STEPS=2

# 日志
LOG_LEVEL=INFO
LOG_FILE=/var/log/hipporag/app.log
```

### 使用环境变量加载

```python
import os
from dotenv import load_dotenv
from hipporag import HippoRAG, BaseConfig

# 加载环境变量
load_dotenv()

config = BaseConfig(
    save_dir=os.getenv('HIPPORAG_SAVE_DIR', './data'),
    llm_name=os.getenv('LLM_NAME', 'gpt-4o-mini'),
    llm_base_url=os.getenv('LLM_BASE_URL'),
    embedding_model_name=os.getenv('EMBEDDING_MODEL_NAME', 'text-embedding-3-small'),
    embedding_base_url=os.getenv('EMBEDDING_BASE_URL'),
    use_pgvector=os.getenv('USE_PGVECTOR', 'false').lower() == 'true',
    pgvector_host=os.getenv('PGVECTOR_HOST', 'localhost'),
    pgvector_port=int(os.getenv('PGVECTOR_PORT', 5432)),
    pgvector_database=os.getenv('PGVECTOR_DATABASE', 'hipporag'),
    pgvector_user=os.getenv('PGVECTOR_USER', 'postgres'),
    pgvector_password=os.getenv('PGVECTOR_PASSWORD', '')
)

hipporag = HippoRAG(global_config=config)
```

---

## 数据库部署

### PostgreSQL + pgvector

#### 使用 Docker 部署

```bash
# 启动 PostgreSQL + pgvector
docker run -d \
  --name postgres-pgvector \
  -e POSTGRES_PASSWORD=hipporag_password \
  -e POSTGRES_DB=hipporag \
  -p 5432:5432 \
  -v /data/postgres:/var/lib/postgresql/data \
  pgvector/pgvector:pg16

# 等待数据库启动
docker exec -it postgres-pgvector psql -U postgres -c "SELECT version();"
```

#### 使用 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: postgres-pgvector
    environment:
      POSTGRES_USER: hipporag
      POSTGRES_PASSWORD: your_secure_password
      POSTGRES_DB: hipporag
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U hipporag"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

启动服务：

```bash
docker-compose up -d
```

#### 手动安装 pgvector

```bash
# 连接到 PostgreSQL
sudo -u postgres psql

# 创建数据库和用户
CREATE DATABASE hipporag;
CREATE USER hipporag_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE hipporag TO hipporag_user;

# 连接到数据库
\c hipporag

# 安装 pgvector 扩展
CREATE EXTENSION vector;

# 验证安装
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### DGraph 部署

#### 使用 Docker 部署

```bash
# 启动 DGraph Zero
docker run -d \
  --name dgraph-zero \
  -p 5080:5080 \
  -p 6080:6080 \
  -v /data/dgraph:/dgraph \
  dgraph/standalone:latest dgraph zero --my=$(hostname -i):5080

# 启动 DGraph Alpha
docker run -d \
  --name dgraph-alpha \
  -p 8080:8080 \
  -p 9080:9080 \
  -v /data/dgraph:/dgraph \
  --link dgraph-zero:dgraph-zero \
  dgraph/standalone:latest dgraph alpha \
    --my=$(hostname -i):9080 \
    --zero dgraph-zero:5080 \
    --security whitelist=0.0.0.0/0

# 启动 Ratel UI（可选）
docker run -d \
  --name dgraph-ratel \
  -p 8000:8000 \
  dgraph/ratel:latest
```

#### 使用 Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  zero:
    image: dgraph/dgraph:latest
    volumes:
      - /data/dgraph:/dgraph
    ports:
      - 5080:5080
      - 6080:6080
    command: dgraph zero --my=zero:5080

  alpha:
    image: dgraph/dgraph:latest
    volumes:
      - /data/dgraph:/dgraph
    ports:
      - 8080:8080
      - 9080:9080
    command: dgraph alpha --my=alpha:9080 --zero=zero:5080 --security whitelist=0.0.0.0/0

  ratel:
    image: dgraph/ratel:latest
    ports:
      - 8000:8000
```

---

## Docker 部署

### 单机部署

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 hipporag
RUN pip install hipporag[pgvector,dgraph]

COPY . .

# 创建数据目录
RUN mkdir -p /data/hipporag

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["python", "main.py"]
```

### Docker Compose 部署

```yaml
version: '3.8'

services:
  hipporag:
    build: .
    container_name: hipporag
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - USE_PGVECTOR=true
      - PGVECTOR_HOST=postgres
      - PGVECTOR_PORT=5432
      - PGVECTOR_DATABASE=hipporag
      - PGVECTOR_USER=hipporag
      - PGVECTOR_PASSWORD=${PGVECTOR_PASSWORD}
    volumes:
      - /data/hipporag:/data/hipporag
      - /var/log/hipporag:/var/log/hipporag
    depends_on:
      - postgres
      - dgraph-zero
      - dgraph-alpha
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: pgvector/pgvector:pg16
    container_name: postgres-pgvector
    environment:
      POSTGRES_USER: hipporag
      POSTGRES_PASSWORD: ${PGVECTOR_PASSWORD}
      POSTGRES_DB: hipporag
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  dgraph-zero:
    image: dgraph/dgraph:latest
    container_name: dgraph-zero
    volumes:
      - dgraph_data:/dgraph
    ports:
      - 5080:5080
      - 6080:6080
    command: dgraph zero --my=dgraph-zero:5080
    restart: unless-stopped

  dgraph-alpha:
    image: dgraph/dgraph:latest
    container_name: dgraph-alpha
    volumes:
      - dgraph_data:/dgraph
    ports:
      - 8080:8080
      - 9080:9080
    command: dgraph alpha --my=dgraph-alpha:9080 --zero=dgraph-zero:5080 --security whitelist=0.0.0.0/0
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: hipporag-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - hipporag
    restart: unless-stopped

volumes:
  postgres_data:
  dgraph_data:
```

---

## Kubernetes 部署

### Namespace 和 ConfigMap

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: hipporag

---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hipporag-config
  namespace: hipporag
data:
  LOG_LEVEL: "INFO"
  HIPPORAG_SAVE_DIR: "/data/hipporag"
  USE_PGVECTOR: "true"
  PGVECTOR_HOST: "postgres-service"
  PGVECTOR_PORT: "5432"
  PGVECTOR_DATABASE: "hipporag"
  EMBEDDING_BATCH_SIZE: "32"
  RETRIEVAL_TOP_K: "200"
  MAX_QA_STEPS: "2"
```

### Secret

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: hipporag-secrets
  namespace: hipporag
type: Opaque
data:
  OPENAI_API_KEY: <base64-encoded-key>
  PGVECTOR_PASSWORD: <base64-encoded-password>
```

### PostgreSQL 部署

```yaml
# postgres.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-pvc
  namespace: hipporag
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: hipporag
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: pgvector/pgvector:pg16
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_USER
          value: "hipporag"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: hipporag-secrets
              key: PGVECTOR_PASSWORD
        - name: POSTGRES_DB
          value: "hipporag"
        - name: PGDATA
          value: "/var/lib/postgresql/data/pgdata"
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: hipporag
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
```

### HippoRAG 部署

```yaml
# hipporag.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hipporag
  namespace: hipporag
spec:
  replicas: 3
  selector:
    matchLabels:
      app: hipporag
  template:
    metadata:
      labels:
        app: hipporag
    spec:
      containers:
      - name: hipporag
        image: hipporag:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: hipporag-secrets
              key: OPENAI_API_KEY
        - name: PGVECTOR_PASSWORD
          valueFrom:
            secretKeyRef:
              name: hipporag-secrets
              key: PGVECTOR_PASSWORD
        envFrom:
        - configMapRef:
            name: hipporag-config
        volumeMounts:
        - name: hipporag-data
          mountPath: /data/hipporag
        - name: hipporag-logs
          mountPath: /var/log/hipporag
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
      volumes:
      - name: hipporag-data
        emptyDir: {}
      - name: hipporag-logs
        emptyDir: {}

---
apiVersion: v1
kind: Service
metadata:
  name: hipporag-service
  namespace: hipporag
spec:
  selector:
    app: hipporag
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: hipporag-hpa
  namespace: hipporag
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hipporag
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 部署命令

```bash
# 创建所有资源
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml
kubectl apply -f postgres.yaml
kubectl apply -f hipporag.yaml

# 查看状态
kubectl get pods -n hipporag
kubectl get services -n hipporag

# 查看日志
kubectl logs -f deployment/hipporag -n hipporag
```

---

## 监控和日志

### 日志配置

```python
import logging
from hipporag import HippoRAG

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/hipporag/app.log'),
        logging.StreamHandler()
    ]
)

# 使用日志
logger = logging.getLogger(__name__)
logger.info("HippoRAG initialized")
```

### Prometheus 监控

```python
from prometheus_client import start_http_server, Counter, Histogram, Gauge
from hipporag import HippoRAG

# 指标定义
request_counter = Counter('hipporag_requests_total', 'Total requests', ['endpoint'])
request_duration = Histogram('hipporag_request_duration_seconds', 'Request duration')
index_duration = Histogram('hipporag_index_duration_seconds', 'Index duration')
retrieval_duration = Histogram('hipporag_retrieval_duration_seconds', 'Retrieval duration')
qa_duration = Histogram('hipporag_qa_duration_seconds', 'QA duration')

# 启动指标服务器
start_http_server(8001)

# 使用指标
@app.post('/query')
@request_duration.time()
def query(request: QueryRequest):
    request_counter.labels(endpoint='query').inc()
    # ... 查询逻辑
```

### Prometheus 配置

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'hipporag'
    static_configs:
      - targets: ['hipporag-service:8001']
```

---

## 性能优化

### 缓存策略

```python
from functools import lru_cache
import hashlib

class CachedHippoRAG:
    def __init__(self, hipporag):
        self.hipporag = hipporag

    @lru_cache(maxsize=1000)
    def query(self, question: str):
        return self.hipporag.rag_qa(queries=[question])

    def query_with_embeddings(self, question: str):
        # 使用嵌入相似度作为缓存键
        embedding = self.hipporag.embedding_model.embed_query(question)
        cache_key = hashlib.md5(embedding.tobytes()).hexdigest()
        return self.query(cache_key)
```

### 批处理优化

```python
class BatchProcessor:
    def __init__(self, hipporag, batch_size=100):
        self.hipporag = hipporag
        self.batch_size = batch_size
        self.buffer = []

    def add(self, doc: str):
        self.buffer.append(doc)
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        if self.buffer:
            self.hipporag.index(docs=self.buffer)
            self.buffer = []
```

---

## 安全最佳实践

### API 密钥管理

```python
import os
from dotenv import load_dotenv

# 使用环境变量
load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")
```

### 输入验证

```python
from pydantic import BaseModel, validator

class QueryRequest(BaseModel):
    query: str

    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        if len(v) > 1000:
            raise ValueError("Query too long")
        return v.strip()
```

### 速率限制

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/query")
@limiter.limit("10/minute")
def query(request: QueryRequest):
    # ...
```

---

## 更多资源

- [集成指南](./INTEGRATION_GUIDE.md)
- [API 参考文档](./API_REFERENCE.md)
- [配置指南](./CONFIGURATION.md)
