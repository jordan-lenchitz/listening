GoCmdWrapper {
    *run { |cmd, args|
        postln("GoWrapper: Executing go/cmd/" + cmd + "/main.go with args: " + args);
    }

    *auth { |user, pass| this.run("auth", user) }
    *config { |key, val| this.run("config", key) }
    *dsp { |file| this.run("dsp", file) }
    *fsst { |file| this.run("fsst", file) }
    *gentest { |type| this.run("gentest", type) }
    *health { this.run("health", "") }
    *logger { |msg| this.run("logger", msg) }
    *musicTheory { |chord| this.run("music-theory", chord) }
    *orchestrator { this.run("orchestrator", "") }
    *rtTracker { this.run("rt-tracker", "") }
    *storage { |id| this.run("storage", id) }
    *tracker { |id| this.run("tracker", id) }
    *tracking { |id| this.run("tracking", id) }
    *visualizer { this.run("visualizer", "") }
}