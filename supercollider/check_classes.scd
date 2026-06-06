"CHECK: SuperCollider Class Library Check Started".postln;
try {
    var tracker = ListeningTracker.new(44100, 2048);
    "CHECK: ListeningTracker instantiated successfully.".postln;
    0.exit;
} { |error|
    "CHECK: ERROR during instantiation:".postln;
    error.dump;
    1.exit;
};