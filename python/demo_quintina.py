import numpy as np
import soundfile as sf
import os
import sys
from scipy.signal import savgol_filter

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from multi_f0_tracker import MultiF0Tracker, TrackerConfig
from affordance_field import AffordanceField
from tracking_result import TrackingResult
from just_intonation import JustIntonation

def synthesize_tenores_voice(t, f0, entry_time, exit_time, sr):
    """Generate synthetic tenores voice with rich harmonics."""
    # Slow vibrato, shallow
    vibrato_rate = 4.0
    vibrato_depth = 0.005
    vibrato = vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)

    # Rich harmonic content
    weights = [1.0, 0.85, 0.7, 0.6, 0.55, 0.5, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15]
    signal = np.zeros_like(t)
    for h_idx, weight in enumerate(weights):
        h = h_idx + 1
        fh = h * f0
        if fh > sr / 2:
            break
        signal += weight * np.sin(2 * np.pi * fh * t + h * vibrato)

    # Amplitude envelope
    envelope = np.zeros_like(t)
    fade_len = int(0.08 * sr)
    entry_idx = int(entry_time * sr)
    exit_idx = int(exit_time * sr)

    if entry_idx + fade_len < len(t):
        envelope[entry_idx:entry_idx+fade_len] = np.linspace(0, 1, fade_len)
    
    if entry_idx + fade_len < exit_idx - fade_len:
        envelope[entry_idx+fade_len:exit_idx-fade_len] = 1.0
        
    if exit_idx - fade_len < len(t) and exit_idx - fade_len > 0:
        envelope[exit_idx-fade_len:exit_idx] = np.linspace(1, 0, fade_len)

    envelope = savgol_filter(envelope, 101, 3)
    envelope = np.clip(envelope, 0, 1)
    
    return signal * envelope

def main():
    sr = 22050
    duration = 10.0
    root = 98.0
    ratios = np.array([[1, 1], [3, 2], [2, 1], [5, 2]])
    voice_names = ["bassu", "contra", "bogi", "falzittu"]
    entry_times = [0.5, 1.5, 2.5, 3.5]
    exit_time = 9.0

    ji = JustIntonation()
    freqs = ji.chord(root, ratios)
    print("🎵 Synthesizing Sardinian tenores chord (Python)...")
    for i, f in enumerate(freqs):
        print(f"  {voice_names[i]:<10} {f:6.2f} Hz  enters {entry_times[i]:.1f}s")

    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t)
    for i in range(len(freqs)):
        audio += synthesize_tenores_voice(t, freqs[i], entry_times[i], exit_time, sr)
    
    audio = audio / np.max(np.abs(audio)) * 0.9
    sf.write("demo_quintina_py.wav", audio, sr)
    print("\n✓ Audio saved: demo_quintina_py.wav")

    print("\n🔍 Running Competition-Model Tracker...")
    config = TrackerConfig(
        max_voices=4,
        min_freq=80,
        max_freq=1600,
        peak_threshold=0.12,
        detect_extra_pitches=True
    )
    tracker = MultiF0Tracker(config=config)
    raw_result = tracker.track(audio, sr)

    # Filter and visualize
    result = TrackingResult(
        times=raw_result["times"],
        voices=raw_result["sung_voices"],
        ghosts=raw_result["extra_pitches"],
        sr=raw_result["sample_rate"],
        hop=raw_result["hop_length"]
    )
    
    result.visualize(title="Tenores Chord · Competition-Model Tracker", output_path="quintina_tracks_py.png")
    result.summary()

    print("\n🔍 Running Affordance Field...")
    af = AffordanceField(sample_rate=sr)
    A = af.compute(audio)
    af.visualize(A, output_path="quintina_affordance_py.png")

    print("\nField Energy by Region (Mean Affordance):")
    regions = [
        ("bassu (fundamental)", [95, 105]),
        ("bogi (fundamental)", [190, 205]),
        ("quintina region", [950, 1500]),
        ("above quintina", [1500, 2200])
    ]
    
    for name, (low, high) in regions:
        mask = (A["frequencies"] >= low) & (A["frequencies"] <= high)
        val = np.mean(A["field"][mask, :])
        print(f"  {name:<30} {low:6.1f} - {high:6.1f} Hz   {val:.4f}")

    print("\n✅ Done!")

if __name__ == "__main__":
    import matplotlib
    matplotlib.use('Agg')
    main()
