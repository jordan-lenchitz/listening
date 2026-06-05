pub struct CouplingDetector {
    pub window_size: usize,
}

impl CouplingDetector {
    pub fn new(window_size: usize) -> Self {
        Self { window_size }
    }

    /// Compute Pearson correlation between two pitch trajectories.
    /// This acts as a proxy for mutual information/coupling in real-time.
    pub fn detect_coupling(&self, traj1: &[f64], traj2: &[f64]) -> f64 {
        let n = traj1.len().min(traj2.len()).min(self.window_size);
        if n < 5 { return 0.0; }

        let t1 = &traj1[traj1.len()-n..];
        let t2 = &traj2[traj2.len()-n..];

        let mean1 = t1.iter().sum::<f64>() / n as f64;
        let mean2 = t2.iter().sum::<f64>() / n as f64;

        let mut cov = 0.0;
        let mut var1 = 0.0;
        let mut var2 = 0.0;

        for i in 0..n {
            let d1 = t1[i] - mean1;
            let d2 = t2[i] - mean2;
            cov += d1 * d2;
            var1 += d1 * d1;
            var2 += d2 * d2;
        }

        if var1 > 0.0 && var2 > 0.0 {
            cov / (var1.sqrt() * var2.sqrt())
        } else {
            0.0
        }
    }
}
