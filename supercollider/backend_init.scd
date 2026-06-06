"SC_BOOT: STARTING".postln;
(
s.options.numOutputBusChannels = 2;
s.options.numInputBusChannels = 0;
s.options.memSize = 8192 * 32;
s.options.device = "Dummy"; 

"SC_BOOT: BOOTING SERVER".postln;

s.waitForBoot({
    var backendAddr;
    
    "SC_BOOT: SERVER ONLINE".postln;
    backendAddr = NetAddr("127.0.0.1", 57121);
    
    OSCdef(\process_audio, { |msg|
        var jobId = msg[1].asString;
        var filePath = msg[2].asString;
        "SC_JOB: % PROCESSING: %".format(jobId, filePath).postln;
        
        Routine({
            var sf, results;
            
            // Basic file validation
            sf = SoundFile.openRead(filePath);
            if (sf.notNil) {
                "SC_JOB: % File opened. SR: % Channels: %".format(jobId, sf.sampleRate, sf.numChannels).postln;
                
                // Simulate processing time
                2.wait; 
                
                sf.close;
                
                results = (
                    jobId: jobId, 
                    status: "complete", 
                    voices: (2..5).choose, 
                    tracks: [
                        (id: 1, freq: (200..400).choose.asFloat, label: "V1", stability: 0.9),
                        (id: 2, freq: (400..800).choose.asFloat, label: "V2", stability: 0.8)
                    ], 
                    affordanceField: Array.fill(32, { 1.0.rand })
                );
                
                "SC_JOB: % SENDING RESULT".format(jobId).postln;
                backendAddr.sendMsg("/result", jobId, results.asJSON);
            } {
                "SC_JOB: % ERROR: Could not open file %".format(jobId, filePath).postln;
                backendAddr.sendMsg("/result", jobId, (jobId: jobId, status: "error", error: "File not found or unreadable").asJSON);
            };
        }).play;
    }, '/process');
    
    "SC_BOOT: READY".postln;
}, {
    "SC_BOOT: ERROR".postln;
    0.exit;
});
)
