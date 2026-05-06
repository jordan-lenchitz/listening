"""
dynamic 0-K multi-F0 Tracker for _ a cappella _ singing 

this implements a dynamic multi-F0 tracking system that can follow  up to K simultaneous sung pitches in polyphonic unaccompanied human singing.
it maintains consistent voice identity and identifies "extra" pitches (overtones, combination tones, etc.).
"""

import numpy as np
from scipy import signal
from scipy.optimize import linear_sum_assignment
from scipy.ndimage import gaussian_filter1d
import librosa
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum, auto
import warnings
warnings.filterwarnings('ignore')


class VoiceState(Enum):
    """State of a voice track."""
    ACTIVE = auto()
    TENTATIVE = auto()  # Recently detected, not yet confirmed
    INACTIVE = auto()   # Recently lost, may return
    TERMINATED = auto() # Confirmed exit


@dataclass
class VoiceTrack:
    """Represents a tracked voice with its pitch trajectory."""
    id: int
    start_frame: int
    pitches: list = field(default_factory=list)      # F0 values (Hz)
    confidences: list = field(default_factory=list)  # Detection confidence
    frames: list = field(default_factory=list)       # Frame indices
    state: VoiceState = VoiceState.TENTATIVE
    inactive_count: int = 0
    tentative_count: int = 0
    is_extra_pitch: bool = False  # True if this is a "ghost" pitch
    
    @property
    def end_frame(self) -> int:
        return self.frames[-1] if self.frames else self.start_frame
    
    @property
    def last_pitch(self) -> float:
        return self.pitches[-1] if self.pitches else 0.0
    
    @property
    def duration(self) -> int:
        return len(self.frames)
    
    def add_observation(self, frame: int, pitch: float, confidence: float):
        """Add a new pitch observation to the track."""
        self.frames.append(frame)
        self.pitches.append(pitch)
        self.confidences.append(confidence)


@dataclass
class TrackerConfig:
    """Configuration parameters for the multi-F0 tracker."""
    # Audio parameters
    sample_rate: int = 22050
    hop_length: int = 512
    frame_length: int = 4096
    
    # Pitch detection parameters
    min_freq: float = 65.0      # ~C2 - lowest bass
    max_freq: float = 1400.0    # ~F6 - highest soprano + room for overtones
    max_voices: int = 8         # Maximum simultaneous voices to track
    
    # Peak detection
    peak_threshold: float = 0.1     # Minimum salience for a peak
    min_peak_distance_cents: float = 50  # Minimum distance between peaks
    
    # Tracking parameters
    max_pitch_jump_cents: float = 300   # Maximum allowed pitch change per frame (~3 semitones)
    assignment_cost_scale: float = 100  # Scale factor for assignment costs
    
    # Voice state management
    tentative_frames: int = 3    # Frames to confirm a new voice
    inactive_frames: int = 5     # Frames before terminating a voice
    
    # Extra pitch detection
    detect_extra_pitches: bool = True
    combination_tone_tolerance_cents: float = 30  # Tolerance for matching combination tones
    overtone_tolerance_cents: float = 20          # Tolerance for matching overtones


