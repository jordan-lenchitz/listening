DSPUtils {
    // Windowing functions
    *hamming { |n|
        ^FloatArray.fill(n, { |i| 0.54 - (0.46 * (2.0 * pi * i / (n - 1)).cos) });
    }

    *hann { |n|
        ^FloatArray.fill(n, { |i| 0.5 * (1.0 - (2.0 * pi * i / (n - 1)).cos) });
    }

    *blackman { |n|
        ^FloatArray.fill(n, { |i|
            0.42 - (0.5 * (2.0 * pi * i / (n - 1)).cos) + (0.08 * (4.0 * pi * i / (n - 1)).cos)
        });
    }

    // Normalization
    *normalize { |array|
        var max = array.abs.maxItem;
        if(max > 0) { ^array / max } { ^array };
    }

    // RMS calculation
    *rms { |array|
        var sum = 0;
        array.do { |x| sum = sum + x.squared };
        ^(sum / array.size).sqrt;
    }

    // Zero-crossing rate
    *zcr { |array|
        var count = 0;
        (1..array.size-1).do { |i|
            if((array[i] >= 0 and: { array[i-1] < 0 }) or: { array[i] < 0 and: { array[i-1] >= 0 } }) {
                count = count + 1;
            };
        };
        ^count / array.size;
    }

    // Spectral centroid (simplified)
    *spectralCentroid { |mag, freqs|
        var sumNum = 0, sumDen = 0;
        mag.do { |m, i|
            sumNum = sumNum + (m * freqs[i]);
            sumDen = sumDen + m;
        };
        if(sumDen > 0) { ^sumNum / sumDen } { ^0 };
    }
}
