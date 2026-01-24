FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy package dependency files
COPY packages/shared/pyproject.toml packages/shared/README.md packages/shared/
COPY packages/database/pyproject.toml packages/database/README.md packages/database/
COPY apps/backend/pyproject.toml apps/backend/README.md apps/backend/
COPY apps/workers/pyproject.toml apps/workers/README.md apps/workers/

# Install CPU-only PyTorch first to avoid 4GB+ CUDA packages
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies (editable mode for development)
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e apps/backend \
    -e apps/workers \
    google-cloud-aiplatform \
    google-cloud-pubsub \
    google-cloud-run \
    sentence-transformers \
    einops

# Pre-download embedding model (nomic-embed-text-v2-moe for 256-dim Matryoshka truncation)
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v2-moe', trust_remote_code=True)"

# Copy source code (gim_* packages, not src/)
COPY packages/shared/gim_shared packages/shared/gim_shared
COPY packages/database/gim_database packages/database/gim_database
COPY packages/database/migrations packages/database/migrations
COPY apps/backend/gim_backend apps/backend/gim_backend
COPY apps/workers/gim_workers apps/workers/gim_workers

# No PYTHONPATH needed - packages installed via pip install -e

# Entry point: run the gim_workers package
CMD ["python", "-m", "gim_workers"]
