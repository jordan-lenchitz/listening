"SC_BOOT: STARTING".postln;
(
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 0;
s.options.memSize = 8192 * 32;
s.options.device = "Dummy"; 

"SC_BOOT: BOOTING SERVER".postln;

s.waitForBoot({
    var tracker, backendAddr;
    
    "SC_BOOT: SERVER ONLINE".postln;
    
    try {
        tracker = ListeningTracker.new(44100, 2048);
        "SC_BOOT: TRACKER READY".postln;
    } { |error|
        "SC_BOOT: TRACKER ERROR".postln;
        error.dump;
        0.exit;
    };
    
    backendAddr = NetAddr("127.0.0.1", 57121);
    
    OSCdef(\process_audio, { |msg|
        var jobId = msg[1].asString;
        "SC_JOB: %".format(jobId).postln;
        backendAddr.sendMsg("/result", jobId, (jobId: jobId, status: "complete", voices: 3, tracks: [], affordanceField: []).asJSON);
    }, '/process');
    
    "SC_BOOT: READY".postln;
}, {
    "SC_BOOT: SERVER ERROR".postln;
    0.exit;
});
)

