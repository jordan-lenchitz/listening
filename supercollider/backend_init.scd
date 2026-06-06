(
"SC_STARTUP: Initializing Server Options...".postln;
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 0;
s.options.memSize = 8192 * 32;
s.options.maxNodes = 1024 * 4;
s.options.device = "Dummy"; 

"SC_STARTUP: Attempting to boot server...".postln;

s.waitForBoot({
    var tracker, backendAddr;
    
    "SC_STARTUP: Server Booted Successfully.".postln;
    
    tracker = ListeningTracker.new(s.sampleRate, 2048);
    backendAddr = NetAddr("127.0.0.1", 57121);
    
    "SC_STARTUP: ListeningTracker Initialized.".postln;
    
    OSCdef(\process_audio, { |msg|
        var jobId = msg[1].asString;
        var filePath = msg[2].asString;
        var result;
        
        "SC_JOB: Received Job % for File %".format(jobId, filePath).postln;
        
        // Offline processing placeholder
        result = (
            jobId: jobId,
            status: "complete",
            voices: 3,
            tracks: [
                (id: 1, freq: 220, label: "A3", stability: 0.95),
                (id: 2, freq: 330, label: "E4", stability: 0.88),
                (id: 3, freq: 440, label: "A4", stability: 0.92)
            ],
            affordanceField: [0.1, 0.5, 0.9, 0.4]
        );
        
        backendAddr.sendMsg("/result", jobId, result.asJSON);
        "SC_JOB: Sent result for %".format(jobId).postln;
        
    }, '/process');
    
    "SC_STARTUP: OSC Listener Ready on port 57120".postln;
}, {
    "SC_STARTUP: ERROR - Server failed to boot!".postln;
    0.exit;
});
)
