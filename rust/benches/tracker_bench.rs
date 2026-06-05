use criterion::{black_box, criterion_group, criterion_main, Criterion};
use listening_tracker::dsp::yin::Yin;
use listening_tracker::tracking::bayesian::BayesianTracker;
use ndarray::Array1;

fn bench_yin(c: &mut Criterion) {
    let frame_size = 1024;
    let sample_rate = 44100.0;
    let yin = Yin::new(frame_size, sample_rate, 50.0, 1000.0);
    
    // Create a 440Hz sine wave
    let mut frame = vec![0.0f32; frame_size];
    for i in 0..frame_size {
        frame[i] = (2.0 * std::f64::consts::PI * 440.0 * i as f64 / sample_rate).sin() as f32;
    }

    c.bench_function("yin_estimate", |b| {
        b.iter(|| yin.estimate(black_box(&frame)))
    });
}

fn bench_bayesian(c: &mut Criterion) {
    let mut tracker = BayesianTracker::new(50.0, 1000.0, 48, 0.95);
    let n_g = tracker.freq_grid.len();
    let measurement_lh = Array1::from_elem(n_g, 1.0 / n_g as f64);
    
    c.bench_function("bayesian_update", |b| {
        b.iter(|| tracker.update(black_box(&measurement_lh), Some(440.0), 0.8))
    });
}

criterion_group!(benches, bench_yin, bench_bayesian);
criterion_main!(benches);
