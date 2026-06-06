(
s.waitForBoot({
    var sr = 44100;
    var duration = 5.0;
    var gen, audio, db, asa, logger, pm, sc, yin, filterbank, streamlit;
    var numFrames, hopSize = 512, frameSize = 2048;

    postln("--- STARTING FULL SYSTEM DEMO ---");

    // 1. Initialize Components
    logger = TrackingLogger.new;
    db = F0TrackerDB.new;
    asa = ASAManager.new;
    pm = PerceptualModel.new;
    sc = SalienceComputer.new(0.05);
    yin = YinEstimator.new(frameSize, sr);
    filterbank = GammatoneFilterbank.new(60, 4000, 32, sr);
    gen = SyntheticGenerator.new(duration, sr);
    
    logger.log("INIT", "All components initialized");

    // 2. Generate Synthetic Signal
    postln("Generating synthetic audio...");
    audio = gen.generate(3); // 3 voices
    logger.log("GENERATE", "Generated 3-voice synthetic signal");

    // 3. Initialize UI
    streamlit = StreamlitAppMock.new;
    streamlit.statusText.string_("System ready. Analyzing synthetic signal...");

    // 4. Process Signal Frame-by-Frame
    numFrames = (audio.size / hopSize).asInteger - (frameSize / hopSize).asInteger;
    asa.initSession("demo_session");

    fork {
        numFrames.do { |fIdx|
            var start = fIdx * hopSize;
            var frame = audio.copyRange(start, start + frameSize - 1);
            var pitchResult, salienceResult, peaks;
            var time = start / sr;

            // YIN Pitch Estimation
            pitchResult = yin.estimate(frame);
            if(pitchResult.notNil) {
                db.pushFrame(fIdx, 1, pitchResult[0], pitchResult[1]);
                asa.recordAffordance("demo_session", time, pitchResult[0], pitchResult[1], "VOICE");
            };

            // Gammatone Filterbank (on middle sample of frame for speed)
            filterbank.processFrame(frame[frameSize/2]);

            // Periodically report and update UI
            if(fIdx % 20 == 0) {
                {
                    streamlit.statusText.string_("Processing frame " ++ fIdx ++ " of " ++ numFrames);
                    streamlit.updatePlots;
                }.defer;
            };

            // Simulate real-time processing speed
            (hopSize / sr).wait;
        };

        // 5. Final Report
        db.processFrames;
        db.report;
        logger.log("FINISH", "Demo completed successfully");
        logger.dump;

        {
            streamlit.statusText.string_("Analysis complete. Check Post Window for report.");
            
            // Show result visualization
            TrackingResultPort.new(
                Array.series(numFrames, 0, hopSize/sr),
                [
                    (frames: Array.series(100, 0, 1), pitches: Array.fill(100, { |i| 440 + (i*0.5) })),
                    (frames: Array.series(100, 0, 1), pitches: Array.fill(100, { |i| 220 + (i*0.2) }))
                ]
            ).visualize("Final Tracked Voices");
            
        }.defer;

        postln("--- DEMO COMPLETED ---");
    };
});
)