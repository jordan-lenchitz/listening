import numpy as np
from scipy.io import wavfile
import csv
import os

def generate_synthetic_data(filename="synthetic_poly", duration=10.0, fs=44100, n_voices=4):
    """
    Generates a polyphonic synthetic audio file with vibrato and frequency slides.
    Exports both .wav and .csv ground truth.
    """
    t = np.linspace(0, duration, int(fs * duration))
    audio = np.zeros_like(t)
    ground_truth = []

    # Pre-defined voice trajectories to ensure interesting interactions (e.g., crossing)
    # Each entry: (freq_func, amplitude_func)
    trajectories = [
        # Voice 1: Steady A3 with vibrato
        (lambda t: 220 + 5.0 * np.sin(2 * np.pi * 5.0 * t), 
         lambda t: 0.25 * np.ones_like(t)),
        
        # Voice 2: E4 sliding down to C4
        (lambda t: 330 - 70.0 * (t / duration) + 8.0 * np.sin(2 * np.pi * 6.2 * t),
         lambda t: 0.2 * np.ones_like(t)),
        
        # Voice 3: A4 sliding up to C5, crossing Voice 2 slide
        (lambda t: 440 + 80.0 * (t / duration) + 12.0 * np.sin(2 * np.pi * 4.5 * t),
         lambda t: 0.15 * np.ones_like(t)),
        
        # Voice 4: G3 with intermittent presence
        (lambda t: 196 + 3.0 * np.sin(2 * np.pi * 5.5 * t),
         lambda t: 0.2 * (np.sin(2 * np.pi * 0.5 * t) > 0).astype(float))
    ]

    for i in range(min(n_voices, len(trajectories))):
        f_func, a_func = trajectories[i]
        freqs = f_func(t)
        amps = a_func(t)
        
        # Phase integration for continuous frequency
        phase = 2 * np.pi * np.cumsum(freqs) / fs
        voice_audio = np.sin(phase) * amps
        
        # Simple fade in/out to avoid clicks
        fade_len = int(0.1 * fs)
        envelope = np.ones_like(t)
        envelope[:fade_len] = np.linspace(0, 1, fade_len)
        envelope[-fade_len:] = np.linspace(1, 0, fade_len)
        
        audio += voice_audio * envelope
        ground_truth.append(freqs * (amps > 0))

    # Add Gaussian noise
    audio += np.random.normal(0, 0.005, len(t))
    
    # Peak normalize
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio /= max_val
    
    # Save files
    wav_path = f"{filename}.wav"
    csv_path = f"{filename}_gt.csv"
    
    wavfile.write(wav_path, fs, (audio * 32767).astype(np.int16))
    
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time"] + [f"voice_{i+1}" for i in range(len(ground_truth))])
        # Sample ground truth every 10ms
        step = int(fs * 0.01)
        for idx in range(0, len(t), step):
            row = [t[idx]] + [ground_truth[v][idx] for v in range(len(ground_truth))]
            writer.writerow(row)
            
    print(f"Generated {wav_path} and {csv_path}")

if __name__ == "__main__":
    generate_synthetic_data()
