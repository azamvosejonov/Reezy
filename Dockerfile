# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    python3-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pip-tools for better dependency resolution
RUN pip install --upgrade pip pip-tools

# Copy requirements first for better caching
COPY requirements.txt .

# Fix the billiard version conflict before installation
RUN sed -i 's/billiard==4.2.1/billiard>=3.6.4.0,<4.0/' requirements.txt

# Try pip-compile first, fallback to direct installation
RUN pip-compile --resolver=backtracking requirements.txt --output-file requirements-resolved.txt && \
    pip install -r requirements-resolved.txt || \
    (echo "Pip-compile failed, installing directly from requirements.txt..." && \
     pip install -r requirements.txt)

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p /app/uploads /app/media /app/static

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]