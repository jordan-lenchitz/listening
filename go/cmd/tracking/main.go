package main

import (
	"encoding/json"
	"log"
	"math"
	"net/http"

	"github.com/jordan-lenchitz/listening/go/pkg/tracking"
)

type TrackingRequest struct {
	Coefficients [][]Complex `json:"coefficients"`
	SampleRate   int         `json:"sample_rate"`
	HopLength    int         `json:"hop_length"`
	FrameLength  int         `json:"frame_length"`
}

type Complex struct {
	Real float64 `json:"real"`
	Imag float64 `json:"imag"`
}

func main() {
	http.HandleFunc("/track", handleTrack)
	log.Println("Tracking service starting on :8082")
	log.Fatal(http.ListenAndServe(":8082", nil))
}

func handleTrack(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req TrackingRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	conf := tracking.DefaultTrackerConfig()
	conf.SampleRate = req.SampleRate
	conf.HopLength = req.HopLength
	conf.FrameLength = req.FrameLength

	tracker := tracking.NewMultiF0Tracker(&conf)
	af := tracking.NewAffordanceField(float64(req.SampleRate), req.FrameLength)
	dt := tracking.NewDualProcessTracker(conf.MinFreq, conf.MaxFreq, 60)

	freqs := make([]float64, req.FrameLength/2+1)
	for i := range freqs {
		freqs[i] = float64(i) * float64(req.SampleRate) / float64(req.FrameLength)
	}

	for _, frame := range req.Coefficients {
		mag := make([]float64, len(frame))
		for i, c := range frame {
			mag[i] = math.Sqrt(c.Real*c.Real + c.Imag*c.Imag)
		}

		field := af.Update(mag)
		f0Candidates, salience := tracker.ComputeSalience(mag, freqs, field)
		salience = dt.HarmonicCombWeight(salience)
		peaks := tracker.DetectPeaks(f0Candidates, salience)
		tracker.Update(peaks, dt.TransitionMatrix, dt.FreqGrid)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(tracker.Tracks)
}
