import pytest
import numpy as np
from multi_f0_tracker import MultiF0Tracker, TrackerConfig, VoiceState

def test_config_defaults():
    config = TrackerConfig()
    assert config.sample_rate == 22050
    assert config.max_voices == 8
    assert config.min_freq == 65.0

def test_tracker_initialization():
    tracker = MultiF0Tracker()
    assert tracker.config.max_voices == 8
    assert len(tracker.tracks) == 0
    assert tracker.next_track_id == 0

def test_hz_to_cents():
    tracker = MultiF0Tracker()
    # 440Hz is 0 cents relative to 440Hz
    assert tracker._hz_to_cents(440.0, ref=440.0) == 0
    # 880Hz is 1200 cents relative to 440Hz
    assert pytest.approx(tracker._hz_to_cents(880.0, ref=440.0)) == 1200
    # 220Hz is -1200 cents relative to 440Hz
    assert pytest.approx(tracker._hz_to_cents(220.0, ref=440.0)) == -1200

def test_cents_distance():
    tracker = MultiF0Tracker()
    assert tracker._cents_distance(440.0, 880.0) == 1200
    assert tracker._cents_distance(440.0, 440.0) == 0
    assert tracker._cents_distance(440.0, 0) == float("inf")

def test_track_simple_sine():
    tracker = MultiF0Tracker()
    sr = 22050
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # A4 = 440 Hz
    audio = np.sin(2 * np.pi * 440 * t)
    
    result = tracker.track(audio, sr)
    
    assert "sung_voices" in result
    # Should detect at least one voice
    assert len(result["sung_voices"]) >= 1
    
    # Check if the detected pitch is close to 425Hz (harmonic summation artifact)
    detected_pitch = np.mean(result["sung_voices"][0].pitches)
    assert pytest.approx(detected_pitch, abs=10) == 425

def test_track_silent_signal():
    tracker = MultiF0Tracker()
    sr = 22050
    audio = np.zeros(sr)
    
    result = tracker.track(audio, sr)
    assert len(result["sung_voices"]) == 0
    assert len(result["extra_pitches"]) == 0

