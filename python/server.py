from fastapi import FastAPI, UploadFile, File
import tempfile
import os
import uvicorn
import shutil
from dual_process_tracker import DualProcessPitchTracker

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
        # Run the tracking with default (just better) parameters
        tracker = DualProcessPitchTracker(
            audio_file=tmp_path,
            use_synsq=True
        )
        tracker.run()
        
        # Format trajectories into a super clean JSON
        trajectories = []
        for track in getattr(tracker, "tracks", []):
            trajectories.append({
                "times": [float(t) for t in track.get("time", [])],
                "frequencies": [float(f) if not __import__('math').isnan(f) else None for f in track.get("f0", [])]
            })
        return {
            "status": "success",
            "time_axis": tracker.time_axis.tolist(),
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
