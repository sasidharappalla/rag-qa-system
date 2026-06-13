FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DATABASE_URL=sqlite:////tmp/docuquery.db \
    CHROMA_PERSIST_DIR=/tmp/chroma \
    UPLOAD_DIR=/tmp/uploads \
    LLM_PROVIDER=mock \
    PLATFORM_DEMO_MODE=true \
    DEPENDENCY_HEALTH_CHECKS=false \
    APP_ENV=demo \
    LOG_LEVEL=INFO

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
    && pip install --requirement /tmp/requirements.txt

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /tmp/chroma /tmp/uploads \
    && chown -R appuser:appuser /tmp/chroma /tmp/uploads /workspace

COPY --chown=appuser:appuser . /workspace/app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
