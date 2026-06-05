use num_complex::Complex;
use std::f64::consts::PI;
use realfft::RealFftPlanner;
use std::sync::Arc;

pub struct Cqt {
    pub n_bins: usize,
    kernels_fft: Vec<Vec<Complex<f64>>>,
    fft_size: usize,
    r2c: Arc<dyn realfft::RealToComplex<f64>>,
}

impl Cqt {
    pub fn new(sample_rate: f64, f_min: f64, bins_per_octave: usize, n_octaves: usize) -> Self {
        let n_bins = bins_per_octave * n_octaves;
        let q = 1.0 / (2.0_f64.powf(1.0 / bins_per_octave as f64) - 1.0);
        
        // Find max window size
        let max_nk = (q * sample_rate / f_min).ceil() as usize;
        let fft_size = max_nk.next_power_of_two();
        
        let mut planner = RealFftPlanner::<f64>::new();
        let r2c = planner.plan_fft_forward(fft_size);
        let mut kernels_fft = Vec::with_capacity(n_bins);

        for k in 0..n_bins {
            let fk = f_min * 2.0_f64.powf(k as f64 / bins_per_octave as f64);
            let nk = (q * sample_rate / fk).ceil() as usize;
            
            // Compute complex kernel
            let mut complex_kernel = vec![Complex::new(0.0, 0.0); fft_size];
            for n in 0..nk {
                // Hamming window
                let w = 0.54 - 0.46 * (2.0 * PI * n as f64 / (nk - 1) as f64).cos();
                let angle = -2.0 * PI * q * n as f64 / nk as f64;
                complex_kernel[n] = Complex::from_polar(w / nk as f64, angle);
            }
            
            // For real-to-complex FFT, we'd normally just use complex-to-complex for CQT kernels.
            // But since our input is real, we can optimize.
            // Actually, CQT kernels are complex. Let's just store them and use them with the FFT of the input.
            // We'll need a Complex-to-Complex FFT for the kernels, or just use the definition.
            
            // To keep it simple and consistent with the project's realfft usage:
            // We'll compute the FFT of the complex kernels (using a complex FFT planner).
            let mut c2c_planner = rustfft::FftPlanner::new();
            let c2c_fft = c2c_planner.plan_fft_forward(fft_size);
            c2c_fft.process(&mut complex_kernel);
            
            kernels_fft.push(complex_kernel);
        }

        Self {
            n_bins,
            kernels_fft,
            fft_size,
            r2c,
        }
    }

    pub fn process(&self, frame: &[f32]) -> Vec<f64> {
        let mut in_data = vec![0.0; self.fft_size];
        for (i, &val) in frame.iter().take(self.fft_size).enumerate() {
            in_data[i] = val as f64;
        }
        
        // FFT of input (Real to Complex)
        let mut spectrum = self.r2c.make_output_vec();
        self.r2c.process(&mut in_data, &mut spectrum).unwrap();
        
        // We need the full complex spectrum for the kernel multiplication 
        // if we use complex kernels.
        let mut full_spectrum = vec![Complex::new(0.0, 0.0); self.fft_size];
        for i in 0..=self.fft_size/2 {
            full_spectrum[i] = spectrum[i];
            if i > 0 && i < self.fft_size/2 {
                full_spectrum[self.fft_size - i] = spectrum[i].conj();
            }
        }

        let mut output = vec![0.0; self.n_bins];
        for k in 0..self.n_bins {
            let mut sum = Complex::new(0.0, 0.0);
            for i in 0..self.fft_size {
                sum += full_spectrum[i] * self.kernels_fft[k][i].conj();
            }
            output[k] = sum.norm();
        }
        
        output
    }
}
