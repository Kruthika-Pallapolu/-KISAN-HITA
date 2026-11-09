# ==============================================================================
# Kisan Hita (కిసాన్ హిత) — Production Containerfile
# Multilingual, voice-first AI agricultural assistant for Indian farmers
# ==============================================================================

FROM python:3.11-slim as runtime

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    DATABASE_PATH=/data/kisan_hita.db

# Install essential runtime tools (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root system user and group
RUN groupadd -r kisan && useradd -r -g kisan -u 1000 -d /app -s /sbin/nologin kisan

# Set working directory and create data mount directory for SQLite persistence
WORKDIR /app
RUN mkdir -p /data && chown -R kisan:kisan /app /data

# Install Python dependencies first (leverages Docker cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend ./backend

# Fix ownership
RUN chown -R kisan:kisan /app /data

# Switch to non-root user
USER kisan

# Expose server port
EXPOSE 8000

# Container healthcheck using the readiness endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/api/ready || exit 1

# Launch production server with Uvicorn
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}"]

