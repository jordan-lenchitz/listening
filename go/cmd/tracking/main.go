package main

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"math"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jordan-lenchitz/listening/go/pkg/tracking"
)

type trackRequest struct {
	Coefficients [][]complexData `json:"coefficients"`
	SampleRate   int             `json:"sample_rate"`
	HopLength    int             `json:"hop_length"`
	FrameLength  int             `json:"frame_length"`
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
	mux.HandleFunc("POST /track", s.handleTrack)
	return mux
}

func (s *server) handleTrack(w http.ResponseWriter, r *http.Request) {
	var req trackRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		s.logger.Error("decode failed", "error", err)
		http.Error(w, "bad request", http.StatusBadRequest)
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
		cands, salience := tracker.ComputeSalience(mag, freqs, field)
		salience = dt.HarmonicCombWeight(salience)
		peaks := tracker.DetectPeaks(cands, salience)
		tracker.Update(peaks, dt.TransitionMatrix, dt.FreqGrid)
	}

	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(tracker.Tracks); err != nil {
		s.logger.Error("encode failed", "error", err)
	}
}

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	srv := &server{logger: logger}

	httpSrv := &http.Server{
		Addr:         ":8082",
		Handler:      srv.routes(),
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 30 * time.Second,
	}

	go func() {
		logger.Info("starting tracking service", "addr", httpSrv.Addr)
		if err := httpSrv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("listen failed", "error", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	httpSrv.Shutdown(ctx)
}
