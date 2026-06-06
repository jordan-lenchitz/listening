import numpy as np
import librosa
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d
from typing import Dict, Any, Tuple, Optional

class AffordanceField:
    """
    Spectral affordance field for a cappella listening.
    Ported from MATLAB implementation.
    """
    def __init__(
        self,
        sample_rate: int = 22050,
        frame_length: int = 4096,
        hop_length: int = 512,
        masking_floor_db: float = -60.0,
        masking_spread_erb: float = 1.5,
        dominance_low_hz: float = 500.0,
        dominance_high_hz: float = 2000.0,
        dominance_weight: float = 1.0,
        persistence_tau: float = 0.4,
        change_tau: float = 0.05,
        continuity_erb_sigma: float = 0.5
    ):
        self.sample_rate = sample_rate
        self.frame_length = frame_length
        self.hop_length = hop_length
        self.masking_floor_db = masking_floor_db
        self.masking_spread_erb = masking_spread_erb
        self.dominance_low_hz = dominance_low_hz
        self.dominance_high_hz = dominance_high_hz
        self.dominance_weight = dominance_weight
        self.persistence_tau = persistence_tau
        self.change_tau = change_tau
        self.continuity_erb_sigma = continuity_erb_sigma

    def compute(self, audio: np.ndarray, stft: Optional[np.ndarray] = None) -> Dict[str, Any]:
        """
        Compute the affordance field and its components.
        """
        # STFT
        if stft is None:
            stft = librosa.stft(
                audio,
                n_fft=self.frame_length,
                hop_length=self.hop_length,
                window="hann",
                center=True,
                dtype=np.complex64
            )
        else:
            stft = stft.astype(np.complex64, copy=False)

        mag = np.abs(stft).astype(np.float32)
        freqs = librosa.fft_frequencies(sr=self.sample_rate, n_fft=self.frame_length).astype(np.float32)
        times = librosa.frames_to_time(
            np.arange(mag.shape[1]),
            sr=self.sample_rate,
            hop_length=self.hop_length
        ).astype(np.float32)

        # Magnitude in dB
        mag_db = 20 * np.log10(mag + 1e-12)

        # Components
        availability = self._peripheral_availability(mag_db, freqs)
        presence = self._feature_presence(mag)
        persistence = self._feature_persistence(presence)
        continuity = self._feature_continuity(presence, freqs)
        change = self._feature_change(presence)
        coherence = self._feature_harmonic_coherence(mag, freqs)

        # Feature integration (geometric mean)
        # Use in-place ops where possible
        feature_stack = (
            presence * 
            persistence * 
            continuity * 
            change * 
            coherence
        )
        feature_stack = np.power(feature_stack, 1.0 / 5.0, out=feature_stack)

        field = (availability * feature_stack).astype(np.float32)

        return {
            "field": field,
            "availability": availability,
            "presence": presence,
            "persistence": persistence,
            "continuity": continuity,
            "change": change,
            "coherence": coherence,
            "frequencies": freqs,
            "times": times
        }

    def _peripheral_availability(self, mag_db: np.ndarray, freqs: np.ndarray) -> np.ndarray:
        # Normalize to peak
        rel = mag_db - np.max(mag_db)
        avail = (rel - self.masking_floor_db) / (0 - self.masking_floor_db)
        avail = np.clip(avail, 0, 1, out=avail)

        # ERB smoothing
        avail = self._smooth_along_erb(avail, freqs, self.masking_spread_erb)

        # Dominance region weighting
        weight = np.ones_like(freqs, dtype=np.float32)
        mask = (freqs >= self.dominance_low_hz) & (freqs <= self.dominance_high_hz)
        weight[mask] = 1.0 + self.dominance_weight
        weight /= np.max(weight)
        
        # Apply weighting across time
        return (avail * weight[:, np.newaxis]).astype(np.float32)

    def _feature_presence(self, mag: np.ndarray) -> np.ndarray:
        mx = np.max(mag)
        if mx < 1e-12:
            return np.zeros_like(mag, dtype=np.float32)
        return (mag / mx).astype(np.float32)

    def _feature_persistence(self, presence: np.ndarray) -> np.ndarray:
        dt = self.hop_length / self.sample_rate
        alpha = np.exp(-dt / self.persistence_tau)
        
        persistence = np.zeros_like(presence, dtype=np.float32)
        prev = np.zeros(presence.shape[0], dtype=np.float32)
        for k in range(presence.shape[1]):
            prev = alpha * prev + (1 - alpha) * presence[:, k]
            persistence[:, k] = prev
            
        mx = np.max(persistence)
        if mx < 1e-12:
            return np.zeros_like(persistence, dtype=np.float32)
        return (persistence / mx).astype(np.float32)

    def _feature_continuity(self, presence: np.ndarray, freqs: np.ndarray) -> np.ndarray:
        # Time-lag correlation
        time_lag = np.zeros_like(presence, dtype=np.float32)
        time_lag[:, 1:] = presence[:, :-1]
        time_coherent = np.sqrt(presence * time_lag)

        # Frequency smoothness
        freq_smoothed = self._smooth_along_erb(presence, freqs, self.continuity_erb_sigma)
        freq_coherent = 1.0 - np.abs(presence - freq_smoothed)
        freq_coherent = np.maximum(0, freq_coherent, out=freq_coherent)

        continuity = time_coherent * freq_coherent
        mx = np.max(continuity)
        if mx > 0:
            continuity /= mx
        return continuity.astype(np.float32)

    def _feature_change(self, presence: np.ndarray) -> np.ndarray:
        dt = self.hop_length / self.sample_rate
        alpha = np.exp(-dt / self.change_tau)
        
        smooth = np.zeros_like(presence, dtype=np.float32)
        prev = np.zeros(presence.shape[0], dtype=np.float32)
        for k in range(presence.shape[1]):
            prev = alpha * prev + (1 - alpha) * presence[:, k]
            smooth[:, k] = prev
            
        change = np.maximum(0, presence - smooth)
        mx = np.max(change)
        if mx > 0:
            change /= mx
        return change.astype(np.float32)

    def _feature_harmonic_coherence(self, mag: np.ndarray, freqs: np.ndarray) -> np.ndarray:
        # Stub for now
        return np.ones_like(mag, dtype=np.float32)

    def _smooth_along_erb(self, X: np.ndarray, freqs: np.ndarray, sigma_erb: float) -> np.ndarray:
        """
        Smooth each column along frequency with a width that grows with ERB.
        """
        Y = np.zeros_like(X, dtype=np.float32)
        erb = 24.7 * (1 + 4.37 * freqs / 1000.0)
        bin_hz = freqs[1] - freqs[0] if len(freqs) > 1 else 1.0
        
        # Precompute kernels for each bin
        for i, f in enumerate(freqs):
            sigma_hz = sigma_erb * erb[i]
            sigma_bins = max(1.0, sigma_hz / bin_hz)
            
            half_win = int(np.ceil(3 * sigma_bins))
            lo = max(0, i - half_win)
            hi = min(len(freqs), i + half_win + 1)
            
            k = np.arange(lo, hi)
            w = np.exp(-0.5 * ((k - i) / sigma_bins) ** 2)
            w /= np.sum(w)
            
            # Apply to all time steps
            Y[i, :] = w @ X[lo:hi, :]
            
        return Y

    def visualize(self, A: Dict[str, Any], output_path: Optional[str] = None):
        """
        Visualize the affordance field components.
        """
        import os
        # Use /tmp for matplotlib if needed
        if "MPLCONFIGDIR" not in os.environ:
            os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"
            
        fig, axes = plt.subplots(3, 2, figsize=(14, 10))
        plt.subplots_adjust(hspace=0.4, wspace=0.3)
        
        times = A["times"]
        freqs = A["frequencies"]
        freq_lim = [60, 4000]

        def plot_map(ax, data, title, vmin=None, vmax=None):
            # Using imshow instead of pcolormesh for efficiency
            im = ax.imshow(
                data, 
                aspect='auto', 
                origin='lower', 
                cmap='turbo', 
                vmin=vmin, 
                vmax=vmax,
                extent=[times[0], times[-1], freqs[0], freqs[-1]]
            )
            ax.set_ylim(freq_lim)
            ax.set_title(title)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Freq (Hz)")
            plt.colorbar(im, ax=ax)

        # We don't have magnitude in A anymore to save memory, but we can use availability or something else if needed
        # Actually I should probably have kept magnitude if visualize needs it
        # But this is just a stub/test method
        
        plot_map(axes[0, 1], A["field"], "Affordance Field A(t, f)")
        plot_map(axes[1, 0], A["availability"], "Peripheral Availability", vmin=0, vmax=1)
        plot_map(axes[1, 1], A["persistence"], "Persistence", vmin=0, vmax=1)
        plot_map(axes[2, 0], A["continuity"], "Continuity", vmin=0, vmax=1)
        plot_map(axes[2, 1], A["change"], "Change", vmin=0, vmax=1)

        if output_path:
            plt.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close(fig)
            print(f"Figure saved: {output_path}")
        else:
            plt.show()

if __name__ == "__main__":
    # Test stub
    import librosa
    audio_path = "/tmp/listening/mp3/example_one.mp3"
    audio, sr = librosa.load(audio_path, sr=22050)
    af = AffordanceField(sample_rate=sr)
    results = af.compute(audio)
    af.visualize(results, output_path="/tmp/affordance_test.png")
