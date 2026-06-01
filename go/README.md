# Go Multi-F0 Pitch Tracker

A high-performance, ecologically inspired multi-pitch tracker implemented in Go. This implementation mirrors the research work done in MATLAB/Python, focusing on spectral affordance fields and dual-process Bayesian tracking.

## Features

- **STFT & FSST:** Standard Short-Time Fourier Transform and Fourier Synchrosqueezing Transform for sharpened spectral analysis.
- **Affordance Field:** Real-time calculation of spectral affordances (presence, availability, persistence, change, continuity, and harmonic coherence).
- **Dual-Process Tracking:** Combines bottom-up salience peaks with top-down Bayesian expectation using a log-frequency transition matrix.
- **Real-time Audio:** Live tracking from microphone/system input using `malgo`.
- **Visualization:** Automatic generation of pitch trajectory plots using `gonum/plot`.

## Directory Structure

- `cmd/tracker/`: CLI for processing WAV files.
- `cmd/rt-tracker/`: CLI for real-time microphone tracking.
- `pkg/tracking/`: Core tracking logic, affordance fields, and Bayesian models.
- `pkg/dsp/`: Digital Signal Processing utilities (STFT, FSST).
- `pkg/music/`: Music theory utilities (Just Intonation, frequency/MIDI conversions).

## Installation

Ensure you have Go 1.26+ installed.

```bash
cd go
go mod download
```

Note: Real-time audio requires `libasound2-dev` on Linux or standard CoreAudio/DirectSound on macOS/Windows for `malgo`.

## Usage

### Process a WAV file
```bash
go run cmd/tracker/main.go test.wav
```
This will generate `results.png` with the tracked pitch trajectories.

### Real-time Tracking
```bash
go run cmd/rt-tracker/main.go
```

## Performance

This implementation is optimized for speed and can process audio much faster than the Python equivalent. Use the included benchmarks to verify on your machine:

```bash
go test -bench . ./pkg/tracking/...
```
