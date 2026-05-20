// sonify_tracker.scd
// SuperCollider Sonification patch for the A Cappella Multi-F0 Tracker
// Listens for Open Sound Control (OSC) messages and synthesizes tracked voices.
// Perfect for highlighting those "phantom tones" and spectral fission phenomena!

s.boot;

s.waitForBoot({
    // 1. Define a Synth for the tracked voices
    SynthDef(\trackedVoice, { |freq=440, amp=0.5, gate=1, pan=0, isExtra=0|
        var sig, env, vib;
        
        // Slight vibrato for a more "vocal" feel on the fundamental voices
        vib = SinOsc.kr(5, 0, 0.01 * freq * (1 - isExtra)); 
        
        // Simple vocal-ish synthesis (sawtooth through a formant-like bandpass filter)
        sig = Saw.ar(freq + vib);
        
        // Emphasize different formants depending on if it's a sung pitch or ghost pitch
        sig = BPF.ar(sig, Select.kr(isExtra, [freq * 2.5, freq * 1.5]), 0.2);
        
        // Envelopes
        env = EnvGen.kr(Env.asr(0.1, 1.0, 0.15), gate, doneAction: 2);
        
        // Pan and output
        Out.ar(0, Pan2.ar(sig * env * amp, pan));
    }).add;

    // 2. Dictionary to keep track of active synth nodes by Track ID
    ~voices = Dictionary.new;

    // 3. OSC Listener for Pitch Updates
    // Expected format: /f0track [trackID, freq, confidence, isExtraPitch]
    OSCdef(\f0receiver, { |msg, time, addr, recvPort|
        var trackID = msg[1];
        var freq = msg[2];
        var conf = msg[3];
        var isExtra = msg[4]; // 1 for ghost pitch, 0 for sung voice

        // Map confidence to amplitude
        var mappedAmp = conf.linexp(0.1, 1.0, 0.01, 0.5);

        if(~voices.at(trackID).isNil) {
            // New voice enters!
            ~voices.put(trackID, Synth(\trackedVoice, [
                \freq, freq, 
                \amp, mappedAmp,
                \isExtra, isExtra,
                // Spatialize: put ghost pitches wide, fundamentals closer to center
                \pan, if(isExtra == 1, rrand(0.6, 1.0) * [1, -1].choose, rrand(-0.3, 0.3))
            ]));
        } {
            // Update existing voice frequency and amplitude smoothly
            ~voices.at(trackID).set(\freq, freq, \amp, mappedAmp);
        };
    }, '/f0track');

    // 4. OSC Listener for Terminating Tracks
    // Expected format: /f0terminate [trackID]
    OSCdef(\f0terminator, { |msg|
        var trackID = msg[1];
        if(~voices.at(trackID).notNil) {
            // Trigger the release envelope and remove from tracker
            ~voices.at(trackID).set(\gate, 0);
            ~voices.removeAt(trackID);
        }
    }, '/f0terminate');

    "".postln;
    "=========================================================".postln;
    "🎤 SuperCollider Multi-F0 Tracker Sonification Ready! 🎤".postln;
    "Listening for OSC on port 57120...".postln;
    "Send /f0track [id, freq, conf, isExtra] to spawn/update".postln;
    "Send /f0terminate [id] to kill a voice".postln;
    "=========================================================".postln;
});