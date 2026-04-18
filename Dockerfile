FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps: build-essential for any wheels without prebuilt binaries (psycopg2, tokenizers).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first for layer caching.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -e .

# Now copy the source.
COPY app ./app
COPY scripts ./scripts
COPY eval ./eval
COPY data ./data

# Writable dirs for Chroma + uploads.
RUN mkdir -p /app/data/chroma /app/data/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
