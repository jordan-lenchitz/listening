package dsp

import (
	"math"
	"gonum.org/v1/gonum/dsp/fourier"
)

type STFT struct {
	FrameLength int
	HopLength   int
	Window      []float64
	fft         *fourier.FFT
}

func NewSTFT(frameLength, hopLength int) *STFT {
	window := make([]float64, frameLength)
	for i := 0; i < frameLength; i++ {
		// Hann window
		window[i] = 0.5 * (1 - math.Cos(2*math.Pi*float64(i)/float64(frameLength-1)))
	}
	return &STFT{
		FrameLength: frameLength,
		HopLength:   hopLength,
		Window:      window,
		fft:         fourier.NewFFT(frameLength),
	}
}

func (s *STFT) Compute(audio []float64) [][]complex128 {
	numFrames := (len(audio)-s.FrameLength)/s.HopLength + 1
	if numFrames <= 0 {
		return nil
	}

	result := make([][]complex128, numFrames)
	frame := make([]float64, s.FrameLength)

	for i := 0; i < numFrames; i++ {
		start := i * s.HopLength
		for j := 0; j < s.FrameLength; j++ {
			if start+j < len(audio) {
				frame[j] = audio[start+j] * s.Window[j]
			} else {
				frame[j] = 0
			}
		}
		coeffs := s.fft.Coefficients(nil, frame)
		result[i] = make([]complex128, len(coeffs))
		copy(result[i], coeffs)
	}
	return result
}

func (s *STFT) FFTFrequencies(sampleRate int) []float64 {
	n := s.FrameLength/2 + 1
	freqs := make([]float64, n)
	for i := range freqs {
		freqs[i] = float64(i) * float64(sampleRate) / float64(s.FrameLength)
	}
	return freqs
}
