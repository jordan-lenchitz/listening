#!/bin/bash
echo "ENTRYPOINT: Starting Xvfb..."
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99

echo "ENTRYPOINT: Starting services..."
# Start the FastAPI backend in the background
python3 python/sc_backend.py &

# Start the Streamlit frontend on the port assigned by Cloud Run (defaulting to 8080)
PORT=${PORT:-8080}
echo "ENTRYPOINT: Launching Streamlit on port $PORT"
streamlit run python/streamlit_app.py --server.port=$PORT --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false --server.headless=true
