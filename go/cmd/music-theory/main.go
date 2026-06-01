package main

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"

	"github.com/jordan-lenchitz/listening/go/pkg/music"
)

type JIRequest struct {
	BaseFreq float64 `json:"base_freq"`
	RatioNum int     `json:"ratio_num"`
	RatioDen int     `json:"ratio_den"`
}

type JIResponse struct {
	TargetFreq float64 `json:"target_freq"`
	CentsDiff  float64 `json:"cents_diff"`
}

func main() {
	http.HandleFunc("/calculate", handleCalculate)
	log.Println("Music-Theory service starting on :8087")
	log.Fatal(http.ListenAndServe(":8087", nil))
}

func handleCalculate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req JIRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, strings.ToLower(err.Error()), http.StatusBadRequest)
		return
	}
	ji := music.NewJustIntonation(req.BaseFreq)
	target, diff := ji.CalculateRatio(req.RatioNum, req.RatioDen)
	resp := JIResponse{
		TargetFreq: target,
		CentsDiff:  diff,
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}
