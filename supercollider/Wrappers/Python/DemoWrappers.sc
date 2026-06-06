DemoAdvancedTrackingWrapper {
    *run { postln("PythonWrapper: Running demo_advanced_tracking.py") }
}

DemoBarbershopWrapper {
    *run { postln("PythonWrapper: Running demo_barbershop.py") }
}

DemoQuintinaWrapper {
    *run { postln("PythonWrapper: Running demo_quintina.py") }
}

StreamlitAppWrapper {
    *launch { postln("PythonWrapper: Launching streamlit_app.py") }
}

JustIntonationPythonWrapper {
    *calculate { |freqs| postln("PythonWrapper: Running just_intonation.py"); ^freqs; }
}