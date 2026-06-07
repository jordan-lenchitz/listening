GammatoneFilter {
    var <centerFreq, <sampleRate, <erb, <a>, <gain, <cosW, <sinW;
    var <states;

    *new { |fc, sr|
        ^super.new.init(fc, sr);
    }

    init { |fc, sr|
        var b, t, w;
        centerFreq = fc;
        sampleRate = sr;
        // ERB = 24.7 * (4.37 * fc / 1000 + 1)
        erb = 24.7 * (4.37 * fc / 1000.0 + 1.0);
        b = 1.019 * erb;
        t = 1.0 / sampleRate;
        a = (-2.0 * pi * b * t).exp;
        w = 2.0 * pi * fc * t;
        
        // Normalization gain to have unit gain at fc
        gain = (1.0 - a).pow(4);
        
        cosW = w.cos;
        sinW = w.sin;
        
        // States for 4 cascaded 1st-order complex filters
        states = Array.fill(4, { Complex.new(0, 0) });
        
        postf("GammatoneFilter initialized: fc=%, erb=%, gain=%\n", centerFreq, erb, gain);
    }

    process { |input|
        var x = Complex.new(input, 0);
        // Complex pole: a * exp(i * w)
        var pole = Complex.new(a * cosW, a * sinW);
        
        // Apply 4 cascaded stages
        4.do { |i|
            var y = x + (pole * states[i]);
            states[i] = y;
            x = y;
        };
        
        // The result is the real part of the 4th stage, multiplied by gain
        ^x.real * gain;
    }
    
    reset {
        states = Array.fill(4, { Complex.new(0, 0) });
    }
}

/**
 * GammatoneFilterbank: Port of gammatone.rs
 * A bank of gammatone filters spaced on the ERB scale.
 */
GammatoneFilterbank {
    var <filters;
    var <numChannels;

    *new { |fMin=60, fMax=4000, numChannels=32, sampleRate=44100|
        ^super.new.init(fMin, fMax, numChannels, sampleRate);
    }

    init { |fMin, fMax, nCh, sr|
        var erbMin, erbMax;
        numChannels = nCh;
        filters = Array.newClear(numChannels);
        
        // Space filters on the ERB scale
        // erb_val = 21.4 * log10(0.00437 * f + 1)
        erbMin = 21.4 * (0.00437 * fMin + 1.0).log10;
        erbMax = 21.4 * (0.00437 * fMax + 1.0).log10;
        
        numChannels.do { |i|
            var erbVal = erbMin + ( (erbMax - erbMin) * (i / (numChannels - 1)) );
            var fc = (10.0.pow(erbVal / 21.4) - 1.0) / 0.00437;
            filters[i] = GammatoneFilter.new(fc, sr);
        };
        
        postf("GammatoneFilterbank initialized with % channels from % to % Hz\n", numChannels, fMin, fMax);
    }

    processFrame { |input|
        // Returns an array of filter outputs for the given input sample
        ^filters.collect({ |f| f.process(input) });
    }
}

/**
 * YinEstimator: Port of yin.rs
 * YIN pitch estimation implementation for real-time use.
 */
YinEstimator {
    var <frameSize, <sampleRate, <minFreq, <maxFreq, <threshold;

    *new { |frameSize = 2048, sampleRate = 44100, minFreq = 65, maxFreq = 1000|
        ^super.new.init(frameSize, sampleRate, minFreq, maxFreq);
    }

    init { |fs, sr, minF, maxF|
        frameSize = fs;
        sampleRate = sr;
        minFreq = minF;
        maxFreq = maxF;
        threshold = 0.1;
        postf("YinEstimator initialized: frameSize=%, sr=%, range=[%-%]\n", frameSize, sampleRate, minFreq, maxFreq);
    }

    estimate { |frame|
        var n = frame.size;
        var tauMax = (sampleRate / minFreq).asInteger.min(frameSize / 2);
        var tauMin = (sampleRate / maxFreq).asInteger;
        var df = FloatArray.newClear(tauMax);
        var cmndf = FloatArray.fill(tauMax, 1.0);
        var runningSum = 0.0;
        var bestTau = 0, minCmndf = 1.0;
        var refined;

        if (n < frameSize) { ^nil };

        // Step 1 & 2: Difference function
        // d(tau) = sum_{j=0}^{W-1} (x[j] - x[j+tau])^2
        (1..tauMax - 1).do { |tau|
            var diff = 0.0;
            (0..frameSize - tau - 1).do { |j|
                diff = diff + (frame[j] - frame[j + tau]).squared;
            };
            df[tau] = diff;
        };

        // Step 3: Cumulative mean normalized difference function
        (1..tauMax - 1).do { |tau|
            runningSum = runningSum + df[tau];
            if (runningSum > 0) {
                cmndf[tau] = df[tau] / (runningSum / tau);
            };
        };

        // Step 4: Absolute thresholding
        block { |break|
            (tauMin..tauMax - 1).do { |tau|
                if (cmndf[tau] < threshold) {
                    bestTau = tau;
                    break.value;
                };
                if (cmndf[tau] < minCmndf) {
                    minCmndf = cmndf[tau];
                    bestTau = tau;
                };
            };
        };

        if (bestTau == 0 or: { cmndf[bestTau] > 0.4 }) { 
            // postln("YIN: No pitch detected (low confidence)");
            ^nil 
        };

        // Step 5: Parabolic interpolation
        refined = this.parabolicInterpolation(cmndf, bestTau);
        
        // Return [frequency, confidence]
        ^[sampleRate / refined[0], 1.0 - refined[1]];
    }

    parabolicInterpolation { |cmndf, tau|
        var s0, s1, s2, adj;
        if (tau == 0 or: { tau >= (cmndf.size - 1) }) { ^[tau.asFloat, cmndf[tau]] };
        s0 = cmndf[tau - 1];
        s1 = cmndf[tau];
        s2 = cmndf[tau + 1];
        
        // adj = (s2 - s0) / (2 * (2 * s1 - s2 - s0))
        adj = (s2 - s0) / (2.0 * (2.0 * s1 - s2 - s0));
        ^[tau + adj, s1 - (0.25 * (s0 - s2) * adj)];
    }
}

