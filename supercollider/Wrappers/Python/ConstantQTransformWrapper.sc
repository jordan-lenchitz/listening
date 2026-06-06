ConstantQTransformWrapper {
    var <scriptPath;

    *new {
        ^super.new.init;
    }

    init {
        scriptPath = "python/constant-q_transform_continuous_chromagram.py";
    }

    transform { |audio|
        postln("PythonWrapper: Calling " + scriptPath);
        ^FloatArray.newClear(84); // Mocked chromagram
    }
}
