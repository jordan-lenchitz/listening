ListeningLogger {
    classvar <levels;
    var <logPath, <currentLevel;

    *initClass {
        levels = (debug: 0, info: 1, warn: 2, error: 3);
    }

    *new { |path, level = \info|
        ^super.new.init(path, level);
    }

    init { |path, level|
        logPath = path;
        currentLevel = levels[level] ?? 1;
    }

    debug { |msg, context = ""| this.log(\debug, msg, context) }
    info { |msg, context = ""| this.log(\info, msg, context) }
    warn { |msg, context = ""| this.log(\warn, msg, context) }
    error { |msg, context = ""| this.log(\error, msg, context) }

    log { |level, msg, context|
        var lvlVal = levels[level];
        if(lvlVal >= currentLevel) {
            var time = Date.getDate.asString;
            var out = "[" + time + "] [" + level.asString.toUpper + "]" ;
            if(context != "") { out = out + "[" + context + "]" };
            out = out + ":" + msg;
            out.postln;
            // In a real environment, we'd also write to a file
        };
    }

    *formatFreq { |freq|
        ^freq.asStringPrec(6) + "Hz";
    }

    *formatCents { |cents|
        ^cents.asStringPrec(4) + "¢";
    }
}