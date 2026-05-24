import numpy as np
import librosa
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from affordance_field import AffordanceField
from dual_process_tracker import DualProcessPitchTracker
from tracking_result import TrackingResult
from just_intonation import JustIntonation

def main():
    print("="*60)
    print("   ADVANCED MULTI-F0 TRACKING & AFFORDANCE ANALYSIS")
    print("="*60)

    # Use example file
    audio_path = "/tmp/listening/mp3/example_one.mp3"
    if not os.path.exists(audio_path):
        print(f"Error: Could not find {audio_path}")
        return

    print(f"\nStep 1: Analyzing Spectral Affordances...")
    audio, sr = librosa.load(audio_path, sr=22050)
    af = AffordanceField(sample_rate=sr)
    affordance_results = af.compute(audio)
    
    affordance_plot = "/tmp/affordance_analysis.png"
    af.visualize(affordance_results, output_path=affordance_plot)
    print(f"   Affordance field visualized and saved to {affordance_plot}")

    print(f"\nStep 2: Running Dual-Process Pitch Tracker...")
    # This might take a moment due to Synchrosqueezing
    tracker = DualProcessPitchTracker(audio_path, use_synsq=True)
    tracker.run()
    
    tracker_plot = "/tmp/pitch_trajectories.png"
    tracker.plot_tracks(output_path=tracker_plot)
    print(f"   Pitch trajectories visualized and saved to {tracker_plot}")

    print(f"\nStep 3: Just Intonation Analysis...")
    # Example: Analyze first frame of top 3 tracks if they exist
    active_tracks = [t for t in tracker.tracks if not np.isnan(t["f0"]).all()]
    if active_tracks:
        print(f"   Detected {len(active_tracks)} active tracks.")
        # Pick a point in time where most voices are active
        # For simplicity, just look at the middle of the first track
        mid_idx = len(active_tracks[0]["f0"]) // 2
        current_freqs = []
        for tr in active_tracks:
            f = tr["f0"][mid_idx]
            if not np.isnan(f):
                current_freqs.append(f)
        
        if current_freqs:
            ji = JustIntonation()
            cents = ji.cents_from_equal_tempered(current_freqs)
            print(f"   Frequencies at mid-point: {np.round(current_freqs, 1)} Hz")
            print(f"   Deviation from ET (cents): {np.round(cents, 1)}")
            
            combos = ji.combination_tones(current_freqs)
            print(f"   Predicted combination tones: {np.round(combos, 1)} Hz")

    print("\n" + "="*60)
    print("   ANALYSIS COMPLETE")
    print("="*60)

if __name__ == "__main__":
    # Ensure matplotlib works in headless environment
    import matplotlib
    matplotlib.use('Agg')
    
    # Set up environment variables for /tmp usage
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"
    os.makedirs("/tmp/matplotlib_cache", exist_ok=True)
    
    main()
