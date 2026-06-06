AuditorySchema {
    var <name, <templates, <rules;

    *new { |name|
        ^super.new.init(name);
    }

    init { |n|
        name = n;
        templates = List.new;
        rules = List.new;
    }

    addTemplate { |harmonics, amplitudes|
        templates.add((harmonics: harmonics, amplitudes: amplitudes));
    }

    addRule { |func|
        rules.add(func);
    }

    match { |peaks|
        var bestScore = 0.0;
        templates.do { |temp|
            var score = this.computeMatchScore(peaks, temp);
            if(score > bestScore) { bestScore = score };
        };
        ^bestScore;
    }

    computeMatchScore { |peaks, template|
        // Complex template matching logic
        var score = 0.0;
        template[\harmonics].do { |h, i|
            var targetFreq = peaks[0][\freq] * h;
            var nearest = peaks.minItem({ |p| (p[\freq] - targetFreq).abs });
            if((nearest[\freq] - targetFreq).abs < 10) {
                score = score + template[\amplitudes][i];
            };
        };
        ^(score / template[\amplitudes].sum);
    }
}

/**
 * VocalSchema: Specialized schema for human voice.
 */
VocalSchema : AuditorySchema {
    *new {
        var schema = super.new("Vocal");
        // Soprano template
        schema.addTemplate([1, 2, 3, 4, 5], [1.0, 0.8, 0.6, 0.4, 0.2]);
        // Bass template
        schema.addTemplate([1, 2, 3, 4, 5, 6, 7, 8], [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]);
        
        // Add rules for vibrato (periodic frequency modulation)
        schema.addRule({ |history|
            var freqMod = history.collect(_[\freq]).differentiate.abs.mean;
            if(freqMod > 2 and: { freqMod < 10 }) { 0.8 } { 0.0 };
        });
        
        ^schema;
    }
}

/**
 * InstrumentalSchema: Schema for musical instruments.
 */
InstrumentalSchema : AuditorySchema {
    *new { |name, harmonics|
        var schema = super.new(name);
        schema.addTemplate(harmonics, Array.fill(harmonics.size, { |i| 1.0 / (i + 1) }));
        ^schema;
    }
}

/**
 * SchemaLibrary: A collection of all known auditory schemas.
 */
SchemaLibrary {
    var <library;

    *new {
        ^super.new.init;
    }

    init {
        library = Dictionary.new;
        library[\soprano] = VocalSchema.new;
        library[\piano] = InstrumentalSchema.new("Piano", [1, 2, 3, 4, 5, 6]);
        library[\flute] = InstrumentalSchema.new("Flute", [1, 2]);
        library[\oboe] = InstrumentalSchema.new("Oboe", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
        
        postln("SchemaLibrary: 4 schemas loaded.");
    }

    identify { |peaks|
        var results = Dictionary.new;
        library.keysValuesDo { |name, schema|
            results[name] = schema.match(peaks);
        };
        ^results;
    }
}