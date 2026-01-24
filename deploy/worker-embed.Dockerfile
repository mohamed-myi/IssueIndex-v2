FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY apps/backend/pyproject.toml apps/backend/README.md apps/backend/
COPY packages/database/pyproject.toml packages/database/README.md packages/database/
COPY packages/shared/pyproject.toml packages/shared/README.md packages/shared/

# Install dependencies
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e apps/backend \
    google-cloud-aiplatform

# Copy source code
COPY packages/shared/gim_shared packages/shared/gim_shared
COPY packages/database/gim_database packages/database/gim_database
COPY apps/backend/gim_backend apps/backend/gim_backend

ENV PORT=8080
ENV EMBEDDING_MODE=nomic

CMD ["uvicorn", "gim_backend.workers.embed_worker:app", "--host", "0.0.0.0", "--port", "8080"]
