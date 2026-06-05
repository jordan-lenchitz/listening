pub struct JustIntonationAdvisor {
    pub ji_ratios: Vec<(f64, &'static str)>,
}

impl Default for JustIntonationAdvisor {
    fn default() -> Self {
        Self {
            ji_ratios: vec![
                (1.0, "1/1"),
                (16.0/15.0, "16/15"),
                (9.0/8.0, "9/8"),
                (6.0/5.0, "6/5"),
                (5.0/4.0, "5/4"),
                (4.0/3.0, "4/3"),
                (45.0/32.0, "45/32"),
                (3.0/2.0, "3/2"),
                (8.0/5.0, "8/5"),
                (5.0/3.0, "5/3"),
                (16.0/9.0, "16/9"),
                (15.0/8.0, "15/8"),
                (2.0, "2/1"),
            ],
        }
    }
}

impl JustIntonationAdvisor {
    pub fn get_advice(&self, root_freq: f64, target_freq: f64) -> (f64, &'static str, f64) {
        let ratio = target_freq / root_freq;
        // Normalize ratio to [1, 2]
        let mut norm_ratio = ratio;
        let mut octave_shift = 0;
        while norm_ratio < 1.0 { norm_ratio *= 2.0; octave_shift -= 1; }
        while norm_ratio >= 2.0 { norm_ratio /= 2.0; octave_shift += 1; }

        let mut best_ratio = 1.0;
        let mut best_label = "1/1";
        let mut min_diff = f64::MAX;

        for &(r, label) in &self.ji_ratios {
            let diff = (norm_ratio / r).ln().abs();
            if diff < min_diff {
                min_diff = diff;
                best_ratio = r * 2.0_f64.powi(octave_shift);
                best_label = label;
            }
        }

        let ideal_freq = best_ratio * root_freq;
        let cents_diff = 1200.0 * (target_freq / ideal_freq).log2();
        
        (ideal_freq, best_label, cents_diff)
    }
}
