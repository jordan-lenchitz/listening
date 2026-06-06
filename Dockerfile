# Use a Python base image with Debian Bookworm
FROM python:3.12-slim-bookworm

# Install SuperCollider and system dependencies
RUN apt-get update && apt-get install -y \
    supercollider-language \
    supercollider-server \
    supercollider-common \
    libsndfile1 \
    xvfb \
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

# Environment setup for headless SuperCollider
ENV DISPLAY=:99
ENV HOME=/root

# Expose the Cloud Run port
EXPOSE 8080

# Start command: use xvfb-run to provide a virtual display for SuperCollider if needed
# though sclang is mostly CLI, scsynth sometimes benefits from it.
CMD ["xvfb-run", "-a", "python3", "python/sc_backend.py"]
