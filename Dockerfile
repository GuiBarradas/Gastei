FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/usr/local

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

WORKDIR /app

# Cacheable dependency layer
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

# Application code + migrations + seeds + UI (theme included)
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY seeds ./seeds
COPY streamlit_app ./streamlit_app
COPY .streamlit ./.streamlit
COPY scripts ./scripts

# Volume so the SQLite DB survives restarts
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 8000

# Apply migrations, then start the API
CMD sh -c "uv run alembic upgrade head && uv run uvicorn gastei.api.main:app --host 0.0.0.0 --port 8000"

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
