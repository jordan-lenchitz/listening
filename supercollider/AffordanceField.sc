AffordanceField {
    var <sampleRate, <frameSize, <nBins;
    var <freqs;
    var <prevPresence, <persistence, <smoothPresence;
    var <>persistenceAlpha, <>changeAlpha;
    var <>maskingFloorDB, <>maskingSpreadERB;
    var <>dominanceLowHz, <>dominanceHighHz, <>dominanceWeight;
    var <>continuityERBSigma;

    *new { |sampleRate = 44100, frameSize = 2048|
        ^super.new.init(sampleRate, frameSize);
    }

    init { |sr, fs|
        sampleRate = sr;
        frameSize = fs;
        nBins = (frameSize / 2 + 1).asInteger;
        freqs = Array.fill(nBins, { |i| i * sampleRate / frameSize });

        prevPresence = FloatArray.fill(nBins, 0);
        persistence = FloatArray.fill(nBins, 0);
        smoothPresence = FloatArray.fill(nBins, 0);

        persistenceAlpha = 0.95;
        changeAlpha = 0.8;
        maskingFloorDB = -60.0;
        maskingSpreadERB = 1.5;
        dominanceLowHz = 500.0;
        dominanceHighHz = 2000.0;
        dominanceWeight = 1.0;
        continuityERBSigma = 0.5;
    }

    update { |mag|
        var presence, availability, normPersistence, change, continuity, coherence, field;
        var maxMag, peakDB, magDB, maxAvail, maxPers, maxChange, maxCont;
        var timeCoherent, freqSmoothed, freqCoherent;

        if (mag.size != nBins) { "Wrong magnitude size".error; ^nil };

        // 1. Presence
        maxMag = mag.maxItem;
        presence = if (maxMag > 0) { mag / maxMag } { FloatArray.fill(nBins, 0) };

        // 2. Availability
        magDB = mag.collect { |x| 20.0 * (x + 1e-12).log10 };
        peakDB = magDB.maxItem;
        availability = magDB.collect { |db|
            ((db - peakDB - maskingFloorDB) / (0.0 - maskingFloorDB)).clip(0.0, 1.0)
        };
        availability = this.smoothAlongERB(availability, maskingSpreadERB);

        freqs.do { |f, i|
            if (f >= dominanceLowHz and: { f <= dominanceHighHz }) {
                availability[i] = availability[i] * (1.0 + dominanceWeight);
            };
        };
        maxAvail = availability.maxItem;
        if (maxAvail > 0) { availability = availability / maxAvail };

        // 3. Persistence
        nBins.do { |i|
            persistence[i] = (persistenceAlpha * persistence[i]) + ((1.0 - persistenceAlpha) * presence[i]);
        };
        maxPers = persistence.maxItem;
        normPersistence = if (maxPers > 0) { persistence / maxPers } { FloatArray.fill(nBins, 0) };

        // 4. Change
        change = FloatArray.newClear(nBins);
        nBins.do { |i|
            smoothPresence[i] = (changeAlpha * smoothPresence[i]) + ((1.0 - changeAlpha) * presence[i]);
            change[i] = (presence[i] - smoothPresence[i]).max(0.0);
        };
        maxChange = change.maxItem;
        if (maxChange > 0) { change = change / maxChange };

        // 5. Continuity
        timeCoherent = (presence * prevPresence).sqrt;
        freqSmoothed = this.smoothAlongERB(presence, continuityERBSigma);
        freqCoherent = (1.0 - (presence - freqSmoothed).abs).max(0.0);
        continuity = timeCoherent * freqCoherent;
        maxCont = continuity.maxItem;
        if (maxCont > 0) { continuity = continuity / maxCont };

        // 6. Coherence (Stub)
        coherence = FloatArray.fill(nBins, 1.0);

        // Integration
        field = FloatArray.newClear(nBins);
        nBins.do { |i|
            var feats = presence[i] * normPersistence[i] * continuity[i] * change[i] * coherence[i];
            field[i] = availability[i] * (feats.pow(0.2));
        };

        prevPresence = presence;
        ^field;
    }

    smoothAlongERB { |x, sigmaERB|
        var y = FloatArray.newClear(nBins);
        var binHz = if (nBins > 1) { freqs[1] - freqs[0] } { 1.0 };

        nBins.do { |i|
            var f = freqs[i];
            var erb = 24.7 * (1.0 + (4.37 * f / 1000.0));
            var sigmaHz = sigmaERB * erb;
            var sigmaBins = (sigmaHz / binHz).max(1.0);
            var halfWin = (3.0 * sigmaBins).ceil.asInteger;
            var sumW = 0.0;
            var val = 0.0;
            var start = (i - halfWin).max(0);
            var end = (i + halfWin).min(nBins - 1);

            (start..end).do { |k|
                var weight = (-0.5 * ((k - i) / sigmaBins).squared).exp;
                val = val + (x[k] * weight);
                sumW = sumW + weight;
            };
            y[i] = if (sumW > 0) { val / sumW } { x[i] };
        };
        ^y;
    }
}