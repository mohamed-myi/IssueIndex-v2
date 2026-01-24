FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Editable installs require source directories to exist
COPY packages/shared packages/shared
COPY packages/database packages/database
COPY apps/backend apps/backend
COPY apps/workers apps/workers

# Install CPU-only PyTorch first to avoid 4GB+ CUDA packages
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install dependencies (editable mode)
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

# Entry point: run the gim_workers package
CMD ["python", "-m", "gim_workers"]
