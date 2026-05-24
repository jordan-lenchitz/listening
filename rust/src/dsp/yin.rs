use ndarray::Array1;
use std::f64::consts::PI;

/// YIN pitch estimation implementation for real-time use.
pub struct Yin {
    frame_size: usize,
    sample_rate: f64,
    min_freq: f64,
    max_freq: f64,
    threshold: f64,
}

impl Yin {
    pub fn new(frame_size: usize, sample_rate: f64, min_freq: f64, max_freq: f64) -> Self {
        Self {
            frame_size,
            sample_rate,
            min_freq,
            max_freq,
            threshold: 0.1,
        }
    }

    /// Estimate pitch from a single frame.
    pub fn estimate(&self, frame: &[f32]) -> Option<(f64, f64)> {
        let n = frame.len();
        let tau_max = (self.sample_rate / self.min_freq) as usize;
        let tau_min = (self.sample_rate / self.max_freq) as usize;
        
        // Step 1 & 2: Difference function
        let mut df = vec![0.0; tau_max];
        for tau in 1..tau_max {
            for j in 0..n - tau_max {
                let diff = (frame[j] - frame[j + tau]) as f64;
                df[tau] += diff * diff;
            }
        }

        // Step 3: Cumulative mean normalized difference function
        let mut cmndf = vec![1.0; tau_max];
        let mut running_sum = 0.0;
        for tau in 1..tau_max {
            running_sum += df[tau];
            if running_sum > 0.0 {
                cmndf[tau] = df[tau] / (running_sum / tau as f64);
            }
        }

        // Step 4: Absolute thresholding
        let mut best_tau = 0;
        for tau in tau_min..tau_max {
            if cmndf[tau] < self.threshold {
                best_tau = tau;
                break;
            }
            if cmndf[tau] < cmndf[best_tau] {
                best_tau = tau;
            }
        }

        if best_tau == 0 || cmndf[best_tau] > 0.4 {
            return None;
        }

        // Step 5: Parabolic interpolation
        let f0 = self.sample_rate / best_tau as f64;
        let confidence = 1.0 - cmndf[best_tau];

        Some((f0, confidence))
    }
}
