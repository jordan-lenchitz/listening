# Use a Python base image with Debian Bookworm
FROM python:3.12-slim-bookworm

# Install SuperCollider and system dependencies
RUN apt-get update && apt-get install -y \
    supercollider-language \
    supercollider-server \
    supercollider-common \
    libsndfile1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn python-multipart python-osc

# Copy the entire project
COPY . .

# Environment setup
ENV PYTHONUNBUFFERED=1
ENV HOME=/root

# Expose the Cloud Run port
EXPOSE 8080

# Start command
CMD ["python3", "python/sc_backend.py"]
