package main

import (
	"fmt"
	"log"
	"math"
	"os"

	"github.com/go-audio/wav"
	"github.com/jordan-lenchitz/listening/go/pkg/dsp"
	"github.com/jordan-lenchitz/listening/go/pkg/tracking"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Usage: tracker <wav-file>")
		return
	}

	filePath := os.Args[1]
	f, err := os.Open(filePath)
	if err != nil {
		log.Fatal(err)
	}
	defer f.Close()

	d := wav.NewDecoder(f)
	if !d.IsValidFile() {
		log.Fatal("Invalid WAV file")
	}

	buf, err := d.FullPCMBuffer()
	if err != nil {
		log.Fatal(err)
	}

	samples := make([]float64, len(buf.Data))
	maxVal := math.Pow(2, float64(buf.SourceBitDepth-1))
	for i, v := range buf.Data {
		samples[i] = float64(v) / maxVal
	}

	sr := d.SampleRate
	tracker := tracking.NewMultiF0Tracker(nil)
	tracker.Config.SampleRate = int(sr)

	stft := dsp.NewSTFT(tracker.Config.FrameLength, tracker.Config.HopLength)
	coeffs := stft.Compute(samples)
	freqs := stft.FFTFrequencies(int(sr))

	af := tracking.NewAffordanceField(float64(sr), tracker.Config.FrameLength)
	dt := tracking.NewDualProcessTracker(tracker.Config.MinFreq, tracker.Config.MaxFreq, 60) // 60 bins per octave

	fmt.Printf("Processing %d frames...\n", len(coeffs))

	for _, frameCoeffs := range coeffs {
		mag := make([]float64, len(frameCoeffs))
		for i, c := range frameCoeffs {
			mag[i] = math.Sqrt(real(c)*real(c) + imag(c)*imag(c))
		}

		field := af.Update(mag)

		f0Candidates, salience := tracker.ComputeSalience(mag, freqs, field)

		// Refine salience with harmonic comb weighting from DualProcessTracker
		salience = dt.HarmonicCombWeight(salience)

		peaks := tracker.DetectPeaks(f0Candidates, salience)
		tracker.Update(peaks, dt.TransitionMatrix, dt.FreqGrid)
	}

	times := make([]float64, len(coeffs))
	for i := range times {
		times[i] = float64(i * tracker.Config.HopLength) / float64(sr)
	}

	result := &tracking.TrackingResult{
		Times:      times,
		SampleRate: int(sr),
		HopLength:  tracker.Config.HopLength,
	}

	fmt.Println("Tracking Results:")
	for _, track := range tracker.Tracks {
		if track.State == tracking.ACTIVE || track.State == tracking.TERMINATED {
			if len(track.Pitches) > 10 {
				fmt.Printf("Track %d: StartFrame=%d, Duration=%d, AvgPitch=%.2f Hz\n",
					track.ID, track.StartFrame, len(track.Pitches), average(track.Pitches))
				result.SungVoices = append(result.SungVoices, track)
			}
		}
	}

	visPath := "results.png"
	if err := result.Visualize(visPath, "Go Multi-F0 Tracking"); err != nil {
		fmt.Printf("Error saving visualization: %v\n", err)
	} else {
		fmt.Printf("Visualization saved to %s\n", visPath)
	}
}

func average(vals []float64) float64 {
	if len(vals) == 0 {
		return 0
	}
	sum := 0.0
	for _, v := range vals {
		sum += v
	}
	return sum / float64(len(vals))
}
