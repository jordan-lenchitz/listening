package tracking

import (
	"testing"
)

func TestAffordanceField_Update(t *testing.T) {
	sr := 22050.0
	frameSize := 1024
	af := NewAffordanceField(sr, frameSize)

	mag := make([]float64, frameSize/2+1)
	// Create a single peak
	mag[10] = 1.0

	field := af.Update(mag)
	if len(field) != len(mag) {
		t.Errorf("Update() returned field with length %d, want %d", len(field), len(mag))
	}

	// Field should be non-zero near peak
	if field[10] == 0 {
		t.Errorf("Update() field[10] is 0, want > 0")
	}

	// Update again to check persistence
	field2 := af.Update(mag)
	if field2[10] == 0 {
		t.Errorf("Update() second pass field[10] is 0, want > 0")
	}
}
