FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY semantix/ ./semantix/

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e .

# Create directories
RUN mkdir -p /data/input /app/artifacts

# Expose port
EXPOSE 8080

# Default command (can be overridden)
CMD ["python", "-m", "semantix.main"]

