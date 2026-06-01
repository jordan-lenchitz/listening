package main

import (
	"fmt"
	"log"
	"math"
	"os"
	"os/signal"
	"syscall"

	"github.com/gen2brain/malgo"
	"github.com/jordan-lenchitz/listening/go/pkg/dsp"
	"github.com/jordan-lenchitz/listening/go/pkg/tracking"
)

const (
	SampleRate  = 22050
	FrameLength = 4096
	HopLength   = 512
)

func main() {
	ctx, err := malgo.InitContext(nil, malgo.ContextConfig{}, func(message string) {
		fmt.Printf("LOG: %v", message)
	})
	if err != nil {
		log.Fatal(err)
	}
	defer func() {
		_ = ctx.Uninit()
		ctx.Free()
	}()

	deviceConfig := malgo.DefaultDeviceConfig(malgo.Capture)
	deviceConfig.Capture.Format = malgo.FormatF32
	deviceConfig.Capture.Channels = 1
	deviceConfig.SampleRate = SampleRate
	deviceConfig.Alsa.NoMMap = 1

	tracker := tracking.NewMultiF0Tracker(nil)
	tracker.Config.SampleRate = SampleRate
	tracker.Config.FrameLength = FrameLength
	tracker.Config.HopLength = HopLength

	af := tracking.NewAffordanceField(float64(SampleRate), FrameLength)
	dt := tracking.NewDualProcessTracker(tracker.Config.MinFreq, tracker.Config.MaxFreq, 60)
	stft := dsp.NewSTFT(FrameLength, HopLength)
	freqs := stft.FFTFrequencies(SampleRate)

	samplesChan := make(chan []float32, 100)
	stopChan := make(chan os.Signal, 1)
	signal.Notify(stopChan, os.Interrupt, syscall.SIGTERM)

	onRec := func(pSample2, pSample []byte, frameCount uint32) {
		samples := make([]float32, frameCount)
		for i := uint32(0); i < frameCount; i++ {
			samples[i] = math.Float32frombits(uint32(pSample[i*4]) | uint32(pSample[i*4+1])<<8 | uint32(pSample[i*4+2])<<16 | uint32(pSample[i*4+3])<<24)
		}
		samplesChan <- samples
	}

	deviceCallbacks := malgo.DeviceCallbacks{
		Data: onRec,
	}

	device, err := malgo.InitDevice(ctx.Context, deviceConfig, deviceCallbacks)
	if err != nil {
		log.Fatal(err)
	}
	defer device.Uninit()

	err = device.Start()
	if err != nil {
		log.Fatal(err)
	}

	fmt.Println("Real-time tracking started... Press Ctrl+C to stop.")

	go func() {
		var buffer []float64
		for {
			newSamples := <-samplesChan
			for _, s := range newSamples {
				buffer = append(buffer, float64(s))
			}

			for len(buffer) >= FrameLength {
				frame := buffer[:FrameLength]

				buffer = buffer[HopLength:]

				coeffs := stft.Compute(frame)
				if len(coeffs) == 0 {
					continue
				}
				frameCoeffs := coeffs[0]
				mag := make([]float64, len(frameCoeffs))
				for i, c := range frameCoeffs {
					mag[i] = math.Sqrt(real(c)*real(c) + imag(c)*imag(c))
				}

				field := af.Update(mag)
				f0Candidates, salience := tracker.ComputeSalience(mag, freqs, field)
				salience = dt.HarmonicCombWeight(salience)
				peaks := tracker.DetectPeaks(f0Candidates, salience)
				tracker.Update(peaks, dt.TransitionMatrix, dt.FreqGrid)

				fmt.Printf("\rFrame %d | Active Voices: %d   ", tracker.CurrentFrame, countActive(tracker.Tracks))
			}
		}
	}()

	<-stopChan
	fmt.Println("\nStopping...")

	fmt.Println("Final Tracking Results:")
	for _, track := range tracker.Tracks {
		if track.State == tracking.ACTIVE || track.State == tracking.TERMINATED {
			if len(track.Pitches) > 10 {
				fmt.Printf("Track %d: StartFrame=%d, Duration=%d, AvgPitch=%.2f Hz\n",
					track.ID, track.StartFrame, len(track.Pitches), average(track.Pitches))
			}
		}
	}
}

func countActive(tracks []*tracking.VoiceTrack) int {
	count := 0
	for _, t := range tracks {
		if t.State == tracking.ACTIVE {
			count++
		}
	}
	return count
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
