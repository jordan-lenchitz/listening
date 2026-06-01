package tracking

import (
	"math"
	"sort"
)

type VoiceState int

const (
	ACTIVE VoiceState = iota
	TENTATIVE
	INACTIVE
	TERMINATED
)

type VoiceTrack struct {
	ID             int
	StartFrame     int
	Pitches        []float64
	Confidences    []float64
	Frames         []int
	State          VoiceState
	InactiveCount  int
	TentativeCount int
	IsExtraPitch   bool
}

func (t *VoiceTrack) EndFrame() int {
	if len(t.Frames) == 0 {
		return t.StartFrame
	}
	return t.Frames[len(t.Frames)-1]
}

func (t *VoiceTrack) LastPitch() float64 {
	if len(t.Pitches) == 0 {
		return 0
	}
	return t.Pitches[len(t.Pitches)-1]
}

func (t *VoiceTrack) Duration() int {
	return len(t.Frames)
}

func (t *VoiceTrack) AddObservation(frame int, pitch float64, confidence float64) {
	t.Frames = append(t.Frames, frame)
	t.Pitches = append(t.Pitches, pitch)
	t.Confidences = append(t.Confidences, confidence)
}

type TrackerConfig struct {
	SampleRate                    int
	HopLength                     int
	FrameLength                   int
	MinFreq                       float64
	MaxFreq                       float64
	MaxVoices                     int
	PeakThreshold                 float64
	MinPeakDistanceCents          float64
	MaxPitchJumpCents             float64
	AssignmentCostScale           float64
	TentativeFrames               int
	InactiveFrames                int
	DetectExtraPitches            bool
	CombinationToneToleranceCents float64
	OvertoneToleranceCents        float64
}

func DefaultTrackerConfig() TrackerConfig {
	return TrackerConfig{
		SampleRate:                    22050,
		HopLength:                     512,
		FrameLength:                   4096,
		MinFreq:                       65.0,
		MaxFreq:                       1400.0,
		MaxVoices:                     8,
		PeakThreshold:                 0.1,
		MinPeakDistanceCents:          50,
		MaxPitchJumpCents:             300,
		AssignmentCostScale:           100,
		TentativeFrames:               3,
		InactiveFrames:                5,
		DetectExtraPitches:            true,
		CombinationToneToleranceCents: 30,
		OvertoneToleranceCents:        20,
	}
}

type MultiF0Tracker struct {
	Config       TrackerConfig
	Tracks       []*VoiceTrack
	NextTrackID  int
	CurrentFrame int
}

func NewMultiF0Tracker(config *TrackerConfig) *MultiF0Tracker {
	conf := DefaultTrackerConfig()
	if config != nil {
		conf = *config
	}
	return &MultiF0Tracker{
		Config: conf,
		Tracks: []*VoiceTrack{},
	}
}

func (m *MultiF0Tracker) HzToCents(freq, ref float64) float64 {
	if freq <= 0 || ref <= 0 {
		return 0
	}
	return 1200 * math.Log2(freq/ref)
}

func (m *MultiF0Tracker) CentsDistance(f1, f2 float64) float64 {
	if f1 <= 0 || f2 <= 0 {
		return math.Inf(1)
	}
	return math.Abs(1200 * math.Log2(f1/f2))
}

func (m *MultiF0Tracker) Update(peaks []Peak, transitionMatrix [][]float64, grid []float64) {
	m.CurrentFrame++

	activeTracks := m.getActiveTracks()

	if len(activeTracks) == 0 {
		for _, peak := range peaks {
			m.startNewTrack(peak)
		}
		return
	}

	if len(peaks) == 0 {
		for _, track := range activeTracks {
			m.markInactive(track)
		}
		return
	}

	costs := make([][]float64, len(activeTracks))
	for i, track := range activeTracks {
		costs[i] = make([]float64, len(peaks))
		for j, peak := range peaks {
			if transitionMatrix != nil && grid != nil {

				tIdx := m.findNearest(grid, track.LastPitch())
				pIdx := m.findNearest(grid, peak.Freq)
				prob := transitionMatrix[pIdx][tIdx]

				costs[i][j] = -math.Log(prob + 1e-6)
			} else {

				dist := m.CentsDistance(track.LastPitch(), peak.Freq)
				if dist > m.Config.MaxPitchJumpCents {
					costs[i][j] = m.Config.AssignmentCostScale
				} else {
					costs[i][j] = dist / m.Config.MaxPitchJumpCents
				}
			}
		}
	}

	assignedTracks := make(map[int]bool)
	assignedPeaks := make(map[int]bool)

	type assign struct {
		i, j int
		cost float64
	}
	var potentials []assign
	for i := range costs {
		for j := range costs[i] {
			if costs[i][j] < m.Config.AssignmentCostScale {
				potentials = append(potentials, assign{i, j, costs[i][j]})
			}
		}
	}
	sort.Slice(potentials, func(i, j int) bool {
		return potentials[i].cost < potentials[j].cost
	})

	for _, p := range potentials {
		if !assignedTracks[p.i] && !assignedPeaks[p.j] {
			activeTracks[p.i].AddObservation(m.CurrentFrame, peaks[p.j].Freq, peaks[p.j].Salience)
			activeTracks[p.i].InactiveCount = 0
			if activeTracks[p.i].State == TENTATIVE {
				activeTracks[p.i].TentativeCount++
				if activeTracks[p.i].TentativeCount >= m.Config.TentativeFrames {
					activeTracks[p.i].State = ACTIVE
				}
			} else if activeTracks[p.i].State == INACTIVE {
				activeTracks[p.i].State = ACTIVE
			}
			assignedTracks[p.i] = true
			assignedPeaks[p.j] = true
		}
	}

	for i, track := range activeTracks {
		if !assignedTracks[i] {
			m.markInactive(track)
		}
	}

	for j, peak := range peaks {
		if !assignedPeaks[j] {
			m.startNewTrack(peak)
		}
	}
}

func (m *MultiF0Tracker) getActiveTracks() []*VoiceTrack {
	var active []*VoiceTrack
	for _, t := range m.Tracks {
		if t.State == ACTIVE || t.State == TENTATIVE || t.State == INACTIVE {
			active = append(active, t)
		}
	}
	return active
}

func (m *MultiF0Tracker) startNewTrack(peak Peak) {
	track := &VoiceTrack{
		ID:             m.NextTrackID,
		StartFrame:     m.CurrentFrame,
		State:          TENTATIVE,
		TentativeCount: 1,
	}
	m.NextTrackID++
	track.AddObservation(m.CurrentFrame, peak.Freq, peak.Salience)
	m.Tracks = append(m.Tracks, track)
}

func (m *MultiF0Tracker) markInactive(t *VoiceTrack) {
	t.InactiveCount++
	if t.InactiveCount >= m.Config.InactiveFrames {
		t.State = TERMINATED
	} else {
		t.State = INACTIVE
	}
}