class MultiF0Tracker:
    """
    Dynamic multi-F0 tracker for a cappella vocal ensembles.
    
    This tracker uses a salience-based multi-pitch estimation followed by
    Hungarian algorithm assignment to maintain consistent voice identity.
    It can detect when voices enter/exit and identify "extra" pitches
    that arise from acoustic interactions.
    """
    
    def __init__(self, config: Optional[TrackerConfig] = None):
        """Initialize the tracker with given configuration."""
        self.config = config or TrackerConfig()
        self.tracks: list[VoiceTrack] = []
        self.next_track_id = 0
        self.current_frame = 0
        
    def _hz_to_cents(self, freq: float, ref: float = 440.0) -> float:
        """Convert frequency to cents relative to reference."""
        if freq <= 0 or ref <= 0:
            return 0
        return 1200 * np.log2(freq / ref)
    
    def _cents_distance(self, f1: float, f2: float) -> float:
        """Calculate absolute distance in cents between two frequencies."""
        if f1 <= 0 or f2 <= 0:
            return float('inf')
        return abs(1200 * np.log2(f1 / f2))
    
    def _compute_salience(self, spectrum: np.ndarray, freqs: np.ndarray) -> tuple:
        """
        Compute pitch salience function from magnitude spectrum.
        
        Uses harmonic summation - for each candidate F0, sum the energy at its harmonics.
        """
        # Candidate F0 frequencies (logarithmically spaced)
        n_bins = 500
        f0_candidates = np.logspace(
            np.log10(self.config.min_freq),
            np.log10(self.config.max_freq),
            n_bins
        )
        
        salience = np.zeros(n_bins)
        n_harmonics = 6  # Number of harmonics to consider
        
        # Weights for harmonics (fundamental strongest, harmonics decay)
        harmonic_weights = np.array([1.0, 0.8, 0.6, 0.5, 0.4, 0.3])
        
        for i, f0 in enumerate(f0_candidates):
            total = 0
            for h in range(1, n_harmonics + 1):
                fh = f0 * h
                if fh > freqs[-1]:
                    break
                # Find nearest frequency bin
                idx = np.argmin(np.abs(freqs - fh))
                # Add weighted magnitude (with tolerance window)
                window = 3
                start = max(0, idx - window)
                end = min(len(spectrum), idx + window + 1)
                total += harmonic_weights[h-1] * np.max(spectrum[start:end])
            salience[i] = total
        
        # Normalize
        if salience.max() > 0:
            salience = salience / salience.max()
        
        return f0_candidates, salience
    
    def _detect_peaks(self, freqs: np.ndarray, salience: np.ndarray) -> list:
        """
        Detect pitch peaks in the salience function.
        
        Returns list of (frequency, salience) tuples for detected pitches.
        """
        # Find local maxima
        peaks = []
        min_dist_bins = int(self.config.min_peak_distance_cents / 
                          (1200 * np.log2(freqs[1]/freqs[0])))  # Convert cents to bins
        min_dist_bins = max(1, min_dist_bins)
        
        from scipy.signal import find_peaks as scipy_find_peaks
        peak_indices, properties = scipy_find_peaks(
            salience,
            height=self.config.peak_threshold,
            distance=min_dist_bins,
            prominence=0.05
        )
        
        for idx in peak_indices:
            # Parabolic interpolation for sub-bin accuracy
            if 0 < idx < len(salience) - 1:
                alpha = salience[idx - 1]
                beta = salience[idx]
                gamma = salience[idx + 1]
                if beta > 0:
                    offset = 0.5 * (alpha - gamma) / (alpha - 2*beta + gamma + 1e-10)
                    refined_freq = freqs[idx] * (2 ** (offset * np.log2(freqs[1]/freqs[0])))
                    peaks.append((refined_freq, salience[idx]))
            else:
                peaks.append((freqs[idx], salience[idx]))
        
        # Sort by salience (strongest first)
        peaks.sort(key=lambda x: x[1], reverse=True)
        
        # Limit to max_voices
        return peaks[:self.config.max_voices * 2]  # Keep extra for combination tone detection
    
    def _compute_assignment_cost(self, track: VoiceTrack, pitch: float) -> float:
        """
        Compute cost of assigning a pitch to an existing track.
        
        Based on pitch distance, with penalty for large jumps.
        """
        if track.state == VoiceState.TERMINATED:
            return float('inf')
        
        cents_dist = self._cents_distance(track.last_pitch, pitch)
        
        # Heavy penalty for jumps beyond threshold
        if cents_dist > self.config.max_pitch_jump_cents:
            return float('inf')
        
        # Cost is proportional to pitch distance
        return cents_dist * self.config.assignment_cost_scale
    
    def _identify_combination_tones(self, sung_pitches: list, detected_pitches: list) -> list:
        """
        Identify which detected pitches are likely combination tones.
        
        Combination tones occur at frequencies like f2-f1 (difference tone)
        or 2*f1-f2, etc.
        """
        if len(sung_pitches) < 2:
            return []
        
        combination_candidates = []
        sung_freqs = [p[0] for p in sung_pitches]
        
        # Generate expected combination tone frequencies
        expected_combinations = set()
        for i, f1 in enumerate(sung_freqs):
            for j, f2 in enumerate(sung_freqs):
                if i >= j:
                    continue
                # Common combination tones
                expected_combinations.add(abs(f2 - f1))           # Difference tone
                expected_combinations.add(2*f1 - f2)              # Cubic difference tone
                expected_combinations.add(2*f2 - f1)              # Cubic difference tone
                expected_combinations.add((f1 + f2) / 2)          # Subharmonic
            # Also check for strong overtones
            for h in range(2, 5):
                expected_combinations.add(f1 * h)
        
        # Check detected pitches against expected combinations
        for pitch, salience in detected_pitches:
            for expected in expected_combinations:
                if expected > 0:
                    cents_diff = self._cents_distance(pitch, expected)
                    if cents_diff < self.config.combination_tone_tolerance_cents:
                        combination_candidates.append((pitch, salience, expected))
                        break
        
        return combination_candidates
    
    def _update_tracks(self, detected_pitches: list, frame: int):
        """
        Update voice tracks with newly detected pitches.
        
        Uses Hungarian algorithm for optimal assignment while maintaining
        voice identity.
        """
        # Get active tracks (not terminated)
        active_tracks = [t for t in self.tracks 
                        if t.state != VoiceState.TERMINATED and not t.is_extra_pitch]
        
        if not active_tracks and not detected_pitches:
            return [], []
        
        sung_pitches = []
        extra_pitches = []
        
        if not active_tracks:
            # No existing tracks - start new ones for strong pitches
            for pitch, salience in detected_pitches[:self.config.max_voices]:
                if salience > self.config.peak_threshold:
                    track = VoiceTrack(
                        id=self.next_track_id,
                        start_frame=frame
                    )
                    track.add_observation(frame, pitch, salience)
                    self.tracks.append(track)
                    self.next_track_id += 1
                    sung_pitches.append((pitch, salience))
            return sung_pitches, extra_pitches
        
        if not detected_pitches:
            # No detected pitches - update inactive counts
            for track in active_tracks:
                track.inactive_count += 1
                if track.inactive_count >= self.config.inactive_frames:
                    track.state = VoiceState.TERMINATED
            return sung_pitches, extra_pitches
        
        # Build cost matrix for Hungarian algorithm
        n_tracks = len(active_tracks)
        n_pitches = len(detected_pitches)
        
        # Pad to make square matrix
        size = max(n_tracks, n_pitches)
        cost_matrix = np.full((size, size), 1e6)  # Large but finite default
        
        for i, track in enumerate(active_tracks):
            for j, (pitch, salience) in enumerate(detected_pitches):
                cost = self._compute_assignment_cost(track, pitch)
                if cost < float('inf'):
                    cost_matrix[i, j] = cost
                # else leave as 1e6 (unassignable but won't break algorithm)
        
        # Solve assignment problem
        try:
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
        except ValueError:
            # Fallback: no valid assignments
            for track in active_tracks:
                track.inactive_count += 1
                if track.inactive_count >= self.config.inactive_frames:
                    track.state = VoiceState.TERMINATED
            return sung_pitches, extra_pitches
        
        assigned_pitches = set()
        
        # Update assigned tracks
        for i, j in zip(row_ind, col_ind):
            if i < n_tracks and j < n_pitches:
                cost = cost_matrix[i, j]
                track = active_tracks[i]
                pitch, salience = detected_pitches[j]
                
                if cost < 1e5:  # Valid assignment (much less than our 1e6 default)
                    track.add_observation(frame, pitch, salience)
                    track.inactive_count = 0
                    if track.state == VoiceState.TENTATIVE:
                        track.tentative_count += 1
                        if track.tentative_count >= self.config.tentative_frames:
                            track.state = VoiceState.ACTIVE
                    assigned_pitches.add(j)
                    sung_pitches.append((pitch, salience))
                else:
                    # Track couldn't be assigned - mark inactive
                    track.inactive_count += 1
                    if track.inactive_count >= self.config.inactive_frames:
                        track.state = VoiceState.TERMINATED
        
        # Handle unassigned pitches (potential new voices or extra pitches)
        unassigned = [(j, detected_pitches[j]) for j in range(n_pitches) 
                      if j not in assigned_pitches]
        
        if self.config.detect_extra_pitches and sung_pitches:
            # Check for combination tones
            combo_tones = self._identify_combination_tones(sung_pitches, 
                                                          [p for _, p in unassigned])
            combo_freqs = {c[0] for c in combo_tones}
            
            for j, (pitch, salience) in unassigned:
                if pitch in combo_freqs:
                    # This is likely an extra pitch
                    track = VoiceTrack(
                        id=self.next_track_id,
                        start_frame=frame,
                        is_extra_pitch=True
                    )
                    track.add_observation(frame, pitch, salience)
                    track.state = VoiceState.ACTIVE
                    self.tracks.append(track)
                    self.next_track_id += 1
                    extra_pitches.append((pitch, salience))
                elif salience > self.config.peak_threshold * 1.2:
                    # Strong unassigned pitch - might be new voice
                    # Count active non-extra tracks
                    n_active = sum(1 for t in self.tracks 
                                  if t.state in [VoiceState.ACTIVE, VoiceState.TENTATIVE]
                                  and not t.is_extra_pitch)
                    if n_active < self.config.max_voices:
                        track = VoiceTrack(
                            id=self.next_track_id,
                            start_frame=frame
                        )
                        track.add_observation(frame, pitch, salience)
                        self.tracks.append(track)
                        self.next_track_id += 1
                        sung_pitches.append((pitch, salience))
        else:
            # Not detecting extra pitches - treat strong unassigned as new voices
            for j, (pitch, salience) in unassigned:
                if salience > self.config.peak_threshold * 1.2:
                    n_active = sum(1 for t in self.tracks 
                                  if t.state in [VoiceState.ACTIVE, VoiceState.TENTATIVE]
                                  and not t.is_extra_pitch)
                    if n_active < self.config.max_voices:
                        track = VoiceTrack(
                            id=self.next_track_id,
                            start_frame=frame
                        )
                        track.add_observation(frame, pitch, salience)
                        self.tracks.append(track)
                        self.next_track_id += 1
                        sung_pitches.append((pitch, salience))
        
        # Update extra pitch tracks
        extra_tracks = [t for t in self.tracks 
                       if t.is_extra_pitch and t.state != VoiceState.TERMINATED]
        for track in extra_tracks:
            # Check if this extra pitch is still present
            found = False
            for pitch, salience in detected_pitches:
                if self._cents_distance(track.last_pitch, pitch) < 50:
                    track.add_observation(frame, pitch, salience)
                    track.inactive_count = 0
                    found = True
                    break
            if not found:
                track.inactive_count += 1
                if track.inactive_count >= 3:  # Extra pitches fade faster
                    track.state = VoiceState.TERMINATED
        
        return sung_pitches, extra_pitches
    
    def track(self, audio: np.ndarray, sr: int) -> dict:
        """
        Track all voices in an audio signal.
        
        Parameters:
        -----------
        audio : np.ndarray
            Audio signal (mono)
        sr : int
            Sample rate of the audio
            
        Returns:
        --------
        dict with:
            - 'tracks': List of VoiceTrack objects
            - 'times': Array of time values for each frame
            - 'sung_voices': List of non-extra-pitch tracks
            - 'extra_pitches': List of extra (ghost) pitch tracks
        """
        # Resample if necessary
        if sr != self.config.sample_rate:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.config.sample_rate)
            sr = self.config.sample_rate
        
        # Reset tracker state
        self.tracks = []
        self.next_track_id = 0
        self.current_frame = 0
        
        # Compute STFT
        stft = librosa.stft(
            audio, 
            n_fft=self.config.frame_length,
            hop_length=self.config.hop_length,
            window='hann'
        )
        magnitude = np.abs(stft)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=self.config.frame_length)
        
        n_frames = magnitude.shape[1]
        times = librosa.frames_to_time(
            np.arange(n_frames),
            sr=sr,
            hop_length=self.config.hop_length
        )
        
        # Process each frame
        for frame in range(n_frames):
            self.current_frame = frame
            spectrum = magnitude[:, frame]
            
            # Compute salience and detect peaks
            f0_candidates, salience = self._compute_salience(spectrum, freqs)
            detected_pitches = self._detect_peaks(f0_candidates, salience)
            
            # Update tracks
            self._update_tracks(detected_pitches, frame)
        
        # Post-process: smooth trajectories and filter short tracks
        for track in self.tracks:
            if len(track.pitches) >= 3:
                # Light smoothing to reduce jitter
                track.pitches = list(gaussian_filter1d(track.pitches, sigma=1))
        
        # Separate sung voices from extra pitches
        sung_voices = [t for t in self.tracks 
                      if not t.is_extra_pitch and t.duration >= self.config.tentative_frames]
        extra_pitches = [t for t in self.tracks 
                        if t.is_extra_pitch and t.duration >= 2]
        
        return {
            'tracks': self.tracks,
            'times': times,
            'sung_voices': sung_voices,
            'extra_pitches': extra_pitches,
            'sample_rate': sr,
            'hop_length': self.config.hop_length
        }


