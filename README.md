# listening to *a cappella* singing: an ecological approach

two complementary computational approaches to the same sound:
- a **competition model** that asks "which partials win?" (the multi-pitch tracker)
- an **affordance model** that asks "where does the sound invite spectral listening, and how strongly?" (the affordance field)

my dissertation argues that certain [pitches of spectral fission](https://youtu.be/m1SKJ5ZA5HI?si=vIj75nll8JCKxYak&t=100) are perceived by listeners who have learned to take up their affordance. trackers sometimes find these only as a side effect, whence the affordance field showing where their perception is structurally supported

## files

core:
- `MultiF0Tracker.m` and `multi_f0_tracker.py` = competition-model tracker.
- `TrackingResult.m` = matlab result container. visualize, export, summarize.
- `AffordanceField.m` = ecological-model field. peripheral availability times affordance features, integrated into a time-frequency field.

## quick start, matlab

```matlab
[audio, sr] = audioread("your_audio.wav");
tracker = MultiF0Tracker();
result = tracker.track(audio, sr);
result.visualize();
result.summary();
```

## quick start, python

```python
from multi_f0_tracker import analyze_audio_file, visualize_tracks
result = analyze_audio_file("your_audio.wav")
visualize_tracks(result, "output.png")
```

## affordance field, matlab

```matlab
[audio, sr] = audioread("your_audio.wav");
field = AffordanceField(SampleRate=sr);
A = field.compute(audio);
field.visualize(A);
```
