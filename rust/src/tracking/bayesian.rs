use ndarray::{Array1, Array2};

pub struct BayesianTracker {
    pub freq_grid: Array1<f64>,
    transition_matrix: Array2<f64>,
    prior: Array1<f64>,
    fade_factor: f64,
}

impl BayesianTracker {
    pub fn new(fmin: f64, fmax: f64, bins_per_oct: usize, fade_factor: f64) -> Self {
        let n_oct = (fmax / fmin).log2();
        let n_bins = (n_oct * bins_per_oct as f64).ceil() as usize;
        let freq_grid = Array1::from_shape_fn(n_bins, |i| {
            fmin * 2.0_f64.powf(i as f64 / bins_per_oct as f64)
        });

        let n_g = freq_grid.len();
        let prior = Array1::from_elem(n_g, 1.0 / n_g as f64);
        
        // Simplified transition matrix: Gaussian around current bin
        let mut transition_matrix = Array2::zeros((n_g, n_g));
        let sigma_cents = 25.0;
        let sigma_ln = sigma_cents / 1200.0;
        
        let lg = freq_grid.mapv(|f| f.ln());
        for j in 0..n_g {
            let mu = lg[j];
            let mut sum = 0.0;
            for i in 0..n_g {
                let diff = lg[i] - mu;
                let val = (-diff * diff / (2.0 * sigma_ln * sigma_ln)).exp();
                transition_matrix[[i, j]] = val;
                sum += val;
            }
            for i in 0..n_g {
                transition_matrix[[i, j]] /= sum;
            }
        }

        Self {
            freq_grid,
            transition_matrix,
            prior,
            fade_factor,
        }
    }

    /// Map a linear frequency field (from AffordanceField) to the log-frequency grid.
    pub fn map_affordance_field(&self, fft_freqs: &Array1<f64>, field: &Array1<f64>) -> Array1<f64> {
        let n_g = self.freq_grid.len();
        let mut mapped = Array1::zeros(n_g);
        
        for i in 0..n_g {
            let target_f = self.freq_grid[i];
            
            // Simple linear interpolation/nearest neighbor for now
            // Find closest FFT bin
            let mut best_idx = 0;
            let mut min_diff = f64::MAX;
            for (j, &f) in fft_freqs.iter().enumerate() {
                let diff = (f - target_f).abs();
                if diff < min_diff {
                    min_diff = diff;
                    best_idx = j;
                }
            }
            mapped[i] = field[best_idx];
        }
        
        mapped
    }

    pub fn update(&mut self, measurement_lh: &Array1<f64>, fast_f0: Option<f64>, fast_conf: f64) -> Array1<f64> {
        let n_g = self.freq_grid.len();
        
        // Fast prior from YIN
        let mut fp = Array1::from_elem(n_g, 1.0 / n_g as f64);
        if let Some(f0) = fast_f0 {
            let lg = self.freq_grid.mapv(|f| f.ln());
            let mu = f0.ln();
            let sigma_ln = 15.0 / 1200.0;
            let mut sum = 0.0;
            for i in 0..n_g {
                let diff = lg[i] - mu;
                let val = (-diff * diff / (2.0 * sigma_ln * sigma_ln)).exp();
                fp[i] = val;
                sum += val;
            }
            fp /= sum;
        }

        let alpha = 0.6 * fast_conf;
        let comb_prior = (alpha * &fp) + ((1.0 - alpha) * &self.prior);
        let comb_prior = &comb_prior / comb_prior.sum();

        // Prediciton step
        let pred_prior = self.transition_matrix.dot(&comb_prior);
        
        // Measurement update
        let mut post = pred_prior * measurement_lh;
        let sum = post.sum();
        if sum > 0.0 {
            post /= sum;
        } else {
            post = Array1::from_elem(n_g, 1.0 / n_g as f64);
        }

        // Update internal prior for next time
        self.prior = (self.fade_factor * &post) + ((1.0 - self.fade_factor) * Array1::from_elem(n_g, 1.0 / n_g as f64));
        
        post
    }
}
