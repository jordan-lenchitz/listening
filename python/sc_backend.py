import os
import subprocess
import time
import json
import logging
import sys
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from pythonosc import udp_client, dispatcher, osc_server
import threading
import tempfile

# Force flush stdout
class Unbuffered(object):
   def __init__(self, stream):
       self.stream = stream
   def write(self, data):
       self.stream.write(data)
       self.stream.flush()
   def writelines(self, datas):
       self.stream.writelines(datas)
       self.stream.flush()
   def __getattr__(self, attr):
       return getattr(self.stream, attr)

sys.stdout = Unbuffered(sys.stdout)
sys.stderr = Unbuffered(sys.stderr)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

logger.info("Starting Listening SC Backend...")

app = FastAPI(title="Listening SuperCollider Backend")

SC_OSC_PORT = 57120
BACKEND_OSC_PORT = 57121
SC_IP = "127.0.0.1"

# OSC Client to talk to SuperCollider
sc_client = udp_client.SimpleUDPClient(SC_IP, SC_OSC_PORT)

# Store results
results_store = {}

def start_osc_listener():
    logger.info(f"Starting OSC listener on {SC_IP}:{BACKEND_OSC_PORT}")
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
    
    try:
        server = osc_server.ThreadingOSCUDPServer((SC_IP, BACKEND_OSC_PORT), disp)
        logger.info(f"OSC Listener server live.")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Failed to start OSC listener: {e}")

# Start OSC listener in a separate thread
threading.Thread(target=start_osc_listener, daemon=True).start()

def start_sclang():
    logger.info("Initializing sclang...")
    startup_script = "/app/supercollider/backend_init.scd"
    
    if not os.path.exists(startup_script):
        logger.error(f"Startup script not found: {startup_script}")
        return

    try:
        # Debug: Check version
        v = subprocess.run(["sclang", "-v"], capture_output=True, text=True, env=os.environ.copy())
        logger.info(f"sclang version output: {v.stdout} {v.stderr}")
        
        env = os.environ.copy()
        env["QTWEBENGINE_DISABLE_SANDBOX"] = "1"
        env["QT_QPA_PLATFORM"] = "minimal"
        
        # Test compilation
        logger.info("Running sclang compilation test...")
        test = subprocess.run(["sclang", "-a"], capture_output=True, text=True, env=env, timeout=30)
        logger.info(f"Compilation test STDOUT: {test.stdout}")
        logger.info(f"Compilation test STDERR: {test.stderr}")
        
        cmd = ["sclang", startup_script]
        logger.info(f"Spawning sclang: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, # Line buffered
            env=env
        )
        
        def log_output(stream, prefix):
            for line in stream:
                # Use print for immediate flushing to stdout if logger is slow
                print(f"{prefix}: {line.strip()}", flush=True)
                logger.info(f"{prefix}: {line.strip()}")
                
        threading.Thread(target=log_output, args=(process.stdout, "SC-STDOUT"), daemon=True).start()
        threading.Thread(target=log_output, args=(process.stderr, "SC-STDERR"), daemon=True).start()
        logger.info("sclang process spawned.")
    except Exception as e:
        logger.error(f"Failed to spawn sclang: {e}")

@app.on_event("startup")
async def startup_event():
    logger.info("FastAPI startup event triggered.")
    # Ensure SuperCollider config is set up
    conf_dir = os.path.expanduser("~/.config/SuperCollider")
    os.makedirs(conf_dir, exist_ok=True)
    conf_path = os.path.join(conf_dir, "sclang_conf.yaml")
    logger.info(f"Writing SC config to {conf_path}")
    try:
        with open(conf_path, "w") as f:
            f.write(f"""
includePaths:
  - /app/supercollider
excludePaths: []
postInlineWarnings: false
""")
        start_sclang()
    except Exception as e:
        logger.error(f"Error in startup_event: {e}")

@app.get("/")
async def root():
    return {"status": "alive", "backend": "supercollider", "engine": "sclang"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/process")
async def process_audio(background_tasks: BackgroundTasks, audio: UploadFile = File(...)):
    job_id = str(time.time())
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{job_id}_{audio.filename}")
    with open(file_path, "wb") as f:
        f.write(await audio.read())
    
    logger.info(f"Processing job {job_id} for file {file_path}")
    sc_client.send_message("/process", [job_id, file_path])
    return {"job_id": job_id, "status": "processing"}

@app.get("/result/{job_id}")
async def get_result(job_id: str):
    if job_id in results_store:
        return results_store[job_id]
    return JSONResponse(status_code=404, content={"status": "not_found"})

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BACKEND_PORT", 8000))
    logger.info(f"Launching uvicorn on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