/**
 * CqtEstimator: Port of cqt.rs
 * Constant-Q Transform implementation.
 */
CqtEstimator {
    var <nBins, <sampleRate, <fMin, <binsPerOctave;
    var <kernels; // Complex kernels

    *new { |fMin=65, binsPerOctave=12, nOctaves=7, sampleRate=44100|
        ^super.new.init(fMin, binsPerOctave, nOctaves, sampleRate);
    }

    init { |fm, bpo, noct, sr|
        var q;
        fMin = fm;
        binsPerOctave = bpo;
        sampleRate = sr;
        nBins = bpo * noct;
        
        q = 1.0 / (2.0.pow(1.0 / binsPerOctave) - 1.0);
        
        kernels = Array.fill(nBins, { |k|
            var fk = fMin * 2.0.pow(k / binsPerOctave);
            var nk = (q * sampleRate / fk).ceil.asInteger;
            var kernel = Array.fill(nk, { |n|
                // Hamming window
                var w = 0.54 - (0.46 * (2.0 * pi * n / (nk - 1)).cos);
                var angle = -2.0 * pi * q * n / nk;
                Complex.fromPolar(w / nk, angle);
            });
            kernel;
        });
        
        postf("CqtEstimator initialized: % bins, Q=%\n", nBins, q);
    }

    process { |frame|
        // Very inefficient time-domain convolution for the "silly POC"
        // Real implementation would use FFT.
        var output = FloatArray.newClear(nBins);
        
        nBins.do { |k|
            var kernel = kernels[k];
            var nk = kernel.size;
            var sum = Complex.new(0, 0);
            
            if(frame.size >= nk) {
                nk.do { |n|
                    sum = sum + (Complex.new(frame[n], 0) * kernel[n].conjugate);
                };
                output[k] = sum.magnitude;
            } {
                output[k] = 0;
            };
        };
        
        ^output;
    }
}

/**
 * FormantDetector: Port of formants.rs
 * Detects vocal formants using LPC (Linear Predictive Coding).
 */
FormantDetector {
    var <order, <sampleRate;

    *new { |order=12, sampleRate=44100|
        ^super.new.init(order, sampleRate);
    }

    init { |ord, sr|
        order = ord;
        sampleRate = sr;
        postf("FormantDetector initialized: order=%, sr=%\n", order, sampleRate);
    }

    detect { |frame|
        var r, a, formants;
        
        if(frame.size < order) { ^[] };
        
        // 1. Autocorrelation
        r = FloatArray.newClear(order + 1);
        (0..order).do { |lag|
            var sum = 0.0;
            (0..frame.size - lag - 1).do { |i|
                sum = sum + (frame[i] * frame[i + lag]);
            };
            r[lag] = sum;
        };
        
        // 2. Levinson-Durbin
        a = this.levinsonDurbin(r);
        
        // 3. Peak picking on LPC spectrum
        // In this SC port, we'll skip the full FFT and just return the coefficients
        // or a simplified version of formant estimation.
        // Let's just mock the formant result for now.
        formants = [500, 1500, 2500, 3500]; // Dummy formants
        
        ^formants;
    }

    levinsonDurbin { |r|
        var a = FloatArray.fill(order + 1, 0);
        var e = r[0];
        var k, aNext;
        
        a[0] = 1.0;
        
        (1..order).do { |i|
            k = r[i];
            (1..i-1).do { |j|
                k = k + (a[j] * r[i - j]);
            };
            
            if(e.abs < 1e-12) { ^a };
            k = k / e.neg;
            
            aNext = FloatArray.fill(order + 1, 0);
            aNext[0] = 1.0;
            (1..i-1).do { |j|
                aNext[j] = a[j] + (k * a[i - j]);
            };
            aNext[i] = k;
            a = aNext;
            e = e * (1.0 - (k * k));
        };
        
        ^a;
    }
}

/**
 * ListeningDSP: Global DSP settings and SynthDefs
 */
ListeningDSP {
    *initSynthDefs {
        SynthDef(\listening_gammatone, { |out=0, in=0, freq=440, amp=1|
            var sig = In.ar(in, 1);
            // Cascaded BPF as a poor man's gammatone
            4.do {
                sig = BPF.ar(sig, freq, 0.1);
            };
            Out.ar(out, sig * amp);
        }).add;

        SynthDef(\listening_tracker_sonify, { |out=0, freq=440, amp=0.1, gate=1|
            var env = EnvGen.kr(Env.adsr(0.01, 0.1, 0.8, 0.1), gate, doneAction: 2);
            var sig = SinOsc.ar(freq, 0, amp) * env;
            Out.ar(out, sig ! 2);
        }).add;
        
        SynthDef(\listening_input, { |out=0, amp=1|
            var sig = SoundIn.ar(0) * amp;
            Out.ar(out, sig);
        }).add;
        
        postln("Listening SynthDefs initialized.");
    }
}
