package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log/slog"
	"math"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/go-audio/wav"
)

type stftRequest struct {
	Audio       []float64 `json:"audio"`
	FrameLength int       `json:"frame_length"`
	HopLength   int       `json:"hop_length"`
}

type stftResponse struct {
	Coefficients [][]complexData `json:"coefficients"`
}

type trackRequest struct {
	Coefficients [][]complexData `json:"coefficients"`
	SampleRate   int             `json:"sample_rate"`
	HopLength    int             `json:"hop_length"`
	FrameLength  int             `json:"frame_length"`
}

type vizRequest struct {
	Tracks     any       `json:"tracks"`
	Times      []float64 `json:"times"`
	SampleRate int       `json:"sample_rate"`
	HopLength  int       `json:"hop_length"`
	Title      string    `json:"title"`
}

type complexData struct {
	Real float64 `json:"real"`
	Imag float64 `json:"imag"`
}

type orchestrator struct {
	logger *slog.Logger
	client *http.Client
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

	stftResp, err := o.callDSP(r.Context(), samples, fl, hl)
	if err != nil {
		o.error(w, "dsp failure", err)
		return
	}

	tracks, err := o.callTracking(r.Context(), stftResp.Coefficients, sr, fl, hl)
	if err != nil {
		o.error(w, "tracking failure", err)
		return
	}

	times := make([]float64, len(stftResp.Coefficients))
	for i := range times {
		times[i] = float64(i*hl) / float64(sr)
	}

	viz, err := o.callVisualizer(r.Context(), tracks, times, sr, hl)
	if err != nil {
		o.error(w, "viz failure", err)
		return
	}
	defer viz.Close()

	w.Header().Set("Content-Type", "image/png")
	io.Copy(w, viz)
}

func (o *orchestrator) callDSP(ctx context.Context, audio []float64, fl, hl int) (*stftResponse, error) {
	data, _ := json.Marshal(stftRequest{Audio: audio, FrameLength: fl, HopLength: hl})
	req, _ := http.NewRequestWithContext(ctx, "POST", "http://localhost:8081/stft", bytes.NewReader(data))
	resp, err := o.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var res stftResponse
	return &res, json.NewDecoder(resp.Body).Decode(&res)
}

func (o *orchestrator) callTracking(ctx context.Context, coeffs [][]complexData, sr, fl, hl int) (any, error) {
	data, _ := json.Marshal(trackRequest{Coefficients: coeffs, SampleRate: sr, FrameLength: fl, HopLength: hl})
	req, _ := http.NewRequestWithContext(ctx, "POST", "http://localhost:8082/track", bytes.NewReader(data))
	resp, err := o.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	var res any
	return res, json.NewDecoder(resp.Body).Decode(&res)
}

func (o *orchestrator) callVisualizer(ctx context.Context, tracks any, times []float64, sr, hl int) (io.ReadCloser, error) {
	data, _ := json.Marshal(vizRequest{Tracks: tracks, Times: times, SampleRate: sr, HopLength: hl, Title: "Microservices Result"})
	req, _ := http.NewRequestWithContext(ctx, "POST", "http://localhost:8083/visualize", bytes.NewReader(data))
	resp, err := o.client.Do(req)
	if err != nil {
		return nil, err
	}
	return resp.Body, nil
}

func (o *orchestrator) error(w http.ResponseWriter, msg string, err error) {
	o.logger.Error(msg, "error", err)
	http.Error(w, msg, http.StatusBadGateway)
}

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	orch := &orchestrator{
		logger: log,
		client: &http.Client{Timeout: 60 * time.Second},
	}

	srv := &http.Server{
		Addr:    ":8080",
		Handler: orch.routes(),
	}

	go func() {
		log.Info("orchestrator live", "port", 8080)
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
