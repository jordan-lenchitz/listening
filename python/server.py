from fastapi import FastAPI, UploadFile, File
import tempfile
import os
import uvicorn
import shutil
import concurrent.futures
import librosa
import numpy as np
import math
from multi_f0_tracker import MultiF0Tracker, TrackerConfig

def process_chunk(file_path: str, offset: float, duration: float):
    audio, sr = librosa.load(file_path, sr=None, mono=True, offset=offset, duration=duration)
    config = TrackerConfig()
    tracker = MultiF0Tracker(config)
    result = tracker.track(audio, sr)
    
    chunk_time_axis = [t + offset for t in result["times"]]
    
    tracks_out = []
    for voice in result["sung_voices"] + result["extra_pitches"]:
        track_times = [chunk_time_axis[f] for f in voice.frames]
        tracks_out.append({"time": track_times, "f0": voice.pitches})
        
    return tracks_out, chunk_time_axis

app = FastAPI(title="Affordance Tracker API", version="1.0.0")

@app.post("/api/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """
    Super easy to use endpoint.
    Upload an audio file (mp3, wav) and get back the tracked affordances.
    No parameters required. The phenomenology is abstracted away.
    """
    # Create a temporary file to save the uploaded audio
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        chunk_duration = 10.0
        total_duration = librosa.get_duration(path=tmp_path)
        chunks = [(tmp_path, i, min(chunk_duration, total_duration - i)) for i in np.arange(0, total_duration, chunk_duration)]
        
        all_tracks = []
        full_time_axis = []
        
        with concurrent.futures.ProcessPoolExecutor() as executor:
            results = list(executor.map(process_chunk, *zip(*chunks)))
            
        for chunk_tracks, chunk_time_axis in results:
            all_tracks.extend(chunk_tracks)
            full_time_axis.extend(chunk_time_axis)
        
        # Format trajectories into a super clean JSON
        trajectories = []
        for track in all_tracks:
            trajectories.append({
                "times": [float(t) for t in track.get("time", [])],
                "frequencies": [float(f) if not math.isnan(f) else None for f in track.get("f0", [])]
            })
            
        return {
            "status": "success",
            "time_axis": full_time_axis,
            "trajectories": trajectories
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    # Super easy to run
    uvicorn.run(app, host="0.0.0.0", port=8000)
