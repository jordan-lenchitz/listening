package music

import (
	"math"
	"testing"
)

func TestJustIntonation_Chord(t *testing.T) {
	ji := JustIntonation{}
	root := 100.0
	ratios := [][2]int{{3, 2}, {5, 4}}
	expected := []float64{150.0, 125.0}
	got := ji.Chord(root, ratios)

	for i, v := range got {
		if math.Abs(v-expected[i]) > 1e-9 {
			t.Errorf("Chord() got[%d] = %v, want %v", i, v, expected[i])
		}
	}
}

func TestJustIntonation_Cents(t *testing.T) {
	ji := JustIntonation{}
	f1, f2 := 440.0, 880.0
	expected := 1200.0
	got := ji.Cents(f1, f2)
	if math.Abs(got-expected) > 1e-9 {
		t.Errorf("Cents() = %v, want %v", got, expected)
	}
}

func TestJustIntonation_NearestNoteName(t *testing.T) {
	ji := JustIntonation{}
	tests := []struct {
		freq float64
		want string
	}{
		{440.0, "A4"},
		{261.63, "C4"},
		{466.16, "A#4"},
	}
	for _, tt := range tests {
		if got := ji.NearestNoteName(tt.freq, 440.0); got != tt.want {
			t.Errorf("NearestNoteName(%v) = %v, want %v", tt.freq, got, tt.want)
		}
	}
}

func TestJustIntonation_CombinationTones(t *testing.T) {
	ji := JustIntonation{}
	freqs := []float64{200.0, 300.0}
	// Difference: 100
	// Cubic: 2*200 - 300 = 100, 2*300 - 200 = 400
	got := ji.CombinationTones(freqs, "all")
	expected := map[float64]bool{100.0: true, 400.0: true}
	
	if len(got) != 3 { // 100 (diff), 100 (cubic), 400 (cubic)
		t.Errorf("CombinationTones() length = %v, want 3", len(got))
	}
	
	for _, v := range got {
		if !expected[v] {
			t.Errorf("CombinationTones() unexpected tone %v", v)
		}
	}
}
