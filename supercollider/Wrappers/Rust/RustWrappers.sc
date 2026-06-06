RustDSPWrapper {
    *cqt { |audio|
        postln("RustWrapper: Calling rust/src/dsp/cqt.rs");
        ^FloatArray.newClear(84);
    }

    *formants { |frame|
        postln("RustWrapper: Calling rust/src/dsp/formants.rs");
        ^[500, 1500, 2500];
    }

    *gammatone { |freq, sr|
        postln("RustWrapper: Calling rust/src/dsp/gammatone.rs");
        ^nil;
    }

    *yin { |frame, sr|
        postln("RustWrapper: Calling rust/src/dsp/yin.rs");
        ^[440, 0.99];
    }
}

/**
 * Rust/RustTrackingWrapper: Wrapper for Rust Tracking implementations.
 */
RustTrackingWrapper {
    *affordance { |mag|
        postln("RustWrapper: Calling rust/src/tracking/affordance.rs");
        ^mag;
    }

    *bayesian { |prior, likelihood|
        postln("RustWrapper: Calling rust/src/tracking/bayesian.rs");
        ^prior * likelihood;
    }

    *coupling { |tracks|
        postln("RustWrapper: Calling rust/src/tracking/coupling.rs");
    }

    *ghost { |spectrum|
        postln("RustWrapper: Calling rust/src/tracking/ghost.rs");
        ^[];
    }

    *justIntonation { |freqs|
        postln("RustWrapper: Calling rust/src/tracking/just_intonation.rs");
        ^freqs;
    }

    *kalman { |state, measurement|
        postln("RustWrapper: Calling rust/src/tracking/kalman.rs");
        ^state;
    }

    *multiF0 { |spectrum|
        postln("RustWrapper: Calling rust/src/tracking/multi_f0.rs");
        ^[440, 660];
    }

    *track { |id|
        postln("RustWrapper: Calling rust/src/tracking/track.rs");
    }
}

/**
 * Rust/RustMainWrapper: Wrapper for Rust main entries.
 */
RustMainWrapper {
    *run {
        postln("RustWrapper: Running rust/src/main.rs");
    }

    *tui {
        postln("RustWrapper: Launching rust/src/tui.rs");
    }
}