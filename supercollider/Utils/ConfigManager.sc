ConfigManager {
    var <settings;

    *new {
        ^super.new.init;
    }

    init {
        settings = Dictionary.new;
        this.loadDefaults;
    }

    loadDefaults {
        settings[\tracker] = (
            minFreq: 65,
            maxFreq: 1400,
            hopSize: 512,
            windowSize: 2048
        );
        settings[\asa] = (
            maxObjects: 4,
            persistenceTau: 0.1
        );
    }

    set { |category, key, value|
        if(settings[category].isNil) { settings[category] = Dictionary.new };
        settings[category][key] = value;
    }

    get { |category, key|
        if(settings[category].isNil) { ^nil };
        ^settings[category][key];
    }

    save { |path|
        postln("ConfigManager: Saving settings to " + path);
        // Mocked JSON export
    }

    load { |path|
        postln("ConfigManager: Loading settings from " + path);
        // Mocked JSON import
    }
}