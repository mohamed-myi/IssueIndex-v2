FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for Docling + model compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Copy all source code first (editable installs require source to exist)
COPY packages/shared packages/shared
COPY packages/database packages/database
COPY apps/backend apps/backend

# Install PyTorch ecosystem from CPU index TOGETHER
# This prevents version conflicts when docling pulls torchvision
RUN pip install --no-cache-dir \
    torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu

# Install packages and ML dependencies
# docling will use the already-installed torchvision
RUN pip install --no-cache-dir \
    -e packages/shared \
    -e packages/database \
    -e "apps/backend[resume]" \
    google-cloud-aiplatform \
    sentence-transformers

# Pre-download GLiNER model
RUN python3 -c "from gliner import GLiNER; GLiNER.from_pretrained('urchade/gliner_base')"

ENV PORT=8080
ENV EMBEDDING_MODE=nomic

CMD ["uvicorn", "gim_backend.workers.resume_worker:app", "--host", "0.0.0.0", "--port", "8080"]
