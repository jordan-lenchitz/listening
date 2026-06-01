package main

import (
	"encoding/json"
	"log"
	"net/http"
	"os"
	"strings"

	"github.com/jordan-lenchitz/listening/go/pkg/tracking"
)

type VisualizeRequest struct {
	Tracks     []*tracking.VoiceTrack `json:"tracks"`
	Times      []float64              `json:"times"`
	SampleRate int                    `json:"sample_rate"`
	HopLength  int                    `json:"hop_length"`
	Title      string                 `json:"title"`
}

func main() {
	http.HandleFunc("/visualize", handleVisualize)
	log.Println("Visualizer service starting on :8083")
	log.Fatal(http.ListenAndServe(":8083", nil))
}

func handleVisualize(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req VisualizeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, strings.ToLower(err.Error()), http.StatusBadRequest)
		return
	}

	result := &tracking.TrackingResult{
		Times:      req.Times,
		SungVoices: req.Tracks,
		SampleRate: req.SampleRate,
		HopLength:  req.HopLength,
	}

	tmpFile := "temp_result.png"
	if err := result.Visualize(tmpFile, req.Title); err != nil {
		http.Error(w, strings.ToLower(err.Error()), http.StatusInternalServerError)
		return
	}
	defer os.Remove(tmpFile)

	data, err := os.ReadFile(tmpFile)
	if err != nil {
		http.Error(w, strings.ToLower(err.Error()), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "image/png")
	w.Write(data)
}
