package main

import (
	"math"
	"os"

	"github.com/go-audio/audio"
	"github.com/go-audio/wav"
)

func main() {
	sr := 22050
	f, err := os.Create("test.wav")
	if err != nil {
		panic(err)
	}
	defer f.Close()

	e := wav.NewEncoder(f, sr, 16, 1, 1)
	
	duration := 2.0
	numSamples := int(float64(sr) * duration)
	buf := &audio.IntBuffer{
		Data:           make([]int, numSamples),
		Format:         &audio.Format{SampleRate: sr, NumChannels: 1},
		SourceBitDepth: 16,
	}

	f1 := 220.0 // A3
	f2 := 330.0 // E4
	for i := 0; i < numSamples; i++ {
		t := float64(i) / float64(sr)
		// Add some harmonics to make it more interesting for salience
		v := 0.5*math.Sin(2*math.Pi*f1*t) + 0.25*math.Sin(2*math.Pi*2*f1*t) +
			0.4*math.Sin(2*math.Pi*f2*t) + 0.2*math.Sin(2*math.Pi*2*f2*t)
		buf.Data[i] = int(v * 16384) // Keep it well within 16-bit range
	}
	e.Write(buf)
	e.Close()
}

