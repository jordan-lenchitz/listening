import numpy as np
import soundfile as sf
import os
import sys
from scipy.signal import savgol_filter

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from multi_f0_tracker import MultiF0Tracker

def synthesize_voice(t, f0, entry_time, exit_time, sr):
    """Generate synthetic voice with vibrato and harmonics."""
    # Vibrato
    vibrato_rate = 5.0      # Hz
    vibrato_depth = 0.015   # 1.5%
    vibrato = vibrato_depth * np.sin(2 * np.pi * vibrato_rate * t)

    # Additive synthesis with formant-like weighting
    weights = [1.0, 0.7, 0.4, 0.3, 0.2, 0.15]
    signal = np.zeros_like(t)
    for h_idx, weight in enumerate(weights):
        h = h_idx + 1
        signal += weight * np.sin(2 * np.pi * h * f0 * t + h * vibrato)

    # Amplitude envelope with smooth attack/release
    envelope = np.zeros_like(t)
    fade_len = int(0.05 * sr)
    entry_idx = int(entry_time * sr)
    exit_idx = int(exit_time * sr)

    # Apply fades
    if entry_idx + fade_len < len(t):
        envelope[entry_idx:entry_idx+fade_len] = np.linspace(0, 1, fade_len)
    
    if entry_idx + fade_len < exit_idx - fade_len:
        envelope[entry_idx+fade_len:exit_idx-fade_len] = 1.0
        
    if exit_idx - fade_len < len(t) and exit_idx - fade_len > 0:
        envelope[exit_idx-fade_len:exit_idx] = np.linspace(1, 0, fade_len)

    # Smooth the envelope
    # Using savgol_filter as a replacement for smoothdata(..., "gaussian")
    envelope = savgol_filter(envelope, 101, 3)
    envelope = np.clip(envelope, 0, 1)
    
    return signal * envelope

def main():
    sr = 22050
    duration = 9.5
    
    # Voice parameters: [frequency, entry_time, exit_time]
    voices = {
        "Bass":     [110.0,  0.5, 9.0],
        "Baritone": [137.5,  1.5, 8.0],
        "Lead":     [165.0,  2.5, 7.0],
        "Tenor":    [192.5,  3.5, 6.0]
    }

    print("🎵 Generating synthetic barbershop quartet (Python)...")
    
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    audio = np.zeros_like(t)

    for name, params in voices.items():
        f0, entry, exit = params
        audio += synthesize_voice(t, f0, entry, exit, sr)
        print(f"  {name}: {f0:.1f} Hz ({entry:.1f}s → {exit:.1f}s)")

    # Normalize
    audio = audio / np.max(np.abs(audio)) * 0.9

    output_wav = "demo_barbershop_py.wav"
    sf.write(output_wav, audio, sr)
    print(f"\n✓ Audio saved: {output_wav}")

    print("\n🔍 Running Multi-F0 Tracker...")
    from multi_f0_tracker import TrackerConfig
    config = TrackerConfig(
        max_voices=4,
        min_freq=80,
        max_freq=600,
        peak_threshold=0.15,
        detect_extra_pitches=False
    )
    tracker = MultiF0Tracker(config=config)

    # track returns a dictionary
    raw_result = tracker.track(audio, sr)

    print("\n📊 Creating visualization...")
    from tracking_result import TrackingResult
    result = TrackingResult(
        times=raw_result["times"],
        voices=raw_result["sung_voices"],
        ghosts=raw_result["extra_pitches"],
        sr=raw_result["sample_rate"],
        hop=raw_result["hop_length"]
    )
    
    output_png = "tracking_result_py.png"
    result.visualize(title="Barbershop Quartet: A Dominant 7th (Just Intonation)", output_path=output_png)
    
    print(f"✓ Visualization saved: {output_png}")
    print("\n✅ Done!")

if __name__ == "__main__":
    # Ensure matplotlib works in headless environment
    import matplotlib
    matplotlib.use('Agg')
    main()
