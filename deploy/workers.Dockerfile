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
# Install packages and ML dependencies
# - huggingface_hub[cli]: For faster model download (avoids QEMU)
# - einops: Required by nomic-embed-text-v2-moe
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e apps/backend \
    -e apps/workers \
    "google-cloud-pubsub>=2.19.0" \
    "sentence-transformers>=3.3.1" \
    einops \
    "huggingface_hub>=0.23.0"

# Pre-download embedding model (nomic-embed-text-v2-moe)
# We use --mount=type=secret to securely pass the token without leaving traces in image layers.
ENV HF_HOME=/root/.cache/huggingface
RUN --mount=type=secret,id=hf_token \
    python -c "from sentence_transformers import SentenceTransformer; \
    import os; \
    token_path = '/run/secrets/hf_token'; \
    token = open(token_path).read().strip() if os.path.exists(token_path) else None; \
    print(f'Downloading with token: {token[:4]}...' if token else 'Downloading without token...'); \
    SentenceTransformer('nomic-ai/nomic-embed-text-v2-moe', trust_remote_code=True, token=token)"

CMD ["python", "-m", "gim_workers"]
