use ndarray::Array1;

/// Spectral affordance field for real-time a cappella listening.
/// Ported and adapted from the Python/MATLAB research implementation.
pub struct AffordanceField {
    pub freqs: Array1<f64>,
    
    // State for persistence and change
    prev_presence: Array1<f64>,
    persistence: Array1<f64>,
    smooth_presence: Array1<f64>,
    
    // Hyperparameters
    persistence_alpha: f64,
    change_alpha: f64,
    masking_floor_db: f64,
    masking_spread_erb: f64,
    dominance_low_hz: f64,
    dominance_high_hz: f64,
    dominance_weight: f64,
    continuity_erb_sigma: f64,
}

impl AffordanceField {
    pub fn new(sample_rate: f64, frame_size: usize) -> Self {
        let n_bins = frame_size / 2 + 1;
        let freqs = Array1::from_shape_fn(n_bins, |i| {
            i as f64 * sample_rate / frame_size as f64
        });
        
        // Time constants (assuming ~23ms hop at 44.1kHz / 1024)
        let persistence_alpha = 0.95; 
        let change_alpha = 0.8;

        Self {
            freqs,
            prev_presence: Array1::zeros(n_bins),
            persistence: Array1::zeros(n_bins),
            smooth_presence: Array1::zeros(n_bins),
            persistence_alpha,
            change_alpha,
            masking_floor_db: -60.0,
            masking_spread_erb: 1.5,
            dominance_low_hz: 500.0,
            dominance_high_hz: 2000.0,
            dominance_weight: 1.0,
            continuity_erb_sigma: 0.5,
        }
    }

    /// Update the affordance field with a new magnitude spectrum frame.
    pub fn update(&mut self, mag: &Array1<f64>) -> Array1<f64> {
        let n = mag.len();
        
        // 1. Feature Presence (normalized magnitude)
        let max_mag = mag.fold(0.0_f64, |a, &b| a.max(b));
        let presence = if max_mag > 0.0 { 
            mag.mapv(|x| x / max_mag) 
        } else { 
            Array1::zeros(n) 
        };

        // 2. Peripheral Availability (Masking + Dominance)
        let mut availability = Array1::zeros(n);
        let mag_db = mag.mapv(|x| 20.0 * (x + 1e-12).log10());
        let peak_db = mag_db.fold(f64::NEG_INFINITY, |a, b| a.max(*b));
        
        for i in 0..n {
            let rel = mag_db[i] - peak_db;
            let val = (rel - self.masking_floor_db) / (0.0 - self.masking_floor_db);
            availability[i] = val.clamp(0.0, 1.0);
        }

        // Apply ERB smoothing to availability
        availability = self.smooth_along_erb(&availability, self.masking_spread_erb);

        // Dominance weight
        for i in 0..n {
            if self.freqs[i] >= self.dominance_low_hz && self.freqs[i] <= self.dominance_high_hz {
                availability[i] *= 1.0 + self.dominance_weight;
            }
        }
        
        // Normalize availability
        let max_avail = availability.fold(0.0_f64, |a, &b| a.max(b));
        if max_avail > 0.0 { 
            availability.mapv_inplace(|x| x / max_avail); 
        }

        // 3. Persistence (Exponential Moving Average)
        for i in 0..n {
            self.persistence[i] = self.persistence_alpha * self.persistence[i] + (1.0 - self.persistence_alpha) * presence[i];
        }
        let max_pers = self.persistence.fold(0.0_f64, |a, &b| a.max(b));
        let norm_persistence = if max_pers > 0.0 { 
            self.persistence.mapv(|x| x / max_pers) 
        } else { 
            Array1::zeros(n) 
        };

        // 4. Change (Onset detection via presence - smoothed presence)
        let mut change = Array1::zeros(n);
        for i in 0..n {
            self.smooth_presence[i] = self.change_alpha * self.smooth_presence[i] + (1.0 - self.change_alpha) * presence[i];
            change[i] = (presence[i] - self.smooth_presence[i]).max(0.0);
        }
        let max_change = change.fold(0.0_f64, |a, &b| a.max(b));
        if max_change > 0.0 { 
            change.mapv_inplace(|x| x / max_change); 
        }

        // 5. Continuity (Temporal correlation + frequency smoothness)
        let mut time_coherent = Array1::zeros(n);
        for i in 0..n {
            time_coherent[i] = (presence[i] * self.prev_presence[i]).sqrt();
        }

        let freq_smoothed = self.smooth_along_erb(&presence, self.continuity_erb_sigma);
        let mut freq_coherent = Array1::zeros(n);
        for i in 0..n {
            freq_coherent[i] = (1.0 - (presence[i] - freq_smoothed[i]).abs()).max(0.0);
        }

        let mut continuity = time_coherent * freq_coherent;
        let max_cont = continuity.fold(0.0_f64, |a, &b| a.max(b));
        if max_cont > 0.0 { 
            continuity.mapv_inplace(|x| x / max_cont); 
        }

        // 6. Harmonic Coherence (Stub)
        let coherence: Array1<f64> = Array1::ones(n);

        // Integration (Geometric mean of features integrated with availability)
        let mut field = Array1::zeros(n);
        for i in 0..n {
            let features: f64 = presence[i] * norm_persistence[i] * continuity[i] * change[i] * coherence[i];
            field[i] = availability[i] * features.powf(0.2);
        }

        // Update temporal state for next frame
        self.prev_presence.assign(&presence);

        field
    }

    fn smooth_along_erb(&self, x: &Array1<f64>, sigma_erb: f64) -> Array1<f64> {
        let n = x.len();
        let mut y = Array1::zeros(n);
        let bin_hz = if n > 1 { self.freqs[1] - self.freqs[0] } else { 1.0 };

        for i in 0..n {
            let f = self.freqs[i];
            let erb = 24.7 * (1.0 + 4.37 * f / 1000.0);
            let sigma_hz = sigma_erb * erb;
            let sigma_bins = (sigma_hz / bin_hz).max(1.0);
            
            let half_win = (3.0 * sigma_bins).ceil() as isize;
            let mut sum_w = 0.0;
            let mut val = 0.0;
            
            let start = (i as isize - half_win).max(0) as usize;
            let end = (i as isize + half_win).min(n as isize - 1) as usize;

            for k in start..=end {
                let weight = ( -0.5 * ((k as f64 - i as f64) / sigma_bins).powi(2) ).exp();
                val += x[k] * weight;
                sum_w += weight;
            }
            y[i] = if sum_w > 0.0 { val / sum_w } else { x[i] };
        }
        y
    }
}

