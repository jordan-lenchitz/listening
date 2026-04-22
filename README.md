# listening

listening to · a cappella · singing: an ecological approach

companion code for the dissertation. two complementary approaches to the same sound:

- a **competition model** that asks "which partials win?" (the multi-pitch tracker)
- an **affordance model** that asks "where does the sound invite spectral listening, and how strongly?" (the affordance field)

the dissertation argues that ghost pitches - la quintina in sardinian tenores singing, the barbershop fifth voice - are not detected by any tracker. they are enacted by listeners who have learned to take up the affordance. the tracker finds them only as a side effect. the affordance field shows where the enactment is structurally supported.

## files

core:
- `MultiF0Tracker.m` and `multi_f0_tracker.py` · competition-model tracker. shared algorithm and parameter names across both languages.
- `TrackingResult.m` · matlab result container. visualize, export, summarize.
- `AffordanceField.m` · ecological-model field. peripheral availability times affordance features, integrated into a time-frequency field.

helpers:
- `justintonation.m` · build chords from integer ratios. used by both demos.

demos:
- `demo_barbershop.m` · synthetic dominant seventh in just intonation, staggered entries and exits. root, major third, perfect fifth, harmonic seventh.
- `demo_quintina.m` · synthetic sardinian tenores chord. four voices with strong overtones. the quintina emerges in the upper partials where the voices lock.
- `quick_start.m` · minimal usage.

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