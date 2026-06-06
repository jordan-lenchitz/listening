ExtendedListeningTracker {
    var <asa, <db, <pm, <sc, <yin, <filterbank, <schemaManager;
    var <currentSessionId;
    var <isProcessing = false;

    *new {
        ^super.new.init;
    }

    init {
        asa = ASAManager.new;
        db = F0TrackerDB.new;
        pm = PerceptualModel.new;
        sc = SalienceComputer.new;
        yin = YinEstimator.new;
        filterbank = GammatoneFilterbank.new;
        schemaManager = SchemaManager.new;
        
        postln("ExtendedListeningTracker: Full system stack initialized.");
    }

    startSession { |id|
        currentSessionId = id;
        asa.initSession(id);
        isProcessing = true;
        postf("ExtendedListeningTracker: Session '%' started.\n", id);
    }

    processFrame { |frame, time|
        var pitch, salience, candidates, peaks;
        
        if(isProcessing.not) { ^nil };

        // 1. Fundamental Frequency Estimation (YIN)
        pitch = yin.estimate(frame);
        
        // 2. Harmonic Salience Computation
        // (Mock spectrum and freqs for this demo)
        candidates = sc.computeSalience(frame.abs, Array.series(frame.size, 0, 20));
        peaks = sc.detectPeaks(candidates[0], candidates[1]);

        // 3. Perceptual Integration
        if(pitch.notNil) {
            var freq = pitch[0];
            var conf = pitch[1];
            var persistentVal = pm.persist(freq, conf, 0.5, 0.01);
            var changeVal = pm.change(freq, conf, 0.5, 0.01);
            
            // 4. Database Storage
            db.pushFrame(time * 100, 1, freq, persistentVal);
            
            // 5. Affordance Recording
            asa.recordAffordance(currentSessionId, time, freq, persistentVal, "PITCH");
            
            if(changeVal > 0.5) {
                asa.recordAffordance(currentSessionId, time, freq, changeVal, "ONSET");
            };
        };

        // 6. Schema Matching
        if(peaks.size > 0) {
            var bestPeak = peaks.maxItem({ |p| p[\salience] });
            var schemaMatch = schemaManager.matchSchema([bestPeak[\freq]], [bestPeak[\salience]]);
            if(schemaMatch[1] > 0.8) {
                asa.recordAffordance(currentSessionId, time, bestPeak[\freq], schemaMatch[1], schemaMatch[0]);
            };
        };
    }

    stopSession {
        isProcessing = false;
        db.processFrames;
        db.report;
        postf("ExtendedListeningTracker: Session '%' stopped and reported.\n", currentSessionId);
    }
}

/**
 * SpectralCoherenceMonitor: Monitors temporal and spectral coherence.
 * Essential for grouping disparate spectral components into a single object.
 */
SpectralCoherenceMonitor {
    var <coherenceMatrix;
    var <trackHistory;

    *new {
        ^super.new.init;
    }

    init {
        coherenceMatrix = Dictionary.new;
        trackHistory = Dictionary.new;
    }

    update { |trackId, freq, magnitude|
        if(trackHistory[trackId].isNil) { trackHistory[trackId] = List.new };
        trackHistory[trackId].add((freq: freq, mag: magnitude, time: Main.elapsedTime));
        
        if(trackHistory[trackId].size > 50) { trackHistory[trackId].removeAt(0) };
        
        this.computeInternalCoherence(trackId);
    }

    computeInternalCoherence { |trackId|
        var history = trackHistory[trackId];
        var coherence = 1.0;
        
        if(history.size < 2) { ^1.0 };
        
        // Simple coherence check: frequency stability
        (1..history.size-1).do { |i|
            var diff = (history[i][\freq] - history[i-1][\freq]).abs;
            if(diff > 20) { coherence = coherence * 0.9 };
        };
        
        coherenceMatrix[trackId] = coherence;
        ^coherence;
    }
}

/**
 * AttentionalAffordanceField: Implements the 2D field of listening affordances.
 */
AttentionalAffordanceField {
    var <field; // 2D array [time][freq]
    var <maxTimeSteps, <maxFreqBins;

    *new { |timeSteps=1000, freqBins=500|
        ^super.new.init(timeSteps, freqBins);
    }

    init { |ts, fb|
        maxTimeSteps = ts;
        maxFreqBins = fb;
        field = Array.fill(maxTimeSteps, { FloatArray.newClear(maxFreqBins) });
        postf("AttentionalAffordanceField initialized: %x%\n", maxTimeSteps, maxFreqBins);
    }

    setAffordance { |timeStep, freqBin, value|
        if(timeStep < maxTimeSteps and: { freqBin < maxFreqBins }) {
            field[timeStep][freqBin] = value;
        };
    }

    getAffordance { |timeStep, freqBin|
        if(timeStep < maxTimeSteps and: { freqBin < maxFreqBins }) {
            ^field[timeStep][freqBin];
        };
        ^0.0;
    }
    
    // Smooth the field using a simple 2D box filter
    blur {
        var newField = Array.fill(maxTimeSteps, { FloatArray.newClear(maxFreqBins) });
        (1..maxTimeSteps-2).do { |t|
            (1..maxFreqBins-2).do { |f|
                var sum = 0.0;
                (-1..1).do { |dt|
                    (-1..1).do { |df|
                        sum = sum + field[t+dt][f+df];
                    };
                };
                newField[t][f] = sum / 9.0;
            };
        };
        field = newField;
        postln("Affordance Field smoothed.");
    }
}

/**
 * BatchAudioProcessor: Port of Python logic for batch processing.
 */
BatchAudioProcessor {
    var <tracker;

    *new { |trackerInstance|
        ^super.new.init(trackerInstance);
    }

    init { |ti|
        tracker = ti;
    }

    processFolder { |path|
        var files = path.asString.pathMatch;
        postf("BatchAudioProcessor: Found % files in %\n", files.size, path);
        
        files.do { |file|
            this.processFile(file);
        };
    }

    processFile { |file|
        var soundFile, buffer, data;
        postf("BatchAudioProcessor: Processing %\n", file);
        
        soundFile = SoundFile.new;
        if(soundFile.openRead(file)) {
            data = FloatArray.newClear(soundFile.numFrames);
            soundFile.readData(data);
            soundFile.close;
            
            tracker.startSession(PathName(file).fileNameWithoutExtension);
            // Process data in chunks...
            tracker.stopSession;
        } {
            postf("ERROR: Could not open file %\n", file);
        };
    }
}