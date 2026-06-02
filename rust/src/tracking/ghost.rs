/// Logic for identifying ghost pitches (combination tones and overtones).
/// Ported from the MATLAB research implementation.

pub struct GhostDetector {
    pub combination_tolerance_cents: f64,
    pub overtone_tolerance_cents: f64,
}

impl Default for GhostDetector {
    fn default() -> Self {
        Self {
            combination_tolerance_cents: 30.0,
            overtone_tolerance_cents: 20.0,
        }
    }
}

impl GhostDetector {
    pub fn new(comb_tol: f64, over_tol: f64) -> Self {
        Self {
            combination_tolerance_cents: comb_tol,
            overtone_tolerance_cents: over_tol,
        }
    }

    /// Returns true if `pitch` is likely a combination tone or overtone of the `sung_freqs`.
    pub fn is_ghost(&self, pitch: f64, sung_freqs: &[f64]) -> bool {
        if sung_freqs.is_empty() {
            return false;
        }

        for (i, &f1) in sung_freqs.iter().enumerate() {
            // Check overtones of each sung frequency
            for h in 2..=4 {
                let overtone = f1 * h as f64;
                if self.cents_diff(pitch, overtone) < self.overtone_tolerance_cents {
                    return true;
                }
            }

            // Check combination tones between pairs
            for &f2 in sung_freqs.iter().skip(i + 1) {
                let combos = [
                    (f2 - f1).abs(),     // Difference tone
                    2.0 * f1 - f2,       // Cubic difference tone 1
                    2.0 * f2 - f1        // Cubic difference tone 2
                ];

                for &c in &combos {
                    if c > 0.0 && self.cents_diff(pitch, c) < self.combination_tolerance_cents {
                        return true;
                    }
                }
            }
        }

        false
    }

    fn cents_diff(&self, f1: f64, f2: f64) -> f64 {
        if f1 <= 0.0 || f2 <= 0.0 {
            return f64::MAX;
        }
        1200.0 * (f1 / f2).log2().abs()
    }
}