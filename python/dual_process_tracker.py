import numpy as np
import librosa
import scipy.signal as signal
from scipy.interpolate import interp1d
from scipy.ndimage import gaussian_filter1d
from typing import Dict, Any, List, Optional
import ssqueezepy
from ssqueezepy import ssq_cwt, extract_ridges

class DualProcessPitchTracker:
    """
    Dual-Process Pitch Tracker using Bayesian filtering and Synchrosqueezing.
    Ported from MATLAB implementation.
    """
    def __init__(
        self,
        audio_file: str,
        frame_duration: float = 0.03,
        frame_shift: float = 0.01,
        fmin: float = 80.0,
        fmax: float = 4000.0,
        grid_bins_per_oct: int = 60,
        alpha_base: float = 0.6,
        fade_factor: float = 0.98,
        voicing_thresh: float = 0.2,
        sigma_cents: float = 25.0,
        harm_comb_width: int = 4,
        track_assoc_cents: float = 35.0,
        kl_alert_thresh: float = 0.5,
        use_synsq: bool = True,
        beta_synsq: float = 0.3,
        ssq_voices_per_octave: int = 48
    ):
        self.audio_file = audio_file
        self.frame_duration = frame_duration
        self.frame_shift = frame_shift
        self.fmin = fmin
        self.fmax = fmax
        self.grid_bins_per_oct = grid_bins_per_oct
        self.alpha_base = alpha_base
        self.fade_factor = fade_factor
        self.voicing_thresh = voicing_thresh
        self.sigma_cents = sigma_cents
        self.harm_comb_width = harm_comb_width
        self.track_assoc_cents = track_assoc_cents
        self.kl_alert_thresh = kl_alert_thresh
        self.use_synsq = use_synsq
        self.beta_synsq = beta_synsq
        self.ssq_voices_per_octave = ssq_voices_per_octave

        # Internal state
        self.audio, self.sr = librosa.load(audio_file, sr=None, mono=True)
        self.frame_len = int(round(self.frame_duration * self.sr))
        self.frame_step = int(round(self.frame_shift * self.sr))
        
        n_frames = int(np.floor((len(self.audio) - self.frame_len) / self.frame_step)) + 1
        self.time_axis = (np.arange(n_frames) * self.frame_shift) + self.frame_duration / 2.0
        
        self._calc_freq_grid()
        self._build_gabor_bank()
        self._build_transition_matrix()
        
        self.synsq_data = {}
        if self.use_synsq:
            self._compute_synchrosqueeze()

    def _calc_freq_grid(self):
        n_oct = np.log2(self.fmax / self.fmin)
        n_bins = int(np.ceil(n_oct * self.grid_bins_per_oct))
        self.freq_grid = self.fmin * 2.0**(np.arange(n_bins) / self.grid_bins_per_oct)

    def _build_gabor_bank(self):
        # Time axis for Gabor window
        t = (np.arange(self.frame_len) - (self.frame_len - 1) / 2.0) / self.sr
        sigma = self.frame_duration / 6.0
        gauss = np.exp(-t**2 / (2 * sigma**2))
        
        # Bank: freq x time
        # We'll use broadcasting to build the complex bank
        bank = np.exp(2j * np.pi * self.freq_grid[:, np.newaxis] * t) * gauss
        self.gabor_bank = {
            "window": gauss,
            "bank": bank
        }

    def _build_transition_matrix(self):
        lg = np.log(self.freq_grid)
        # Sigma grows smaller in ln-Hz for higher frequencies? 
        # MATLAB: sigma_ln = (obj.SigmaCents / 1200) ./ (obj.freqGrid / 1000);
        sigma_ln = (self.sigma_cents / 1200.0) / (self.freq_grid / 1000.0)
        
        # X is target (row), Y is source (col)
        # We want to know P(X|Y)
        X, Y = np.meshgrid(lg, lg, indexing='ij')
        # Here we need sigma_ln to be per-source frequency (Y)
        T = np.exp(-(X - Y)**2 / (2 * sigma_ln**2))
        T /= np.sum(T, axis=0) # Column-stochastic
        self.transition_matrix = T

    def _compute_synchrosqueeze(self):
        print(f"Computing Synchrosqueezing (Morlet, {self.ssq_voices_per_octave} voices/oct) ...")
        
        # ssqueezepy implementation
        # Note: ssq_cwt returns (Tx, Wx, ssq_freqs, scales, ...)
        # We need to map our fmin/fmax to ssqueezepy scales
        scales = 'log-piecewise' # or custom
        Tx, Wx, ssq_freqs, scales, *rest = ssq_cwt(self.audio, fs=self.sr, nv=self.ssq_voices_per_octave)
        
        # Extract ridges
        # extract_ridges(Wx, scales, ...)
        # This is a bit different from MATLAB's wsstridge. 
        # We'll use a simple ridge extraction for now or look for more sophisticated one.
        ridges = extract_ridges(Tx, ssq_freqs, penalty=5, n_ridges=3)
        
        # ridges is actually (n_samples, n_ridges)
        # Map to our time_axis
        t_ssq = np.arange(len(self.audio)) / self.sr
        ridge_f = np.zeros((3, len(self.time_axis)))
        for i in range(min(3, ridges.shape[1] if len(ridges.shape) > 1 else 1)):
            ridge_data = ridges[:, i] if len(ridges.shape) > 1 else ridges
            f_interp = interp1d(t_ssq, ridge_data, kind='linear', fill_value='extrapolate')
            ridge_f[i, :] = f_interp(self.time_axis)
            
        self.synsq_data = {
            "time": t_ssq,
            "freq_axis": ssq_freqs,
            "tfr": Tx,
            "ridges": ridge_f
        }
        print(f"Synchrosqueeze done - ridge 1 median f0 = {np.median(ridge_f[0, :]):.1f} Hz")

    def _harmonic_comb_weight(self, P: np.ndarray) -> np.ndarray:
        comb_p = P.copy()
        n = len(P)
        for m in range(2, self.harm_comb_width + 1):
            shift = int(round(n / m))
            if shift < n:
                # MATLAB: combP(1 : end - shift) = combP(1 : end - shift) + P(1 + shift : end) / m ^ 2;
                comb_p[:-shift] += P[shift:] / (m**2)
        return comb_p

    def _fast_prior(self, f0: float) -> np.ndarray:
        if np.isnan(f0) or f0 <= 0:
            return np.ones(len(self.freq_grid)) / len(self.freq_grid)
        
        lg = np.log(self.freq_grid)
        mu = np.log(f0)
        sigma_ln = 15.0 / 1200.0 # 15 cents
        fp = np.exp(-(lg - mu)**2 / (2 * sigma_ln**2))
        return fp / np.sum(fp)

    def run(self):
        n_f = len(self.time_axis)
        n_g = len(self.freq_grid)
        
        self.fast_f0 = np.full(n_f, np.nan)
        self.fast_conf = np.zeros(n_f)
        self.posteriors = np.zeros((n_g, n_f))
        self.kl_div = np.zeros(n_f)
        
        # YIN pass
        print("Running YIN pass...")
        # librosa.yin returns f0 per frame
        self.fast_f0 = librosa.yin(
            self.audio,
            fmin=self.fmin,
            fmax=self.fmax,
            sr=self.sr,
            hop_length=self.frame_step,
            frame_length=self.frame_len,
            center=True
        )
        # librosa doesn't return confidence in yin directly, we can use a proxy
        # or use pyin. For simplicity, we'll assume a constant confidence if f0 is found.
        # Actually, let's use pyin for better confidence
        f0_pyin, voiced_flag, voiced_prob = librosa.pyin(
            self.audio,
            fmin=self.fmin,
            fmax=self.fmax,
            sr=self.sr,
            hop_length=self.frame_step,
            frame_length=self.frame_len,
            center=True
        )
        # Pad or trim to match n_f if needed
        self.fast_f0 = f0_pyin[:n_f]
        self.fast_conf = voiced_prob[:n_f]

        # Bayesian Filtering
        print("Running Bayesian filtering...")
        prior = np.ones(n_g) / n_g
        fade = self.fade_factor
        
        for i in range(n_f):
            # Frame indexing
            start = i * self.frame_step
            end = start + self.frame_len
            if end > len(self.audio):
                # Zero pad if needed
                frame_raw = np.zeros(self.frame_len)
                chunk = self.audio[start:]
                frame_raw[:len(chunk)] = chunk
            else:
                frame_raw = self.audio[start:end]
            
            frame_raw = frame_raw - np.mean(frame_raw)
            
            # Unvoiced early exit
            if self.fast_conf[i] < self.voicing_thresh:
                self.posteriors[:, i] = prior
                self.kl_div[i] = 0
                prior = fade * prior + (1 - fade) * (np.ones(n_g) / n_g)
                continue
            
            # Measurement likelihood
            frame_win = frame_raw * self.gabor_bank["window"]
            coeff = self.gabor_bank["bank"] @ frame_win
            P = np.abs(coeff)**2
            P = self._harmonic_comb_weight(P)
            meas_lh = P / np.sum(P)
            
            # Priors
            fp = self._fast_prior(self.fast_f0[i])
            if self.use_synsq:
                rp = self._fast_prior(self.synsq_data["ridges"][0, i])
            else:
                rp = np.zeros_like(fp)
                
            alpha_i = self.alpha_base * self.fast_conf[i]
            beta_i = self.beta_synsq if self.use_synsq else 0.0
            
            comb_prior = (alpha_i * fp) + (beta_i * rp) + (1.0 - alpha_i - beta_i) * prior
            comb_prior /= np.sum(comb_prior)
            
            # Update
            pred_prior = self.transition_matrix @ comb_prior
            post = pred_prior * meas_lh
            post /= np.sum(post)
            
            self.posteriors[:, i] = post
            
            # KL divergence
            self.kl_div[i] = np.sum(post * np.log(np.maximum(post, 1e-12) / np.maximum(comb_prior, 1e-12)))
            
            # Update prior for next frame
            prior = fade * post + (1 - fade) * (np.ones(n_g) / n_g)

        # Multi-hypothesis tracking
        print("Running Hungarian tracking...")
        self._tracking_hungarian()

    def _tracking_hungarian(self):
        from scipy.optimize import linear_sum_assignment
        
        n_f = self.posteriors.shape[1]
        top_n = 5
        peaks = []
        
        for i in range(n_f):
            # Find peaks in posterior
            post = self.posteriors[:, i]
            # Simple peak picking: find local maxima
            locs = signal.find_peaks(post)[0]
            if len(locs) == 0:
                peaks.append(np.array([]))
                continue
            
            pks = post[locs]
            idx = np.argsort(pks)[::-1][:top_n]
            peaks.append(np.column_stack((locs[idx], pks[idx])))
            
        tracks = []
        if not peaks or len(peaks[0]) == 0:
            self.tracks = []
            return
            
        # Initial tracks
        for j in range(len(peaks[0])):
            tracks.append({
                "time": [self.time_axis[0]],
                "f0": [self.freq_grid[int(peaks[0][j, 0])]],
                "prob": [peaks[0][j, 1]]
            })
            
        cents_tol = self.track_assoc_cents
        
        for i in range(1, n_f):
            if len(peaks[i]) == 0:
                # Add NaNs to all tracks
                for tr in tracks:
                    tr["time"].append(self.time_axis[i])
                    tr["f0"].append(np.nan)
                    tr["prob"].append(0.0)
                continue
                
            cand_idx = peaks[i][:, 0].astype(int)
            cand_f0 = self.freq_grid[cand_idx]
            n_t = len(tracks)
            n_c = len(cand_f0)
            
            # Cost matrix in cents
            cost = np.full((n_t, n_c), cents_tol)
            for r in range(n_t):
                last_f0 = tracks[r]["f0"][-1]
                if not np.isnan(last_f0):
                    # abs(1200 * log2(candF0 / lastF0))
                    cost[r, :] = np.abs(1200 * np.log2(cand_f0 / last_f0))
            
            # Linear sum assignment (Hungarian)
            # matchpairs in MATLAB is slightly different but LSA is standard
            # We filter by cents_tol after
            row_ind, col_ind = linear_sum_assignment(cost)
            
            assigned_rows = set()
            assigned_cols = set()
            for r, c in zip(row_ind, col_ind):
                if cost[r, c] < cents_tol:
                    tracks[r]["time"].append(self.time_axis[i])
                    tracks[r]["f0"].append(cand_f0[c])
                    tracks[r]["prob"].append(peaks[i][c, 1])
                    assigned_rows.add(r)
                    assigned_cols.add(c)
            
            # New tracks for unassigned candidates
            for c in range(n_c):
                if c not in assigned_cols:
                    tracks.append({
                        "time": [self.time_axis[i]],
                        "f0": [cand_f0[c]],
                        "prob": [peaks[i][c, 1]]
                    })
                    
            # Gap placeholders for unassigned tracks
            for r in range(n_t):
                if r not in assigned_rows:
                    tracks[r]["time"].append(self.time_axis[i])
                    tracks[r]["f0"].append(np.nan)
                    tracks[r]["prob"].append(0.0)
                    
        self.tracks = tracks

    def plot_tracks(self, output_path: Optional[str] = None):
        import os
        if "MPLCONFIGDIR" not in os.environ:
            os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"
            
        plt.figure(figsize=(14, 8))
        # Plot spectrogram
        D = librosa.amplitude_to_db(np.abs(librosa.stft(self.audio)), ref=np.max)
        librosa.display.specshow(D, sr=self.sr, x_axis='time', y_axis='log', cmap='magma')
        
        # Plot tracks
        for i, tr in enumerate(self.tracks):
            plt.plot(tr["time"], tr["f0"], linewidth=2, label=f"Track {i+1}")
            
        plt.ylim(self.fmin, self.fmax)
        plt.title("Dual-Process Pitch Tracking")
        if output_path:
            plt.savefig(output_path)
            print(f"Saved plot to {output_path}")
        else:
            plt.show()

if __name__ == "__main__":
    audio_path = "/tmp/listening/mp3/example_one.mp3"
    tracker = DualProcessPitchTracker(audio_path, use_synsq=True)
    tracker.run()
    tracker.plot_tracks(output_path="/tmp/tracker_test.png")
