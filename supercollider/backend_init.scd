(
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 0;
s.options.memSize = 8192 * 16;
s.options.device = "dummy"; // Try dummy if available, otherwise just boot

s.waitForBoot({
    var tracker, backendAddr;
    
    tracker = ListeningTracker.new(s.sampleRate, 2048);
    backendAddr = NetAddr("127.0.0.1", 57121);
    
    "SuperCollider Backend Initialized".postln;
    
    OSCdef(\process_audio, { |msg|
        var jobId = msg[1].asString;
        var filePath = msg[2].asString;
        var result;
        
        "Processing Job: % File: %".format(jobId, filePath).postln;
        
        // Offline processing logic
        // For a quick test, we'll just simulate some analysis results
        // In a real scenario, we'd use SoundFile or Buffer to analyze
        
        result = (
            jobId: jobId,
            status: "complete",
            voices: 3,
            tracks: [
                (id: 1, freq: 220, label: "A3", stability: 0.95),
                (id: 2, freq: 330, label: "E4", stability: 0.88),
                (id: 3, freq: 440, label: "A4", stability: 0.92)
            ],
            affordanceField: [0.1, 0.5, 0.9, 0.4] // Simplified
        );
        
        backendAddr.sendMsg("/result", jobId, result.asJSON);
        "Sent result for %".format(jobId).postln;
        
    }, '/process');
    
    "OSC Listener Ready on port 57120".postln;
});
)
