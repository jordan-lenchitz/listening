package dsp

import (
	"math"
	"math/cmplx"
)

func (s *STFT) FSST(stft [][]complex128, sampleRate float64) [][]float64 {
	numFrames := len(stft)
	if numFrames < 2 {
		return nil
	}
	nBins := len(stft[0])
	fsst := make([][]float64, numFrames)
	for i := range fsst {
		fsst[i] = make([]float64, nBins)
	}

	dt := float64(s.HopLength) / sampleRate

	for t := 1; t < numFrames; t++ {
		for f := 0; f < nBins; f++ {

			phase1 := cmplx.Phase(stft[t-1][f])
			phase2 := cmplx.Phase(stft[t][f])

			dPhase := phase2 - phase1

			for dPhase > math.Pi {
				dPhase -= 2 * math.Pi
			}
			for dPhase < -math.Pi {
				dPhase += 2 * math.Pi
			}

			ifFreq := (dPhase / (2 * math.Pi * dt))

			binHz := sampleRate / float64(s.FrameLength)
			ifIdx := int(math.Round(ifFreq / binHz))

			mag := cmplx.Abs(stft[t][f])
			if ifIdx >= 0 && ifIdx < nBins {
				fsst[t][ifIdx] += mag
			}
		}
	}

	for f := 0; f < nBins; f++ {
		fsst[0][f] = cmplx.Abs(stft[0][f])
	}

	return fsst
}
