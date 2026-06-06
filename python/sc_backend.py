import os
import subprocess
import time
import json
import logging
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from python_osc import udp_client, dispatcher, osc_server
import threading
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Listening SuperCollider Backend")

SC_OSC_PORT = 57120
BACKEND_OSC_PORT = 57121
SC_IP = "127.0.0.1"

# OSC Client to talk to SuperCollider
sc_client = udp_client.SimpleUDPClient(SC_IP, SC_OSC_PORT)

# Store results
results_store = {}

def start_osc_listener():
    disp = dispatcher.Dispatcher()
    
    def result_handler(address, *args):
        logger.info(f"Received result from SC: {args}")
        try:
            job_id = args[0]
            data = json.loads(args[1])
            results_store[job_id] = data
        except Exception as e:
            logger.error(f"Error parsing SC result: {e}")

    disp.map("/result", result_handler)
    
    server = osc_server.ThreadingOSCUDPServer((SC_IP, BACKEND_OSC_PORT), disp)
    logger.info(f"OSC Listener started on port {BACKEND_OSC_PORT}")
    server.serve_forever()

# Start OSC listener in a separate thread
threading.Thread(target=start_osc_listener, daemon=True).start()

def start_sclang():
    logger.info("Starting sclang...")
    # Create a startup script for SC
    startup_script = "/app/supercollider/backend_init.scd"
    
    # Run sclang
    process = subprocess.Popen(
        ["sclang", startup_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Log SC output in background
    def log_output(stream, prefix):
        for line in stream:
            logger.info(f"{prefix}: {line.strip()}")
            
    threading.Thread(target=log_output, args=(process.stdout, "SC-STDOUT"), daemon=True).start()
    threading.Thread(target=log_output, args=(process.stderr, "SC-STDERR"), daemon=True).start()

@app.on_event("startup")
async def startup_event():
    # Ensure SuperCollider config is set up (classes included)
    os.makedirs("/root/.config/SuperCollider", exist_ok=True)
    with open("/root/.config/SuperCollider/sclang_conf.yaml", "w") as f:
        f.write(f"""
includePaths:
  - /app/supercollider
  - /app/supercollider/Utils
  - /app/supercollider/Library
  - /app/supercollider/Simulation
  - /app/supercollider/Wrappers
excludePaths: []
postInlineWarnings: false
""")
    start_sclang()

@app.get("/")
async def root():
    return {"status": "alive", "backend": "supercollider", "engine": "sclang"}

@app.post("/process")
async def process_audio(background_tasks: BackgroundTasks, audio: UploadFile = File(...)):
    job_id = str(time.time())
    
    # Save audio to a temporary file
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{job_id}_{audio.filename}")
    with open(file_path, "wb") as f:
        f.write(await audio.read())
    
    logger.info(f"Processing job {job_id} for file {file_path}")
    
    # Tell SC to process the file
    # We'll send the job_id and the file path
    sc_client.send_message("/process", [job_id, file_path])
    
    return {"job_id": job_id, "status": "processing"}

@app.get("/result/{job_id}")
async def get_result(job_id: str):
    if job_id in results_store:
        return results_store[job_id]
    return JSONResponse(status_code=404, content={"status": "not_found", "message": "Result not ready yet or job id invalid"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
