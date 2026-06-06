JustIntonationSystem {
    var <referenceFreq;
    var <ratios;

    *new { |ref=440|
        ^super.new.init(ref);
    }

    init { |ref|
        referenceFreq = ref;
        // Basic JI ratios
        ratios = (
            unison: 1/1,
            minorSecond: 16/15,
            majorSecond: 9/8,
            minorThird: 6/5,
            majorThird: 5/4,
            perfectFourth: 4/3,
            tritone: 45/32,
            perfectFifth: 3/2,
            minorSixth: 8/5,
            majorSixth: 5/3,
            minorSeventh: 9/5,
            majorSeventh: 15/8,
            octave: 2/1
        );
        postf("JustIntonationSystem initialized with ref=% Hz\n", referenceFreq);
    }

    getFreq { |intervalName, octave=0|
        var ratio = ratios[intervalName.asSymbol];
        if(ratio.isNil) { ^referenceFreq };
        ^(referenceFreq * ratio * (2.pow(octave)));
    }

    findNearestInterval { |freq|
        var cents = ScaleUtils.cents(referenceFreq, freq) % 1200;
        var minDiff = 1200, bestInterval = \unison;
        
        ratios.keysValuesDo { |name, ratio|
            var intervalCents = 1200 * (ratio.log / 2.log);
            var diff = (cents - intervalCents).abs;
            if(diff < minDiff) {
                minDiff = diff;
                bestInterval = name;
            };
        };
        
        ^[bestInterval, minDiff];
    }
}

/**
 * ChordAnalyzer: Identifies chords from a list of frequencies.
 */
ChordAnalyzer {
    var <jiSystem;

    *new {
        ^super.new.init;
    }

    init {
        jiSystem = JustIntonationSystem.new;
    }

    analyze { |freqs|
        var root, relativeCents, intervals;
        
        if(freqs.size == 0) { ^nil };
        
        // Assume lowest freq is root
        root = freqs.minItem;
        intervals = freqs.collect({ |f| jiSystem.findNearestInterval(f) });
        
        postf("ChordAnalyzer: Analyzing chord with root % Hz\n", root);
        intervals.do { |int|
            postf("  Interval: % (error: % cents)\n", int[0], int[1]);
        };
        
        ^this.identifyChord(intervals.collect(_[0]));
    }

    identifyChord { |intervalNames|
        var names = intervalNames.asSet;
        if(names.includes(\majorThird) and: { names.includes(\perfectFifth) }) { ^\MajorTriad };
        if(names.includes(\minorThird) and: { names.includes(\perfectFifth) }) { ^\MinorTriad };
        if(names.includes(\perfectFourth) and: { names.includes(\perfectFifth) }) { ^\Sus4 };
        ^\UnknownChord;
    }
}

/**
 * IntervalMonitor: Monitors harmonic intervals between active tracks.
 */
IntervalMonitor {
    var <activeIntervals;

    *new {
        ^super.new.init;
    }

    init {
        activeIntervals = Dictionary.new;
    }

    update { |tracks|
        var ids = tracks.keys.asArray.sort;
        if(ids.size < 2) { ^this };
        
        (0..ids.size-2).do { |i|
            (i+1..ids.size-1).do { |j|
                var f1 = tracks[ids[i]][\freq];
                var f2 = tracks[ids[j]][\freq];
                var cents = ScaleUtils.cents(f1, f2);
                activeIntervals[ids[i].asString ++ "_" ++ ids[j].asString] = cents;
            };
        };
    }
    
    report {
        postln("--- Harmonic Interval Report ---");
        activeIntervals.keysValuesDo { |pair, cents|
            postf("  Pair %: % cents\n", pair, cents);
        };
    }
}

/**
 * TuningSystem: Abstract base class for different tunings.
 */
TuningSystem {
    var <name;
    
    *new { |name|
        ^super.newCopyArgs(name);
    }
    
    freqToPitch { |freq| ^0 }
    pitchToFreq { |pitch| ^440 }
}

/**
 * PythagoreanTuning: Tuning based on pure fifths (3/2).
 */
PythagoreanTuning : TuningSystem {
    *new { ^super.new("Pythagorean") }
    
    pitchToFreq { |pitch|
        // Simplified Pythagorean calculation
        var fifths = pitch * 7 % 12;
        ^(440 * (1.5.pow(fifths)) / (2.pow((fifths * 7 / 12).asInteger)));
    }
}

/**
 * WerckmeisterTuning: A classic well-temperament.
 */
WerckmeisterTuning : TuningSystem {
    *new { ^super.new("Werckmeister III") }
    
    // Detailed offsets from ET in cents
    offsets {
        ^[0, -10, -8, -6, -10, -2, -12, -4, -8, -10, -6, -2];
    }
}