#[derive(Debug, Clone, Copy, PartialEq)]
pub enum VoiceState {
    Active,
    Tentative,
    Inactive,
    Terminated,
}

#[derive(Debug, Clone)]
pub struct VoiceTrack {
    pub id: usize,
    pub start_frame: usize,
    pub pitches: Vec<f64>,
    pub confidences: Vec<f64>,
    pub frames: Vec<usize>,
    pub state: VoiceState,
    pub inactive_count: usize,
}

impl VoiceTrack {
    pub fn new(id: usize, start_frame: usize) -> Self {
        Self {
            id,
            start_frame,
            pitches: Vec::new(),
            confidences: Vec::new(),
            frames: Vec::new(),
            state: VoiceState::Tentative,
            inactive_count: 0,
        }
    }

    pub fn add_observation(&mut self, frame: usize, pitch: f64, confidence: f64) {
        self.frames.push(frame);
        self.pitches.push(pitch);
        self.confidences.push(confidence);
        self.inactive_count = 0;
    }
}
