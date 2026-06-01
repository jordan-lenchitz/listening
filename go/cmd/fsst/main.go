package main

import (
	"encoding/json"
	"log"
	"net/http"

	"github.com/jordan-lenchitz/listening/go/pkg/dsp"
)

type FSSTRequest struct {
	Audio       []float64 `json:"audio"`
	FrameLength int       `json:"frame_length"`
	HopLength   int       `json:"hop_length"`
	SampleRate  int       `json:"sample_rate"`
}

type Complex struct {
	Real float64 `json:"real"`
	Imag float64 `json:"imag"`
}

type FSSTResponse struct {
	Coefficients [][]Complex `json:"coefficients"`
}

func main() {
	http.HandleFunc("/fsst", handleFSST)
	log.Println("FSST service starting on :8088")
	log.Fatal(http.ListenAndServe(":8088", nil))
}

func handleFSST(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	var req FSSTRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	s := dsp.NewSTFT(req.FrameLength, req.HopLength)
	coeffs := s.Compute(req.Audio)
	fsst := dsp.NewFSST(req.SampleRate, req.FrameLength, req.HopLength)
	fsstCoeffs := fsst.Compute(coeffs)
	
	respCoeffs := make([][]Complex, len(fsstCoeffs))
	for i, frame := range fsstCoeffs {
		respCoeffs[i] = make([]Complex, len(frame))
		for j, c := range frame {
			respCoeffs[i][j] = Complex{Real: real(c), Imag: imag(c)}
		}
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(FSSTResponse{Coefficients: respCoeffs})
}
