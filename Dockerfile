# Use official Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# Set working directory
WORKDIR /app

# Install system dependencies needed for Postgres and python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python packaging and dependency management
RUN pip install --no-cache-dir uv

# Copy configuration files
COPY pyproject.toml uv.lock ./

# Install project dependencies globally in the container using the lockfile
RUN uv sync --frozen --system --no-install-project

# Copy the application source code and relevant files
COPY src/ ./src
COPY data/ ./data
COPY main.py app.py ingestion.py start.sh ./

# Install the project itself (editable) without re-resolving dependencies
RUN uv pip install --system -e . --no-deps

# Make startup script executable
RUN chmod +x start.sh

# Expose FastAPI backend and Streamlit frontend ports
EXPOSE 8005
EXPOSE 8501

# Default command launches the app using start.sh (which manages both backend and frontend)
CMD ["./start.sh"]
