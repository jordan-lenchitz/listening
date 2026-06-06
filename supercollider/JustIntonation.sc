JustIntonation {
    *chord { |rootHz, ratios|
        // ratios should be an array of arrays, e.g., [[3, 2], [5, 4]]
        ^ratios.collect { |r| rootHz * r[0] / r[1] };
    }

    *cents { |f1, f2|
        ^(1200 * (f1 / f2).log2).abs;
    }

    *centsFromEqualTempered { |freqs, a4 = 440.0|
        ^freqs.collect { |f|
            var semis = 12 * (f / a4).log2;
            var nearest = semis.round;
            100 * (semis - nearest);
        };
    }

    *nearestNoteName { |freq, a4 = 440.0|
        var names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
        var semisFromA4 = (12 * (freq / a4).log2).round;
        var midi = 69 + semisFromA4;
        var octave = (midi / 12).floor - 1;
        var pc = midi.asInteger % 12;
        ^(names[pc] ++ octave.asString);
    }

    *combinationTones { |freqs, orders = 'all'|
        var sorted = freqs.sort;
        var n = sorted.size;
        var combos = List.new;
        n.do { |i|
            (i + 1 .. n - 1).do { |j|
                var f1 = sorted[i];
                var f2 = sorted[j];
                if (orders == 'difference' or: { orders == 'all' }) {
                    if (f2 - f1 > 0) { combos.add(f2 - f1) };
                };
                if (orders == 'cubic' or: { orders == 'all' }) {
                    if (2 * f1 - f2 > 0) { combos.add(2 * f1 - f2) };
                    if (2 * f2 - f1 > 0) { combos.add(2 * f2 - f1) };
                };
            };
        };
        ^combos.asArray;
    }
}

JustIntonationAdvisor {
    var <jiRatios;

    *new {
        ^super.new.init;
    }

    init {
        jiRatios = [
            [1.0, "1/1"],
            [16.0/15.0, "16/15"],
            [9.0/8.0, "9/8"],
            [6.0/5.0, "6/5"],
            [5.0/4.0, "5/4"],
            [4.0/3.0, "4/3"],
            [45.0/32.0, "45/32"],
            [3.0/2.0, "3/2"],
            [8.0/5.0, "8/5"],
            [5.0/3.0, "5/3"],
            [16.0/9.0, "16/9"],
            [15.0/8.0, "15/8"],
            [2.0, "2/1"]
        ];
    }

    getAdvice { |rootFreq, targetFreq|
        var ratio = targetFreq / rootFreq;
        var normRatio = ratio;
        var octaveShift = 0;
        var bestRatio = 1.0;
        var bestLabel = "1/1";
        var minDiff = 1e10;
        var idealFreq, centsDiff;

        while { normRatio < 1.0 } { normRatio = normRatio * 2.0; octaveShift = octaveShift - 1; };
        while { normRatio >= 2.0 } { normRatio = normRatio / 2.0; octaveShift = octaveShift + 1; };

        jiRatios.do { |pair|
            var r = pair[0];
            var label = pair[1];
            var diff = (normRatio / r).log.abs;
            if (diff < minDiff) {
                minDiff = diff;
                bestRatio = r * (2.0 ** octaveShift);
                bestLabel = label;
            };
        };

        idealFreq = bestRatio * rootFreq;
        centsDiff = 1200.0 * (targetFreq / idealFreq).log2;

        ^[idealFreq, bestLabel, centsDiff];
    }
}