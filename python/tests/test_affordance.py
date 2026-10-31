import pytest
import numpy as np
from affordance_field import AffordanceField

def test_affordance_field_initialization():
    af = AffordanceField()
    assert af.sr == 22050
    assert af.n_fft == 2048

def test_affordance_field_compute_shape():
    af = AffordanceField(sr=22050, n_fft=1024)
    sr = 22050
    duration = 0.5
    audio = np.random.randn(int(sr * duration))
    
    result = af.compute(audio, sr)
    
    assert "field" in result
    assert "availability" in result
    assert "presence" in result
    
    assert result["field"].shape[0] == 513
    assert result["field"].ndim == 2

def test_affordance_field_sine_wave():
    af = AffordanceField(sr=22050, n_fft=2048, floor_hz=100.0)
    sr = 22050
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * 440.0 * t) + 0.25 * np.sin(2 * np.pi * 880.0 * t)
    
    result = af.compute(audio, sr)
    assert np.all(result["field"] >= 0.0)
    assert np.all(result["field"] <= 1.0)
    peak_freq = result["frequencies"][np.argmax(result["A_mean"])]
    assert abs(peak_freq - 440.0) < 25.0 or abs(peak_freq - 880.0) < 25.0
