pub struct KalmanFilter {
    pub x: [f64; 2], // [pitch_semitones, velocity]
    p: [[f64; 2]; 2],
    q: [[f64; 2]; 2],
    r: f64,
}

impl KalmanFilter {
    pub fn new(initial_pitch_hz: f64) -> Self {
        let p0 = 12.0 * (initial_pitch_hz / 440.0).log2() + 69.0;
        Self {
            x: [p0, 0.0],
            p: [[1.0, 0.0], [0.0, 1.0]],
            q: [[0.01, 0.0], [0.0, 0.001]],
            r: 0.1,
        }
    }

    pub fn predict(&mut self, dt: f64) {
        // x = F * x
        self.x[0] += self.x[1] * dt;
        
        // P = F * P * F' + Q
        let p00 = self.p[0][0] + dt * (self.p[1][0] + self.p[0][1] + dt * self.p[1][1]);
        let p01 = self.p[0][1] + dt * self.p[1][1];
        let p10 = self.p[1][0] + dt * self.p[1][1];
        let p11 = self.p[1][1];
        
        self.p[0][0] = p00 + self.q[0][0];
        self.p[0][1] = p01 + self.q[0][1];
        self.p[1][0] = p10 + self.q[1][0];
        self.p[1][1] = p11 + self.q[1][1];
    }

    pub fn update(&mut self, pitch_hz: f64) {
        let z = 12.0 * (pitch_hz / 440.0).log2() + 69.0;
        let y = z - self.x[0];
        let s = self.p[0][0] + self.r;
        let k0 = self.p[0][0] / s;
        let k1 = self.p[1][0] / s;
        
        self.x[0] += k0 * y;
        self.x[1] += k1 * y;
        
        let p00 = (1.0 - k0) * self.p[0][0];
        let p01 = (1.0 - k0) * self.p[0][1];
        let p10 = -k1 * self.p[0][0] + self.p[1][0];
        let p11 = -k1 * self.p[0][1] + self.p[1][1];
        
        self.p[0][0] = p00;
        self.p[0][1] = p01;
        self.p[1][0] = p10;
        self.p[1][1] = p11;
    }

    pub fn current_pitch_hz(&self) -> f64 {
        440.0 * 2.0_f64.powf((self.x[0] - 69.0) / 12.0)
    }
}
