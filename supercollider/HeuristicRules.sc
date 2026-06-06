HeuristicEngine {
    var <rules;

    *new {
        ^super.new.init;
    }

    init {
        rules = List.new;
        this.addDefaultRules;
    }

    addDefaultRules {
        // Rule 1: Common Fate - components that change together belong together
        rules.add({ |tracks|
            var score = 0.0;
            if(tracks.size < 2) { ^0.0 };
            // Compare frequency derivatives
            score = 1.0 - (tracks[0].deriv - tracks[1].deriv).abs.mean;
            score;
        });

        // Rule 2: Harmonicity - integer multiples of a fundamental
        rules.add({ |tracks|
            var f0 = tracks.minItem({ |t| t.freq }).freq;
            var score = 1.0;
            tracks.do { |t|
                var ratio = t.freq / f0;
                var error = (ratio - ratio.round).abs;
                if(error > 0.1) { score = score * 0.8 };
            };
            score;
        });

        // Rule 3: Spectral Continuity
        rules.add({ |tracks|
            var score = 1.0;
            tracks.do { |t|
                if(t.history.size > 2) {
                    var lastDiff = (t.history.last.freq - t.history[t.history.size-2].freq).abs;
                    if(lastDiff > 50) { score = score * 0.7 };
                };
            };
            score;
        });
    }

    evaluate { |candidateGroup|
        var totalScore = 0.0;
        rules.do { |rule|
            totalScore = totalScore + rule.value(candidateGroup);
        };
        ^(totalScore / rules.size);
    }
}

/**
 * CommonFateMonitor: Specifically tracks synchronized frequency/amplitude modulation.
 */
CommonFateMonitor {
    var <trackData;

    *new {
        ^super.new.init;
    }

    init {
        trackData = Dictionary.new;
    }

    observe { |id, freq, amp|
        if(trackData[id].isNil) { trackData[id] = List.new };
        trackData[id].add((freq: freq, amp: amp, time: Main.elapsedTime));
        if(trackData[id].size > 20) { trackData[id].removeAt(0) };
    }

    checkCoherence { |id1, id2|
        var data1 = trackData[id1];
        var data2 = trackData[id2];
        var correlation = 0.0;
        
        if(data1.isNil or: {data2.isNil} or: {data1.size < 10} or: {data2.size < 10}) { ^0.0 };
        
        // Compute correlation of frequency changes
        correlation = this.correlate(
            data1.collect(_[\freq]).differentiate.drop(1),
            data2.collect(_[\freq]).differentiate.drop(1)
        );
        
        ^correlation;
    }

    correlate { |a, b|
        var ma, mb, num=0.0, den1=0.0, den2=0.0;
        var size = a.size.min(b.size);
        ma = a.mean;
        mb = b.mean;
        size.do { |i|
            var da = a[i] - ma;
            var db = b[i] - mb;
            num = num + (da * db);
            den1 = den1 + (da * da);
            den2 = den2 + (db * db);
        };
        if(den1 * den2 == 0) { ^0.0 };
        ^(num / (den1.sqrt * den2.sqrt));
    }
}
