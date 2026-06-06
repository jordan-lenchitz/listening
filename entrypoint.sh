#!/bin/bash
# Start the FastAPI backend in the background
python3 python/sc_backend.py &

# Start the Streamlit frontend on the port assigned by Cloud Run (defaulting to 8080)
PORT=${PORT:-8080}
streamlit run python/streamlit_app.py --server.port=$PORT --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false --server.headless=true
