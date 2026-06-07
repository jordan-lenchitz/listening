ASAManager {
    var <sessions;

    *new {
        ^super.new.init;
    }

    init {
        sessions = Dictionary.new;
    }

    // Initialize a new listening session (Port of INIT^ASA)
    initSession { |id|
        sessions[id] = (
            status: "INITIALIZING",
            startTime: Main.elapsedTime,
            affordanceCount: 0,
            affordances: List.new,
            groups: Dictionary.new,
            groupCount: 0
        );
        postf("Session % initialized.\n", id);
    }

    // Record a spectral affordance (Port of AFFORD^ASA)
    recordAffordance { |id, time, freq, sal, type|
        var session = sessions[id];
        var node;
        if(session.isNil) { 
            postf("WARNING: Attempted to record affordance for non-existent session %\n", id);
            ^this 
        };
        
        session[\affordanceCount] = session[\affordanceCount] + 1;
        node = (
            time: time,
            freq: freq,
            sal: sal,
            type: type,
            timestamp: Main.elapsedTime
        );
        session[\affordances].add(node);
        
        // Check for schema matches (highly salient perceptions)
        if(sal > 0.9) {
            postf("!!! Schema Match: % at % Hz detected (Confidence: %) !!!\n", type, freq, sal);
            this.triggerAttentionalShift(id, node);
        }
    }

    // Trigger an attentional shift based on high-salience events
    triggerAttentionalShift { |id, affordance|
        postf("ASA: Attentional shift triggered in session % by % at % Hz\n", id, affordance[\type], affordance[\freq]);
        // In a real implementation, this would update the priors in the PerceptualModel
    }

    // Group multiple tracks into a single "Source" or "Object" (Port of GROUP^ASA)
    groupTracks { |id, trackIds|
        var session = sessions[id];
        var gid;
        if(session.isNil) { ^this };
        
        session[\groupCount] = session[\groupCount] + 1;
        gid = session[\groupCount];
        session[\groups][gid] = (
            tracks: trackIds,
            startTime: Main.elapsedTime,
            coherence: 1.0 // Initial coherence assumption
        );
        
        postf("Formed Auditory Object % (GID: %) from tracks: %\n", gid, gid, trackIds);
    }
    
    // Retrieve all active sessions
    activeSessions {
        ^sessions.keys.asArray;
    }
    
    // Clean up old sessions
    clearSessions {
        sessions = Dictionary.new;
        postln("ASA: All sessions cleared.");
    }
}

/**
 * SchemaManager: New class for managing auditory schemas.
 * This extends the original ASA.m logic with more explicit schema definitions.
 */
SchemaManager {
    var <schemas;

    *new {
        ^super.new.init;
    }

    init {
        schemas = Dictionary.new;
        this.loadDefaultSchemas;
    }

    loadDefaultSchemas {
        schemas[\vocal] = (
            harmonics: [1, 2, 3, 4, 5, 6],
            formants: [500, 1500, 2500],
            vibratoRange: 0.05
        );
        schemas[\ghost] = (
            harmonics: [1, 3, 5],
            description: "Hollow spectral character"
        );
        postln("SchemaManager: Default schemas loaded.");
    }

    addSchema { |name, properties|
        schemas[name] = properties;
        postf("SchemaManager: Added new schema '%'\n", name);
    }

    matchSchema { |freqs, magnitudes|
        // Complex schema matching logic would go here
        ^[\vocal, 0.85]; // Dummy result
    }
}

/**
 * F0TrackerDB: Port of F0TRACK.m
 * Multi-F0 Tracker Database Backend.
 * Implements state management and tracking data structures.
 */
F0TrackerDB {
    var <config;
    var <tracks;
    var <frames;
    var <state;

    *new {
        ^super.new.init;
    }

    init {
        config = (
            maxVoices: 8,
            minFreq: 65,
            maxFreq: 1400
        );
        tracks = Dictionary.new;
        frames = Dictionary.new;
        state = "READY";
        postln("Initializing A Cappella Tracker Database...");
    }

    // Add a pitch observation to a track (Port of ADDPITCH^F0TRACK)
    addPitch { |trackId, frame, freq, conf|
        if(tracks[trackId].isNil) {
            tracks[trackId] = Dictionary.new;
            tracks[trackId][\state] = "ACTIVE";
        };
        tracks[trackId][frame] = (freq: freq, conf: conf);
        postf("Added pitch % Hz to Track % at Frame %\n", freq, trackId, frame);
    }

    // Mark a track as terminated (Port of TERMINAT^F0TRACK)
    terminateTrack { |trackId|
        if(tracks[trackId].notNil) {
            tracks[trackId][\state] = "TERMINATED";
            postf("Track % terminated.\n", trackId);
        }
    }

    // Process raw DSP frames (Port of PROCESS^F0TRACK)
    processFrames {
        postln("Processing DSP frames from local buffer...");
        frames.keysValuesDo { |frm, pdata|
            postf("  Analyzing Frame %\n", frm);
            pdata.keysValuesDo { |pidx, data|
                this.addPitch(pidx, frm, data[\freq], data[\conf]);
            };
        };
        postln("Finished processing frames.");
    }

    // Print summary of all tracked voices (Port of REPORT^F0TRACK)
    report {
        postln("\n--- SUPERCOLLIDER PORT MULTI-F0 TRACKING REPORT ---");
        tracks.keys.asArray.sort.do { |trackId|
            var tData = tracks[trackId];
            postf("Voice Track % (%):\n", trackId, tData[\state]);
            tData.keys.asArray.sort.do { |frame|
                if(frame != \state) {
                    var d = tData[frame];
                    postf("  Frame % -> Freq: % Hz, Conf: %\n", frame, d[\freq], d[\conf]);
                }
            };
        };
        postln("--- END OF REPORT ---\n");
    }
    
    // Simulate DSP engine push
    pushFrame { |frameId, pitchIdx, freq, conf|
        if(frames[frameId].isNil) { frames[frameId] = Dictionary.new };
        frames[frameId][pitchIdx] = (freq: freq, conf: conf);
    }
}

