import numpy as np
import scipy.ndimage
import scipy.signal
import librosa
from typing import Dict, Any, Tuple, Optional

class AffordanceField:
    """
    Spectral affordance field for a cappella listening.
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

    @staticmethod
    def _build_range_queries(starts: np.ndarray, ends: np.ndarray):
        """Group [starts[f], ends[f]) range-max queries by power-of-two level k."""
        mask = starts < ends
        if not np.any(mask):
            return [], 0
        lens = ends[mask] - starts[mask]
        ks = np.floor(np.log2(lens)).astype(np.intp)
        rows = np.flatnonzero(mask)
        s1 = starts[mask]
        s2 = ends[mask] - (1 << ks)
        max_k = int(ks.max())
        groups = []
        for k in range(max_k + 1):
            m = ks == k
            if np.any(m):
                groups.append((k, rows[m], s1[m], s2[m]))
        return groups, max_k

    @staticmethod
    def _eval_range_max(st_levels, groups, out: np.ndarray, accumulate: bool = False):
        """Evaluate pre-grouped [lo, hi) range-max queries using sparse table levels."""
        for k, rows, s1, s2 in groups:
            stk = st_levels[k]
            vals = np.maximum(stk[s1], stk[s2])
            out[rows] = np.maximum(out[rows], vals) if accumulate else vals
        return out

    def _precompute(self):
        self.freqs_hz = librosa.fft_frequencies(sr=self.sr, n_fft=self.n_fft)
        self.freqs_erb = self._hz_to_erb(self.freqs_hz)
        self.n_freq = len(self.freqs_hz)
        
        # 1. Contiguous ERB neighborhood bounds [lo, hi) excluding f itself
        lo = np.searchsorted(self.freqs_erb, self.freqs_erb - self.masking_radius_erb, side="left")
        hi = np.searchsorted(self.freqs_erb, self.freqs_erb + self.masking_radius_erb, side="right")
        for f in range(self.n_freq):
            while lo[f] > 0 and abs(self.freqs_erb[lo[f] - 1] - self.freqs_erb[f]) <= self.masking_radius_erb:
                lo[f] -= 1
            while lo[f] < f and abs(self.freqs_erb[lo[f]] - self.freqs_erb[f]) > self.masking_radius_erb:
                lo[f] += 1
            while hi[f] < self.n_freq and abs(self.freqs_erb[hi[f]] - self.freqs_erb[f]) <= self.masking_radius_erb:
                hi[f] += 1
            while hi[f] > f + 1 and abs(self.freqs_erb[hi[f] - 1] - self.freqs_erb[f]) > self.masking_radius_erb:
                hi[f] -= 1

        fs = np.arange(self.n_freq)
        self._neighbor_left_q, k_l = self._build_range_queries(lo, fs)
        self._neighbor_right_q, k_r = self._build_range_queries(fs + 1, hi)
        max_k = max(k_l, k_r)
        
        # 2. Contiguous harmonic and subharmonic query groups per ratio
        tolerance_ratio = 2 ** (self.harmonic_tolerance_cents / 1200.0)
        self._harmonic_queries = []
        for ratio in self.harmonic_check_ratios:
            target_up = self.freqs_hz * ratio
            lower_up = target_up / tolerance_ratio
            upper_up = target_up * tolerance_ratio
            up_lo = np.searchsorted(self.freqs_hz, lower_up, side="left")
            up_hi = np.searchsorted(self.freqs_hz, upper_up, side="right")
            down_lo = np.searchsorted(upper_up, self.freqs_hz, side="left")
            down_hi = np.searchsorted(lower_up, self.freqs_hz, side="right")
            q_up, k_u = self._build_range_queries(up_lo, up_hi)
            q_down, k_d = self._build_range_queries(down_lo, down_hi)
            max_k = max(max_k, k_u, k_d)
            self._harmonic_queries.append((q_up, q_down))
        self._max_sparse_k = max_k
                
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
        
        # Build shared sparse table over frequency axis for O(1) range-max queries
        st_levels = [power_dB]
        for k in range(1, self._max_sparse_k + 1):
            step = 1 << (k - 1)
            st_levels.append(np.maximum(st_levels[k - 1][:-step], st_levels[k - 1][step:]))

        # 2. Peripheral availability (vectorized via sparse table)
        max_neighbor = np.full_like(power_dB, -np.inf)
        self._eval_range_max(st_levels, self._neighbor_left_q, max_neighbor, accumulate=False)
        self._eval_range_max(st_levels, self._neighbor_right_q, max_neighbor, accumulate=True)
                
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
        
        # Persistence P
        alpha_P = np.exp(-self.hop_ms / self.persistence_halflife_ms * np.log(2))
        P = scipy.signal.lfilter([1 - alpha_P], [1, -alpha_P], E, axis=1)
        # Fix initial condition to match loop behavior
        P[:, 0] = E[:, 0]
        P = P / (np.max(P) + 1e-12)
        
        # Continuity C
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
        
        # Harmonic coherence H (vectorized via shared sparse table)
        H = np.zeros_like(E)
        max_frame_dB = np.max(power_dB, axis=0) # shape (n_time,)
        valid_f0 = (self.freqs_hz >= self.floor_hz)[:, np.newaxis] & (power_dB >= max_frame_dB[np.newaxis, :] - 40)
        
        harmonic_power = np.empty_like(power_dB)
        subharmonic_power = np.empty_like(power_dB)
        for q_up, q_down in self._harmonic_queries:
            harmonic_power.fill(-np.inf)
            self._eval_range_max(st_levels, q_up, harmonic_power, accumulate=False)
            support_up = harmonic_power >= power_dB - self.harmonic_amplitude_threshold_db

            subharmonic_power.fill(-np.inf)
            self._eval_range_max(st_levels, q_down, subharmonic_power, accumulate=False)
            suppress_down = subharmonic_power > power_dB + self.harmonic_amplitude_threshold_db

            H += (support_up & (~suppress_down)) * valid_f0
            
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
        
        # Cull slightly to reduce "redness" and spurious high-affordance frequencies
        A = A ** 3
        
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
