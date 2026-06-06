StreamlitAppMock {
    var <window, <layout;
    var <spectrogramPlot, <ssqPlot, <cepstrogramPlot, <affordancePlot;
    var <sidebar, <statusText;

    *new {
        ^super.new.init;
    }

    init {
        window = Window("listening affordance field and spectral analysis", Rect(100, 100, 1200, 800)).front;
        window.view.decorator = FlowLayout(window.view.bounds, 10@10, 10@10);
        
        this.initSidebar;
        this.initMainPanel;
        
        postln("Streamlit Mock UI Initialized.");
    }

    initSidebar {
        sidebar = CompositeView(window, Rect(0, 0, 200, 780)).background_(Color.grey(0.8));
        sidebar.decorator = FlowLayout(sidebar.bounds, 5@5, 5@5);
        
        StaticText(sidebar, Rect(0, 0, 190, 30)).string_("SETTINGS").font_(Font("Arial", 16, true));
        
        StaticText(sidebar, Rect(0, 0, 190, 20)).string_("Affordance Color Map:");
        PopUpMenu(sidebar, Rect(0, 0, 190, 25)).items_(['viridis', 'plasma', 'inferno', 'magma', 'cividis']);
        
        Button(sidebar, Rect(0, 0, 190, 40)).states_([["Upload Audio File", Color.black, Color.green(0.7)]])
            .action_({ this.simulateProcessing });
            
        statusText = StaticText(sidebar, Rect(0, 0, 190, 100))
            .string_("Welcome! Please upload an audio file to begin.")
            .wordWrap_(true);
    }

    initMainPanel {
        var main = CompositeView(window, Rect(0, 0, 970, 780));
        main.decorator = FlowLayout(main.bounds, 10@10, 10@10);
        
        StaticText(main, Rect(0, 0, 950, 40)).string_("REFERENCE SPECTRAL ANALYSIS").font_(Font("Arial", 20, true));
        
        // Spectrogram
        StaticText(main, Rect(0, 0, 300, 20)).string_("Spectrogram");
        spectrogramPlot = Plotter("Spectrogram", Rect(0, 0, 300, 200), main);
        spectrogramPlot.plot(Array.fill(100, { |i| (i/10).sin * (i/20).cos }));
        
        // SSQ
        StaticText(main, Rect(0, 0, 300, 20)).string_("Synchrosqueezed (SSQ)");
        ssqPlot = Plotter("SSQ", Rect(0, 0, 300, 200), main);
        ssqPlot.plot(Array.fill(100, { |i| (i/5).sin.abs }));
        
        // Cepstrogram
        StaticText(main, Rect(0, 0, 300, 20)).string_("Cepstrogram");
        cepstrogramPlot = Plotter("Cepstrogram", Rect(0, 0, 300, 200), main);
        cepstrogramPlot.plot(Array.fill(100, { |i| (i/15).cos.squared }));
        
        // Affordance Field (Full width)
        StaticText(main, Rect(0, 0, 950, 20)).string_("Spectral Affordance Field (A, T, F)");
        affordancePlot = Plotter("Affordance Field", Rect(0, 0, 940, 300), main);
        affordancePlot.plot(Array.fill(50, { Array.fill(100, { 1.0.rand }) }));
    }

    simulateProcessing {
        statusText.string_("Processing audio... this may take a minute.");
        AppClock.sched(2.0, {
            statusText.string_("Processing complete.");
            this.updatePlots;
            nil;
        });
    }

    updatePlots {
        spectrogramPlot.value = Array.fill(100, { 1.0.rand });
        ssqPlot.value = Array.fill(100, { 1.0.rand });
        cepstrogramPlot.value = Array.fill(100, { 1.0.rand });
        affordancePlot.value = Array.fill(50, { Array.fill(100, { 1.0.rand }) });
        
        spectrogramPlot.refresh;
        ssqPlot.refresh;
        cepstrogramPlot.refresh;
        affordancePlot.refresh;
    }
}

/**
 * SyntheticGenerator: Port of synthetic_generator.py
 * Generates polyphonic synthetic audio for testing.
 */
SyntheticGenerator {
    var <sampleRate, <duration;

    *new { |duration=10.0, sampleRate=44100|
        ^super.new.init(duration, sampleRate);
    }

    init { |dur, sr|
        duration = dur;
        sampleRate = sr;
    }

    // Generate a signal similar to the one in Python
    generate { |nVoices=4|
        var t = Array.series((duration * sampleRate).asInteger, 0, 1.0/sampleRate);
        var audio = FloatArray.newClear(t.size);
        
        // Voice 1: Steady A3 with vibrato
        this.addVoice(audio, t, { |time| 220 + (5.0 * (2 * pi * 5.0 * time).sin) }, 0.25);
        
        if(nVoices > 1) {
            // Voice 2: E4 sliding down to C4
            this.addVoice(audio, t, { |time| 330 - (70.0 * (time / duration)) + (8.0 * (2 * pi * 6.2 * time).sin) }, 0.2);
        };
        
        if(nVoices > 2) {
            // Voice 3: A4 sliding up to C5
            this.addVoice(audio, t, { |time| 440 + (80.0 * (time / duration)) + (12.0 * (2 * pi * 4.5 * time).sin) }, 0.15);
        };
        
        if(nVoices > 3) {
            // Voice 4: G3 with intermittent presence
            this.addVoice(audio, t, { |time| 196 + (3.0 * (2 * pi * 5.5 * time).sin) }, 
                { |time| if((2 * pi * 0.5 * time).sin > 0) { 0.2 } { 0 } });
        };
        
        // Normalize
        audio = audio / audio.abs.maxItem;
        
        ^audio;
    }

    addVoice { |audio, t, freqFunc, ampFunc|
        var phase = 0;
        t.do { |time, i|
            var freq = freqFunc.value(time);
            var amp = if(ampFunc.isFunction) { ampFunc.value(time) } { ampFunc };
            phase = phase + (2 * pi * freq / sampleRate);
            audio[i] = audio[i] + (phase.sin * amp);
        };
    }
    
    // Play the generated audio
    play { |audio|
        {
            var buf = Buffer.loadCollection(s, audio);
            PlayBuf.ar(1, buf, doneAction: 2);
        }.play;
    }
}