# Fast, secure, production-grade Dockerfile for RepoViva Graph MCP Server
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install build dependencies if needed, then cleanup to keep image slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Layer cache: Copy requirements first so package installation is cached
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Create persistent data directory
RUN mkdir -p /app/data

# Expose port (overridden by cloud providers dynamically via $PORT)
EXPOSE 8000

# Healthcheck to verify the server is responding quickly
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT:-8000}/api/status || exit 1

# Start the combined FastAPI Dashboard + Remote MCP Server
CMD ["python", "main.py"]

