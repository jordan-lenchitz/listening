VoiceState {
    *active { ^0 }
    *tentative { ^1 }
    *inactive { ^2 }
    *terminated { ^3 }
}

VoiceTrack {
    var <id, <startFrame, <pitches, <confidences, <frames;
    var <>state, <>inactiveCount, <>tentativeCount, <>isExtraPitch;

    *new { |id, startFrame|
        ^super.new.init(id, startFrame);
    }

    init { |argId, argStartFrame|
        id = argId;
        startFrame = argStartFrame;
        pitches = List.new;
        confidences = List.new;
        frames = List.new;
        state = VoiceState.tentative;
        inactiveCount = 0;
        tentativeCount = 0;
        isExtraPitch = false;
    }

    addObservation { |frame, pitch, confidence|
        frames.add(frame);
        pitches.add(pitch);
        confidences.add(confidence);
    }

    endFrame {
        ^if (frames.size > 0) { frames.last } { startFrame };
    }

    lastPitch {
        ^if (pitches.size > 0) { pitches.last } { 0.0 };
    }

    duration {
        ^frames.size;
    }
}

TrackerConfig {
    var <>sampleRate, <>hopLength, <>frameLength;
    var <>minFreq, <>maxFreq, <>maxVoices;
    var <>peakThreshold, <>minPeakDistanceCents;
    var <>maxPitchJumpCents, <>assignmentCostScale;
    var <>tentativeFrames, <>inactiveFrames;
    var <>detectExtraPitches;
    var <>combinationToneToleranceCents, <>overtoneToleranceCents;

    *new {
        ^super.new.init;
    }

    init {
        sampleRate = 22050;
        hopLength = 512;
        frameLength = 4096;
        minFreq = 65.0;
        maxFreq = 1400.0;
        maxVoices = 8;
        peakThreshold = 0.1;
        minPeakDistanceCents = 50;
        maxPitchJumpCents = 300;
        assignmentCostScale = 100;
        tentativeFrames = 3;
        inactiveFrames = 5;
        detectExtraPitches = true;
        combinationToneToleranceCents = 30;
        overtoneToleranceCents = 20;
    }
}

MultiF0Tracker {
    var <config, <tracks, <nextTrackId, <currentFrame;

    *new { |config|
        ^super.new.init(config);
    }

    init { |argConfig|
        config = argConfig ?? { TrackerConfig.new };
        tracks = List.new;
        nextTrackId = 0;
        currentFrame = 0;
    }

    hzToCents { |freq, ref = 440.0|
        if (freq <= 0 or: { ref <= 0 }) { ^0 };
        ^1200 * (freq / ref).log2;
    }

    centsDistance { |f1, f2|
        if (f1 <= 0 or: { f2 <= 0 }) { ^inf };
        ^(1200 * (f1 / f2).log2).abs;
    }

    computeSalience { |spectrum, freqs|
        var nBins = 500;
        var f0Candidates = Array.fill(nBins, { |i|
            config.minFreq * (config.maxFreq / config.minFreq).pow(i / (nBins - 1))
        });
        var salience = FloatArray.newClear(nBins);
        var nHarmonics = 6;
        var harmonicWeights = [1.0, 0.8, 0.6, 0.5, 0.4, 0.3];

        f0Candidates.do { |f0, i|
            var total = 0;
            (1..nHarmonics).do { |h|
                var fh = f0 * h;
                var idx, start, end, submag;
                if (fh <= freqs.last) {
                    idx = freqs.indexOfNearest(fh);
                    start = (idx - 3).max(0);
                    end = (idx + 3).min(spectrum.size - 1);
                    submag = 0;
                    (start..end).do { |k| submag = submag.max(spectrum[k]) };
                    total = total + (harmonicWeights[h-1] * submag);
                };
            };
            salience[i] = total;
        };

        if (salience.maxItem > 0) { salience = salience / salience.maxItem };
        ^[f0Candidates, salience];
    }

    // Peak detection and Hungarian assignment would be complex in pure SC
    // For this "silly proof of concept", I'll provide structural implementations
    
    detectPeaks { |freqs, salience|
        var peaks = List.new;
        // Simplified peak detection
        salience.do { |val, i|
            if (val > config.peakThreshold) {
                if (i > 0 and: { i < (salience.size - 1) }) {
                    if (val > salience[i-1] and: { val > salience[i+1] }) {
                        peaks.add([freqs[i], val]);
                    };
                };
            };
        };
        ^peaks.sort({ |a, b| a[1] > b[1] }).keep(config.maxVoices * 2);
    }

    updateTracks { |detectedPitches, frame|
        // Simplified track update logic without Hungarian algorithm
        // (Matching nearest pitch to track)
        var activeTracks = tracks.select { |t| t.state != VoiceState.terminated and: { t.isExtraPitch.not } };
        var assignedPitches = Set.new;
        var sungPitches = List.new;

        activeTracks.do { |track|
            var bestDist = config.maxPitchJumpCents;
            var bestIdx = -1;
            detectedPitches.do { |p, j|
                var dist = this.centsDistance(track.lastPitch, p[0]);
                if (dist < bestDist) {
                    bestDist = dist;
                    bestIdx = j;
                };
            };

            if (bestIdx != -1) {
                track.addObservation(frame, detectedPitches[bestIdx][0], detectedPitches[bestIdx][1]);
                track.inactiveCount = 0;
                if (track.state == VoiceState.tentative) {
                    track.tentativeCount = track.tentativeCount + 1;
                    if (track.tentativeCount >= config.tentativeFrames) {
                        track.state = VoiceState.active;
                    };
                };
                assignedPitches.add(bestIdx);
                sungPitches.add(detectedPitches[bestIdx]);
            } {
                track.inactiveCount = track.inactiveCount + 1;
                if (track.inactiveCount >= config.inactiveFrames) {
                    track.state = VoiceState.terminated;
                };
            };
        };

        // Handle unassigned as new tracks
        detectedPitches.do { |p, j|
            if (assignedPitches.includes(j).not) {
                if (p[1] > (config.peakThreshold * 1.2)) {
                    if (activeTracks.size < config.maxVoices) {
                        var track = VoiceTrack.new(nextTrackId, frame);
                        track.addObservation(frame, p[0], p[1]);
                        tracks.add(track);
                        nextTrackId = nextTrackId + 1;
                        sungPitches.add(p);
                    };
                };
            };
        };
        
        ^sungPitches;
    }
}