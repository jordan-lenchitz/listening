(
s.waitForBoot({
    var tracker, buffer, win;
    
    // Initialize DSP
    ListeningDSP.initSynthDefs;
    
    // Load some audio (placeholder)
    // buffer = Buffer.read(s, "/root/listening/mp3/example_one.mp3");
    
    tracker = ListeningTracker.new(s.sampleRate, 2048);
    
    "Listening Tracker Initialized.".postln;
    "Components:".postln;
    "- Multi-F0 Tracker".postln;
    "- Affordance Field".postln;
    "- Dual Process Bayesian Prior".postln;
    "- Just Intonation Advisor".postln;
    "- Auditory Scene Analysis Manager".postln;
    
    // Simulate some tracking
    Routine({
        10.do { |i|
            var mockFreqs = [220, 330, 440] * (1.0 + (0.01 * 5.rand2));
            var mockPitches = mockFreqs.collect { |f| [f, 0.8 + 0.2.rand] };
            
            tracker.multiF0.updateTracks(mockPitches, i);
            
            "Frame %: Detected % voices".format(i, mockPitches.size).postln;
            tracker.multiF0.tracks.do { |t|
                if (t.state == VoiceState.active) {
                    var advice = JustIntonationAdvisor.new.getAdvice(220, t.lastPitch);
                    "  Track %: % Hz (% deviation: % cents)".format(t.id, t.lastPitch.round(0.1), advice[1], advice[2].round(0.1)).postln;
                };
            };
            
            0.5.wait;
        };
        "Demo complete.".postln;
    }).play;
});
)