def visualize_tracks(result: dict, output_path: str = None, show: bool = True):
    """
    Visualize the multi-F0 tracking results.
    
    Creates a plot showing:
    - Individual voice trajectories (colored lines)
    - Voice entry points (circles)
    - Voice exit points (X marks)
    - Extra pitches (dashed lines)
    """
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    
    times = result['times']
    sung_voices = result['sung_voices']
    extra_pitches = result['extra_pitches']
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Color palette for voices
    colors = plt.cm.tab10(np.linspace(0, 1, max(8, len(sung_voices))))
    
    # Plot sung voices
    for i, track in enumerate(sung_voices):
        color = colors[i % len(colors)]
        track_times = times[track.frames]
        track_pitches = track.pitches
        
        # Main trajectory
        ax.plot(track_times, track_pitches, '-', color=color, linewidth=2,
               label=f'Voice {track.id + 1}')
        
        # Entry point (circle)
        ax.plot(track_times[0], track_pitches[0], 'o', color=color, 
               markersize=12, markerfacecolor='white', markeredgewidth=2)
        
        # Exit point (X)
        ax.plot(track_times[-1], track_pitches[-1], 'X', color=color,
               markersize=12, markeredgewidth=2)
    
    # Plot extra pitches
    for track in extra_pitches:
        track_times = times[track.frames]
        track_pitches = track.pitches
        
        ax.plot(track_times, track_pitches, '--', color='purple', 
               linewidth=2, alpha=0.7)
        ax.plot(track_times[0], track_pitches[0], 's', color='purple',
               markersize=8, alpha=0.7)
    
    # Formatting
    ax.set_xlabel('Time (seconds)', fontsize=12)
    ax.set_ylabel('Frequency (Hz)', fontsize=12)
    ax.set_title('Multi-F0 Voice Tracking Results', fontsize=14)
    
    # Use log scale for frequency
    ax.set_yscale('log')
    ax.set_ylim(60, 1500)
    
    # Custom y-ticks with note names
    yticks = [65.41, 130.81, 196.00, 261.63, 329.63, 392.00, 523.25, 659.25, 783.99, 1046.50]
    yticklabels = ['C2', 'C3', 'G3', 'C4', 'E4', 'G4', 'C5', 'E5', 'G5', 'C6']
    ax.set_yticks(yticks)
    ax.set_yticklabels(yticklabels)
    
    ax.grid(True, alpha=0.3)
    
    # Legend
    legend_elements = [
        Line2D([0], [0], marker='o', color='gray', label='Voice Entry',
               markerfacecolor='white', markersize=10, markeredgewidth=2, linestyle='None'),
        Line2D([0], [0], marker='X', color='gray', label='Voice Exit',
               markersize=10, markeredgewidth=2, linestyle='None'),
        Line2D([0], [0], linestyle='--', color='purple', label='Extra Pitch (ghost tone)',
               linewidth=2)
    ]
    
    # Add voice legends
    for i, track in enumerate(sung_voices[:6]):  # Limit legend entries
        color = colors[i % len(colors)]
        legend_elements.append(
            Line2D([0], [0], color=color, linewidth=2, label=f'Voice {track.id + 1}')
        )
    
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"Plot saved to {output_path}")
    
    if show:
        plt.show()
    
    return fig, ax


