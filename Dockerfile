# use python 3.12 slim for a small image size
from python:3.12-slim

# install system dependencies for audio processing
run apt-get update && apt-get install -y \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# set the working directory
workdir /app

# copy requirements and install
copy python/requirements.txt .
run pip install --no-cache-dir -r requirements.txt
run pip install --no-cache-dir streamlit

# copy the app code
copy python/streamlit_app.py .
copy python/affordance_field.py .

# expose streamlit port
expose 8080

# run streamlit
cmd ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false", "--server.headless=true", "--server.enableWebsocketCompression=false", "--browser.gatherUsageStats=false"]
