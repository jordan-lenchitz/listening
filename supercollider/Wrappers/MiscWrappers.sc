CPPMultiF0Wrapper {
    *track { |audio|
        postln("CPPWrapper: Calling cpp/multi_f0_tracker.cpp");
        ^[440, 660, 880];
    }
}

CPPBindingWrapper {
    *bind {
        postln("CPPWrapper: Initializing ydb_dsp_binding.cpp");
    }
}

/**
 * Mumps/MumpsWrappers: Wrapper for legacy MUMPS logic.
 */
MumpsASAWrapper {
    *run { postln("MumpsWrapper: Executing ASA.m") }
}

MumpsF0TrackWrapper {
    *run { postln("MumpsWrapper: Executing F0TRACK.m") }
}

MumpsJustIntWrapper {
    *run { postln("MumpsWrapper: Executing JUSTINT.m") }
}

MumpsLoggerWrapper {
    *run { postln("MumpsWrapper: Executing LOGGER.m") }
}

MumpsPerceptWrapper {
    *run { postln("MumpsWrapper: Executing PERCEPT.m") }
}

MumpsScalesWrapper {
    *run { postln("MumpsWrapper: Executing SCALES.m") }
}

MumpsTrackingWrapper {
    *run { postln("MumpsWrapper: Executing TRACKING.m") }
}