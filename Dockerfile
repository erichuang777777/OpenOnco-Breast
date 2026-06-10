# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: build the React PWA
# ─────────────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --prefer-offline

COPY frontend/ ./
RUN npm run build          # outputs to /app/frontend/dist

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Python backend + static files
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS backend

# System deps for pdfplumber / pytesseract (extraction pipeline)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cache layer)
COPY pyproject.toml ./
COPY requirements.txt ./
RUN pip install --no-cache-dir \
        fastapi uvicorn[standard] \
        sqlalchemy[asyncio] aiosqlite asyncpg alembic \
        pydantic pydantic-settings \
        python-jose[cryptography] passlib[bcrypt] \
        httpx \
        slowapi \
        pywebpush \
        pyyaml \
        anthropic \
    && pip install --no-cache-dir -e "."

# Copy source
COPY hospital/ ./hospital/
COPY knowledge_base/ ./knowledge_base/
COPY alembic.ini ./

# Copy built frontend into a location the app can serve
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Non-root user for runtime
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app
USER appuser

# Alembic migrations run at startup via entrypoint
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 8000
CMD ["uvicorn", "hospital.main:app", "--host", "0.0.0.0", "--port", "8000"]
