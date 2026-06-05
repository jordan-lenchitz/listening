use num_complex::Complex;
use std::f64::consts::PI;

pub struct GammatoneFilter {
    pub center_freq: f64,
    pub erb: f64,
    a: f64,
    gain: f64,
    cos_w: f64,
    sin_w: f64,
    // States for 4 cascaded 1st-order complex filters
    states: [Complex<f64>; 4],
}

impl GammatoneFilter {
    pub fn new(fc: f64, sample_rate: f64) -> Self {
        let erb = 24.7 * (4.37 * fc / 1000.0 + 1.0);
        let b = 1.019 * erb;
        let t = 1.0 / sample_rate;
        
        let a = (-2.0 * PI * b * t).exp();
        let w = 2.0 * PI * fc * t;
        
        // Normalization gain to have unit gain at fc
        // For a single stage: H(z) = (1 - a e^{iw}) / (1 - a e^{iw} z^{-1})
        // But we often use a simpler version and normalize at the end.
        let gain = (1.0 - a).powi(4);

        Self {
            center_freq: fc,
            erb,
            a,
            gain,
            cos_w: w.cos(),
            sin_w: w.sin(),
            states: [Complex::new(0.0, 0.0); 4],
        }
    }

    pub fn process(&mut self, input: f64) -> f64 {
        let mut x = Complex::new(input, 0.0);
        // Complex pole: a * exp(i * w)
        let pole = Complex::new(self.a * self.cos_w, self.a * self.sin_w);

        for i in 0..4 {
            let y = x + pole * self.states[i];
            self.states[i] = y;
            x = y;
        }

        // The result is the real part of the 4th stage, multiplied by gain
        x.re * self.gain
    }
}

pub struct GammatoneFilterbank {
    pub filters: Vec<GammatoneFilter>,
}

impl GammatoneFilterbank {
    pub fn new(f_min: f64, f_max: f64, num_channels: usize, sample_rate: f64) -> Self {
        let mut filters = Vec::with_capacity(num_channels);
        
        // Space filters on the ERB scale
        let erb_min = 21.4 * (0.00437 * f_min + 1.0).log10();
        let erb_max = 21.4 * (0.00437 * f_max + 1.0).log10();
        
        for i in 0..num_channels {
            let erb_val = erb_min + (erb_max - erb_min) * (i as f64 / (num_channels - 1) as f64);
            let fc = (10.0_f64.powf(erb_val / 21.4) - 1.0) / 0.00437;
            filters.push(GammatoneFilter::new(fc, sample_rate));
        }

        Self { filters }
    }

    pub fn process_frame(&mut self, input: &[f32], output: &mut [Vec<f64>]) {
        for (i, &sample) in input.iter().enumerate() {
            for (ch, filter) in self.filters.iter_mut().enumerate() {
                output[ch][i] = filter.process(sample as f64);
            }
        }
    }
}
