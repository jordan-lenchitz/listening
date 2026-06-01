package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math"
	"net/http"

	"github.com/go-audio/wav"
)

type STFTRequest struct {
	Audio       []float64 `json:"audio"`
	FrameLength int       `json:"frame_length"`
	HopLength   int       `json:"hop_length"`
}

type STFTResponse struct {
	Coefficients [][]Complex `json:"coefficients"`
}

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

type VisualizeRequest struct {
	Tracks     interface{} `json:"tracks"`
	Times      []float64   `json:"times"`
	SampleRate int         `json:"sample_rate"`
	HopLength  int         `json:"hop_length"`
	Title      string      `json:"title"`
}

func main() {
	http.HandleFunc("/process", handleProcess)
	log.Println("Orchestrator starting on :8080")
	log.Fatal(http.ListenAndServe(":8080", nil))
}

func handleProcess(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	file, _, err := r.FormFile("audio")
	if err != nil {
		http.Error(w, "Missing audio file", http.StatusBadRequest)
		return
	}
	defer file.Close()

	d := wav.NewDecoder(file)
	if !d.IsValidFile() {
		http.Error(w, "Invalid WAV file", http.StatusBadRequest)
		return
	}

	buf, err := d.FullPCMBuffer()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	samples := make([]float64, len(buf.Data))
	maxVal := math.Pow(2, float64(buf.SourceBitDepth-1))
	for i, v := range buf.Data {
		samples[i] = float64(v) / maxVal
	}

	sr := int(d.SampleRate)
	fl := 4096
	hl := 512

	stftReq := STFTRequest{
		Audio:       samples,
		FrameLength: fl,
		HopLength:   hl,
	}
	stftData, _ := json.Marshal(stftReq)
	resp, err := http.Post("http://localhost:8081/stft", "application/json", bytes.NewBuffer(stftData))
	if err != nil {
		http.Error(w, "DSP service error: "+err.Error(), http.StatusInternalServerError)
		return
	}
	var stftResp STFTResponse
	json.NewDecoder(resp.Body).Decode(&stftResp)
	resp.Body.Close()

	trackReq := TrackingRequest{
		Coefficients: stftResp.Coefficients,
		SampleRate:   sr,
		HopLength:    hl,
		FrameLength:  fl,
	}
	trackData, _ := json.Marshal(trackReq)
	resp, err = http.Post("http://localhost:8082/track", "application/json", bytes.NewBuffer(trackData))
	if err != nil {
		http.Error(w, "Tracking service error: "+err.Error(), http.StatusInternalServerError)
		return
	}
	var tracks interface{}
	json.NewDecoder(resp.Body).Decode(&tracks)
	resp.Body.Close()

	numFrames := len(stftResp.Coefficients)
	times := make([]float64, numFrames)
	for i := range times {
		times[i] = float64(i*hl) / float64(sr)
	}

	vizReq := VisualizeRequest{
		Tracks:     tracks,
		Times:      times,
		SampleRate: sr,
		HopLength:  hl,
		Title:      "Microservices Pitch Tracking",
	}
	vizData, _ := json.Marshal(vizReq)
	resp, err = http.Post("http://localhost:8083/visualize", "application/json", bytes.NewBuffer(vizData))
	if err != nil {
		http.Error(w, "Visualizer service error: "+err.Error(), http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "image/png")
	io.Copy(w, resp.Body)
}
