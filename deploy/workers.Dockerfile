FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy all source code first (editable installs require source to exist)
COPY packages/shared packages/shared
COPY packages/database packages/database
COPY apps/backend apps/backend
COPY apps/workers apps/workers

# Install PyTorch from CPU index (avoids 4GB CUDA packages)
RUN pip install --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

# Install packages and ML dependencies
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

# Pre-download embedding model (nomic-embed-text-v2-moe)
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v2-moe', trust_remote_code=True)"

CMD ["python", "-m", "gim_workers"]
