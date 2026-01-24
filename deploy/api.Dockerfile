FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Editable installs require source directories to exist
COPY packages/shared packages/shared
COPY packages/database packages/database
COPY apps/backend apps/backend

# Install dependencies (includes Vertex AI client for search embeddings)
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e apps/backend \
    google-cloud-aiplatform

ENV PORT=8080
ENV EMBEDDING_MODE=nomic

# Run with uvicorn
CMD ["uvicorn", "gim_backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
