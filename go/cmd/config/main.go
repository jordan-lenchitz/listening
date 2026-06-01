package main

import (
	"encoding/json"
	"log"
	"net/http"
)

type Config struct {
	SampleRate  int     `json:"sample_rate"`
	FrameLength int     `json:"frame_length"`
	HopLength   int     `json:"hop_length"`
	MinFreq     float64 `json:"min_freq"`
	MaxFreq     float64 `json:"max_freq"`
}

func main() {
	http.HandleFunc("/config", handleConfig)
	log.Println("Config service starting on :8090")
	log.Fatal(http.ListenAndServe(":8090", nil))
}

func handleConfig(w http.ResponseWriter, r *http.Request) {
	cfg := Config{
		SampleRate:  22050,
		FrameLength: 4096,
		HopLength:   512,
		MinFreq:     65.0,
		MaxFreq:     1400.0,
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(cfg)
}
