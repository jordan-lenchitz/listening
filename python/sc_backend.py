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

def split_audio(file_path, chunk_duration=10):
    temp_dir = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    safe_base_name = "".join([c if c.isalnum() or c in ".-_" else "_" for c in base_name])
    output_pattern = os.path.join(temp_dir, f"chunk_%03d_{safe_base_name}")
    
    logger.info(f"Splitting {file_path} into {chunk_duration}s segments...")
    cmd = [
        "ffmpeg", "-i", file_path,
        "-f", "segment",
        "-segment_time", str(chunk_duration),
        "-c", "copy",
        output_pattern
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg failed: {e.stderr.decode()}")
        raise

    # List the generated chunks
    chunks = sorted([
        os.path.join(temp_dir, f) 
        for f in os.listdir(temp_dir) 
        if f.startswith("chunk_") and safe_base_name in f
    ])
    return chunks

def start_osc_listener():
    logger.info(f"Starting OSC listener on {SC_IP}:{BACKEND_OSC_PORT}")
    disp = dispatcher.Dispatcher()
    
    def result_handler(address, *args):
        logger.info(f"Received result from SC: {args}")
        try:
            sub_job_id = args[0]
            data = json.loads(args[1])
            
            if "_" in sub_job_id:
                parts = sub_job_id.rsplit("_", 1)
                if len(parts) == 2:
                    job_id, chunk_idx = parts
                    if job_id in results_store:
                        results_store[job_id]["chunks"][int(chunk_idx)] = data
                        num_done = len(results_store[job_id]["chunks"])
                        total = results_store[job_id]["total_chunks"]
                        logger.info(f"Job {job_id}: {num_done}/{total} chunks complete")
                        if num_done == total:
                            results_store[job_id]["status"] = "complete"
                        return

            results_store[sub_job_id] = data
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
    # Use path relative to the script
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    startup_script = os.path.join(base_dir, "supercollider", "backend_init.scd")
    
    if not os.path.exists(startup_script):
        logger.error(f"Startup script not found: {startup_script}")
        # Fallback to local path if running from root
        startup_script = "supercollider/backend_init.scd"
        if not os.path.exists(startup_script):
            logger.error(f"Fallback startup script not found: {startup_script}")
            return

    try:
        # Debug: Check version
        v = subprocess.run(["sclang", "-v"], capture_output=True, text=True, env=os.environ.copy())
        logger.info(f"sclang version output: {v.stdout} {v.stderr}")
        
        cmd = ["sclang", startup_script]
        logger.info(f"Spawning sclang: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, # Line buffered
            env=os.environ.copy()
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
    
    # Get absolute path to supercollider dir
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sc_dir = os.path.join(base_dir, "supercollider")
    
    logger.info(f"Writing SC config to {conf_path}")
    try:
        with open(conf_path, "w") as f:
            f.write(f"""
includePaths:
  - {sc_dir}
excludePaths:
  - {sc_dir}/Utils
  - {sc_dir}/Library
  - {sc_dir}/Simulation
  - {sc_dir}/Wrappers
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
    # Use a more unique job_id to avoid collisions
    job_id = f"{int(time.time())}_{os.urandom(4).hex()}"
    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, f"{job_id}_{audio.filename}")
    with open(file_path, "wb") as f:
        f.write(await audio.read())
    
    logger.info(f"Processing job {job_id} for file {file_path}")
    
    try:
        chunks = split_audio(file_path)
        logger.info(f"Split into {len(chunks)} chunks")
        
        results_store[job_id] = {
            "status": "processing",
            "total_chunks": len(chunks),
            "chunks": {},
            "start_time": time.time()
        }
        
        for i, chunk_path in enumerate(chunks):
            sub_job_id = f"{job_id}_{i}"
            logger.info(f"Sending chunk {i} to SC: {chunk_path}")
            sc_client.send_message("/process", [sub_job_id, chunk_path])
            
        return {"job_id": job_id, "status": "processing", "num_chunks": len(chunks)}
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

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
