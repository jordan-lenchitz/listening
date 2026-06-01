package main

import (
	"encoding/json"
	"log"
	"net/http"

	"github.com/jordan-lenchitz/listening/go/pkg/dsp"
)

type STFTRequest struct {
	Audio       []float64 `json:"audio"`
	FrameLength int       `json:"frame_length"`
	HopLength   int       `json:"hop_length"`
}

type STFTResponse struct {
	Coefficients [][]Complex `json:"coefficients"`
}

type Complex struct {
	Real float64 `json:"real"`
	Imag float64 `json:"imag"`
}

func main() {
	http.HandleFunc("/stft", handleSTFT)
	log.Println("DSP service starting on :8081")
	log.Fatal(http.ListenAndServe(":8081", nil))
}

func handleSTFT(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req STFTRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	s := dsp.NewSTFT(req.FrameLength, req.HopLength)
	coeffs := s.Compute(req.Audio)

	respCoeffs := make([][]Complex, len(coeffs))
	for i, frame := range coeffs {
		respCoeffs[i] = make([]Complex, len(frame))
		for j, c := range frame {
			respCoeffs[i][j] = Complex{Real: real(c), Imag: imag(c)}
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(STFTResponse{Coefficients: respCoeffs})
}
