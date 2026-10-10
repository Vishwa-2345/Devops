# SelfHealOps backend image — FastAPI + Uvicorn.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Create an unprivileged runtime user and a persistent data directory.
RUN groupadd --system app \
    && useradd --system --gid app --create-home app \
    && mkdir -p /data \
    && chown -R app:app /data /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --upgrade pip && pip install .

RUN chown -R app:app /app

USER app

# Default to a persistent SQLite database on the /data volume.
ENV DATABASE_URL=sqlite:////data/selfhealops.db \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
