import numpy as np
import matplotlib.pyplot as plt
from typing import List, Dict, Any, Optional

class TrackingResult:
    """
    Container for Multi-F0 tracking results with visualization.
    Ported from MATLAB implementation.
    """
    def __init__(self, times: np.ndarray, voices: List[Dict[str, Any]], ghosts: List[Dict[str, Any]], sr: int, hop: int):
        self.times = times
        self.sung_voices = voices
        self.extra_pitches = ghosts
        self.sample_rate = sr
        self.hop_length = hop

    @property
    def num_voices(self) -> int:
        return len(self.sung_voices)

    @property
    def num_ghosts(self) -> int:
        return len(self.extra_pitches)

    @property
    def duration(self) -> float:
        return self.times[-1] if len(self.times) > 0 else 0.0

    def visualize(self, output_path: Optional[str] = None, show_ghosts: bool = True, ylim: Optional[List[float]] = None, title: str = "Multi-F0 Voice Tracking"):
        import os
        if "MPLCONFIGDIR" not in os.environ:
            os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"

        plt.figure(figsize=(14, 8), facecolor="white")
        
        colors = [
            (0.180, 0.525, 0.671), # Blue
            (0.635, 0.231, 0.447), # Purple
            (0.945, 0.561, 0.004), # Orange
            (0.780, 0.243, 0.114), # Red
            (0.153, 0.682, 0.376), # Green
            (0.580, 0.404, 0.741)  # Violet
        ]

        # Plot sung voices
        for i, voice in enumerate(self.sung_voices):
            color = colors[i % len(colors)]
            # In Python port, we assume voice is a dict with "frames" and "f0" or "pitches"
            # To match multi_f0_tracker.py: VoiceTrack object
            # To match dual_process_tracker.py: dict with "time", "f0", "prob"
            
            if isinstance(voice, dict):
                tt = voice.get("time", [])
                pp = voice.get("f0", [])
            else: # VoiceTrack object
                tt = self.times[voice.frames]
                pp = voice.pitches

            plt.plot(tt, pp, "-", color=color, linewidth=2.5, label=f"Voice {i+1}")
            
            if len(tt) > 0:
                # Entry marker
                plt.plot(tt[0], pp[0], "o", color=color, markersize=10, markerfacecolor="white", markeredgewidth=2)
                # Exit marker
                plt.plot(tt[-1], pp[-1], "x", color=color, markersize=10, markeredgewidth=2)

        # Plot ghost pitches
        if show_ghosts and self.num_ghosts > 0:
            for i, ghost in enumerate(self.extra_pitches):
                if isinstance(ghost, dict):
                    tt = ghost.get("time", [])
                    pp = ghost.get("f0", [])
                else: # VoiceTrack object
                    tt = self.times[ghost.frames]
                    pp = ghost.pitches
                
                plt.plot(tt, pp, "--", color=(0.5, 0, 0.5), linewidth=2, alpha=0.7)
                if i == 0:
                    # Add a proxy for legend if needed, but normally we just label one
                    pass

        plt.xlabel("Time (seconds)", fontsize=12, fontweight="bold")
        plt.ylabel("Frequency (Hz)", fontsize=12, fontweight="bold")
        plt.title(title, fontsize=14, fontweight="bold")
        
        if ylim:
            plt.ylim(ylim)
        
        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to {output_path}")
        else:
            plt.show()

    def summary(self):
        print(f"Tracking Results Summary:")
        print(f"  Duration: {self.duration:.2f} seconds")
        print(f"  Sung Voices: {self.num_voices}")
        print(f"  Ghost Pitches: {self.num_ghosts}")
