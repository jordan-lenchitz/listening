use crate::tracking::track::{VoiceTrack, VoiceState};
use crate::tracking::ghost::GhostDetector;

pub struct MultiF0Tracker {
    pub tracks: Vec<VoiceTrack>,
    pub next_track_id: usize,
    pub current_frame: usize,
    
    // Config
    pub max_voices: usize,
    pub min_freq: f64,
    pub max_freq: f64,
    pub peak_threshold: f64,
    pub max_pitch_jump_cents: f64,
    pub tentative_frames: usize,
    pub inactive_frames: usize,
    pub detect_extra_pitches: bool,
    
    ghost_detector: GhostDetector,
}

impl Default for MultiF0Tracker {
    fn default() -> Self {
        Self {
            tracks: Vec::new(),
            next_track_id: 0,
            current_frame: 0,
            max_voices: 8,
            min_freq: 65.0,
            max_freq: 1400.0,
            peak_threshold: 0.1,
            max_pitch_jump_cents: 300.0,
            tentative_frames: 3,
            inactive_frames: 5,
            detect_extra_pitches: true,
            ghost_detector: GhostDetector::default(),
        }
    }
}

impl MultiF0Tracker {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn update(&mut self, frame: usize, detected_peaks: &[(f64, f64)]) {
        self.current_frame = frame;
        
        let active_indices: Vec<usize> = self.tracks.iter().enumerate()
            .filter(|(_, t)| t.state != VoiceState::Terminated)
            .map(|(i, _)| i)
            .collect();
            
        if active_indices.is_empty() {
            for &(pitch, conf) in detected_peaks {
                if conf > self.peak_threshold {
                    self.create_track(frame, pitch, conf, false);
                }
            }
            return;
        }

        // Simple greedy assignment (replacement for matchpairs/Hungarian for now)
        // In a real expansion, we'd use the 'pathfinding' crate for Munkres
        let unassigned_peaks: Vec<(f64, f64)> = detected_peaks.to_vec();
        let mut assigned_peaks = vec![false; detected_peaks.len()];
        let mut assigned_tracks = vec![false; active_indices.len()];

        for (i, &t_idx) in active_indices.iter().enumerate() {
            let last_pitch = *self.tracks[t_idx].pitches.last().unwrap();
            
            let mut best_peak_idx = None;
            let mut min_cents = self.max_pitch_jump_cents;
            
            for (j, &(pitch, _)) in unassigned_peaks.iter().enumerate() {
                if assigned_peaks[j] { continue; }
                
                let cents = 1200.0 * (pitch / last_pitch).log2().abs();
                if cents < min_cents {
                    min_cents = cents;
                    best_peak_idx = Some(j);
                }
            }
            
            if let Some(j) = best_peak_idx {
                let (pitch, conf) = unassigned_peaks[j];
                self.tracks[t_idx].add_observation(frame, pitch, conf);
                
                if self.tracks[t_idx].state == VoiceState::Tentative {
                    // Tentative count is implicitly tracked by pitches.len()
                    if self.tracks[t_idx].pitches.len() >= self.tentative_frames {
                        self.tracks[t_idx].state = VoiceState::Active;
                    }
                }
                
                assigned_peaks[j] = true;
                assigned_tracks[i] = true;
            }
        }

        // Update unassigned tracks
        for (i, &assigned) in assigned_tracks.iter().enumerate() {
            if !assigned {
                let t_idx = active_indices[i];
                self.tracks[t_idx].inactive_count += 1;
                if self.tracks[t_idx].inactive_count >= self.inactive_frames {
                    self.tracks[t_idx].state = VoiceState::Terminated;
                } else {
                    self.tracks[t_idx].state = VoiceState::Inactive;
                }
            }
        }

        // Handle unassigned peaks (new voices or ghosts)
        let sung_freqs: Vec<f64> = self.tracks.iter()
            .filter(|t| t.state == VoiceState::Active && !t.is_extra)
            .map(|t| *t.pitches.last().unwrap())
            .collect();

        let n_active_voices = self.tracks.iter()
            .filter(|t| t.state != VoiceState::Terminated && !t.is_extra)
            .count();

        for (j, &assigned) in assigned_peaks.iter().enumerate() {
            if !assigned {
                let (pitch, conf) = unassigned_peaks[j];
                if conf > self.peak_threshold * 1.2 {
                    let is_ghost = self.detect_extra_pitches && self.ghost_detector.is_ghost(pitch, &sung_freqs);
                    
                    if is_ghost {
                        self.create_track(frame, pitch, conf, true);
                    } else if n_active_voices < self.max_voices {
                        self.create_track(frame, pitch, conf, false);
                    }
                }
            }
        }
    }

    fn create_track(&mut self, frame: usize, pitch: f64, conf: f64, is_extra: bool) {
        let track_id = self.next_track_id;
        self.next_track_id += 1;

        // Try to reuse a terminated track
        for track in self.tracks.iter_mut() {
            if track.state == VoiceState::Terminated {
                track.reset(track_id, frame, is_extra);
                track.add_observation(frame, pitch, conf);
                return;
            }
        }

        // No terminated tracks found, push a new one
        let mut track = VoiceTrack::new(track_id, frame, is_extra);
        track.add_observation(frame, pitch, conf);
        self.tracks.push(track);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_track_reuse() {
        let mut tracker = MultiF0Tracker::new();
        tracker.inactive_frames = 1;
        
        // 1. Create a track
        tracker.update(0, &[(440.0, 0.9)]);
        assert_eq!(tracker.tracks.len(), 1);
        assert_eq!(tracker.tracks[0].id, 0);
        
        // 2. Terminate the track
        tracker.update(1, &[]); // No peaks, should become Inactive
        tracker.update(2, &[]); // Still no peaks, should become Terminated (since inactive_frames=1)
        assert_eq!(tracker.tracks[0].state, VoiceState::Terminated);
        
        // 3. Create a new track, should reuse slot 0
        tracker.update(3, &[(220.0, 0.9)]);
        assert_eq!(tracker.tracks.len(), 1);
        assert_eq!(tracker.tracks[0].id, 1);
        assert_eq!(tracker.tracks[0].pitches[0], 220.0);
    }
}
