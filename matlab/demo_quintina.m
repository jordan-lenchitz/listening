%% demo_quintina.m  ·  sardinian cuncordu, four voices that produce a fifth
%
% in sardinian cuncordu singing the four voices bassu, contra, bogi, and falzittu 
% are tuned such that their overtones align and a fifth voice = la quintina ['the little fifth']
% is perceived by listeners who have learned to take up its affordance
%
% this demo synthesizes a plausible chord with rich harmonic spectra 
% and runs both the competition-model tracker and the ecological affordance field against it!
%
% the tracker may find the quintina as a ghost pitch track
% BUT the affordance field should show an availability bright spot at the quintina frequency regardless of whether anything "tracks" it
%
% chord, root at g2 (98 hz), just intonation ratios:
%   bassu       1 : 1    = 98.00 hz   (g2)
%   contra      3 : 2    = 147.00 hz  (d3, perfect fifth)
%   bogi        2 : 1    = 196.00 hz  (g3, octave)
%   falzittu    5 : 2    = 245.00 hz  (b3, just major third above g3)

clear; close all; clc;

%% configuration
sr = 22050;
duration = 10.0;
root = 98;
ratios = [1 1; 3 2; 2 1; 5 2];
voiceNames = ["bassu", "contra", "bogi", "falzittu"];

% staggered entries so the tracker can establish voice identity in order
% all voices exit together - the quintina dies with the ensemble
entryTimes = [0.5, 1.5, 2.5, 3.5];
exitTime = 9.0;

%% build the chord
freqs = justintonation.chord(root, ratios);
fprintf("synthesizing sardinian tenores chord:\n\n");
justintonation.printChord(freqs);
fprintf("\n");

%% synthesize
t = (0:round(duration * sr) - 1)' / sr;
audio = zeros(size(t));
for i = 1:numel(freqs)
    audio = audio + synthesizeTenoresVoice(t, freqs(i), entryTimes(i), exitTime, sr);
    fprintf("  %-10s  %6.2f hz  enters %.1fs\n", voiceNames(i), freqs(i), entryTimes(i));
end
audio = audio / max(abs(audio)) * 0.9;

audiowrite("demo_quintina.wav", audio, sr);
fprintf("\naudio saved: demo_quintina.wav\n");

%% competition model, tracker
fprintf("\nrunning competition-model tracker...\n");
tracker = MultiF0Tracker( ...
    MaxVoices=4, ...
    MinFreq=80, ...
    MaxFreq=1600, ...
    PeakThreshold=0.12, ...
    DetectExtraPitches=true);
result = tracker.track(audio, sr);

% keep substantive tracks only
minFrames = 20;
result.SungVoices = result.SungVoices(cellfun(@(v) numel(v.Pitches) >= minFrames, result.SungVoices));
result.ExtraPitches = result.ExtraPitches(cellfun(@(v) numel(v.Pitches) >= 10, result.ExtraPitches));

result.visualize( ...
    Title="tenores chord · competition-model tracker", ...
    OutputPath="quintina_tracks.png");
result.summary();
result.exportCSV("quintina_tracks.csv");

%% ecological model, affordance field
fprintf("\nrunning affordance field...\n");
field = AffordanceField(SampleRate=sr);
A = field.compute(audio);
field.visualize(A, ...
    Title="tenores chord · ecological affordance field", ...
    FrequencyLimit=[80, 2500], ...
    OutputPath="quintina_affordance.png");

%% quintina region inspection
% print the mean availability in a narrow band around each sung fundamental and around the expected quintina region
% the quintina region should show significant availability and persistence even though no voice is singing in it!
fprintf("\nfield energy by region (mean affordance):\n");
regions = { ...
    "bassu (fundamental)",      [95, 105]; ...
    "bogi (fundamental)",       [190, 205]; ...
    "quintina region",          [950, 1500]; ...
    "above quintina",           [1500, 2200]};
for i = 1:size(regions, 1)
    name = regions{i, 1};
    band = regions{i, 2};
    sel = A.Frequencies >= band(1) & A.Frequencies <= band(2);
    val = mean(A.Field(sel, :), "all");
    fprintf("  %-30s %6.1f - %6.1f hz   %.4f\n", name, band(1), band(2), val);
end

fprintf("\ndone.\n");

%% ===================== helper =====================
function signal = synthesizeTenoresVoice(t, f0, entryTime, exitTime, sr)
    % tenores voices have dense harmonic spectra. this matters for quintina
    % emergence: the fifth voice lives in the overtones.
    arguments
        t (:,1) double
        f0 (1,1) double {mustBePositive}
        entryTime (1,1) double
        exitTime (1,1) double
        sr (1,1) double
    end

    % slow vibrato, shallow. tenores singing uses very little vibrato.
    vibratoRate = 4;
    vibratoDepth = 0.005;
    vibrato = vibratoDepth * sin(2*pi*vibratoRate*t);

    % rich harmonic content. weights approximate a vocal pressed register
    % that keeps energy high into the upper partials.
    weights = [1.0, 0.85, 0.7, 0.6, 0.55, 0.5, 0.4, 0.35, 0.3, 0.25, 0.2, 0.15];
    signal = zeros(size(t));
    for h = 1:numel(weights)
        if h * f0 > sr / 2, break; end
        signal = signal + weights(h) * sin(2*pi*h*f0*t + h*vibrato);
    end

    % envelope with smooth attack and release
    envelope = zeros(size(t));
    fadeLen = round(0.08 * sr);
    entryIdx = round(entryTime * sr) + 1;
    exitIdx = round(exitTime * sr);
    for i = 1:numel(t)
        if i < entryIdx
            envelope(i) = 0;
        elseif i < entryIdx + fadeLen
            envelope(i) = (i - entryIdx) / fadeLen;
        elseif i < exitIdx - fadeLen
            envelope(i) = 1;
        elseif i < exitIdx
            envelope(i) = (exitIdx - i) / fadeLen;
        end
    end
    envelope = smoothdata(envelope, "gaussian", 50);
    signal = signal .* envelope;
end
