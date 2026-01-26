# =============================================================================
# Stage 1: Build Flutter web app
# =============================================================================
FROM debian:bookworm-slim AS flutter-builder

# Install dependencies for Flutter
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    unzip \
    xz-utils \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Flutter via git (more reliable than tarball download)
RUN git clone --depth 1 --branch stable https://github.com/flutter/flutter.git /opt/flutter

ENV PATH="/opt/flutter/bin:$PATH"

# Pre-download Flutter dependencies and accept licenses
RUN flutter precache --web \
    && flutter doctor

WORKDIR /app

# Copy frontend source
COPY frontend/ frontend/

# Build Flutter web
WORKDIR /app/frontend
RUN flutter pub get
RUN flutter build web --release


# =============================================================================
# Stage 2: Build Python backend and seed database
# =============================================================================
FROM python:3.11-slim AS python-builder

# Install uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy dependency files
COPY backend/pyproject.toml backend/uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and scripts
COPY backend/src/ src/
COPY backend/scripts/ scripts/

# Install the project
RUN uv sync --frozen --no-dev

# Soccer data (soccer_players.json) is pre-generated with logos and committed to repo
# To regenerate: uv run python scripts/transform_soccer_data.py --with-logos

# Seed the database (creates src/sports_trivia/data/sports_trivia.db)
ENV PYTHONPATH="/app/src"
RUN uv run python scripts/seed_database.py --reset


# =============================================================================
# Stage 3: Production image
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Copy Python virtual environment from builder
COPY --from=python-builder /app/.venv /app/.venv

# Copy backend source code
COPY --from=python-builder /app/src /app/src

# Copy Flutter web build to static directory
COPY --from=flutter-builder /app/frontend/build/web /app/src/static

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1
ENV DATA_SOURCE=db

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["uvicorn", "sports_trivia.main:app", "--host", "0.0.0.0", "--port", "8000"]
