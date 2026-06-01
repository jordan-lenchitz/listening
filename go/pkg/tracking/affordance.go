package tracking

import (
	"math"
)

type AffordanceField struct {
	Frequencies []float64

	prevPresence   []float64
	persistence    []float64
	smoothPresence []float64

	PersistenceAlpha   float64
	ChangeAlpha        float64
	MaskingFloorDB     float64
	MaskingSpreadERB   float64
	DominanceLowHz     float64
	DominanceHighHz    float64
	DominanceWeight    float64
	ContinuityERBSigma float64
}

func NewAffordanceField(sampleRate float64, frameSize int) *AffordanceField {
	nBins := frameSize/2 + 1
	freqs := make([]float64, nBins)
	for i := range freqs {
		freqs[i] = float64(i) * sampleRate / float64(frameSize)
	}

	return &AffordanceField{
		Frequencies:        freqs,
		prevPresence:       make([]float64, nBins),
		persistence:        make([]float64, nBins),
		smoothPresence:     make([]float64, nBins),
		PersistenceAlpha:   0.95,
		ChangeAlpha:        0.8,
		MaskingFloorDB:     -60.0,
		MaskingSpreadERB:   1.5,
		DominanceLowHz:     500.0,
		DominanceHighHz:    2000.0,
		DominanceWeight:    1.0,
		ContinuityERBSigma: 0.5,
	}
}

func (af *AffordanceField) Update(mag []float64) []float64 {
	n := len(mag)
	if n != len(af.Frequencies) {

		return nil
	}

	maxMag := 0.0
	for _, v := range mag {
		if v > maxMag {
			maxMag = v
		}
	}
	presence := make([]float64, n)
	if maxMag > 0 {
		for i, v := range mag {
			presence[i] = v / maxMag
		}
	}

	availability := make([]float64, n)
	peakDB := math.Inf(-1)
	magDB := make([]float64, n)
	for i, v := range mag {
		db := 20.0 * math.Log10(v+1e-12)
		magDB[i] = db
		if db > peakDB {
			peakDB = db
		}
	}

	for i := range availability {
		rel := magDB[i] - peakDB
		val := (rel - af.MaskingFloorDB) / (0.0 - af.MaskingFloorDB)
		if val < 0 {
			val = 0
		} else if val > 1 {
			val = 1
		}
		availability[i] = val
	}

	availability = af.smoothAlongERB(availability, af.MaskingSpreadERB)

	maxAvail := 0.0
	for i := range availability {
		if af.Frequencies[i] >= af.DominanceLowHz && af.Frequencies[i] <= af.DominanceHighHz {
			availability[i] *= 1.0 + af.DominanceWeight
		}
		if availability[i] > maxAvail {
			maxAvail = availability[i]
		}
	}

	if maxAvail > 0 {
		for i := range availability {
			availability[i] /= maxAvail
		}
	}

	maxPers := 0.0
	normPersistence := make([]float64, n)
	for i := range af.persistence {
		af.persistence[i] = af.PersistenceAlpha*af.persistence[i] + (1.0-af.PersistenceAlpha)*presence[i]
		if af.persistence[i] > maxPers {
			maxPers = af.persistence[i]
		}
	}
	if maxPers > 0 {
		for i := range normPersistence {
			normPersistence[i] = af.persistence[i] / maxPers
		}
	}

	change := make([]float64, n)
	maxChange := 0.0
	for i := range af.smoothPresence {
		af.smoothPresence[i] = af.ChangeAlpha*af.smoothPresence[i] + (1.0-af.ChangeAlpha)*presence[i]
		val := presence[i] - af.smoothPresence[i]
		if val < 0 {
			val = 0
		}
		change[i] = val
		if change[i] > maxChange {
			maxChange = change[i]
		}
	}
	if maxChange > 0 {
		for i := range change {
			change[i] /= maxChange
		}
	}

	timeCoherent := make([]float64, n)
	hasPrev := false
	for _, v := range af.prevPresence {
		if v > 0 {
			hasPrev = true
			break
		}
	}

	for i := range timeCoherent {
		if !hasPrev {
			timeCoherent[i] = presence[i]
		} else {
			timeCoherent[i] = math.Sqrt(presence[i] * af.prevPresence[i])
		}
	}

	freqSmoothed := af.smoothAlongERB(presence, af.ContinuityERBSigma)
	freqCoherent := make([]float64, n)
	for i := range freqCoherent {
		val := 1.0 - math.Abs(presence[i]-freqSmoothed[i])
		if val < 0 {
			val = 0
		}
		freqCoherent[i] = val
	}

	continuity := make([]float64, n)
	maxCont := 0.0
	for i := range continuity {
		continuity[i] = timeCoherent[i] * freqCoherent[i]
		if continuity[i] > maxCont {
			maxCont = continuity[i]
		}
	}
	if maxCont > 0 {
		for i := range continuity {
			continuity[i] /= maxCont
		}
	}

	coherence := af.harmonicCoherence(mag)

	field := make([]float64, n)
	for i := range field {

		featSum := presence[i] + normPersistence[i] + continuity[i] + change[i]
		if featSum == 0 {
			field[i] = 0
			continue
		}

		eps := 0.01
		features := (presence[i] + eps) * (normPersistence[i] + eps) * (continuity[i] + eps) * (change[i] + eps) * (coherence[i] + eps)
		field[i] = availability[i] * math.Pow(features, 0.2)
	}

	copy(af.prevPresence, presence)

	return field
}

func (af *AffordanceField) harmonicCoherence(mag []float64) []float64 {
	n := len(mag)
	coherence := make([]float64, n)
	nHarmonics := 4
	weights := []float64{1.0, 0.5, 0.33, 0.25}

	binHz := af.Frequencies[1] - af.Frequencies[0]

	for i := 1; i < n; i++ {
		f0 := af.Frequencies[i]
		var score float64
		for h := 1; h <= nHarmonics; h++ {
			fh := f0 * float64(h)
			if fh > af.Frequencies[n-1] {
				break
			}
			idx := int(math.Round(fh / binHz))
			if idx < n {
				score += weights[h-1] * mag[idx]
			}
		}
		coherence[i] = score
	}

	maxCoh := 0.0
	for _, v := range coherence {
		if v > maxCoh {
			maxCoh = v
		}
	}
	if maxCoh > 0 {
		for i := range coherence {
			coherence[i] /= maxCoh
		}
	}
	return coherence
}

func (af *AffordanceField) smoothAlongERB(x []float64, sigmaERB float64) []float64 {
	n := len(x)
	y := make([]float64, n)
	binHz := 1.0
	if n > 1 {
		binHz = af.Frequencies[1] - af.Frequencies[0]
	}

	for i := 0; i < n; i++ {
		f := af.Frequencies[i]
		erb := 24.7 * (1.0 + 4.37*f/1000.0)
		sigmaHz := sigmaERB * erb
		sigmaBins := sigmaHz / binHz
		if sigmaBins < 1.0 {
			sigmaBins = 1.0
		}

		halfWin := int(math.Ceil(3.0 * sigmaBins))
		sumW := 0.0
		val := 0.0

		start := i - halfWin
		if start < 0 {
			start = 0
		}
		end := i + halfWin
		if end >= n {
			end = n - 1
		}

		for k := start; k <= end; k++ {
			diff := float64(k - i)
			weight := math.Exp(-0.5 * math.Pow(diff/sigmaBins, 2))
			val += x[k] * weight
			sumW += weight
		}
		if sumW > 0 {
			y[i] = val / sumW
		} else {
			y[i] = x[i]
		}
	}
	return y
}