def export_to_csv(result: dict, output_path: str):
    """
    Export tracking results to CSV format.
    
    Columns: time, voice_id, frequency_hz, confidence, is_extra_pitch
    """
    times = result['times']
    all_tracks = result['sung_voices'] + result['extra_pitches']
    
    with open(output_path, 'w') as f:
        f.write("time,voice_id,frequency_hz,confidence,is_extra_pitch\n")
        
        for track in all_tracks:
            for i, frame in enumerate(track.frames):
                time = times[frame]
                freq = track.pitches[i]
                conf = track.confidences[i]
                extra = 1 if track.is_extra_pitch else 0
                f.write(f"{time:.4f},{track.id},{freq:.2f},{conf:.4f},{extra}\n")
    
    print(f"Results exported to {output_path}")


def analyze_audio_file(audio_path: str, config: TrackerConfig = None) -> dict:
    """
    Convenience function to analyze an audio file.
    
    Parameters:
    -----------
    audio_path : str
        Path to audio file (WAV, MP3, etc.)
    config : TrackerConfig, optional
        Configuration parameters
        
    Returns:
    --------
    dict with tracking results
    """
    # Load audio
    audio, sr = librosa.load(audio_path, sr=None, mono=True)
    
    print(f"Loaded audio: {len(audio)/sr:.2f} seconds at {sr} Hz")
    
    # Create tracker and process
    tracker = MultiF0Tracker(config)
    result = tracker.track(audio, sr)
    
    # Print summary
    print(f"\nTracking Summary:")
    print(f"  Sung voices detected: {len(result['sung_voices'])}")
    print(f"  Extra pitches detected: {len(result['extra_pitches'])}")
    
    for track in result['sung_voices']:
        duration = (track.end_frame - track.start_frame) * result['hop_length'] / result['sample_rate']
        mean_pitch = np.mean(track.pitches)
        print(f"  Voice {track.id + 1}: {duration:.2f}s, mean F0 = {mean_pitch:.1f} Hz")
    
    for track in result['extra_pitches']:
        mean_pitch = np.mean(track.pitches)
        print(f"  Extra pitch: mean F0 = {mean_pitch:.1f} Hz (possible ghost tone)")
    
    return result


# Example usage and demo
if __name__ == "__main__":
    print("Multi-F0 Tracker for A Cappella Vocal Ensembles")
    print("=" * 50)
    print("\nUsage:")
    print("  from multi_f0_tracker import MultiF0Tracker, TrackerConfig")
    print("  from multi_f0_tracker import analyze_audio_file, visualize_tracks")
    print()
    print("  # Quick analysis")
    print("  result = analyze_audio_file('quartet.wav')")
    print("  visualize_tracks(result, 'output.png')")
    print()
    print("  # Custom configuration")
    print("  config = TrackerConfig(max_voices=4, min_freq=80)")
    print("  tracker = MultiF0Tracker(config)")
    print("  result = tracker.track(audio, sample_rate)")
