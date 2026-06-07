# Use a Python base image with Debian Bookworm
FROM python:3.12-slim-bookworm

# Install SuperCollider and system dependencies
RUN apt-get update && apt-get install -y \
    supercollider-language \
    supercollider-server \
    supercollider-common \
    libsndfile1 \
    xvfb \
    libqt5widgets5 \
    libqt5gui5 \
    libqt5core5a \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Environment setup
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV HOME=/root
ENV BACKEND_PORT=8000
ENV QT_QPA_PLATFORM=offscreen

# Copy requirements and install Python dependencies
COPY python/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn python-multipart python-osc streamlit requests

# Copy the entire project
COPY . .

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Expose the Cloud Run port
EXPOSE 8080

# Start command
CMD ["./entrypoint.sh"]
