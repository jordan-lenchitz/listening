MultiF0TrackerWrapper {
    var <scriptPath;

    *new {
        ^super.new.init;
    }

    init {
        scriptPath = "python/multi_f0_tracker.py";
    }

    track { |audioPath|
        postln("PythonWrapper: Executing " + scriptPath + " on " + audioPath);
        ^[ [440, 0.9], [660, 0.8] ]; // Mocked detections
    }
}