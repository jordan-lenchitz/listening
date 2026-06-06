DualProcessTrackerWrapper {
    var <scriptPath;

    *new {
        ^super.new.init;
    }

    init {
        scriptPath = "python/dual_process_tracker.py";
    }

    process { |frame|
        postln("PythonWrapper: Dual process update via " + scriptPath);
        ^frame; // Mocked pass-through
    }
}
