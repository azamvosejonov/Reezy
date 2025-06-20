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

# Use pip-tools to resolve conflicts automatically
RUN pip-compile --resolver=backtracking requirements.txt --output-file requirements-resolved.txt || \
    (echo "Trying alternative resolution method..." && \
     pip install --no-deps -r requirements.txt 2>/dev/null || \
     pip install --force-reinstall --no-deps click==8.0.4 && \
     pip install --force-reinstall --no-deps celery==5.2.7 && \
     pip install --force-reinstall --no-deps gtts==2.5.3 && \
     pip install --force-reinstall --no-deps oci-cli==3.59.0 && \
     pip install -r requirements.txt --force-reinstall)

# Alternative: Install problematic packages separately with specific versions
RUN pip install \
    click==8.0.4 \
    celery==5.2.7 \
    gtts==2.5.3 \
    oci-cli==3.59.0

# Install remaining packages
RUN pip install -r requirements.txt --force-reinstall

# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p /app/uploads /app/media /app/static

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]