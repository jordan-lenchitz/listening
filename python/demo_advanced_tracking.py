import numpy as np
import librosa
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from affordance_field import AffordanceField
from multi_f0_tracker import MultiF0Tracker, TrackerConfig, visualize_tracks
from tracking_result import TrackingResult
from just_intonation import JustIntonation

def main():
    audio_path = os.path.join(os.path.dirname(__file__), "..", "mp3", "example_one.mp3")
    if not os.path.exists(audio_path):
        print(f"Error: Could not find {audio_path}")
        return

    print("Analyzing spectral affordances...")
    audio, sr = librosa.load(audio_path, sr=22050)
    af = AffordanceField(sr=sr)
    affordance_results = af.compute(audio, sr)

    print("Running multi-F0 tracker...")
    audio, sr = librosa.load(audio_path, sr=None, mono=True)
    tracker = MultiF0Tracker(TrackerConfig())
    result = tracker.track(audio, sr)
    
    tracker_plot = "/tmp/pitch_trajectories.png"
    visualize_tracks(result, output_path=tracker_plot, show=False)
    print(f"Pitch trajectories saved to {tracker_plot}")

    print("Running just intonation analysis...")
    active_tracks = result["sung_voices"]
    if active_tracks:
        print(f"Detected {len(active_tracks)} active tracks.")
        mid_idx = len(active_tracks[0].pitches) // 2
        current_freqs = []
        for tr in active_tracks:
            if len(tr.pitches) > mid_idx:
                current_freqs.append(tr.pitches[mid_idx])
        
        if current_freqs:
            ji = JustIntonation()
            cents = ji.cents_from_equal_tempered(current_freqs)
            print(f"Frequencies at mid-point: {np.round(current_freqs, 1)} Hz")
            print(f"Deviation from ET (cents): {np.round(cents, 1)}")
            
            combos = ji.combination_tones(current_freqs)
            print(f"Predicted combination tones: {np.round(combos, 1)} Hz")

if __name__ == "__main__":
    # Ensure matplotlib works in headless environment
    import matplotlib
    matplotlib.use('Agg')
    
    # Set up environment variables for /tmp usage
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"
    os.makedirs("/tmp/matplotlib_cache", exist_ok=True)
    
    main()
