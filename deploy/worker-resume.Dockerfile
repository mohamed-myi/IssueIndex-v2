FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for Docling
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Editable installs require source directories to exist
COPY packages/shared packages/shared
COPY packages/database packages/database
COPY apps/backend apps/backend

# Install dependencies
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e "apps/backend[resume]" \
    google-cloud-aiplatform

# Pre-download GLiNER model
RUN python3 -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_base')"

ENV PORT=8080
ENV EMBEDDING_MODE=nomic

CMD ["uvicorn", "gim_backend.workers.resume_worker:app", "--host", "0.0.0.0", "--port", "8080"]
