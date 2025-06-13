FROM python:3.11-slim

# Install system dependencies for serial communication
RUN apt-get update && apt-get install -y \
    udev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py ./

# Copy Docker-specific config loader
COPY docker-env-config.py ./nfc_config.py

# Create non-root user for security (optional, can run as root for device access)
RUN groupadd -r nfc && useradd -r -g nfc nfc

# Create log directory
RUN mkdir -p /var/log/nfc-reader && chown -R nfc:nfc /var/log/nfc-reader

# Expose any ports if needed (none required for this service)

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "nfc_reader_service.py", "start"]