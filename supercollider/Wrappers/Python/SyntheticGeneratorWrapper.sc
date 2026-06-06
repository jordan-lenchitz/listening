SyntheticGeneratorWrapper {
    var <scriptPath;

    *new {
        ^super.new.init;
    }

    init {
        scriptPath = "python/synthetic_generator.py";
    }

    generate { |params|
        postln("PythonWrapper: Generating synthetic audio with " + scriptPath);
        ^"/tmp/synthetic.wav";
    }
}