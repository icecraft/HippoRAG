#!/bin/bash
# HippoRAG RESTful API 启动脚本

# 切换到脚本所在目录
cd src/

# 加载环境变量
if [ -f .env ]; then
    echo "Loading environment variables from .env..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# 默认配置
HOST=${API_HOST:-0.0.0.0}
PORT=${API_PORT:-8000}
WORKERS=${API_WORKERS:-1}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --workers)
            WORKERS="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --host HOST       API server host (default: 0.0.0.0)"
            echo "  --port PORT       API server port (default: 8000)"
            echo "  --workers N       Number of worker processes (default: 1)"
            echo "  --help            Show this help message"
            echo ""
            echo "Environment variables (can be set in .env file):"
            echo "  API_HOST          API server host"
            echo "  API_PORT          API server port"
            echo "  API_WORKERS       Number of workers"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Starting HippoRAG API Server"
echo "=========================================="
echo "Host: $HOST"
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo ""
echo "API Documentation: http://localhost:$PORT/docs"
echo "=========================================="
echo ""

# 启动服务
# 使用 src.hipporag.api 路径，避免需要先 pip install -e .
if [ "$WORKERS" -gt 1 ]; then
    uvicorn hipporag.api:app --host "$HOST" --port "$PORT" --workers "$WORKERS"
else
    uvicorn hipporag.api:app --host "$HOST" --port "$PORT"
fi
