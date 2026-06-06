TestASAManager : UnitTest {
    test_initSession {
        var asa = ASAManager.new;
        asa.initSession("test_id");
        this.assert(asa.sessions["test_id"].notNil, "Session should be initialized");
        this.assert(asa.sessions["test_id"][\status] == "INITIALIZING", "Status should be INITIALIZING");
    }

    test_recordAffordance {
        var asa = ASAManager.new;
        asa.initSession("test_id");
        asa.recordAffordance("test_id", 0.1, 440, 0.95, "GHOST");
        this.assert(asa.sessions["test_id"][\affordanceCount] == 1, "Affordance count should increment");
        this.assert(asa.sessions["test_id"][\affordances].size == 1, "Affordance list should have 1 item");
    }

    test_groupTracks {
        var asa = ASAManager.new;
        asa.initSession("test_id");
        asa.groupTracks("test_id", [1, 2, 3]);
        this.assert(asa.sessions["test_id"][\groupCount] == 1, "Group count should increment");
        this.assert(asa.sessions["test_id"][\groups][1] == [1, 2, 3], "Group 1 should contain tracks 1, 2, 3");
    }
}

TestF0TrackerDB : UnitTest {
    test_addPitch {
        var db = F0TrackerDB.new;
        db.addPitch(1, 0, 440, 0.9);
        this.assert(db.tracks[1].notNil, "Track 1 should exist");
        this.assert(db.tracks[1][0][\freq] == 440, "Frequency should be 440");
    }

    test_terminateTrack {
        var db = F0TrackerDB.new;
        db.addPitch(1, 0, 440, 0.9);
        db.terminateTrack(1);
        this.assert(db.tracks[1][\state] == "TERMINATED", "Track 1 should be terminated");
    }
}

TestPerceptualModel : UnitTest {
    test_persist {
        var pm = PerceptualModel.new;
        var res = pm.persist(440, 1.0, 1.0, 0.1);
        this.assert(res > 0 and: { res < 1.0 }, "Persistence should be between 0 and 1");
    }

    test_gaussianWindow {
        var pm = PerceptualModel.new;
        var res = pm.gaussianWindow(440, 440, 15);
        this.assert(res == 1.0, "Gaussian window at center should be 1.0");
        res = pm.gaussianWindow(880, 440, 15);
        this.assert(res < 0.1, "Gaussian window far from center should be small");
    }
}

TestScaleUtils : UnitTest {
    test_freqToErb {
        this.assert(ScaleUtils.freqToErb(1000) == (24.7 * (1 + 4.37)), "ERB calculation should be correct");
    }

    test_cents {
        this.assert(ScaleUtils.cents(440, 880) == 1200, "Octave should be 1200 cents");
    }

    test_freqToMidi {
        this.assert(ScaleUtils.freqToMidi(440) == 69, "440Hz should be MIDI 69");
    }
}

TestGammatoneFilter : UnitTest {
    test_process {
        var filter = GammatoneFilter.new(440, 44100);
        var output = filter.process(1.0);
        this.assert(output.isFloat, "Process should return a float");
    }
}

TestYinEstimator : UnitTest {
    test_estimate {
        var yin = YinEstimator.new(2048, 44100, 65, 1000);
        var frame = FloatArray.fill(2048, { |i| (2 * pi * 440 * i / 44100).sin });
        var result = yin.estimate(frame);
        this.assert(result.notNil, "YIN should detect pitch");
        this.assert((result[0] - 440).abs < 5, "Detected pitch should be around 440Hz");
    }
}

TestSalienceComputer : UnitTest {
    test_computeSalience {
        var sc = SalienceComputer.new;
        var freqs = FloatArray.series(1024, 0, 44100/2048);
        var spectrum = FloatArray.newClear(1024);
        var result;
        
        // Add harmonic peak at 440Hz
        [440, 880, 1320].do { |f|
            var idx = (f / (44100/2048)).asInteger;
            if(idx < 1024) { spectrum[idx] = 1.0 };
        };
        
        result = sc.computeSalience(spectrum, freqs);
        this.assert(result[0].size == 500, "Should return 500 candidates");
        this.assert(result[1].maxItem > 0.5, "Salience should have a strong peak");
    }
}

TestSyntheticGenerator : UnitTest {
    test_generate {
        var gen = SyntheticGenerator.new(1.0, 44100);
        var audio = gen.generate(2);
        this.assert(audio.size == 44100, "Should generate 1 second of audio");
        this.assert(audio.abs.maxItem <= 1.0, "Audio should be normalized");
    }
}
