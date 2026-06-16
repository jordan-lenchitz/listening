package main

import (
	"context"
	"errors"
	"log/slog"
	"math"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-audio/wav"
	"github.com/jordan-lenchitz/listening/go/pkg/dsp"
	"github.com/jordan-lenchitz/listening/go/pkg/tracking"
)

type orchestrator struct {
	logger *slog.Logger
}

func (o *orchestrator) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /process", o.handleProcess)
	return mux
}

func (o *orchestrator) handleProcess(w http.ResponseWriter, r *http.Request) {
	file, _, err := r.FormFile("audio")
	if err != nil {
		http.Error(w, "missing audio", http.StatusBadRequest)
		return
	}
	defer file.Close()

	dec := wav.NewDecoder(file)
	if !dec.IsValidFile() {
		http.Error(w, "invalid wav", http.StatusBadRequest)
		return
	}

	buf, err := dec.FullPCMBuffer()
	if err != nil {
		o.logger.Error("decode failed", "error", err)
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}

	samples := make([]float64, len(buf.Data))
	max := math.Pow(2, float64(buf.SourceBitDepth-1))
	for i, v := range buf.Data {
		samples[i] = float64(v) / max
	}

	sr, fl, hl := int(dec.SampleRate), 4096, 512

	// 1. DSP (STFT)
	stft := dsp.NewSTFT(fl, hl)
	coeffs := stft.Compute(samples)

	if len(coeffs) == 0 {
		http.Error(w, "audio too short", http.StatusBadRequest)
		return
	}

	// 2. Tracking
	conf := tracking.DefaultTrackerConfig()
	conf.SampleRate = sr
	conf.HopLength = hl
	conf.FrameLength = fl

	tracker := tracking.NewMultiF0Tracker(&conf)
	af := tracking.NewAffordanceField(float64(sr), fl)
	dt := tracking.NewDualProcessTracker(conf.MinFreq, conf.MaxFreq, 60)

	freqs := make([]float64, fl/2+1)
	for i := range freqs {
		freqs[i] = float64(i) * float64(sr) / float64(fl)
	}

	for _, frame := range coeffs {
		mag := make([]float64, len(frame))
		for i, c := range frame {
			mag[i] = math.Sqrt(real(c)*real(c) + imag(c)*imag(c))
		}

		field := af.Update(mag)
		cands, salience := tracker.ComputeSalience(mag, freqs, field)
		salience = dt.HarmonicCombWeight(salience)
		peaks := tracker.DetectPeaks(cands, salience)
		tracker.Update(peaks, dt.TransitionMatrix, dt.FreqGrid)
	}

	// 3. Visualize
	times := make([]float64, len(coeffs))
	for i := range times {
		times[i] = float64(i*hl) / float64(sr)
	}

	result := &tracking.TrackingResult{
		Times:      times,
		SungVoices: tracker.Tracks,
		SampleRate: sr,
		HopLength:  hl,
	}

	tmpFile := "temp_result.png"
	if err := result.Visualize(tmpFile, "Monolith Result"); err != nil {
		o.logger.Error("visualize failed", "error", err)
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}
	defer os.Remove(tmpFile)

	data, err := os.ReadFile(tmpFile)
	if err != nil {
		o.logger.Error("read png failed", "error", err)
		http.Error(w, "internal error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "image/png")
	w.Write(data)
}

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	orch := &orchestrator{
		logger: log,
	}

	srv := &http.Server{
		Addr:    ":8080",
		Handler: orch.routes(),
	}

	go func() {
		log.Info("monolith backend live", "port", 8080)
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("fatal", "error", err)
			os.Exit(1)
		}
	}()

	done := make(chan os.Signal, 1)
	signal.Notify(done, syscall.SIGINT, syscall.SIGTERM)
	<-done

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	srv.Shutdown(ctx)
}
