package tracking

import (
	"fmt"
	"image/color"

	"gonum.org/v1/plot"
	"gonum.org/v1/plot/plotter"
	"gonum.org/v1/plot/vg"
)

type TrackingResult struct {
	Times        []float64
	SungVoices   []*VoiceTrack
	ExtraPitches []*VoiceTrack
	SampleRate   int
	HopLength    int
}

func (tr *TrackingResult) Visualize(outputPath string, title string) error {
	p := plot.New()
	p.Title.Text = title
	p.X.Label.Text = "Time (seconds)"
	p.Y.Label.Text = "Frequency (Hz)"

	colors := []color.Color{
		color.RGBA{R: 46, G: 134, B: 171, A: 255},
		color.RGBA{R: 162, G: 59, B: 114, A: 255},
		color.RGBA{R: 241, G: 143, B: 1, A: 255},
		color.RGBA{R: 199, G: 62, B: 29, A: 255},
		color.RGBA{R: 39, G: 174, B: 96, A: 255},
	}

	for i, v := range tr.SungVoices {
		pts := make(plotter.XYs, 0, len(v.Pitches))
		for j := range v.Pitches {
			idx := v.Frames[j]

			idx--
			if idx >= 0 && idx < len(tr.Times) {
				pts = append(pts, plotter.XY{X: tr.Times[idx], Y: v.Pitches[j]})
			}
		}
		if len(pts) == 0 {
			continue
		}
		line, err := plotter.NewLine(pts)
		if err != nil {
			return err
		}
		line.Color = colors[i%len(colors)]
		line.Width = vg.Points(2)
		p.Add(line)
		p.Legend.Add(fmt.Sprintf("Voice %d", i+1), line)
	}

	for _, g := range tr.ExtraPitches {
		pts := make(plotter.XYs, len(g.Pitches))
		for j := range g.Pitches {
			pts[j].X = tr.Times[g.Frames[j]]
			pts[j].Y = g.Pitches[j]
		}
		line, err := plotter.NewLine(pts)
		if err != nil {
			return err
		}
		line.Color = color.RGBA{R: 128, G: 0, B: 128, A: 180}
		line.Dashes = []vg.Length{vg.Points(2), vg.Points(2)}
		p.Add(line)
	}

	return p.Save(14*vg.Inch, 8*vg.Inch, outputPath)
}
