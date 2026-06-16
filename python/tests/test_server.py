import os
import tempfile
import numpy as np
import scipy.io.wavfile as wavfile
from fastapi.testclient import TestClient

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import app

client = TestClient(app)

def test_analyze_audio():
    # Generate a tiny dummy WAV file
    sample_rate = 16000
    duration = 2.0  # seconds
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # A 440 Hz sine wave
    audio_data = 0.5 * np.sin(2 * np.pi * 440 * t)
    audio_data = (audio_data * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        wavfile.write(tmp_wav.name, sample_rate, audio_data)
        tmp_wav_path = tmp_wav.name

    try:
        # Open the generated file and POST it to the endpoint
        with open(tmp_wav_path, "rb") as f:
            response = client.post(
                "/api/analyze",
                files={"file": ("test.wav", f, "audio/wav")}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success", f"Error returned: {data.get('message', 'Unknown')}"
        assert "time_axis" in data
        assert "trajectories" in data
    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_wav_path):
            os.remove(tmp_wav_path)