/**
 * TrackingLogger: Port of LOGGER.m
 * Structured Event Logger for Tracking History.
 */
TrackingLogger {
    var <logData;

    *new {
        ^super.new.init;
    }

    init {
        logData = List.new;
    }

    // Log an event (Port of LOG^LOGGER)
    log { |event, data|
        var entry = (
            timestamp: Date.getDate.asString,
            event: event,
            data: data
        );
        logData.add(entry);
    }

    // Dump log to post window (Port of DUMP^LOGGER)
    dump {
        logData.do { |entry, i|
            postf("[%] %: %\n", entry[\timestamp], entry[\event], entry[\data]);
        };
    }
}

/**
 * PerceptualModel: Port of PERCEPT.m
 * Perceptual Modeling and Bayesian State Updates.
 */
PerceptualModel {
    var <state;

    *new {
        ^super.new.init;
    }

    init {
        state = (
            energy: Dictionary.new,
            prior: Dictionary.new
        );
    }

    // Leaky Integrator for persistence (Port of PERSIST^PERCEPT)
    persist { |freq, val, tau, dt|
        var alpha = (dt.neg / tau).exp;
        var energyDict = state[\energy][freq];
        var prev = if(energyDict.notNil) { energyDict.atFail(\persist, { 0 }) } { 0 };
        var res = (alpha * prev) + ((1 - alpha) * val);
        
        if(state[\energy][freq].isNil) { state[\energy][freq] = Dictionary.new };
        state[\energy][freq][\persist] = res;
        ^res;
    }

    // Change Detection (Port of CHANGE^PERCEPT)
    change { |freq, val, tau, dt|
        var smooth = this.persist(freq, val, tau, dt);
        var diff = val - smooth;
        if(diff < 0) { diff = 0 };
        if(state[\energy][freq].isNil) { state[\energy][freq] = Dictionary.new };
        state[\energy][freq][\change] = diff;
        ^diff;
    }

    // Bayesian Update for a single frequency bin (Port of BUPDATE^PERCEPT)
    bayesianUpdate { |freq, measLH, f0Fast, ridge|
        var alpha = 0.6;
        var beta = 0.3;
        var prior = state[\prior].atFail(freq, { 0 });
        
        var fp = this.gaussianWindow(freq, f0Fast, 15);
        var rp = this.gaussianWindow(freq, ridge, 10);
        
        var combinedPrior = (alpha * fp) + (beta * rp) + ((1 - alpha - beta) * prior);
        var posterior = combinedPrior * measLH;
        
        state[\prior][freq] = posterior;
        ^posterior;
    }

    // Gaussian Window helper for priors (Port of WINDOW^PERCEPT)
    gaussianWindow { |freq, center, sigmaCents|
        var diff, sln, val;
        if(center.isNil || { center <= 0 }) { ^0 };
        sln = sigmaCents / 1200;
        diff = (freq / center).log;
        val = ( (diff * diff).neg / (2 * sln * sln) ).exp;
        ^val;
    }
}

/**
 * ScaleUtils: Port of SCALES.m
 * Frequency Scale Conversions.
 */
ScaleUtils {
    // Freq to ERB (Port of ERB^SCALES)
    *freqToErb { |f|
        ^24.7 * (1 + (4.37 * f / 1000));
    }

    // Distance in Cents (Port of CENTS^SCALES)
    *cents { |f1, f2|
        if(f1 == 0 || { f2 == 0 }) { ^0 };
        ^1200 * ((f2 / f1).log / (2.log));
    }

    // Freq to MIDI (Port of MIDI^SCALES)
    *freqToMidi { |f|
        if(f <= 0) { ^0 };
        ^(69 + (12 * ((f / 440).log / (2.log)))).round;
    }
}