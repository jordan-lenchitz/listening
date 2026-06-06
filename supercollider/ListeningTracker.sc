ListeningTracker {
    var <config, <multiF0, <affordanceField, <dualProcess, <asa, <percept;
    var <sampleRate, <frameSize;

    *new { |sr = 44100, fs = 2048|
        ^super.new.init(sr, fs);
    }

    init { |sr, fs|
        sampleRate = sr;
        frameSize = fs;
        
        config = TrackerConfig.new;
        config.sampleRate = sampleRate;
        config.frameLength = frameSize;

        multiF0 = MultiF0Tracker.new(config);
        affordanceField = AffordanceField.new(sampleRate, frameSize);
        dualProcess = DualProcessTracker.new;
        
        // Use the new ported classes from MumpsPort.sc
        asa = ASAManager.new;
        percept = PerceptualModel.new;
        db = F0TrackerDB.new;
        logger = TrackingLogger.new;

        asa.initSession("default");
        logger.log("INIT", "ListeningTracker initialized with sr=" ++ sr);
    }

    processFrame { |audioFrame, time|
        var spectrum = audioFrame.fft(FloatArray.newClear(frameSize), Signal.hanningWindow(frameSize)).magnitude;
        var mag = spectrum.keep(frameSize / 2 + 1);
        var freqs = multiF0.computeSalience(mag, multiF0.config.sampleRate / frameSize * (0..frameSize/2));
        var peaks = multiF0.detectPeaks(freqs[0], freqs[1]);
        var field = affordanceField.update(mag);
        var results;

        multiF0.updateTracks(peaks, time);

        // Integrate ASA
        peaks.do { |p|
            var advice = JustIntonationAdvisor.new.getAdvice(p[0], p[0]); // Simplified
            asa.afford("default", time, p[0], p[1], "SUNG");
        };

        ^field;
    }

    sonify { |tracks|
        // Sonification logic
        tracks.do { |t|
            if (t.state == VoiceState.active) {
                Synth(\listening_tracker_sonify, [\freq, t.lastPitch, \amp, 0.1]);
            };
        };
    }
}