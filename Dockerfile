# use python 3.12 slim for a small image size
FROM python:3.12-slim

# install system dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# set the working directory
WORKDIR /app

# copy requirements and install
COPY python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# pre-build matplotlib font cache in the image layer
ENV MPLCONFIGDIR=/root/.cache/matplotlib
RUN python -c "import matplotlib.pyplot as plt; fig, _ = plt.subplots(); plt.close(fig)"

# copy the app code and pre-compile bytecode
COPY python/streamlit_app.py .
COPY python/affordance_field.py .
RUN python -m compileall /app

# expose streamlit port
EXPOSE 8080

# run streamlit
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false", "--server.headless=true", "--server.enableWebsocketCompression=false", "--browser.gatherUsageStats=false", "--server.fileWatcherType=none"]
