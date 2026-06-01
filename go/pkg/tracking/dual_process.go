package tracking

import (
	"math"
)

type DualProcessTracker struct {
	Fmin             float64
	Fmax             float64
	GridBinsPerOct   int
	FreqGrid         []float64
	TransitionMatrix [][]float64
	SigmaCents       float64
	AlphaBase        float64
	FadeFactor       float64
	VoicingThresh    float64
	HarmCombWidth    int
}

func NewDualProcessTracker(fmin, fmax float64, binsPerOct int) *DualProcessTracker {
	nOct := math.Log2(fmax / fmin)
	nBins := int(math.Ceil(nOct * float64(binsPerOct)))
	freqGrid := make([]float64, nBins)
	for i := 0; i < nBins; i++ {
		freqGrid[i] = fmin * math.Pow(2, float64(i)/float64(binsPerOct))
	}

	dt := &DualProcessTracker{
		Fmin:           fmin,
		Fmax:           fmax,
		GridBinsPerOct: binsPerOct,
		FreqGrid:       freqGrid,
		SigmaCents:     25.0,
		AlphaBase:      0.6,
		FadeFactor:     0.98,
		VoicingThresh:  0.2,
		HarmCombWidth:  4,
	}
	dt.buildTransitionMatrix()
	return dt
}

func (dt *DualProcessTracker) buildTransitionMatrix() {
	n := len(dt.FreqGrid)
	matrix := make([][]float64, n)
	for i := range matrix {
		matrix[i] = make([]float64, n)
	}

	lg := make([]float64, n)
	for i, f := range dt.FreqGrid {
		lg[i] = math.Log(f)
	}

	for j := 0; j < n; j++ {
		sigmaLn := (dt.SigmaCents / 1200.0) / (dt.FreqGrid[j] / 1000.0)
		sum := 0.0
		for i := 0; i < n; i++ {
			val := math.Exp(-math.Pow(lg[i]-lg[j], 2) / (2 * math.Pow(sigmaLn, 2)))
			matrix[i][j] = val
			sum += val
		}
		if sum > 0 {
			for i := 0; i < n; i++ {
				matrix[i][j] /= sum
			}
		}
	}
	dt.TransitionMatrix = matrix
}

func (dt *DualProcessTracker) HarmonicCombWeight(P []float64) []float64 {
	n := len(P)
	combP := make([]float64, n)
	copy(combP, P)
	for m := 2; m <= dt.HarmCombWidth; m++ {
		shift := int(math.Round(float64(n) / float64(m)))
		if shift < n {
			for i := 0; i < n-shift; i++ {
				combP[i] += P[i+shift] / float64(m*m)
			}
		}
	}
	return combP
}
