FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY apps/workers/pyproject.toml apps/workers/README.md apps/workers/
COPY apps/backend/pyproject.toml apps/backend/README.md apps/backend/
COPY packages/database/pyproject.toml packages/database/README.md packages/database/
COPY packages/shared/pyproject.toml packages/shared/README.md packages/shared/

# Install CPU-only PyTorch first to avoid 4GB+ CUDA packages
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e apps/backend \
    -e apps/workers \
    sentence-transformers \
    einops

# Pre-download embedding model
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)"

# Copy source code
COPY packages/shared/src packages/shared/src
COPY packages/database/src packages/database/src
COPY apps/backend/src apps/backend/src
COPY apps/workers/src apps/workers/src

ENV PYTHONPATH=/app/apps/workers:/app/apps/backend:/app/packages/database:/app/packages/shared

# Entry point set by JOB_TYPE environment variable
CMD ["python", "-m", "src"]

