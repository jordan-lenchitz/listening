mod dsp;
mod tracking;

use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use crate::dsp::yin::Yin;
use crate::tracking::BayesianTracker;
use std::sync::{Arc, Mutex};
use ringbuf::{LocalRb, Rb, SharedRb};
use crossbeam_channel::{unbounded, Receiver, Sender};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("A Cappella Multi-F0 Tracker (Rust Real-time Edition)");

    // Audio setup
    let host = cpal::default_host();
    let device = host.default_input_device().expect("no input device available");
    let config: cpal::StreamConfig = device.default_input_config()?.into();
    let sr = config.sample_rate.0 as f64;
    
    println!("Input device: {}", device.name()?);
    println!("Sample rate: {} Hz", sr);

    // DSP components
    let frame_size = 2048;
    let yin = Yin::new(frame_size, sr, 65.0, 1000.0);
    let mut tracker = BayesianTracker::new(65.0, 1000.0, 60, 0.98);

    // Channel for passing audio blocks to the processing thread
    let (tx, rx): (Sender<Vec<f32>>, Receiver<Vec<f32>>) = unbounded();

    // Audio input stream
    let input_data_fn = move |data: &[f32], _: &cpal::InputCallbackInfo| {
        let _ = tx.send(data.to_vec());
    };

    let input_stream = device.build_input_stream(&config, input_data_fn, |err| {
        eprintln!("An error occurred on the input audio stream: {}", err);
    }, None)?;

    input_stream.play()?;

    println!("Listening... Press Ctrl+C to stop.");

    // Simple processing loop
    let mut buffer = Vec::new();
    while let Ok(data) = rx.recv() {
        buffer.extend(data);
        
        while buffer.len() >= frame_size {
            let frame: Vec<f32> = buffer.drain(0..frame_size).collect();
            
            // 1. YIN estimate
            if let Some((f0, conf)) = yin.estimate(&frame) {
                // 2. Dummy measurement likelihood (normalized FFT magnitude or Gabor)
                // For now, we'll just use a uniform one to see it running
                let n_g = 60 * (1000.0/65.0 as f64).log2().ceil() as usize;
                let meas_lh = ndarray::Array1::from_elem(n_g, 1.0 / n_g as f64);
                
                // 3. Bayesian update
                let post = tracker.update(&meas_lh, Some(f0), conf);
                
                // 4. Output top pitch
                if conf > 0.5 {
                    println!("Detected F0: {:.1} Hz (conf: {:.2})", f0, conf);
                }
            }
        }
    }

    Ok(())
}
