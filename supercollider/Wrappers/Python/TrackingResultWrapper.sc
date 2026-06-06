TrackingResultWrapper {
    var <scriptPath;

    *new {
        ^super.new.init;
    }

    init {
        scriptPath = "python/tracking_result.py";
    }

    format { |data|
        postln("PythonWrapper: Formatting results via " + scriptPath);
        ^data.asString;
    }
}