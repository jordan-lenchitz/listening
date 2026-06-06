GoPkgDSPWrapper {
    *fsst { |input|
        postln("GoWrapper: Calling go/pkg/dsp/fsst.go");
        ^input;
    }

    *stft { |input|
        postln("GoWrapper: Calling go/pkg/dsp/stft.go");
        ^input;
    }
}

/**
 * Go/GoPkgMusicWrapper: Wrapper for Go Music package logic.
 */
GoPkgMusicWrapper {
    *justIntonation { |freqs|
        postln("GoWrapper: Calling go/pkg/music/just_intonation.go");
        ^freqs;
    }
}

/**
 * Go/GoPkgTrackingWrapper: Wrapper for Go Tracking package logic.
 */
GoPkgTrackingWrapper {
    *affordance { |mag|
        postln("GoWrapper: Calling go/pkg/tracking/affordance.go");
        ^mag;
    }

    *dualProcess { |state|
        postln("GoWrapper: Calling go/pkg/tracking/dual_process.go");
        ^state;
    }

    *salience { |spectrum|
        postln("GoWrapper: Calling go/pkg/tracking/salience.go");
        ^spectrum;
    }

    *tracker { |config|
        postln("GoWrapper: Calling go/pkg/tracking/tracker.go");
        ^nil;
    }

    *result { |data|
        postln("GoWrapper: Calling go/pkg/tracking/result.go");
        ^data.asString;
    }
}
