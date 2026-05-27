import pytest
import numpy as np
from affordance_field import AffordanceField

def test_affordance_field_initialization():
    af = AffordanceField()
    assert af.sample_rate == 22050
    assert af.frame_length == 4096

def test_affordance_field_compute_shape():
    af = AffordanceField(frame_length=1024, hop_length=256)
    sr = 22050
    duration = 0.5
    audio = np.random.randn(int(sr * duration))
    
    result = af.compute(audio)
    
    assert "field" in result
    assert "availability" in result
    assert "presence" in result
    
    # Check shapes
    # n_freqs = frame_length // 2 + 1 = 1024 // 2 + 1 = 513
    assert result["field"].shape[0] == 513
    # n_frames = (len(audio) // hop_length) + 1 (approximately, depends on centering)
    assert result["field"].ndim == 2

def test_affordance_field_silence():
    af = AffordanceField()
    sr = 22050
    audio = np.zeros(sr)
    
    result = af.compute(audio)
    # field should be very low for silence
    assert np.all(result["field"] <= 0.1)
