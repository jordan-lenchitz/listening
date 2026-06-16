use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use listening_tracker::dsp::yin::Yin;
use listening_tracker::tracking::BayesianTracker;

use crossbeam_channel::{unbounded, Receiver, Sender};
use std::env;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = env::args().collect();
    let file_path = args.get(1);

    if let Some(path) = file_path {
        println!("Processing file: {}", path);
        process_file(path)?;
    } else {
        println!("A Cappella Multi-F0 Tracker (Rust Real-time Edition)");
        run_realtime()?;
    }
    Ok(())
}

fn run_realtime() -> Result<(), Box<dyn std::error::Error>> {
    // Audio setup
    let host = cpal::default_host();
    let device = host.default_input_device()
        .ok_or("No input device available")?;
    
    let config: cpal::StreamConfig = device.default_input_config()?.into();
    let sr = config.sample_rate.0 as f64;
    
    println!("Input device: {}", device.name()?);
    println!("Sample rate: {} Hz", sr);

    let (tx, rx): (Sender<Vec<f32>>, Receiver<Vec<f32>>) = unbounded();
    let input_data_fn = move |data: &[f32], _: &cpal::InputCallbackInfo| {
        let _ = tx.send(data.to_vec());
    };

    let input_stream = device.build_input_stream(&config, input_data_fn, |err| {
        eprintln!("An error occurred on the input audio stream: {}", err);
    }, None)?;

    input_stream.play()?;
    println!("Listening... Press Ctrl+C to stop.");
    
    process_loop(rx, sr)
}

fn process_file(path: &str) -> Result<(), Box<dyn std::error::Error>> {
    let mut reader = hound::WavReader::open(path)?;
    let spec = reader.spec();
    let sr = spec.sample_rate as f64;
    
    let (tx, rx): (Sender<Vec<f32>>, Receiver<Vec<f32>>) = unbounded();
    
    let samples: Vec<f32> = match spec.sample_format {
        hound::SampleFormat::Float => reader.samples::<f32>().map(|s| s.unwrap()).collect(),
        hound::SampleFormat::Int => {
            let max_val = (1 << (spec.bits_per_sample - 1)) as f32;
            reader.samples::<i32>().map(|s| s.unwrap() as f32 / max_val).collect()
        },
    };

    tx.send(samples)?;
    drop(tx);

    process_loop(rx, sr)
}

fn process_loop(rx: Receiver<Vec<f32>>, sr: f64) -> Result<(), Box<dyn std::error::Error>> {
    // DSP components
    let frame_size = 2048;
    let yin = Yin::new(frame_size, sr, 65.0, 1000.0);
    let mut tracker = BayesianTracker::new(65.0, 1000.0, 60, 0.98);
    let mut multi_tracker = listening_tracker::tracking::MultiF0Tracker::new();
    let mut affordance = listening_tracker::tracking::affordance::AffordanceField::new(sr, frame_size);

    let mut planner = realfft::RealFftPlanner::<f64>::new();
    let r2c = planner.plan_fft_forward(frame_size);
    let mut fft_in = vec![0.0; frame_size];
    let mut fft_out = r2c.make_output_vec();

    let mut buffer = Vec::new();
    let mut frame_count = 0;

    while let Ok(data) = rx.recv() {
        buffer.extend(data);
        
        while buffer.len() >= frame_size {
            let frame: Vec<f32> = buffer.drain(0..frame_size).collect();
            
            for (i, &v) in frame.iter().enumerate() { fft_in[i] = v as f64; }
            let _ = r2c.process(&mut fft_in, &mut fft_out);
            let mag = ndarray::Array1::from_shape_fn(fft_out.len(), |i| fft_out[i].norm());
            
            let field = affordance.update(&mag);
            let meas_lh = tracker.map_affordance_field(&affordance.freqs, &field);
            
            // Peak detection on measurement likelihood
            let mut peaks = Vec::new();
            for i in 1..meas_lh.len() - 1 {
                if meas_lh[i] > meas_lh[i-1] && meas_lh[i] > meas_lh[i+1] && meas_lh[i] > 0.1 {
                    peaks.push((tracker.freq_grid[i], meas_lh[i]));
                }
            }

            // Update Multi-F0 tracker
            multi_tracker.update(frame_count, &peaks);

            if let Some((f0, conf)) = yin.estimate(&frame) {
                let _post = tracker.update(&meas_lh, Some(f0), conf);
            } else {
                let _post = tracker.update(&meas_lh, None, 0.0);
            }

            // Print active tracks
            let active_tracks: Vec<_> = multi_tracker.tracks.iter()
                .filter(|t| t.state == listening_tracker::tracking::track::VoiceState::Active)
                .collect();

            if !active_tracks.is_empty() {
                print!("\rFrame {}: ", frame_count);
                for t in active_tracks {
                    let kind = if t.is_extra { "ghost" } else { "voice" };
                    print!("[ID {} {}: {:.1} Hz] ", t.id, kind, t.pitches.last().unwrap());
                }
                use std::io::Write;
                std::io::stdout().flush().unwrap();
            }

            frame_count += 1;
        }
    }

    Ok(())
}

