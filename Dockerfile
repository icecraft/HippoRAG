# HippoRAG REST API Dockerfile
# Build: docker build -t hipporag-api .
# Run: docker run -p 8000:8000 --env-file .env hipporag-api

FROM python:3.11-slim

COPY debian.sources /etc/apt/sources.list.d

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# Copy application code
COPY src/ ./src/
COPY setup.py .

# Create outputs directory
RUN mkdir -p /app/outputs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the API server
CMD ["uvicorn", "hipporag.api:app", "--host", "0.0.0.0", "--port", "8000"]
