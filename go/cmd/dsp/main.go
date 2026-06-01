package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jordan-lenchitz/listening/go/pkg/dsp"
)

type stftRequest struct {
	Audio       []float64 `json:"audio"`
	FrameLength int       `json:"frame_length"`
	HopLength   int       `json:"hop_length"`
}

type stftResponse struct {
	Coefficients [][]complexData `json:"coefficients"`
}

type complexData struct {
	Real float64 `json:"real"`
	Imag float64 `json:"imag"`
}

type server struct {
	logger *slog.Logger
}

func (s *server) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /stft", s.handleSTFT)
	return mux
}

func (s *server) handleSTFT(w http.ResponseWriter, r *http.Request) {
	var req stftRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		s.logger.Error("decode failed", "error", err)
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}

	if req.FrameLength <= 0 || req.HopLength <= 0 || len(req.Audio) == 0 {
		http.Error(w, "invalid parameters", http.StatusUnprocessableEntity)
		return
	}

	stft := dsp.NewSTFT(req.FrameLength, req.HopLength)
	coeffs := stft.Compute(req.Audio)

	res := stftResponse{
		Coefficients: make([][]complexData, len(coeffs)),
	}

	for i, frame := range coeffs {
		res.Coefficients[i] = make([]complexData, len(frame))
		for j, c := range frame {
			res.Coefficients[i][j] = complexData{
				Real: real(c),
				Imag: imag(c),
			}
		}
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(res); err != nil {
		s.logger.Error("encode failed", "error", err)
	}
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	srv := &server{logger: logger}

	httpSrv := &http.Server{
		Addr:         ":8081",
		Handler:      srv.routes(),
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  time.Minute,
	}

	go func() {
		logger.Info("starting dsp service", "addr", httpSrv.Addr)
		if err := httpSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("listen failed", "error", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := httpSrv.Shutdown(ctx); err != nil {
		logger.Error("shutdown failed", "error", err)
	}
}
