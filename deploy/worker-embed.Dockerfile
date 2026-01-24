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

# Install PyTorch from CPU index (avoids 4GB CUDA packages)
RUN pip install --no-cache-dir \
    torch \
    --index-url https://download.pytorch.org/whl/cpu

# Install packages and ML dependencies
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e apps/backend \
    google-cloud-aiplatform \
    sentence-transformers

ENV PORT=8080
ENV EMBEDDING_MODE=nomic

CMD ["uvicorn", "gim_backend.workers.embed_worker:app", "--host", "0.0.0.0", "--port", "8080"]
