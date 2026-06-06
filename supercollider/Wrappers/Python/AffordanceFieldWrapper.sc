AffordanceFieldWrapper {
    var <scriptPath;

    *new {
        ^super.new.init;
    }

    init {
        scriptPath = "python/affordance_field.py";
    }

    calculate { |spectrum|
        postln("PythonWrapper: Calling " + scriptPath + " for spectrum of size " + spectrum.size);
        // Mocked result
        ^FloatArray.fill(spectrum.size, { |i| spectrum[i] * 0.9 });
    }
}
