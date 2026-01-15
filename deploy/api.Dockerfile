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

# Install dependencies (includes Vertex AI client for search embeddings)
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e apps/backend \
    google-cloud-aiplatform

# Copy source code
COPY packages/shared/src packages/shared/src
COPY packages/database/src packages/database/src
COPY apps/backend/src apps/backend/src

# Set environment
# - /app/apps/backend: for "from src.x" imports in backend code
# - /app/packages/database/src: for "from models.x" direct imports
# - /app/packages/shared/src: for "from constants" direct imports
ENV PYTHONPATH=/app/apps/backend:/app/packages/database/src:/app/packages/shared/src
ENV PORT=8080
ENV EMBEDDING_MODE=nomic

# Run with uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
