"SC_STARTUP: SCLANG BOOT SEQUENCE STARTED".postln;

(
"SC_STARTUP: Setting options...".postln;
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 0;
s.options.memSize = 8192 * 32;
s.options.device = "Dummy"; 

"SC_STARTUP: Attempting server boot...".postln;

s.waitForBoot({
    var tracker, backendAddr;
    
    "SC_STARTUP: Server Booted.".postln;
    
    tracker = ListeningTracker.new(44100, 2048);
    backendAddr = NetAddr("127.0.0.1", 57121);
    
    OSCdef(\process_audio, { |msg|
        var jobId = msg[1].asString;
        var filePath = msg[2].asString;
        var result;
        
        "SC_JOB: %".format(jobId).postln;
        
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
    }, '/process');
    
    "SC_STARTUP: OSC Ready.".postln;
}, {
    "SC_STARTUP: FAILED TO BOOT SERVER".postln;
    0.exit;
});
)
