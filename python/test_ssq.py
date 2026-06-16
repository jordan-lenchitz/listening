import numpy as np
import ssqueezepy
from ssqueezepy import ssq_cwt, extract_ridges

audio = np.random.randn(16000)
Tx, Wx, ssq_freqs, scales, *rest = ssq_cwt(audio, fs=16000, nv=48)
ridges = extract_ridges(Tx, ssq_freqs, penalty=5, n_ridges=3)
print(type(ridges))
print(len(ridges))
if isinstance(ridges, tuple):
    for idx, r in enumerate(ridges):
        print(f"Item {idx}: type={type(r)} shape={np.shape(r)}")
else:
    print(ridges.shape)
