use std::sync::Arc;
use realfft::{RealFftPlanner, RealToComplex, ComplexToReal};

/// YIN pitch estimation implementation for real-time use.
/// Optimized using FFT for O(N log N) performance.
pub struct Yin {
    frame_size: usize,
    fft_size: usize,
    sample_rate: f64,
    min_freq: f64,
    max_freq: f64,
    threshold: f64,
    r2c: Arc<dyn RealToComplex<f64>>,
    c2r: Arc<dyn ComplexToReal<f64>>,
}

impl Yin {
    pub fn new(frame_size: usize, sample_rate: f64, min_freq: f64, max_freq: f64) -> Self {
        let fft_size = (frame_size * 2).next_power_of_two();
        let mut planner = RealFftPlanner::<f64>::new();
        let r2c = planner.plan_fft_forward(fft_size);
        let c2r = planner.plan_fft_inverse(fft_size);

        Self {
            frame_size,
            fft_size,
            sample_rate,
            min_freq,
            max_freq,
            threshold: 0.1,
            r2c,
            c2r,
        }
    }

    /// Estimate pitch from a single frame.
    pub fn estimate(&self, frame: &[f32]) -> Option<(f64, f64)> {
        let n = frame.len();
        if n < self.frame_size {
            return None;
        }

        let tau_max = (self.sample_rate / self.min_freq) as usize;
        let tau_min = (self.sample_rate / self.max_freq) as usize;
        let tau_max = tau_max.min(self.frame_size / 2);

        // Step 1 & 2: Difference function using FFT
        // d(tau) = sum_{j=0}^{W-1} (x[j] - x[j+tau])^2
        // d(tau) = sum x[j]^2 + sum x[j+tau]^2 - 2 * sum x[j]x[j+tau]
        
        // 1. Compute autocorrelation using FFT
        let mut in_data = vec![0.0; self.fft_size];
        for (i, &val) in frame.iter().take(self.frame_size).enumerate() {
            in_data[i] = val as f64;
        }

        let mut spectrum = self.r2c.make_output_vec();
        self.r2c.process(&mut in_data, &mut spectrum).unwrap();

        for val in spectrum.iter_mut() {
            *val = *val * val.conj();
        }

        let mut out_data = self.c2r.make_output_vec();
        self.c2r.process(&mut spectrum, &mut out_data).unwrap();
        
        // Normalize autocorrelation
        let r = out_data.iter().map(|&x| x / self.fft_size as f64).collect::<Vec<_>>();

        // 2. Compute energy terms
        let mut energy = vec![0.0; tau_max + 1];
        let mut current_energy = 0.0;
        for i in 0..self.frame_size {
            current_energy += (frame[i] * frame[i]) as f64;
        }
        energy[0] = current_energy;

        for tau in 1..=tau_max {
            // energy[tau] = sum_{j=tau}^{W+tau-1} x[j]^2
            // For simplicity in this frame-based approach, we'll approximate 
            // the shifting window energy or just use the first window's energy 
            // if we assume stationarity over the frame.
            // A more precise version would use a larger frame to have x[j+tau].
            energy[tau] = energy[0]; // Approximation for now
        }

        let mut df = vec![0.0; tau_max];
        for tau in 1..tau_max {
            df[tau] = energy[0] + energy[tau] - 2.0 * r[tau];
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
        let mut min_cmndf = 1.0;

        for tau in tau_min..tau_max {
            if cmndf[tau] < self.threshold {
                best_tau = tau;
                break;
            }
            if cmndf[tau] < min_cmndf {
                min_cmndf = cmndf[tau];
                best_tau = tau;
            }
        }

        if best_tau == 0 || cmndf[best_tau] > 0.4 {
            return None;
        }

        // Step 5: Parabolic interpolation
        let (refined_tau, refined_val) = self.parabolic_interpolation(&cmndf, best_tau);
        
        let f0 = self.sample_rate / refined_tau;
        let confidence = 1.0 - refined_val;

        Some((f0, confidence))
    }

    fn parabolic_interpolation(&self, cmndf: &[f64], tau: usize) -> (f64, f64) {
        if tau == 0 || tau >= cmndf.len() - 1 {
            return (tau as f64, cmndf[tau]);
        }

        let s0 = cmndf[tau - 1];
        let s1 = cmndf[tau];
        let s2 = cmndf[tau + 1];

        let adj = (s2 - s0) / (2.0 * (2.0 * s1 - s2 - s0));
        let refined_tau = tau as f64 + adj;
        let refined_val = s1 - 0.25 * (s0 - s2) * adj;

        (refined_tau, refined_val)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_yin_sine_wave() {
        let sr = 44100.0;
        let frame_size = 2048;
        let yin = Yin::new(frame_size, sr, 65.0, 1000.0);
        
        let freq = 440.0;
        let mut frame = vec![0.0f32; frame_size];
        for i in 0..frame_size {
            frame[i] = (2.0 * std::f64::consts::PI * freq * i as f64 / sr).sin() as f32;
        }

        let result = yin.estimate(&frame);
        if let Some((f0, conf)) = result {
            println!("Detected F0: {} Hz (conf: {})", f0, conf);
        } else {
            println!("No pitch detected");
        }
        assert!(result.is_some());
        let (f0, conf) = result.unwrap();
        assert!((f0 - 440.0).abs() < 5.0, "Expected f0 around 440Hz, got {}", f0);
        assert!(conf > 0.5, "Expected high confidence, got {}", conf);
    }
}
