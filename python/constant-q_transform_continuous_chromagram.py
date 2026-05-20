import librosa
import librosa.display
import numpy as np
import matplotlib.pyplot as plt

# load the audio file
audio_path = "file.wav"
y, sr = librosa.load(audio_path, sr=44100)

# compute the continuous chromagram using constant-q transform (CQT)
fmin = 200  # Minimum frequency for CQT
bins_per_octave = 48  # Higher resolution for better pitch tracking
n_octaves = 6  # Number of octaves to analyze

cqt = librosa.cqt(
    y,
    sr=sr,
    fmin=fmin,
    bins_per_octave=bins_per_octave,
    n_bins=bins_per_octave * n_octaves,
)
chromagram = librosa.amplitude_to_db(np.abs(cqt), ref=np.max)
times = librosa.times_like(cqt, sr=sr)

# generate the frequency labels for better visualization
freqs = librosa.cqt_frequencies(
    n_bins=chromagram.shape[0], fmin=fmin, bins_per_octave=bins_per_octave
)

# plot it
fig, ax = plt.subplots(figsize=(12, 6))
img = librosa.display.specshow(
    chromagram,
    x_axis="time",
    y_axis="cqt_note",
    sr=sr,
    fmin=fmin,
    bins_per_octave=bins_per_octave,
    ax=ax,
)

ax.set_title("Continuous Chromagram")
ax.set_ylabel("Pitch (Musical Notes)")
fig.colorbar(img, ax=ax, format="%+2.0f dB")

# show the plot
plt.show()
