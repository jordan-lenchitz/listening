use realfft::RealFftPlanner;
use std::sync::Arc;

pub struct FormantDetector {
    order: usize,
    sample_rate: f64,
    fft_size: usize,
    r2c: Arc<dyn realfft::RealToComplex<f64>>,
}

impl FormantDetector {
    pub fn new(sample_rate: f64, order: usize) -> Self {
        let fft_size = 1024;
        let mut planner = RealFftPlanner::<f64>::new();
        let r2c = planner.plan_fft_forward(fft_size);
        
        Self {
            order,
            sample_rate,
            fft_size,
            r2c,
        }
    }

    pub fn detect(&self, frame: &[f32]) -> Vec<f64> {
        if frame.len() < self.order {
            return vec![];
        }

        // 1. Autocorrelation
        let mut r = vec![0.0; self.order + 1];
        for lag in 0..=self.order {
            let mut sum = 0.0;
            for i in 0..(frame.len() - lag) {
                sum += (frame[i] * frame[i + lag]) as f64;
            }
            r[lag] = sum;
        }

        // 2. Levinson-Durbin
        let a = self.levinson_durbin(&r);

        // 3. LPC Spectrum via FFT
        let mut in_data = vec![0.0; self.fft_size];
        for (i, &val) in a.iter().enumerate() {
            in_data[i] = val;
        }
        
        let mut spectrum = self.r2c.make_output_vec();
        self.r2c.process(&mut in_data, &mut spectrum).unwrap();
        
        let mut lpc_spectrum = vec![0.0; self.fft_size / 2];
        for i in 0..(self.fft_size / 2) {
            let mag_sq = spectrum[i].norm_sqr();
            if mag_sq > 1e-12 {
                lpc_spectrum[i] = 1.0 / mag_sq; // Spectrum of 1/A(z)
            }
        }

        // 4. Peak picking for formants
        let mut formants = vec![];
        for i in 1..(lpc_spectrum.len() - 1) {
            if lpc_spectrum[i] > lpc_spectrum[i - 1] && lpc_spectrum[i] > lpc_spectrum[i + 1] {
                let freq = i as f64 * self.sample_rate / self.fft_size as f64;
                if freq > 200.0 && freq < 5000.0 {
                    formants.push(freq);
                }
            }
        }

        formants.sort_by(|a, b| a.partial_cmp(b).unwrap());
        formants.truncate(4); // Return F1-F4
        formants
    }

    fn levinson_durbin(&self, r: &[f64]) -> Vec<f64> {
        let mut a = vec![0.0; self.order + 1];
        let mut e = r[0];
        a[0] = 1.0;
        
        for i in 1..=self.order {
            let mut k = r[i];
            for j in 1..i {
                k += a[j] * r[i - j];
            }
            if e.abs() < 1e-12 { break; }
            k /= -e;
            
            let mut a_next = vec![0.0; self.order + 1];
            a_next[0] = 1.0;
            for j in 1..i {
                a_next[j] = a[j] + k * a[i - j];
            }
            a_next[i] = k;
            a = a_next;
            e *= 1.0 - k * k;
        }
        a
    }
}
