AuditorySceneAnalysis {
    var <sessions;

    *new {
        ^super.new.init;
    }

    init {
        sessions = Dictionary.new;
    }

    initSession { |id|
        sessions[id] = Dictionary[
            "status" -> "INITIALIZING",
            "startTime" -> Main.elapsedTime,
            "affordanceCount" -> 0,
            "affordances" -> List.new,
            "groups" -> List.new
        ];
        ("Session " ++ id ++ " initialized.").postln;
    }

    afford { |id, time, freq, sal, type|
        var session = sessions[id];
        var node;
        if (session.isNil) { ^nil };
        
        session["affordanceCount"] = session["affordanceCount"] + 1;
        node = Dictionary[
            "time" -> time,
            "freq" -> freq,
            "sal" -> sal,
            "type" -> type
        ];
        session["affordances"].add(node);

        if (sal > 0.9) {
            ("!!! Schema Match: " ++ type ++ " at " ++ freq ++ " Hz detected !!!").postln;
        };
    }

    group { |id, tracks|
        var session = sessions[id];
        var gid;
        if (session.isNil) { ^nil };
        
        gid = session["groups"].size + 1;
        session["groups"].add(tracks);
        ("Formed Auditory Object " ++ gid ++ " from tracks: " ++ tracks).postln;
    }
}

Percept {
    var <state;

    *new {
        ^super.new.init;
    }

    init {
        state = Dictionary[
            \persist -> Dictionary.new,
            \change -> Dictionary.new,
            \prior -> Dictionary.new
        ];
    }

    persist { |freq, val, tau, dt|
        var alpha = (-dt / tau).exp;
        var persistDict = state[\persist];
        var prev = persistDict.atFail(freq, { 0 });
        var newState = (alpha * prev) + ((1 - alpha) * val);
        persistDict.put(freq, newState);
        ^newState;
    }

    change { |freq, val, tau, dt|
        var smooth = this.persist(freq, val, tau, dt);
        var diff = (val - smooth).max(0);
        state[\change].put(freq, diff);
        ^diff;
    }

    bUpdate { |freq, measLH, f0Fast, ridge|
        var alpha = 0.6, beta = 0.3;
        var prior = state[\prior].atFail(freq, { 0 });
        var fp = this.window(freq, f0Fast, 15);
        var rp = this.window(freq, ridge, 10);
        var comb = (alpha * fp) + (beta * rp) + ((1 - alpha - beta) * prior);
        var post = comb * measLH;
        state[\prior].put(freq, post);
        ^post;
    }

    window { |freq, center, sigma|
        var sln, diff, val;
        if (center.isNil || { center <= 0 }) { ^0 };
        sln = sigma / 1200.0;
        diff = (freq / center).log;
        val = (-(diff * diff) / (2 * sln * sln)).exp;
        ^val;
    }
}