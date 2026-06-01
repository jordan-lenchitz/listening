package music

import (
	"fmt"
	"math"
	"sort"
)

// JustIntonation provides helpers for building chords from integer ratios and musical calculations.
type JustIntonation struct{}

// Chord builds chord frequencies from a root and a slice of [num, den] pairs.
func (ji JustIntonation) Chord(rootHz float64, ratios [][2]int) []float64 {
	freqs := make([]float64, len(ratios))
	for i, ratio := range ratios {
		freqs[i] = rootHz * float64(ratio[0]) / float64(ratio[1])
	}
	return freqs
}

// Cents calculates the absolute cents distance between two frequencies.
func (ji JustIntonation) Cents(f1, f2 float64) float64 {
	return math.Abs(1200 * math.Log2(f1/f2))
}

// CentsFromEqualTempered calculates the signed cents deviation from the nearest equal-tempered pitch.
func (ji JustIntonation) CentsFromEqualTempered(freqs []float64, a4 float64) []float64 {
	if a4 == 0 {
		a4 = 440.0
	}
	cents := make([]float64, len(freqs))
	for i, f := range freqs {
		semis := 12 * math.Log2(f/a4)
		nearest := math.Round(semis)
		cents[i] = 100 * (semis - nearest)
	}
	return cents
}

// NearestNoteName returns the nearest twelve-tone note name with octave number.
func (ji JustIntonation) NearestNoteName(freq float64, a4 float64) string {
	if a4 == 0 {
		a4 = 440.0
	}
	names := []string{"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"}
	semisFromA4 := math.Round(12 * math.Log2(freq/a4))
	midi := 69 + int(semisFromA4)
	octave := (midi / 12) - 1
	pc := midi % 12
	// Handle negative modulo in Go if necessary, but midi is usually positive for audible frequencies
	if pc < 0 {
		pc += 12
	}
	return fmt.Sprintf("%s%d", names[pc], octave)
}

// CombinationTones generates expected combination tone frequencies for a set of frequencies.
// orders can be "difference", "cubic", or "all".
func (ji JustIntonation) CombinationTones(freqs []float64, orders string) []float64 {
	sortedFreqs := make([]float64, len(freqs))
	copy(sortedFreqs, freqs)
	sort.Float64s(sortedFreqs)

	var combos []float64
	n := len(sortedFreqs)
	for i := 0; i < n; i++ {
		for j := i + 1; j < n; j++ {
			f1, f2 := sortedFreqs[i], sortedFreqs[j]
			if orders == "difference" || orders == "all" {
				if f2-f1 > 0 {
					combos = append(combos, f2-f1)
				}
			}
			if orders == "cubic" || orders == "all" {
				if 2*f1-f2 > 0 {
					combos = append(combos, 2*f1-f2)
				}
				if 2*f2-f1 > 0 {
					combos = append(combos, 2*f2-f1)
				}
			}
		}
	}
	return combos
}
