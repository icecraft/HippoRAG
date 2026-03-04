# HippoRAG 文档

本目录包含 HippoRAG 的完整文档，帮助第三方系统快速集成和使用。

## 文档索引

### 快速开始
- [快速开始指南](./QUICKSTART.md) - 5 分钟快速上手
- [集成指南](./INTEGRATION_GUIDE.md) - 第三方系统集成 HippoRAG 的完整指南
- [DGraph 支持说明](./dgraph_support.md) - 精简版图存储（DGraph）和向量存储（pgvector）配置

### 核心文档
- [REST API 文档](./REST_API.md) - RESTful API 接口文档
- [API 参考文档](./API_REFERENCE.md) - 详细的 Python API 接口文档
- [配置指南](./CONFIGURATION.md) - 配置参数详细说明
- [架构概述](./ARCHITECTURE.md) - 系统架构和设计原理
- [部署指南](./DEPLOYMENT.md) - 生产环境部署指南

## 快速导航

### 我想...

| 需求 | 推荐文档 |
|------|----------|
| 快速上手 | [快速开始指南](./QUICKSTART.md) |
| 使用 REST API | [REST API 文档](./REST_API.md) |
| 了解 Python API | [API 参考文档](./API_REFERENCE.md#hipporag-类) |
| 配置参数 | [配置指南](./CONFIGURATION.md#配置概述) |
| 部署到生产 | [部署指南](./DEPLOYMENT.md#系统要求) |
| 理解架构 | [架构概述](./ARCHITECTURE.md#架构概述) |
| 使用数据库 | [集成指南 - 数据存储集成](./INTEGRATION_GUIDE.md#数据存储集成) |
| 集成到 Web 应用 | [集成指南 - 第三方系统集成示例](./INTEGRATION_GUIDE.md#第三方系统集成示例) |
| Docker 部署 | [部署指南 - Docker 部署](./DEPLOYMENT.md#docker-部署) |
| Kubernetes 部署 | [部署指南 - Kubernetes 部署](./DEPLOYMENT.md#kubernetes-部署) |

## 系统概述

HippoRAG 2 是一个受神经生物学启发的 LLM 记忆框架，通过知识图谱和图算法增强大语言模型的检索能力。

### 核心特性

- **记忆增强检索**: 基于知识图谱的多跳检索
- **高效索引**: 相比其他图 RAG 方法，索引成本更低
- **灵活部署**: 支持多种存储后端和图数据库
- **易于集成**: 简单的 Python API

### 支持的集成方式

- **Web 服务**: FastAPI / Flask / Django
- **数据库集成**: PostgreSQL pgvector / DGraph
- **容器化**: Docker / Kubernetes
- **云服务**: 可部署到任何云平台

## 文档结构

```
docs/
├── README.md              # 本文件（文档索引）
├── INTEGRATION_GUIDE.md   # 集成指南
├── API_REFERENCE.md       # API 参考
├── CONFIGURATION.md       # 配置指南
├── ARCHITECTURE.md        # 架构概述
└── DEPLOYMENT.md          # 部署指南
```

## 技术支持

- **GitHub Issues**: [提交问题](https://github.com/OSU-NLP-Group/HippoRAG/issues)
- **邮件**: hipporag@osu.edu
- **论文**: [arXiv:2502.14802](https://arxiv.org/abs/2502.14802)

## 相关链接

- [GitHub 仓库](https://github.com/OSU-NLP-Group/HippoRAG)
- [PyPI 包](https://pypi.org/project/hipporag/)
- [HuggingFace 数据集](https://huggingface.co/datasets/osunlp/HippoRAG_v2)

---

*最后更新: 2026-03*
