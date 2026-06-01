package tracking

import (
	"math"
)

func (m *MultiF0Tracker) ComputeSalience(spectrum []float64, freqs []float64) ([]float64, []float64) {
	nBins := 500
	f0Candidates := make([]float64, nBins)
	minLog := math.Log10(m.Config.MinFreq)
	maxLog := math.Log10(m.Config.MaxFreq)
	step := (maxLog - minLog) / float64(nBins-1)
	for i := 0; i < nBins; i++ {
		f0Candidates[i] = math.Pow(10, minLog+float64(i)*step)
	}

	salience := make([]float64, nBins)
	nHarmonics := 6
	harmonicWeights := []float64{1.0, 0.8, 0.6, 0.5, 0.4, 0.3}

	for i, f0 := range f0Candidates {
		var total float64
		for h := 1; h <= nHarmonics; h++ {
			fh := f0 * float64(h)
			if fh > freqs[len(freqs)-1] {
				break
			}
			// Find nearest frequency bin
			idx := m.findNearest(freqs, fh)
			// Add weighted magnitude (with tolerance window)
			window := 3
			start := idx - window
			if start < 0 {
				start = 0
			}
			end := idx + window + 1
			if end > len(spectrum) {
				end = len(spectrum)
			}
			
			maxVal := 0.0
			for k := start; k < end; k++ {
				if spectrum[k] > maxVal {
					maxVal = spectrum[k]
				}
			}
			total += harmonicWeights[h-1] * maxVal
		}
		salience[i] = total
	}

	// Normalize
	maxSal := 0.0
	for _, v := range salience {
		if v > maxSal {
			maxSal = v
		}
	}
	if maxSal > 0 {
		for i := range salience {
			salience[i] /= maxSal
		}
	}

	return f0Candidates, salience
}

func (m *MultiF0Tracker) findNearest(freqs []float64, target float64) int {
	low, high := 0, len(freqs)-1
	for low <= high {
		mid := low + (high-low)/2
		if freqs[mid] < target {
			low = mid + 1
		} else if freqs[mid] > target {
			high = mid - 1
		} else {
			return mid
		}
	}
	if low >= len(freqs) {
		return len(freqs) - 1
	}
	if high < 0 {
		return 0
	}
	if math.Abs(freqs[low]-target) < math.Abs(freqs[high]-target) {
		return low
	}
	return high
}

type Peak struct {
	Freq     float64
	Salience float64
}

func (m *MultiF0Tracker) DetectPeaks(f0Candidates []float64, salience []float64) []Peak {
	var peaks []Peak
	for i := 1; i < len(salience)-1; i++ {
		if salience[i] > salience[i-1] && salience[i] > salience[i+1] && salience[i] >= m.Config.PeakThreshold {
			// Parabolic interpolation
			alpha := salience[i-1]
			beta := salience[i]
			gamma := salience[i+1]
			
			denom := alpha - 2*beta + gamma
			if math.Abs(denom) > 1e-10 {
				offset := 0.5 * (alpha - gamma) / denom
				
				logF0 := math.Log2(f0Candidates[i])
				logStep := math.Log2(f0Candidates[i+1] / f0Candidates[i])
				refinedFreq := math.Pow(2, logF0+offset*logStep)
				
				peaks = append(peaks, Peak{Freq: refinedFreq, Salience: beta})
			} else {
				peaks = append(peaks, Peak{Freq: f0Candidates[i], Salience: beta})
			}
		}
	}
	return peaks
}
