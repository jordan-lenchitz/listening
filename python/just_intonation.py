import numpy as np
from typing import List, Optional

class JustIntonation:
    """
    Helpers for building chords from integer ratios and musical calculations.
    Ported from MATLAB implementation.
    """
    @staticmethod
    def chord(root_hz: float, ratios: np.ndarray) -> np.ndarray:
        """
        Build chord frequencies from a root and an n-by-2 ratio matrix or list of pairs.
        """
        ratios = np.atleast_2d(ratios)
        freqs = root_hz * ratios[:, 0] / ratios[:, 1]
        return freqs

    @staticmethod
    def cents(f1: float, f2: float) -> float:
        """
        Absolute cents distance between two frequencies.
        """
        return np.abs(1200 * np.log2(f1 / f2))

    @staticmethod
    def cents_from_equal_tempered(freqs: np.ndarray, a4: float = 440.0) -> np.ndarray:
        """
        Signed cents deviation from the nearest equal-tempered pitch.
        Positive means sharp, negative means flat.
        """
        semis = 12 * np.log2(np.array(freqs) / a4)
        nearest = np.round(semis)
        return 100 * (semis - nearest)

    @staticmethod
    def nearest_note_name(freq: float, a4: float = 440.0) -> str:
        """
        Nearest twelve-tone note name with octave number.
        """
        names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        semis_from_a4 = int(round(12 * np.log2(freq / a4)))
        midi = 69 + semis_from_a4
        octave = (midi // 12) - 1
        pc = midi % 12
        return f"{names[pc]}{octave}"

    @staticmethod
    def combination_tones(freqs: np.ndarray, orders: str = "all") -> np.ndarray:
        """
        Generate expected combination tone frequencies for a set of sung pitches.
        """
        freqs = np.sort(freqs)
        n = len(freqs)
        combos = []
        for i in range(n):
            for j in range(i + 1, n):
                f1, f2 = freqs[i], freqs[j]
                if orders in ["difference", "all"]:
                    combos.append(f2 - f1)
                if orders in ["cubic", "all"]:
                    combos.append(2 * f1 - f2)
                    combos.append(2 * f2 - f1)
        return np.array([c for c in combos if c > 0])
