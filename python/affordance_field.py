import numpy as np
import scipy.ndimage
import scipy.signal
import librosa
from typing import Dict, Any, Tuple, Optional

class AffordanceField:
    """
    Spectral affordance field for a cappella listening.
    Ported strictly from the MATLAB affordance_field_sandbox3 implementation.
    Optimized and vectorized for Python.
    """
    def __init__(
        self,
        sr: int = 22050,
        n_fft: int = 2048,
        # Peripheral
        masking_radius_erb: float = 2.0,
        masking_threshold_db: float = 10.0,
        dominance_region_hz: Tuple[float, float] = (600.0, 1400.0),
        # Affordance features
        persistence_halflife_ms: float = 50.0,
        continuity_neighborhood_erb: float = 0.5,
        onset_weight: float = 0.65,
        offset_weight: float = 0.35,
        harmonic_check_ratios: Tuple[float, ...] = (2.0, 3.0),
        harmonic_tolerance_cents: float = 50.0,
        harmonic_amplitude_threshold_db: float = 20.0,
        # Integration
        weight_presence: float = 0.4,
        weight_persistence: float = 0.6,
        weight_continuity: float = 1.0,
        weight_change: float = 1.2,
        weight_harmonic: float = 0.8,
        smoothing_halflife_ms: float = 30.0,
        # Signal
        window_ms: float = 40.0,
        hop_ms: float = 10.0,
        floor_hz: float = 800.0
    ):
        self.sr = sr
        self.n_fft = n_fft
        
        self.masking_radius_erb = masking_radius_erb
        self.masking_threshold_db = masking_threshold_db
        self.dominance_region_hz = dominance_region_hz
        
        self.persistence_halflife_ms = persistence_halflife_ms
        self.continuity_neighborhood_erb = continuity_neighborhood_erb
        self.onset_weight = onset_weight
        self.offset_weight = offset_weight
        self.harmonic_check_ratios = harmonic_check_ratios
        self.harmonic_tolerance_cents = harmonic_tolerance_cents
        self.harmonic_amplitude_threshold_db = harmonic_amplitude_threshold_db
        
        self.weight_presence = weight_presence
        self.weight_persistence = weight_persistence
        self.weight_continuity = weight_continuity
        self.weight_change = weight_change
        self.weight_harmonic = weight_harmonic
        self.smoothing_halflife_ms = smoothing_halflife_ms
        
        self.window_ms = window_ms
        self.hop_ms = hop_ms
        self.floor_hz = floor_hz
        
        # Precompute mappings
        self._precompute()

    def _hz_to_erb(self, f: np.ndarray) -> np.ndarray:
        return 21.4 * np.log10(1 + 0.00437 * f)

    def _precompute(self):
        self.freqs_hz = librosa.fft_frequencies(sr=self.sr, n_fft=self.n_fft)
        self.freqs_erb = self._hz_to_erb(self.freqs_hz)
        self.n_freq = len(self.freqs_hz)
        
        # 1. Neighborhood mask for availability
        self.in_neighborhood_mask = np.abs(self.freqs_erb[:, np.newaxis] - self.freqs_erb[np.newaxis, :]) <= self.masking_radius_erb
        np.fill_diagonal(self.in_neighborhood_mask, False)
        
        # 2. Harmonic masks for H
        self.harmonic_mask = np.zeros((len(self.harmonic_check_ratios), self.n_freq, self.n_freq), dtype=bool)
        tolerance_ratio = 2 ** (self.harmonic_tolerance_cents / 1200.0)
        
        for r_idx, ratio in enumerate(self.harmonic_check_ratios):
            for f in range(self.n_freq):
                # Look up (for harmonic support)
                target_up = self.freqs_hz[f] * ratio
                lower_up = target_up / tolerance_ratio
                upper_up = target_up * tolerance_ratio
                self.harmonic_mask[r_idx, f, :] = (self.freqs_hz >= lower_up) & (self.freqs_hz <= upper_up)
                
        # ERB bins for continuity
        self.erb_per_bin = np.mean(np.diff(self.freqs_erb)) if self.n_freq > 1 else 1.0
        self.neighborhood_bins = max(1, int(np.round(self.continuity_neighborhood_erb / self.erb_per_bin)))

    def compute(self, audio: np.ndarray, sr: int) -> Dict[str, Any]:
        """
        Compute the affordance field and its components.
        """
        # 1. Spectrogram
        window_n = int(np.round(self.window_ms / 1000 * sr))
        hop_n = int(np.round(self.hop_ms / 1000 * sr))

        stft = librosa.stft(audio, n_fft=self.n_fft, hop_length=hop_n, win_length=window_n, window="hann", center=False)
        magnitude = np.abs(stft)
        power_dB = 20 * np.log10(magnitude + 1e-12)
        
        n_time = magnitude.shape[1]
        
        # 2. Peripheral availability (Vectorized over time)
        max_neighbor = np.zeros_like(power_dB)
        for f in range(self.n_freq):
            mask = self.in_neighborhood_mask[f]
            if np.any(mask):
                max_neighbor[f, :] = np.max(power_dB[mask, :], axis=0)
            else:
                max_neighbor[f, :] = -np.inf
                
        shortfall = (max_neighbor - self.masking_threshold_db) - power_dB
        availability = np.where(max_neighbor > -np.inf,
                                np.where(power_dB >= max_neighbor - self.masking_threshold_db, 
                                         1.0, 
                                         np.maximum(0.0, 1.0 - shortfall / 12.0)),
                                1.0).astype(np.float32)

        # 3. Affordance features
        # Presence E
        E = power_dB - np.min(power_dB)
        E = E / (np.max(E) + 1e-12)
        
        # Persistence P (lfilter is much faster than Python loop)
        alpha_P = np.exp(-self.hop_ms / self.persistence_halflife_ms * np.log(2))
        P = scipy.signal.lfilter([1 - alpha_P], [1, -alpha_P], E, axis=1)
        # Fix initial condition to match loop behavior
        P[:, 0] = E[:, 0]
        P = P / (np.max(P) + 1e-12)
        
        # Continuity C
        # Using maximum_filter1d on the whole array is fully vectorized and very fast
        max_prev = scipy.ndimage.maximum_filter1d(E, size=2*self.neighborhood_bins+1, axis=0, mode="constant", cval=0.0)
        # Shift by 1 step
        max_prev_shifted = np.zeros_like(max_prev)
        max_prev_shifted[:, 1:] = max_prev[:, :-1]
        max_prev_shifted[:, 0] = E[:, 0] # initial boundary
        
        C = np.minimum(E, max_prev_shifted)
        C = C / (np.max(C) + 1e-12)
        
        # Change D
        diff_E = np.zeros_like(E)
        diff_E[:, 1:] = E[:, 1:] - E[:, :-1]
        onset = np.maximum(0, diff_E)
        offset = np.maximum(0, -diff_E)
        D = self.onset_weight * onset + self.offset_weight * offset
        D = D / (np.max(D) + 1e-12)
        
        # Harmonic coherence H (Vectorized over time)
        H = np.zeros_like(E)
        max_frame_dB = np.max(power_dB, axis=0) # shape (n_time,)
        valid_f0 = (self.freqs_hz >= self.floor_hz)[:, np.newaxis] & (power_dB >= max_frame_dB[np.newaxis, :] - 40)
        
        for r_idx in range(len(self.harmonic_check_ratios)):
            mask = self.harmonic_mask[r_idx]
            harmonic_support_ratio = np.zeros_like(power_dB)
            for f in range(self.n_freq):
                m = mask[f]
                if np.any(m):
                    harmonic_power = np.max(power_dB[m, :], axis=0)
                    harmonic_support_ratio[f, :] = (harmonic_power >= power_dB[f, :] - self.harmonic_amplitude_threshold_db)
            H += harmonic_support_ratio * valid_f0
            
        H = H / len(self.harmonic_check_ratios)
        
        # 4. Affordance Integration
        A_raw = (self.weight_presence * E + 
                 self.weight_persistence * P + 
                 self.weight_continuity * C + 
                 self.weight_change * D + 
                 self.weight_harmonic * H)
        A_raw = A_raw / (np.max(A_raw) + 1e-12)
        
        A_gated = A_raw * availability
        
        alpha_smooth = np.exp(-self.hop_ms / self.smoothing_halflife_ms * np.log(2))
        A = scipy.signal.lfilter([1 - alpha_smooth], [1, -alpha_smooth], A_gated, axis=1)
        A[:, 0] = A_gated[:, 0]
        
        A = A ** 2
        
        times = librosa.frames_to_time(np.arange(n_time), sr=sr, hop_length=hop_n)
        
        return {
            "power_dB": power_dB,
            "availability": availability,
            "presence": E,
            "persistence": P,
            "continuity": C,
            "change": D,
            "coherence": H,
            "field": A,
            "frequencies": self.freqs_hz,
            "times": times,
            "A_mean": np.mean(A, axis=1)
        }
