# Use official Python image
FROM python:3.10-slim

# Install system dependencies required by Playwright
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        wget \
        gnupg \
        ca-certificates \
        libnss3 \
        libatk1.0-0 \
        libatk-bridge2.0-0 \
        libcups2 \
        libxkbcommon0 \
        libxcomposite1 \
        libxdamage1 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (must be done during build)
RUN playwright install --with-deps chromium

# Copy application code
COPY app ./app
COPY start_server.py .
COPY README.md .

# Create necessary directories
RUN mkdir -p storage uploads

# Expose port for FastAPI
EXPOSE 8000

# Start the server
CMD ["python", "start_server.py"]

 