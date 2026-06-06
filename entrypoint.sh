#!/bin/bash
export QT_QPA_PLATFORM=offscreen
export DISPLAY=:99
export PYTHONUNBUFFERED=1

echo "ENTRYPOINT: Starting Xvfb..."
Xvfb :99 -screen 0 1024x768x24 &
sleep 2

echo "ENTRYPOINT: Starting Backend..."
python3 python/sc_backend.py &
sleep 2

echo "ENTRYPOINT: Starting Streamlit..."
PORT=${PORT:-8080}
streamlit run python/streamlit_app.py --server.port=$PORT --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false --server.headless=true
