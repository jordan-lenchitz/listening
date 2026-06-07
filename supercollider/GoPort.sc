SalienceComputer {
    var <config;

    *new { |peakThreshold=0.1|
        ^super.new.init(peakThreshold);
    }

    init { |peakThresh|
        config = (
            minFreq: 65.0,
            maxFreq: 2000.0,
            peakThreshold: peakThresh
        );
    }

    // Compute salience (Port of ComputeSalience in Go)
    computeSalience { |spectrum, freqs, affordance|
        var nBins = 500;
        var f0Candidates = FloatArray.newClear(nBins);
        var minLog = config[\minFreq].log10;
        var maxLog = config[\maxFreq].log10;
        var step = (maxLog - minLog) / (nBins - 1);
        var salience = FloatArray.newClear(nBins);
        var nHarmonics = 6;
        var harmonicWeights = [1.0, 0.8, 0.6, 0.5, 0.4, 0.3];
        var maxSal = 0.0;

        nBins.do { |i|
            f0Candidates[i] = 10.pow(minLog + (i * step));
        };

        f0Candidates.do { |f0, i|
            var total = 0.0;
            block { |break|
                (1..nHarmonics).do { |h|
                    var fh = f0 * h;
                    var idx, window = 3, start, end, maxVal = 0.0;
                    
                    if (fh > freqs.last) { break.value };
                    
                    idx = this.findNearest(freqs, fh);
                    start = (idx - window).max(0);
                    end = (idx + window).min(spectrum.size - 1);
                    
                    (start..end).do { |k|
                        if(spectrum[k] > maxVal) { maxVal = spectrum[k] };
                    };
                    total = total + (harmonicWeights[h-1] * maxVal);
                };
            };

            if(affordance.notNil) {
                var affIdx = this.findNearest(freqs, f0);
                total = total * affordance[affIdx];
            };

            salience[i] = total;
            if(total > maxSal) { maxSal = total };
        };

        if(maxSal > 0) {
            salience.do { |v, i| salience[i] = v / maxSal };
        };

        ^[f0Candidates, salience];
    }

    findNearest { |freqs, target|
        var low = 0, high = freqs.size - 1, mid;
        while { low <= high } {
            mid = ((low + high) / 2).asInteger;
            if (freqs[mid] < target) {
                low = mid + 1;
            } {
                if (freqs[mid] > target) {
                    high = mid - 1;
                } {
                    ^mid;
                }
            };
        };
        if (low >= freqs.size) { ^freqs.size - 1 };
        if (high < 0) { ^0 };
        if ((freqs[low] - target).abs < (freqs[high] - target).abs) { ^low } { ^high };
    }

    // Detect peaks (Port of DetectPeaks in Go)
    detectPeaks { |f0Candidates, salience|
        var peaks = List.new;
        (1..salience.size - 2).do { |i|
            if (salience[i] > salience[i-1] and: { salience[i] > salience[i+1] } and: { salience[i] >= config[\peakThreshold] }) {
                var alpha = salience[i-1];
                var beta = salience[i];
                var gamma = salience[i+1];
                var denom = alpha - (2 * beta) + gamma;
                
                if (denom.abs > 1e-10) {
                    var offset = 0.5 * (alpha - gamma) / denom;
                    var logF0 = f0Candidates[i].log2;
                    var logStep = (f0Candidates[i+1] / f0Candidates[i]).log2;
                    var refinedFreq = 2.pow(logF0 + (offset * logStep));
                    peaks.add((freq: refinedFreq, salience: beta));
                } {
                    peaks.add((freq: f0Candidates[i], salience: beta));
                };
            };
        };
        ^peaks;
    }
}

/**
 * TrackingResultPort: Port of result.go
 * Visualizes tracking results.
 */
TrackingResultPort {
    var <times, <sungVoices, <sampleRate, <hopLength;

    *new { |times, sungVoices, sampleRate=44100, hopLength=512|
        ^super.new.init(times, sungVoices, sampleRate, hopLength);
    }

    init { |t, sv, sr, hl|
        times = t;
        sungVoices = sv;
        sampleRate = sr;
        hopLength = hl;
    }

    // Visualize (Mock of Visualize in Go using SC Plotter)
    visualize { |title="Tracking Results"|
        var plotter = Plotter(title, Rect(200, 200, 800, 500));
        var data = List.new;
        
        sungVoices.do { |v|
            var voiceData = FloatArray.newClear(times.size);
            v[\frames].do { |frmIdx, i|
                if(frmIdx < times.size) {
                    voiceData[frmIdx] = v[\pitches][i];
                };
            };
            data.add(voiceData);
        };
        
        plotter.plot(data);
        plotter.setProperties((
            gridOnX: true,
            gridOnY: true,
            labelX: "Time (s)",
            labelY: "Frequency (Hz)"
        ));
        
        postf("Visualization '%' displayed.\n", title);
    }
}
